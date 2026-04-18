import os
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    DateTime,
    LargeBinary,
)
from sqlalchemy import create_engine

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Base class for all models
Base = declarative_base()


# Datasource model matching ingestion CSV columns
class Datasource(Base):
    __tablename__ = "datasources"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    external_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    abstract_or_summary = Column(Text, nullable=True)
    authors = Column(String, nullable=True)
    date = Column(String, nullable=True)
    url = Column(String, unique=True, nullable=False)
    tags = Column(String, nullable=True)
    analyzed = Column(Boolean, default=False, nullable=False)


class DatasourceAnalysis(Base):
    __tablename__ = "datasource_analysis"

    id = Column(Integer, primary_key=True, index=True)
    datasource_id = Column(Integer, ForeignKey("datasources.id"), unique=True)
    topics = Column(String, nullable=True)  # e.g., "AutoML, LLM for ETL"
    keywords = Column(String, nullable=True)  # e.g., "RAG, data lakes"
    emerging_algorithms = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    impact = Column(String, nullable=True)  # optional: low/medium/high
    created_at = Column(DateTime, default=datetime.utcnow)
    exported = Column(Boolean, default=False, nullable=False)


## files


# Reports model
class Reports(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Documents model
class Documents(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    file = Column(LargeBinary, nullable=False)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)


# Database connection
engine = create_engine(os.getenv("DATABASE_URL"))  # SQLite database file

# Session factory
SessionLocal = sessionmaker(bind=engine)

# This creates all tables defined in Base subclasses
if __name__ == "__main__":
    Base.metadata.create_all(engine)


