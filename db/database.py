import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_gateway.db")

# Database connection parameters
DB_HOST = os.getenv("DB_HOST", "gateway_db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "gateway")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

# Create SQLAlchemy engine and session
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info(f"Database connection established to {DB_HOST}:{DB_PORT}/{DB_NAME}")
except Exception as e:
    logger.error(f"Failed to create database engine: {str(e)}")
    # Create a fallback engine that will fail gracefully
    engine = None
    SessionLocal = None
    Base = declarative_base()

@contextmanager
def get_db():
    """Provide a transactional scope around a series of operations."""
    if not SessionLocal:
        logger.error("Database session not initialized")
        raise Exception("Database connection not available")
        
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

async def init_db():
    """Initialize database connection."""
    try:
        # Create the tables if they don't exist yet
        if engine:
            # Import models to ensure they're registered with Base
            from models.models import TestResult, ServiceHealth
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            return True
        else:
            logger.error("Database engine not initialized")
            return False
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False