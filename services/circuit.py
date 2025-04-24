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
    # Configure different thresholds for different services
    if service == "image" or service == "video":
        # More lenient settings for resource-intensive services
        return {
            'state': 'closed',
            'failure_count': 0,
            'failure_threshold': 8,  # More failures allowed before opening
            'timeout': 45,          # Longer recovery time
            'opened_at': 0,
            'consecutive_successes': 0,
            'success_threshold': 3  # Require multiple successes to fully close
        }
    else:
        # Default settings for most services
        return {
            'state': 'closed',
            'failure_count': 0,
            'failure_threshold': 5,
            'timeout': 30,
            'opened_at': 0,
            'consecutive_successes': 0,
            'success_threshold': 2
        }


async def call_service_with_status(service: str, method: str, url: str, headers: Dict, params: Dict, body: bytes):
    """Make HTTP request to a service with circuit breaking and preserve status code"""
    # Check if circuit is open for this service
    if service in circuit_states and circuit_states[service]['state'] == 'open':
        current_time = time.time()
        if current_time - circuit_states[service]['opened_at'] > circuit_states[service]['timeout']:
            circuit_states[service]['state'] = 'half-open'
            logger.info(f"Circuit for {service} changed to half-open state")
        else:
            # Circuit is open, fail fast
            CIRCUIT_STATE.labels(service=service).set(1)
            raise HTTPException(status_code=503, detail=f"Circuit open for service '{service}'")
    
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
            if circuit_states[service]['state'] == 'half-open':
                circuit_states[service]['consecutive_successes'] += 1
                if circuit_states[service]['consecutive_successes'] >= circuit_states[service]['success_threshold']:
                    circuit_states[service]['state'] = 'closed'
                    circuit_states[service]['consecutive_successes'] = 0
                    CIRCUIT_STATE.labels(service=service).set(0)
                    logger.info(f"Circuit closed for service {service} after {circuit_states[service]['success_threshold']} successful requests")
        
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