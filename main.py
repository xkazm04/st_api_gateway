from fastapi import FastAPI, HTTPException, Request
import os
import time
import logging
from fastapi.middleware.cors import CORSMiddleware
import consul
from prometheus_fastapi_instrumentator import Instrumentator
from circuitbreaker import circuit
import asyncio
from db.database import init_db
from routes import api_router
from services.health_service import HealthService
from services.circuit import call_service_with_status

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("api_gateway")

# Initialize Consul client for service discovery
CONSUL_HOST = os.getenv("CONSUL_HOST", "consul")
CONSUL_PORT = int(os.getenv("CONSUL_PORT", "8500"))

# Determine if running in Docker or locally
RUNNING_IN_DOCKER = os.getenv("CONTAINER_ENV", "0") == "1"

# Set default URLs based on environment
if RUNNING_IN_DOCKER:
    CORE_SERVICE_URL = os.getenv("CORE_SERVICE_URL", "http://core_service:8000")
    USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user_service:8002")
    IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://image_service:8003")
    AUDIO_SERVICE_URL = os.getenv("AUDIO_SERVICE_URL", "http://audio_service:8004")
    VIDEO_SERVICE_URL = os.getenv("VIDEO_SERVICE_URL", "http://video_service:8005")
    WORKFLOW_SERVICE_URL = os.getenv("WORKFLOW_SERVICE_URL", "http://workflow_service:8006")
else:
    CORE_SERVICE_URL = os.getenv("CORE_SERVICE_URL", "http://localhost:8000")
    USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8002")
    IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://localhost:8003")
    AUDIO_SERVICE_URL = os.getenv("AUDIO_SERVICE_URL", "http://localhost:8004")
    VIDEO_SERVICE_URL = os.getenv("VIDEO_SERVICE_URL", "http://localhost:8005")
    WORKFLOW_SERVICE_URL = os.getenv("WORKFLOW_SERVICE_URL", "http://localhost:8006")

consul_client = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)


app = FastAPI(title="API Gateway")
app.include_router(api_router)
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
SERVICE_CACHE_TTL = 300  # seconds

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
                        # Use ServiceAddress if available, otherwise fall back to Address
                        address = instance['ServiceAddress'] or instance['Address']
                        port = instance['ServicePort']
                        services[service_name] = f"http://{address}:{port}"
                        logger.info(f"Discovered service: {service_name} at {address}:{port}")
            
            # Update service cache
            global service_cache
            service_cache = {
                "timestamp": time.time(),
                "services": services
            }
            logger.info(f"Updated service cache: {services}")
        except Exception as e:
            logger.error(f"Error refreshing services: {str(e)}")
        
        await asyncio.sleep(SERVICE_CACHE_TTL)


# Global variable for health service
health_service = None

@app.on_event("startup")
async def startup_event():
    global health_service
    
    # Initialize fallback service registry if Consul is not available
    global service_cache
    service_cache = {
        "timestamp": time.time(),
        "services": {
            "core": CORE_SERVICE_URL,
            "user": USER_SERVICE_URL,
            "audio": AUDIO_SERVICE_URL,
            "workflow": WORKFLOW_SERVICE_URL,
            "image": IMAGE_SERVICE_URL,
            "video": VIDEO_SERVICE_URL
        }
    }
    logger.info(f"Initialized service cache with fallbacks: {service_cache['services']}")
    
    # Initialize database
    db_initialized = await init_db()
    if db_initialized:
        # Initialize health service
        from db.database import SessionLocal
        health_service = HealthService(SessionLocal)
        await health_service.load_service_definitions(service_cache)
        
        # Start health monitoring in background with a delay
        # This gives services time to register and start up fully
        async def delayed_start():
            await asyncio.sleep(30)  # Wait 1 minute before first health check
            logger.info("Starting scheduled health monitoring")
            await health_service.start_monitoring()
            
        asyncio.create_task(delayed_start())
        logger.info("Health monitoring scheduled to start in 30 seconds")
    else:
        logger.warning("Database initialization failed, health monitoring disabled")

# Add shutdown event to clean up resources
@app.on_event("shutdown")
async def shutdown_event():
    global health_service
    if health_service:
        health_service.stop_monitoring()

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



@circuit
async def circuit_protected_call_service(service, method, url, headers, params, body):
    """Call a service with circuit breaker protection"""
    return await call_service_with_status(service, method, url, headers, params, body)

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
        params = dict(request.query_params)
        
        # Call the service with circuit breaking
        response = await circuit_protected_call_service(service, method, target_url, headers, params, body)
        return response
        
    except HTTPException as exc:
        logger.error(f"HTTP Exception: {exc.detail}")
        raise exc
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Error handling for application startup
@app.on_event("startup")
async def debug_startup():
    """Log detailed information during startup for debugging"""
    try:
        logger.info("=== API Gateway Starting ===")
        logger.info(f"Environment: {'Docker' if RUNNING_IN_DOCKER else 'Local'}")
        logger.info(f"Database host: {os.getenv('DB_HOST', 'gateway_db')}")
    
    except Exception as e:
        logger.error(f"Error during startup debugging: {str(e)}")