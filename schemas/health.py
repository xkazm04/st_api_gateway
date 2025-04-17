
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class TestResult(BaseModel):
    service_name: str
    test_name: str
    last_status: str
    error_message: Optional[str] = None
    duration_ms: int
    updated_at: datetime

class TestResultsResponse(BaseModel):
    results: List[TestResult]
    total: int