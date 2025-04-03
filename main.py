from fastapi import FastAPI, HTTPException, Request, Depends
import httpx
import os
import time
import json
import logging
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
import consul
from prometheus_client import Counter, Histogram, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from circuitbreaker import circuit
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("api_gateway")

# Initialize Consul client for service discovery
CONSUL_HOST = os.getenv("CONSUL_HOST", "consul")
CONSUL_PORT = int(os.getenv("CONSUL_PORT", "8500"))

consul_client = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)

# Circuit breaker state
circuit_states = {}

# Prometheus metrics
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

app = FastAPI(title="API Gateway")

# Add CORS middleware to allow calls from localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Add Prometheus instrumentation
Instrumentator().instrument(app).expose(app)

# Service cache with TTL
service_cache = {}
SERVICE_CACHE_TTL = 30  # seconds

async def refresh_services():
    """Background task to refresh service registry from Consul"""
    while True:
        try:
            services = {}
            index, consul_services = consul_client.catalog.services()
            
            for service_name in consul_services:
                if service_name != 'consul':  # Skip the consul service itself
                    index, service_data = consul_client.catalog.service(service_name)
                    if service_data:
                        # Use the first instance of the service for simplicity
                        instance = service_data[0]
                        address = instance['ServiceAddress'] or instance['Address']
                        port = instance['ServicePort']
                        services[service_name] = f"http://{address}:{port}"
            
            # Update service cache
            global service_cache
            service_cache = {
                "timestamp": time.time(),
                "services": services
            }
            logger.info(f"Discovered services: {services}")
        except Exception as e:
            logger.error(f"Error refreshing services: {str(e)}")
        
        await asyncio.sleep(SERVICE_CACHE_TTL)

@app.on_event("startup")
async def startup_event():
    # Start the background task to refresh services
    asyncio.create_task(refresh_services())
    
    # Initialize fallback service registry if Consul is not available
    global service_cache
    service_cache = {
        "timestamp": time.time(),
        "services": {
            "user": os.getenv("USER_SERVICE_URL", "http://user_service:8002"),
            # TBD 
        }
    }

def get_service_url(service: str) -> str:
    """Get service URL from cache or environment variable fallback"""
    if service in service_cache["services"]:
        return service_cache["services"][service]
    
    # Fallback to environment variable
    env_var = f"{service.upper()}_SERVICE_URL"
    fallback_url = os.getenv(env_var)
    if fallback_url:
        return fallback_url
    
    raise HTTPException(status_code=404, detail=f"Service '{service}' not found")

@app.get("/")
async def root():
    return {"message": "API Gateway - Route requests to microservices"}

@app.get("/services")
async def list_services():
    """List all available services"""
    return {"services": list(service_cache["services"].keys())}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

@circuit
async def call_service(service: str, method: str, url: str, headers: Dict, params: Dict, body: bytes) -> Dict:
    """Make HTTP request to a service with circuit breaking"""
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                content=body
            )
            
        REQUEST_LATENCY.labels(service=service).observe(time.time() - start_time)
        
        if service in circuit_states and circuit_states[service]['state'] == 'half-open':
            circuit_states[service]['state'] = 'closed'
            circuit_states[service]['failure_count'] = 0
            CIRCUIT_STATE.labels(service=service).set(0)
            logger.info(f"Circuit for {service} closed")
            
        return response.json()
        
    except Exception as exc:
        # Record latency even for failures
        REQUEST_LATENCY.labels(service=service).observe(time.time() - start_time)
        
        if service not in circuit_states:
            circuit_states[service] = {
                'state': 'closed',
                'failure_count': 0,
                'failure_threshold': 5,
                'timeout': 30,  # seconds
                'opened_at': 0
            }
            
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
            "path": url.split("/", 3)[-1] if "/" in url else "",
        }
        logger.error(f"Service request failed: {json.dumps(log_data)}")
        
        # Raise the exception
        if isinstance(exc, httpx.RequestError):
            raise HTTPException(status_code=503, detail=f"Service '{service}' unavailable")
        raise HTTPException(status_code=500, detail=f"Error calling service: {str(exc)}")

@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_to_service(service: str, path: str, request: Request):
    """Proxy requests to the appropriate service"""
    method = request.method
    logger.info(f"Incoming request: {method} /{service}/{path}")
    
    try:
        # Get service URL from service discovery
        service_url = get_service_url(service)
        target_url = f"{service_url}/{path}"
        
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)
        
        headers["X-From-Gateway"] = "true"
        headers["X-Request-ID"] = headers.get("X-Request-ID", str(time.time()))
        
        params = dict(request.query_params)
        
        # Call the service with circuit breaking
        response = await call_service(service, method, target_url, headers, params, body)
        return response
        
    except HTTPException as exc:
        logger.error(f"HTTP Exception: {exc.detail}")
        raise exc
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")