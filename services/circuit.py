from fastapi.responses import JSONResponse, Response
from fastapi import HTTPException
from typing import Dict
import json
import logging
import time
import httpx
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNT = Counter(
    'gateway_requests_total', 
    'Total count of requests by service and method', 
    ['service', 'method']
)
REQUEST_LATENCY = Histogram(
    'gateway_request_latency_seconds', 
    'Request latency in seconds', 
    ['service']
)
CIRCUIT_STATE = Gauge(
    'gateway_circuit_state', 
    'Circuit state (1=open, 0=closed)', 
    ['service']
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("api_gateway")


# Circuit breaker state
circuit_states = {}

def initialize_circuit_state(service: str) -> Dict:
    """Initialize circuit state with service-specific settings"""
    # Base configuration that can be customized per service
    configs = {
        "image": {
            "failure_threshold": 8,
            "timeout": 45,
            "success_threshold": 3,
            "request_timeout": 60.0,
            "backoff_factor": 1.5
        },
        "video": {
            "failure_threshold": 8,
            "timeout": 45,
            "success_threshold": 3,
            "request_timeout": 60.0,
            "backoff_factor": 1.5
        },
        "core": {
            "failure_threshold": 5,
            "timeout": 30,
            "success_threshold": 2,
            "request_timeout": 15.0,
            "backoff_factor": 1.2
        },
        # Add other services with specific configs
    }
    
    # Get service config or use default
    config = configs.get(service, {
        "failure_threshold": 5,
        "timeout": 30,
        "success_threshold": 2,
        "request_timeout": 10.0,
        "backoff_factor": 1.0
    })
    
    return {
        'state': 'closed',
        'failure_count': 0,
        'failure_threshold': config["failure_threshold"],
        'timeout': config["timeout"],
        'opened_at': 0,
        'consecutive_successes': 0,
        'success_threshold': config["success_threshold"],
        'request_timeout': config["request_timeout"],
        'backoff_factor': config["backoff_factor"],
        'retry_count': 0
    }


async def call_service_with_status(service: str, method: str, url: str, headers: Dict, params: Dict, body: bytes):
    """Make HTTP request to a service with circuit breaking and preserve status code"""
    # Initialize state if not exists
    if service not in circuit_states:
        circuit_states[service] = initialize_circuit_state(service)
    
    state = circuit_states[service]
    
    # Check if circuit is open for this service
    if state['state'] == 'open':
        current_time = time.time()
        # Calculate progressive backoff
        backoff_multiplier = min(5, 1 + (state['retry_count'] * state['backoff_factor']))
        timeout_with_backoff = state['timeout'] * backoff_multiplier
        
        if current_time - state['opened_at'] > timeout_with_backoff:
            state['state'] = 'half-open'
            logger.info(f"Circuit for {service} changed to half-open state (backoff: {backoff_multiplier}x)")
            state['retry_count'] += 1
        else:
            # Circuit is open, fail fast
            time_remaining = int(state['opened_at'] + timeout_with_backoff - current_time)
            CIRCUIT_STATE.labels(service=service).set(1)
            raise HTTPException(
                status_code=503, 
                detail=f"Circuit open for service '{service}'. Retry in ~{time_remaining}s"
            )
    
    # Calculate metrics
    start_time = time.time()
    REQUEST_COUNT.labels(service=service, method=method).inc()
    
    try:
        # Use a longer timeout for image service
        timeout = 60.0 if service == "image" else 10.0
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Ensure we set the content-type header for proper JSON handling
            if body and (method == "POST" or method == "PUT" or method == "PATCH"):
                headers["Content-Type"] = "application/json"
                
            response = await client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                content=body
            )
            
        REQUEST_LATENCY.labels(service=service).observe(time.time() - start_time)
        
        # Log the response for debugging
        logger.info(f"Service {service} response status: {response.status_code}")
        
        # Reset failure count on successful response
        if service in circuit_states and response.status_code < 500:
            state = circuit_states[service]
            
            # Reset failure count on any successful response
            if state['state'] == 'closed':
                state['failure_count'] = max(0, state['failure_count'] - 1)  # Gradually reduce failures
            
            # For half-open state, track consecutive successes
            if state['state'] == 'half-open':
                state['consecutive_successes'] += 1
                if state['consecutive_successes'] >= state['success_threshold']:
                    state['state'] = 'closed'
                    state['consecutive_successes'] = 0
                    state['failure_count'] = 0
                    state['retry_count'] = 0  # Reset retry counter
                    CIRCUIT_STATE.labels(service=service).set(0)
                    logger.info(f"Circuit fully closed for {service} after {state['success_threshold']} successful requests")
        
        try:
            content = response.json()
            # Return JSONResponse with original status code
            return JSONResponse(
                content=content,
                status_code=response.status_code
            )
        except json.JSONDecodeError:
            # If we can't decode as JSON, return text content with original status code
            logger.warning(f"Could not decode response as JSON: {response.text[:100]}...")
            return Response(
                content=response.text,
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "text/plain")
            )
        
    except Exception as exc:
        # Record latency even for failures
        REQUEST_LATENCY.labels(service=service).observe(time.time() - start_time)
        
        if service not in circuit_states:
            circuit_states[service] = initialize_circuit_state(service)
            
        if circuit_states[service]['state'] == 'closed':
            circuit_states[service]['failure_count'] += 1
            if circuit_states[service]['failure_count'] >= circuit_states[service]['failure_threshold']:
                circuit_states[service]['state'] = 'open'
                circuit_states[service]['opened_at'] = time.time()
                CIRCUIT_STATE.labels(service=service).set(1)
                logger.warning(f"Circuit opened for service {service} after {circuit_states[service]['failure_count']} failures")
                
        log_data = {
            "service": service,
            "method": method,
            "url": url,
            "error": str(exc),
            "error_type": type(exc).__name__,
            "path": url.split("/", 3)[-1] if "/" in url else "",
        }
        logger.error(f"Service request failed: {json.dumps(log_data)}")
        
        # Raise the exception with more detailed error message
        if isinstance(exc, httpx.TimeoutException):
            raise HTTPException(status_code=504, detail=f"Service '{service}' request timed out")
        elif isinstance(exc, httpx.RequestError):
            raise HTTPException(status_code=503, detail=f"Service '{service}' unavailable: {str(exc)}")
        raise HTTPException(status_code=500, detail=f"Error calling service: {str(exc)}")