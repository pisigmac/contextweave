"""Pytest fixtures for ContextWeave."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from services.shared.models import Base, configure_engine, init_db, SessionLocal, WeaveFile, Entry, Tag, EntryLink
from services.parser.parser import WeaveParser
from services.query.engine import QueryEngine
from services.graph.engine import GraphEngine


@pytest.fixture(scope="function")
def db_session(tmp_path):
    """Create a fresh database for each test."""
    db_path = tmp_path / "test.db"
    configure_engine(f"sqlite:///{db_path}")
    init_db()

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def parser():
    """Provide a WeaveParser instance."""
    return WeaveParser()


@pytest.fixture
def sample_weave_text():
    """Sample valid .weave.md content."""
    return """# Project: Payment Gateway
# Status: Active

# Decision: Use Postgres
Because: Need ACID compliance
Risk: Operational overhead
Outcome: Pending
Tags: database, architecture

# Task: Set up schema
Status: In Progress
Owner: @user

# Requirement: Handle 1000 req/s
Scope: Active
Blocked by: #Decision-1 in ../auth-service
"""


@pytest.fixture
def sample_weave_file(db_session):
    """Create a sample weave file with entries in the database."""
    weave_file = WeaveFile(
        file_path="./payment-gateway.weave.md",
        project_name="Payment Gateway",
        status="active",
    )
    db_session.add(weave_file)
    db_session.flush()

    entries = [
        Entry(
            weave_file_id=weave_file.id,
            entry_type="Decision",
            title="Use Postgres",
            content="Need ACID compliance",
            outcome="Pending",
            tags=[],
        ),
        Entry(
            weave_file_id=weave_file.id,
            entry_type="Task",
            title="Set up schema",
            content="Create tables and indexes",
            status="In Progress",
            owner="@user",
        ),
        Entry(
            weave_file_id=weave_file.id,
            entry_type="Requirement",
            title="Handle 1000 req/s",
            content="Performance requirement",
            scope="Active",
            source_ref="#Decision-1 in ../auth-service",
        ),
    ]

    for entry in entries:
        db_session.add(entry)

    db_session.commit()
    return weave_file
