"""Tests for the WeaveSyncService."""
import pytest
from pathlib import Path

from services.sync.watcher import WeaveSyncService
from services.shared.models import WeaveFile, Entry


class TestWeaveSyncService:
    """Test suite for file system sync."""

    def test_initial_sync(self, db_session, tmp_path):
        """Service should sync all .weave.md files."""
        # Create test files
        d1 = tmp_path / "project-a.weave.md"
        d1.write_text("""# Project: Project A
# Status: Active

# Decision: Use SQLite
Outcome: Accepted

# Task: Set up DB
Status: Done
""")

        d2 = tmp_path / "project-b.weave.md"
        d2.write_text("""# Project: Project B
# Status: Build

# Requirement: Handle 1000 req/s
Scope: Active
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        count = service.initial_sync()

        assert count == 2

        # Verify in DB
        files = db_session.query(WeaveFile).all()
        assert len(files) == 2

        entries = db_session.query(Entry).all()
        assert len(entries) == 3  # 2 + 1

    def test_sync_creates_project_entries(self, db_session, tmp_path):
        """Service should create entries with correct types."""
        d = tmp_path / "test.weave.md"
        d.write_text("""# Project: Test
# Status: Active

# Decision: Use Postgres
Because: ACID compliance
Outcome: Pending
Tags: database

# Task: Migration
Status: In Progress
Owner: @dev
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        service.initial_sync()

        entries = db_session.query(Entry).order_by(Entry.created_at).all()
        assert len(entries) == 2

        decision = [e for e in entries if e.entry_type == "Decision"][0]
        assert decision.title == "Use Postgres"
        assert decision.outcome == "Pending"

        task = [e for e in entries if e.entry_type == "Task"][0]
        assert task.title == "Migration"
        assert task.status == "In Progress"

    def test_sync_preserves_file_path(self, db_session, tmp_path):
        """Service should store the file path."""
        d = tmp_path / "test.weave.md"
        d.write_text("""# Project: Test
# Status: Active

# Decision: D1
Outcome: Accepted
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        service.initial_sync()

        file = db_session.query(WeaveFile).first()
        assert file.file_path == str(d)

    def test_sync_updates_existing(self, db_session, tmp_path):
        """Service should update existing files on re-sync."""
        d = tmp_path / "test.weave.md"
        d.write_text("""# Project: Test
# Status: Active

# Decision: Old
Outcome: Accepted
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        service.initial_sync()

        # Modify file
        d.write_text("""# Project: Test
# Status: Build

# Decision: New
Outcome: Pending
""")

        service.initial_sync()

        file = db_session.query(WeaveFile).first()
        assert file.status == "build"  # normalized to lowercase

        entries = db_session.query(Entry).all()
        assert len(entries) == 1
        assert entries[0].title == "New"


class TestWeaveEventHandler:
    """Test the file system event handler."""

    def test_is_weave_file(self):
        """Handler should identify .weave.md files."""
        from services.sync.watcher import WeaveEventHandler
        from services.parser.parser import WeaveParser

        handler = WeaveEventHandler(parser=WeaveParser(), on_change=lambda p, fp, et: None)

        assert handler._is_weave_file("/path/to/file.weave.md")
        assert not handler._is_weave_file("/path/to/file.md")
        assert not handler._is_weave_file("/path/to/file.txt")
