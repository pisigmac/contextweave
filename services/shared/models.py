"""SQLAlchemy models for ContextWeave."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Generator

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, Table, Index
)
from sqlalchemy.orm import declarative_base, relationship, Session, sessionmaker
from sqlalchemy import create_engine, text as sa_text

Base = declarative_base()

# Use String(36) for UUIDs in SQLite
UUID_COL = String(36)

# Association: entries <-> tags
entry_tags = Table(
    "entry_tags",
    Base.metadata,
    Column("entry_id", UUID_COL, ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UUID_COL, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class WeaveFile(Base):
    """A .weave.md file in the workspace."""
    __tablename__ = "weave_files"

    id = Column(UUID_COL, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_path = Column(String(2000), nullable=False, unique=True, index=True)
    project_name = Column(String(500), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    entries = relationship("Entry", back_populates="weave_file", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "file_path": self.file_path,
            "project_name": self.project_name,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "entry_count": len(self.entries),
        }


class Entry(Base):
    """A typed entry within a .weave.md file."""
    __tablename__ = "entries"

    id = Column(UUID_COL, primary_key=True, default=lambda: str(uuid.uuid4()))
    weave_file_id = Column(UUID_COL, ForeignKey("weave_files.id", ondelete="CASCADE"), nullable=False)
    entry_type = Column(String(50), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    outcome = Column(String(100), nullable=True)
    scope = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True)
    owner = Column(String(200), nullable=True)
    source_ref = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    weave_file = relationship("WeaveFile", back_populates="entries")
    tags = relationship("Tag", secondary=entry_tags, back_populates="entries")
    outgoing_links = relationship(
        "EntryLink",
        foreign_keys="EntryLink.from_entry_id",
        back_populates="from_entry",
        cascade="all, delete-orphan"
    )
    incoming_links = relationship(
        "EntryLink",
        foreign_keys="EntryLink.to_entry_id",
        back_populates="to_entry",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_entries_type_title", "entry_type", "title"),
        Index("ix_entries_outcome", "outcome"),
        Index("ix_entries_status", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "weave_file_id": str(self.weave_file_id),
            "file_path": self.weave_file.file_path if self.weave_file else None,
            "entry_type": self.entry_type,
            "title": self.title,
            "content": self.content,
            "outcome": self.outcome,
            "scope": self.scope,
            "status": self.status,
            "owner": self.owner,
            "source_ref": self.source_ref,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "tags": [t.name for t in self.tags],
        }


class Tag(Base):
    """A tag for entries."""
    __tablename__ = "tags"

    id = Column(UUID_COL, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    entries = relationship("Entry", secondary=entry_tags, back_populates="tags")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EntryLink(Base):
    """A link between two entries."""
    __tablename__ = "entry_links"

    id = Column(UUID_COL, primary_key=True, default=lambda: str(uuid.uuid4()))
    from_entry_id = Column(UUID_COL, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    to_entry_id = Column(UUID_COL, ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    link_type = Column(String(50), nullable=False, default="references")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    from_entry = relationship("Entry", foreign_keys=[from_entry_id], back_populates="outgoing_links")
    to_entry = relationship("Entry", foreign_keys=[to_entry_id], back_populates="incoming_links")

    __table_args__ = (
        Index("ix_link_from", "from_entry_id"),
        Index("ix_link_to", "to_entry_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "from_entry_id": str(self.from_entry_id),
            "to_entry_id": str(self.to_entry_id),
            "link_type": self.link_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Engine and session factory (configurable)
_engine = None
_SessionLocal = None


def configure_engine(database_url: str = None) -> None:
    """Configure the database engine. Call before using models."""
    global _engine, _SessionLocal
    url = database_url or "sqlite:///weave.db"
    _engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        echo=False,
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_engine():
    """Get the current engine, initializing if needed."""
    global _engine
    if _engine is None:
        configure_engine()
    return _engine


def SessionLocal():
    """Get a session factory, initializing if needed."""
    global _SessionLocal
    if _SessionLocal is None:
        configure_engine()
    return _SessionLocal()


def get_db() -> Generator[Session, None, None]:
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(database_url: str = None) -> None:
    """Initialize the database."""
    if database_url:
        configure_engine(database_url)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    # Create FTS5 virtual table for search
    with engine.connect() as conn:
        conn.execute(sa_text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entry_search USING fts5(
                title, content
            )
        """))
        conn.commit()
