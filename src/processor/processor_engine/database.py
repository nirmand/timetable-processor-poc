"""Database setup and models for processor engine."""

from pathlib import Path
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class TimetableSource(Base):
    """Represents the input timetable file source."""
    __tablename__ = "timetable_sources"

    id = Column(Integer, primary_key=True)
    file_path = Column(String(500), nullable=False, unique=True)
    processed_at = Column(DateTime, nullable=True)

class TimeslotActivities(Base):
    """Represents the vocabulary of events/ activities."""
    __tablename__ = "timeslot_activities"

    id = Column(Integer, primary_key=True)
    activity_name = Column(String(100), nullable=False, unique=True)


class ExtractedActivities(Base):
    """Represents a single extracted row/cell from the timetable."""
    __tablename__ = "extracted_activities"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("timetable_sources.id"), nullable=False)
    activity_id = Column(Integer, ForeignKey("timeslot_activities.id"), nullable=True)
    day = Column(String(50), nullable=False)
    start_time = Column(String(100), nullable=False)
    end_time = Column(String(100), nullable=False)
    notes = Column(String(500), nullable=True)


def get_db_engine(db_path: str = "timetable_data.db"):
    """
    Create and return a SQLAlchemy Engine connected to SQLite database.

    Args:
        db_path: Path to the SQLite database file (default: timetable_data.db in project root)

    Returns:
        sqlalchemy.Engine: Database engine instance
    """
    # Resolve to project root
    project_root = Path(__file__).parent.parent
    full_db_path = project_root / db_path
    connection_string = f"sqlite:///{full_db_path}"

    return create_engine(connection_string, echo=False)


def create_tables(engine) -> None:
    """
    Create all database tables defined in Base.metadata.

    Args:
        engine: SQLAlchemy Engine instance
    """
    Base.metadata.create_all(engine)
