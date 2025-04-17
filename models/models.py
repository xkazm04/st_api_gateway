from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class TestResult(Base):
    """Model for storing test results from health checks"""
    __tablename__ = "test_results"
    
    id = Column(Integer, primary_key=True)
    service_name = Column(String(100), nullable=False)
    test_name = Column(String(255), nullable=False)
    last_status = Column(String(20), nullable=False)  # OK, ERROR, NA
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

class ServiceHealth(Base):
    """Model for storing service health status"""
    __tablename__ = "service_health"
    
    id = Column(Integer, primary_key=True)
    service_name = Column(String(100), nullable=False, unique=True)
    status = Column(String(20), nullable=False)  # OK, DEGRADED, DOWN
    last_successful_check = Column(DateTime, nullable=True)
    total_tests = Column(Integer, default=0)
    passing_tests = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)