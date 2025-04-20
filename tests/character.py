
import uuid
import logging
import time
import asyncio
import argparse
import os 
from typing import Dict, List, Optional, Callable, Any, TypeVar
from colorama import Fore, Style, init

# TBD no module name services
from services.test_engine import ApiTestEngine, TestResult

T = TypeVar('T')
EndpointTest = Callable[..., Dict[str, Any]]
ResourceCreator = Callable[[], Dict[str, Any]]
init(autoreset=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("api_gateway.tests.character")

project_id = "afad8da2-06da-4a81-9422-5a8bcc6f72ee"

class CharacterServiceTests(ApiTestEngine):
    """Test class for Character API endpoints"""
    
    @property
    def endpoint_prefix(self) -> str:
        return "characters"
    
    async def test_create_character(self, project_id: Optional[str] = None) -> Dict:
        """Test character creation endpoint"""
        result = TestResult("test_create_character")
        
        try:                
            character_data = {
                "name": f"Test Character {uuid.uuid4()}",
                "project_id": project_id,
                "type": "NPC"
            }
            
            response_data = await self.handle_request(
                "post", 
                f"{self.endpoint_prefix}/", 
                result, 
                json=character_data
            )
            
            if response_data is not None:
                return result.success()
            return result.as_dict()
            
        except Exception as e:
            return result.fail(str(e))
    
    async def test_get_characters_by_project(self, project_id: Optional[str] = None) -> Dict:
        """Test get characters by project endpoint"""
        result = TestResult("test_get_characters_by_project")
        
        try:            
            # Get characters for this project
            characters = await self.handle_request(
                "get", 
                f"{self.endpoint_prefix}/project/{project_id}", 
                result
            )
            
            if characters is None:
                return result.as_dict()
                
            if not characters:
                return result.fail("No characters returned for project")
                
            # Get first character ID for subsequent tests
            character_id = characters[0]["id"]
            return result.success(project_id=project_id, character_id=character_id)
            
        except Exception as e:
            return result.fail(str(e))
    
    async def get_or_create_test_character(self, character_id: Optional[str] = None) -> Dict:
        """Helper to get or create a test character"""
        if character_id:
            return {"character_id": character_id}
            
        # Try to get character from cache
        if "test_character" in self.resource_cache:
            return self.resource_cache["test_character"]
        
        # Create a new test character
        create_result = await self.test_create_character()
        if create_result["status"] != "OK":
            return {"error": "Failed to create character"}
            
        # Get characters to find ID
        get_chars_result = await self.test_get_characters_by_project(project_id)
        if get_chars_result["status"] != "OK" or "character_id" not in get_chars_result:
            return {"error": "Failed to retrieve character ID"}
            
        # Cache for future tests
        character_data = {
            "character_id": get_chars_result["character_id"],
            "project_id": project_id
        }
        self.resource_cache["test_character"] = character_data
        return character_data
    
    async def test_edit_character(self, character_id: Optional[str] = None) -> Dict:
        """Test character edit endpoint"""
        result = TestResult("test_edit_character")
        
        try:
            # Get or create test character
            char_data = await self.get_or_create_test_character(character_id)
            if "error" in char_data:
                return result.fail(char_data["error"])
                
            character_id = char_data["character_id"]
            
            # Edit the character
            edit_data = {
                "name": f"Edited Character {uuid.uuid4()}",
                "description": "Updated character description",
                "type": "Player"
            }
            
            response_data = await self.handle_request(
                "put", 
                f"{self.endpoint_prefix}/{character_id}", 
                result, 
                json=edit_data
            )
            
            if response_data is not None:
                return result.success(character_id=character_id)
            return result.as_dict()
            
        except Exception as e:
            return result.fail(str(e))
    
    async def test_assign_voice(self, character_id: Optional[str] = None) -> Dict:
        """Test assigning voice to character endpoint"""
        result = TestResult("test_assign_voice")
        
        try:
            # Get or create test character
            char_data = await self.get_or_create_test_character(character_id)
            if "error" in char_data:
                return result.fail(char_data["error"])
                
            character_id = char_data["character_id"]
            
            # Assign a voice
            voice_id = str(uuid.uuid4())
            voice_data = {"voice_id": voice_id}
            
            response_data = await self.handle_request(
                "put", 
                f"{self.endpoint_prefix}/{character_id}/voice", 
                result, 
                json=voice_data
            )
            
            if response_data is not None:
                return result.success(character_id=character_id)
            return result.as_dict()
            
        except Exception as e:
            return result.fail(str(e))
    
    async def test_rename_character(self, character_id: Optional[str] = None) -> Dict:
        """Test character rename endpoint"""
        result = TestResult("test_rename_character")
        
        try:
            # Get or create test character
            char_data = await self.get_or_create_test_character(character_id)
            if "error" in char_data:
                return result.fail(char_data["error"])
                
            character_id = char_data["character_id"]
            
            # Rename the character
            new_name = f"Renamed Character {uuid.uuid4()}"
            rename_data = {"new_name": new_name}
            
            response_data = await self.handle_request(
                "put", 
                f"{self.endpoint_prefix}/{character_id}/rename", 
                result, 
                json=rename_data
            )
            
            if response_data is not None:
                return result.success(character_id=character_id)
            return result.as_dict()
            
        except Exception as e:
            return result.fail(str(e))
    
    async def test_add_avatar(self, character_id: Optional[str] = None) -> Dict:
        """Test adding avatar URL to character endpoint"""
        result = TestResult("test_add_avatar")
        
        try:
            # Get or create test character
            char_data = await self.get_or_create_test_character(character_id)
            if "error" in char_data:
                return result.fail(char_data["error"])
                
            character_id = char_data["character_id"]
            
            # Add avatar URL
            avatar_data = {"avatar_url": f"https://example.com/avatar-{uuid.uuid4()}.png"}
            
            response_data = await self.handle_request(
                "put", 
                f"{self.endpoint_prefix}/{character_id}/avatar", 
                result, 
                json=avatar_data
            )
            
            if response_data is not None:
                return result.success(character_id=character_id)
            return result.as_dict()
            
        except Exception as e:
            return result.fail(str(e))
    
    async def test_get_character_by_id(self, character_id: Optional[str] = None) -> Dict:
        """Test get character by ID endpoint"""
        result = TestResult("test_get_character_by_id")
        
        try:
            # Get or create test character
            char_data = await self.get_or_create_test_character(character_id)
            if "error" in char_data:
                return result.fail(char_data["error"])
                
            character_id = char_data["character_id"]
            
            # Get character by ID
            character_data = await self.handle_request(
                "get", 
                f"{self.endpoint_prefix}/{character_id}", 
                result
            )
            
            if character_data is None:
                return result.as_dict()
                
            if not character_data:
                return result.fail("Empty character data returned")
                
            return result.success(character_id=character_id)
            
        except Exception as e:
            return result.fail(str(e))
    
    async def test_delete_character(self, character_id: Optional[str] = None) -> Dict:
        """Test character deletion endpoint"""
        result = TestResult("test_delete_character")
        
        try:
            # Get or create test character
            char_data = await self.get_or_create_test_character(character_id)
            if "error" in char_data:
                return result.fail(char_data["error"])
                
            character_id = char_data["character_id"]
            
            # Delete the character
            response_data = await self.handle_request(
                "delete", 
                f"{self.endpoint_prefix}/{character_id}", 
                result
            )
            
            if response_data is not None:
                # Remove from cache if exists
                if "test_character" in self.resource_cache and \
                   self.resource_cache["test_character"].get("character_id") == character_id:
                    del self.resource_cache["test_character"]
                    
                return result.success(character_id=character_id)
            return result.as_dict()
            
        except Exception as e:
            return result.fail(str(e))
    
    async def run_all_tests(self) -> List[Dict]:
        """Run all character service tests in sequence"""
        results = []
        
        # Create a character for testing
        create_result = await self.test_create_character()
        results.append(create_result)
        
        # Run dependent tests
        if create_result["status"] == "OK" and "project_id" in create_result:
            # Get characters
            get_chars_result = await self.test_get_characters_by_project(project_id)
            results.append(get_chars_result)
            
            # If we successfully got characters, use the same character for all tests
            if get_chars_result["status"] == "OK" and "character_id" in get_chars_result:
                character_id = get_chars_result["character_id"]
                
                # Store in cache for other tests
                self.resource_cache["test_character"] = {
                    "character_id": character_id,
                    "project_id": project_id
                }
                
                # Run all tests with the same character
                test_functions = [
                    self.test_edit_character,
                    self.test_assign_voice,
                    self.test_rename_character,
                    self.test_add_avatar,
                    self.test_get_character_by_id,
                    self.test_delete_character
                ]
                
                for test_func in test_functions:
                    results.append(await test_func(character_id))
            else:
                # Run tests independently
                results.extend(await self._run_independent_tests())
        else:
            # Run tests independently
            results.extend(await self._run_independent_tests())
        
        return results
    
    async def _run_independent_tests(self) -> List[Dict]:
        """Run all tests independently (each creating its own resources)"""
        results = []
        
        test_functions = [
            self.test_get_characters_by_project,
            self.test_edit_character,
            self.test_assign_voice,
            self.test_rename_character,
            self.test_add_avatar,
            self.test_get_character_by_id,
            self.test_delete_character
        ]
        
        for test_func in test_functions:
            # Clear previous cached character to ensure independent tests
            if "test_character" in self.resource_cache:
                del self.resource_cache["test_character"]
            
            results.append(await test_func())
        
        return results


def log_result(result: Dict) -> None:
    """Log test result with colored output"""
    if result["status"] == "OK":
        status_colored = f"{Fore.GREEN}{result['status']}{Style.RESET_ALL}"
    else:
        status_colored = f"{Fore.RED}{result['status']}{Style.RESET_ALL}"
    
    print(f"{result['test_name']} - {status_colored} ({result['duration_ms']}ms)")
    
    if result.get("error_message"):
        print(f"  {Fore.YELLOW}Error: {result['error_message']}{Style.RESET_ALL}")

async def run_tests(base_url, specific_test=None):
    """Run all tests or a specific test"""
    print(f"\n{Fore.CYAN}=== Character API Tests ==={Style.RESET_ALL}")
    print(f"Testing against: {base_url}")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    character_tests = CharacterServiceTests(base_url)
    
    try:
        if specific_test:
            # Run a specific test
            test_method = getattr(character_tests, specific_test, None)
            if not test_method:
                print(f"{Fore.RED}Error: Test '{specific_test}' not found{Style.RESET_ALL}")
                return
            
            print(f"Running single test: {specific_test}")
            result = await test_method()
            log_result(result)
        else:
            # Run all tests
            results = await character_tests.run_all_tests()
            
            # Count successes and failures
            success_count = sum(1 for r in results if r["status"] == "OK")
            failure_count = len(results) - success_count
            
            for result in results:
                log_result(result)
            
            # Print summary
            print(f"\n{Fore.CYAN}=== Test Summary ==={Style.RESET_ALL}")
            print(f"Total tests: {len(results)}")
            print(f"Successful: {Fore.GREEN}{success_count}{Style.RESET_ALL}")
            print(f"Failed: {Fore.RED if failure_count > 0 else ''}{failure_count}{Style.RESET_ALL}")
    finally:
        await character_tests.close()
        logger.debug("Closed HTTP client")

def main():
    """Main entry point for command line usage"""
    parser = argparse.ArgumentParser(description="Character API Testing Tool")
    parser.add_argument("--url", type=str, default="http://localhost:8001/core", 
                        help="Base URL for API testing (default: http://localhost:8001/core)")
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