import asyncio
import httpx
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

# Configure logging
logger = logging.getLogger("api_gateway.health")

class HealthService:
    """Service for monitoring health of microservices"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.services_config = {}
        self.running = False
        self.async_client = None
    
    async def load_service_definitions(self, service_cache: Dict):
        """Load service configurations from the gateway's service cache"""
        if not service_cache or "services" not in service_cache:
            logger.warning("Service cache is empty")
            return
            
        self.services_config = {}
        for service_name, service_url in service_cache["services"].items():
            self.services_config[service_name] = {
                "base_url": service_url,
                "tests": self._get_default_tests(service_name)
            }
            
        logger.info(f"Loaded health configurations for {len(self.services_config)} services")
        
        # Initialize HTTP client
        self.async_client = httpx.AsyncClient(timeout=10.0)
    
    def _get_default_tests(self, service_name: str) -> List[Dict]:
        """Get default tests for a specific service"""
        # Basic health check for all services
        tests = [
            {
                "name": "health_check",
                "method": "GET",
                "path": "/health",
                "expected_status": [200]
            }
        ]
        
        # Add service-specific tests
        if service_name == "audio":
            tests.extend([
                {
                    "name": "get_voices_list",
                    "method": "GET",
                    "path": "/voices/project/00000000-0000-0000-0000-000000000000",
                    "expected_status": [200]
                }
            ])
        elif service_name == "user":
            tests.extend([
                {
                    "name": "user_check",
                    "method": "GET",
                    "path": "/users/health",
                    "expected_status": [200]
                }
            ])
        
        return tests
    
    async def run_test(self, service_name: str, test: Dict) -> Dict:
        """Run a single test against a service endpoint"""
        test_name = test["name"]
        method = test["method"]
        path = test["path"]
        expected_status = test["expected_status"]
        
        if not self.async_client:
            self.async_client = httpx.AsyncClient(timeout=10.0)
        
        if service_name not in self.services_config:
            return {
                "service_name": service_name,
                "test_name": test_name,
                "last_status": "NA",
                "error_message": "Service not configured",
                "duration_ms": 0,
                "updated_at": datetime.utcnow()
            }
        
        base_url = self.services_config[service_name]["base_url"]
        full_url = f"{base_url}{path}"
        
        start_time = time.time()
        try:
            if method == "GET":
                response = await self.async_client.get(full_url)
            elif method == "POST":
                response = await self.async_client.post(full_url)
            else:
                return {
                    "service_name": service_name,
                    "test_name": test_name,
                    "last_status": "ERROR",
                    "error_message": f"Unsupported method: {method}",
                    "duration_ms": 0,
                    "updated_at": datetime.utcnow()
                }
            
            duration_ms = int((time.time() - start_time) * 1000)
            status = "OK" if response.status_code in expected_status else "ERROR"
            error_message = None
            
            if status == "ERROR":
                error_message = f"Unexpected status code: {response.status_code}"
            
            return {
                "service_name": service_name,
                "test_name": test_name,
                "last_status": status,
                "error_message": error_message,
                "duration_ms": duration_ms,
                "updated_at": datetime.utcnow()
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "service_name": service_name,
                "test_name": test_name,
                "last_status": "ERROR",
                "error_message": str(e),
                "duration_ms": duration_ms,
                "updated_at": datetime.utcnow()
            }
    
    async def run_all_tests(self):
        """Run all tests for all services"""
        results = []
        
        for service_name, config in self.services_config.items():
            for test in config["tests"]:
                result = await self.run_test(service_name, test)
                results.append(result)
                
                # Store result in database
                await self._save_test_result(result)
                
                # Small delay to avoid overwhelming services
                await asyncio.sleep(0.5)
        
        return results
    
    async def _save_test_result(self, result: Dict):
        """Save test result to database"""
        try:
            # Here we would save to database, but we'll just log for simplicity
            logger.info(f"Test result: {result['service_name']}/{result['test_name']} - {result['last_status']}")
            # In a real implementation, this would save to your database
        except Exception as e:
            logger.error(f"Failed to save test result: {str(e)}")
    
    async def get_test_results(self, service_name: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get test results"""
        # This would normally query the database
        # For now, we'll return mock data
        return [
            {
                "service_name": "audio",
                "test_name": "health_check",
                "last_status": "OK",
                "error_message": None,
                "duration_ms": 150,
                "updated_at": datetime.utcnow()
            },
            {
                "service_name": "user",
                "test_name": "health_check",
                "last_status": "OK",
                "error_message": None,
                "duration_ms": 120,
                "updated_at": datetime.utcnow()
            }
        ]
    
    async def start_monitoring(self, interval_seconds=3600, initial_delay_seconds=60):
        """Start periodic health monitoring with optional initial delay"""
        if self.running:
            logger.warning("Health monitoring is already running")
            return
            
        self.running = True
        
        try:
            # Initial delay
            if initial_delay_seconds > 0:
                logger.info(f"Waiting {initial_delay_seconds}s before first health check")
                await asyncio.sleep(initial_delay_seconds)
            
            # Adaptive check interval for newly registered services
            # First run every 30 seconds for 5 minutes, then at normal interval
            logger.info("Starting accelerated initial health checks")
            start_time = time.time()
            accelerated_period = 300  # 5 minutes
            accelerated_interval = 30  # 30 seconds
            
            while self.running:
                await self.run_all_tests()
                
                # Determine next check interval
                current_time = time.time()
                elapsed_time = current_time - start_time
                
                if elapsed_time < accelerated_period:
                    # Still in accelerated period
                    next_interval = accelerated_interval
                    logger.info(f"Next health check in {next_interval}s (accelerated mode)")
                else:
                    # Normal interval
                    next_interval = interval_seconds
                    logger.info(f"Next health check in {next_interval}s (normal mode)")
                    
                await asyncio.sleep(next_interval)
                
        except asyncio.CancelledError:
            logger.info("Health monitoring task cancelled")
        except Exception as e:
            logger.error(f"Error in health monitoring task: {str(e)}")
        finally:
            self.running = False
            # Close all clients
            for client in self.clients.values():
                if hasattr(client, 'aclose'):
                    await client.aclose()
                    
