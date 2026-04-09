from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings
from loguru import logger

# Build connection URL
DATABASE_URL = (
    f"postgresql://{settings.db_user}:{settings.db_password}"
    f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
)


def get_engine():
    """Create SQLAlchemy engine."""
    return create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # verify connection is alive before using
        echo=False,          # set True to see all SQL queries in logs
    )


def get_session():
    """Create a database session."""
    engine = get_engine()
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    return SessionLocal()


def init_db():
    """Create all tables if they don't exist."""
    from db.models import Base
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully!")