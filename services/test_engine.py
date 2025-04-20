import httpx
from typing import Dict, Union, Callable, Any, Union, TypeVar
import time

T = TypeVar('T')
EndpointTest = Callable[..., Dict[str, Any]]
ResourceCreator = Callable[[], Dict[str, Any]]

class TestResult:
    """Class to handle test result data and formatting"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = time.time()
        self.status = "ERROR"  # Default to error, will be updated on success
        self.error_message = None
        self.duration_ms = 0
        self.data = {}  # Additional data to carry between tests
    
    def success(self, **kwargs) -> Dict:
        """Mark test as successful and return result dict"""
        self.status = "OK"
        self.duration_ms = int((time.time() - self.start_time) * 1000)
        self.data.update(kwargs)
        return self.as_dict()
    
    def fail(self, error_message: str, **kwargs) -> Dict:
        """Mark test as failed and return result dict"""
        self.status = "ERROR"
        self.error_message = error_message
        self.duration_ms = int((time.time() - self.start_time) * 1000)
        self.data.update(kwargs)
        return self.as_dict()
    
    def as_dict(self) -> Dict:
        """Convert to dictionary format"""
        result = {
            "test_name": self.test_name,
            "status": self.status,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            **self.data
        }
        return result


class ApiTestEngine:
    """Base class for API testing with reusable methods"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=15.0)
        self.resource_cache = {}  # Cache for storing resources created during tests
    
    async def close(self):
        await self.client.aclose()
    
    async def handle_request(self, 
                           method: str, 
                           endpoint: str, 
                           result: TestResult, 
                           expected_status: int = 200, 
                           **kwargs) -> Union[Dict, None]:
        """Generic method for handling HTTP requests with error handling"""
        try:
            http_method = getattr(self.client, method.lower())
            response = await http_method(f"{self.base_url}/{endpoint}", **kwargs)
            
            if response.status_code == expected_status:
                try:
                    return response.json() if response.content else {}
                except Exception as e:
                    return None
            else:
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', 'Unknown error')
                    result.fail(f"Status {response.status_code}: {error_detail}")
                except:
                    result.fail(f"Unexpected status code: {response.status_code}")
                return None
                
        except Exception as e:
            result.fail(f"Request failed: {str(e)}")
            return None
    
    async def create_resource_if_needed(self, 
                                     resource_type: str, 
                                     resource_id: str = None, 
                                     creator_func: ResourceCreator = None) -> Dict:
        """Create a resource if it doesn't exist already"""
        if resource_id:
            return {"id": resource_id}
        
        # Check cache first
        if resource_type in self.resource_cache:
            return self.resource_cache[resource_type]
        
        # Create new resource
        if creator_func:
            result = await creator_func()
            
            # Cache the resource for future tests
            if result and result.get("status") == "OK":
                self.resource_cache[resource_type] = {
                    k: v for k, v in result.items() 
                    if k not in ["test_name", "status", "error_message", "duration_ms"]
                }
                return self.resource_cache[resource_type]
        
        return {}
    
    def test_wrapper(self, test_func: EndpointTest) -> EndpointTest:
        """Decorator to wrap test functions with common error handling"""
        async def wrapped(*args, **kwargs) -> Dict:
            test_name = test_func.__name__
            result = TestResult(test_name)
            
            try:
                return await test_func(self, result, *args, **kwargs)
            except Exception as e:
                return result.fail(str(e))
                
        return wrapped
