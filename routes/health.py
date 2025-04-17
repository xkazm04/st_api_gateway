from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import asyncio
from datetime import datetime
from db.database import get_db
from schemas.health import TestResultsResponse
from typing import Optional
router = APIRouter()

def get_health_service():
    """Dependency to get the health service instance"""
    global health_service
    if not health_service:
        raise HTTPException(status_code=503, detail="Health service not available")
    return health_service

def init_health_service(service):
    """Initialize the health service"""
    global health_service
    health_service = service
    
@router.get("/")
async def health_check():
    """Basic health check endpoint for the API Gateway itself"""
    return {
        "status": "OK",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
    
@router.get("/tests", response_model=TestResultsResponse)
async def get_health_tests(
    health_service = Depends(get_health_service),
    service: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):    
    if not health_service:
        raise HTTPException(status_code=503, detail="Health service not available")
        
    results = await health_service.get_test_results(service, limit, offset)
    
    return {
        "results": results,
        "total": len(results)
    }

@router.post("/run-tests")
async def run_health_tests(
    health_service = Depends(get_health_service)
):
    """Manually trigger health tests"""
    if not health_service:
        raise HTTPException(status_code=503, detail="Health service not available")
        
    # Run tests asynchronously and return immediately
    asyncio.create_task(health_service.run_all_tests())
    
    return {"message": "Tests started"}

# Add monitoring status endpoint
@router.get("/status")
async def get_monitoring_status(health_service = Depends(get_health_service)):
    """Get monitoring status"""
    if not health_service:
        raise HTTPException(status_code=503, detail="Health service not available")
        
    return {
        "running": health_service.running,
        "services_monitored": list(health_service.services_config.keys())   
    }

@router.get("/detail")
async def detailed_health(db: Session = Depends(get_db), health_service = Depends(get_health_service)):
    """Detailed health check with database status"""
    try:
        # Check if database is accessible
        db_status = "OK"
        db_error = None
        
        try:
            # Try to execute a simple query
            db.execute("SELECT 1").fetchone()
        except Exception as e:
            db_status = "ERROR"
            db_error = str(e)
        
        return {
            "status": "OK" if db_status == "OK" else "ERROR",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "components": {
                "api": {"status": "OK"},
                "database": {
                    "status": db_status,
                    "error": db_error
                },
                "health_monitoring": {
                    "status": "OK" if health_service and health_service.running else "DOWN",
                    "running": health_service.running if health_service else False
                }
            }
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@router.get("/dashboard")
async def get_health_dashboard(health_service = Depends(get_health_service)):
    """Get health dashboard data"""
    if not health_service:
        raise HTTPException(status_code=503, detail="Health service not available")
        
    results = await health_service.get_test_results()
    
    # Organize by service
    services = {}
    for result in results:
        service_name = result["service_name"]
        if service_name not in services:
            services[service_name] = {
                "name": service_name,
                "status": "OK",
                "tests": [],
                "last_updated": None
            }
            
        # Add the test
        services[service_name]["tests"].append({
            "name": result["test_name"],
            "status": result["last_status"],
            "error": result["error_message"],
            "duration_ms": result["duration_ms"],
            "updated_at": result["updated_at"]
        })
        
        # Update service status (if any test fails, service status is ERROR)
        if result["last_status"] == "ERROR":
            services[service_name]["status"] = "ERROR"
            
        # Track the most recent update
        test_updated_at = result["updated_at"]
        service_updated_at = services[service_name]["last_updated"]
        
        if not service_updated_at or (test_updated_at and test_updated_at > service_updated_at):
            services[service_name]["last_updated"] = test_updated_at
    
    return {
        "services": list(services.values()),
        "last_updated": max([s["last_updated"] for s in services.values()]) if services else None
    }

