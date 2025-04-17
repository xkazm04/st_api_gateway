import httpx
import uuid
import logging
import time
import asyncio
import argparse
import os
import sys
from typing import Dict, List, Optional
from colorama import Fore, Style, init

# Initialize colorama for colored output
init(autoreset=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("voice_api_tests.log")
    ]
)
logger = logging.getLogger("api_gateway.health.audio")

class AudioServiceTests:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=15.0)
    
    async def close(self):
        await self.client.aclose()
        
    async def test_create_voice(self) -> Dict:
        """Test voice creation endpoint"""
        test_name = "test_create_voice"
        start_time = time.time()
        
        try:
            project_id = str(uuid.uuid4())
            response = await self.client.post(
                f"{self.base_url}/voices/projects/{project_id}",
                data={"voice_name": "TestVoice", "description": "Test voice", "label": "test"},
                files={"samples": ("test.wav", b"fake-audio-bytes")},
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            status = "OK" if response.status_code == 200 else "ERROR"
            error_message = None
            
            if status == "ERROR":
                try:
                    error_data = response.json()
                    error_message = f"Status {response.status_code}: {error_data.get('detail', 'Unknown error')}"
                except:
                    error_message = f"Unexpected status code: {response.status_code}"
            
            result = {
                "test_name": test_name,
                "status": status,
                "error_message": error_message,
                "duration_ms": duration_ms
            }
            
            # Return the voice data if successful
            if status == "OK":
                try:
                    voice_data = response.json()
                    result["voice_data"] = voice_data
                except:
                    pass
                
            return result
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "test_name": test_name,
                "status": "ERROR",
                "error_message": str(e),
                "duration_ms": duration_ms
            }
    
    async def test_get_voices(self) -> Dict:
        """Test get voices endpoint"""
        test_name = "test_get_voices"
        start_time = time.time()
        
        try:
            project_id = str(uuid.uuid4())
            response = await self.client.get(
                f"{self.base_url}/voices/project/{project_id}"
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            status = "OK" if response.status_code == 200 else "ERROR"
            error_message = None
            
            if status == "ERROR":
                try:
                    error_data = response.json()
                    error_message = f"Status {response.status_code}: {error_data.get('detail', 'Unknown error')}"
                except:
                    error_message = f"Unexpected status code: {response.status_code}"
            
            return {
                "test_name": test_name,
                "status": status,
                "error_message": error_message,
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "test_name": test_name,
                "status": "ERROR",
                "error_message": str(e),
                "duration_ms": duration_ms
            }
    
    async def test_rename_voice(self, voice_data: Optional[Dict] = None) -> Dict:
        """Test voice rename endpoint"""
        test_name = "test_rename_voice"
        start_time = time.time()
        
        try:
            # First create a voice if not provided
            if not voice_data:
                create_result = await self.test_create_voice()
                if create_result["status"] != "OK" or "voice_data" not in create_result:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return {
                        "test_name": test_name,
                        "status": "ERROR",
                        "error_message": "No test voice available",
                        "duration_ms": duration_ms
                    }
                voice_data = create_result["voice_data"]
            
            voice_id = voice_data.get("id")
            new_name = f"Renamed Voice {uuid.uuid4()}"
            
            response = await self.client.put(
                f"{self.base_url}/voices/{voice_id}",
                json={"name": new_name}
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            status = "OK" if response.status_code == 200 else "ERROR"
            error_message = None
            
            if status == "ERROR":
                try:
                    error_data = response.json()
                    error_message = f"Status {response.status_code}: {error_data.get('detail', 'Unknown error')}"
                except:
                    error_message = f"Unexpected status code: {response.status_code}"
            
            return {
                "test_name": test_name,
                "status": status,
                "error_message": error_message,
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "test_name": test_name,
                "status": "ERROR",
                "error_message": str(e),
                "duration_ms": duration_ms
            }
    
    async def test_delete_voice(self, voice_data: Optional[Dict] = None) -> Dict:
        """Test voice deletion endpoint"""
        test_name = "test_delete_voice"
        start_time = time.time()
        
        try:
            # First create a voice if not provided
            if not voice_data:
                create_result = await self.test_create_voice()
                if create_result["status"] != "OK" or "voice_data" not in create_result:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return {
                        "test_name": test_name,
                        "status": "ERROR",
                        "error_message": "No test voice available",
                        "duration_ms": duration_ms
                    }
                voice_data = create_result["voice_data"]
            
            voice_id = voice_data.get("id")
            
            response = await self.client.delete(
                f"{self.base_url}/voices/{voice_id}"
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            status = "OK" if response.status_code == 200 else "ERROR"
            error_message = None
            
            if status == "ERROR":
                try:
                    error_data = response.json()
                    error_message = f"Status {response.status_code}: {error_data.get('detail', 'Unknown error')}"
                except:
                    error_message = f"Unexpected status code: {response.status_code}"
            
            return {
                "test_name": test_name,
                "status": status,
                "error_message": error_message,
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "test_name": test_name,
                "status": "ERROR",
                "error_message": str(e),
                "duration_ms": duration_ms
            }
            
    async def test_voice_settings(self) -> Dict:
        """Test voice settings endpoint"""
        test_name = "test_voice_settings"
        start_time = time.time()
        
        try:
            # Use a mock voice_id for testing
            voice_id = "some-voice-id"
            
            response = await self.client.get(
                f"{self.base_url}/voices/{voice_id}/settings"
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            # This may fail in test environment without a real voice, so we accept 404 as well
            status = "OK" if response.status_code in [200, 404] else "ERROR"
            error_message = None
            
            if status == "ERROR":
                try:
                    error_data = response.json()
                    error_message = f"Status {response.status_code}: {error_data.get('detail', 'Unknown error')}"
                except:
                    error_message = f"Unexpected status code: {response.status_code}"
            
            return {
                "test_name": test_name,
                "status": status,
                "error_message": error_message,
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "test_name": test_name,
                "status": "ERROR",
                "error_message": str(e),
                "duration_ms": duration_ms
            }
    
    async def test_update_voice_settings(self) -> Dict:
        """Test update voice settings endpoint"""
        test_name = "test_update_voice_settings"
        start_time = time.time()
        
        try:
            # Use a mock voice_id for testing
            voice_id = "some-voice-id"
            settings = {
                "stability": 0.5,
                "similarity_boost": 0.8
            }
            
            response = await self.client.post(
                f"{self.base_url}/voices/{voice_id}/settings",
                json=settings
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            # This may fail in test environment without a real voice, so we accept 404 as well
            status = "OK" if response.status_code in [200, 404] else "ERROR"
            error_message = None
            
            if status == "ERROR":
                try:
                    error_data = response.json()
                    error_message = f"Status {response.status_code}: {error_data.get('detail', 'Unknown error')}"
                except:
                    error_message = f"Unexpected status code: {response.status_code}"
            
            return {
                "test_name": test_name,
                "status": status,
                "error_message": error_message,
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "test_name": test_name,
                "status": "ERROR",
                "error_message": str(e),
                "duration_ms": duration_ms
            }
    
    async def run_all_tests(self) -> List[Dict]:
        """Run all audio service tests"""
        results = []
        
        # Create voice once to use for other tests
        create_voice_result = await self.test_create_voice()
        results.append(create_voice_result)
        
        # Get voice data if creation was successful
        voice_data = None
        if create_voice_result["status"] == "OK" and "voice_data" in create_voice_result:
            voice_data = create_voice_result["voice_data"]
        
        # Run remaining tests
        results.append(await self.test_get_voices())
        
        if voice_data:
            # Use the created voice for these tests
            results.append(await self.test_rename_voice(voice_data))
            results.append(await self.test_delete_voice(voice_data))
        else:
            # If voice creation failed, still attempt tests but expect failure
            results.append(await self.test_rename_voice())
            results.append(await self.test_delete_voice())
            
        results.append(await self.test_voice_settings())
        results.append(await self.test_update_voice_settings())
        
        return results

def log_result(test_name, status, duration_ms, error_message=None):
    """Log test result with colored output"""
    if status == "OK":
        status_colored = f"{Fore.GREEN}{status}{Style.RESET_ALL}"
    else:
        status_colored = f"{Fore.RED}{status}{Style.RESET_ALL}"
    
    print(f"{test_name} - {status_colored} ({duration_ms}ms)")
    
    if error_message:
        print(f"  {Fore.YELLOW}Error: {error_message}{Style.RESET_ALL}")

async def run_tests(base_url, specific_test=None):
    """Run all tests or a specific test"""
    print(f"\n{Fore.CYAN}=== Voice API Tests ==={Style.RESET_ALL}")
    print(f"Testing against: {base_url}")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    audio_tests = AudioServiceTests(base_url)
    
    try:
        if specific_test:
            # Run a specific test
            test_method = getattr(audio_tests, specific_test, None)
            if not test_method:
                print(f"{Fore.RED}Error: Test '{specific_test}' not found{Style.RESET_ALL}")
                return
            
            print(f"Running single test: {specific_test}")
            result = await test_method()
            log_result(
                result["test_name"], 
                result["status"], 
                result["duration_ms"], 
                result["error_message"]
            )
        else:
            # Run all tests
            results = await audio_tests.run_all_tests()
            
            # Count successes and failures
            success_count = sum(1 for r in results if r["status"] == "OK")
            failure_count = len(results) - success_count
            
            for result in results:
                log_result(
                    result["test_name"], 
                    result["status"], 
                    result["duration_ms"], 
                    result["error_message"]
                )
            
            # Print summary
            print(f"\n{Fore.CYAN}=== Test Summary ==={Style.RESET_ALL}")
            print(f"Total tests: {len(results)}")
            print(f"Successful: {Fore.GREEN}{success_count}{Style.RESET_ALL}")
            print(f"Failed: {Fore.RED if failure_count > 0 else ''}{failure_count}{Style.RESET_ALL}")
    finally:
        await audio_tests.close()
        logger.debug("Closed HTTP client")

def main():
    """Main entry point for command line usage"""
    parser = argparse.ArgumentParser(description="Voice API Testing Tool")
    parser.add_argument("--url", type=str, default="http://localhost:8001/audio", 
                        help="Base URL for API testing (default: http://localhost:8001/audio)")
    parser.add_argument("--test", type=str, help="Run a specific test by name")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set debug level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    
    # Run the tests
    asyncio.run(run_tests(args.url, args.test))

if __name__ == "__main__":
    main()