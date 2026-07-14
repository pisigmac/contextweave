"""Tests for the QueryEngine."""
import pytest

from services.query.engine import QueryEngine
from services.shared.models import WeaveFile, Entry


class TestQueryEngine:
    """Test suite for query execution."""

    def test_query_by_entry_type(self, db_session):
        """Engine should filter by entry type."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        engine = QueryEngine(db_session)
        results = engine.query("Decision")

        assert len(results) == 1
        assert results[0]["entry_type"] == "Decision"

    def test_query_with_where_condition(self, db_session):
        """Engine should handle WHERE conditions."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C", outcome="Pending")
        e2 = Entry(weave_file_id=f.id, entry_type="Decision", title="D2", content="C", outcome="Accepted")
        db_session.add_all([e1, e2])
        db_session.commit()

        engine = QueryEngine(db_session)
        results = engine.query("Decision WHERE outcome=Pending")

        assert len(results) == 1
        assert results[0]["title"] == "D1"

    def test_query_with_like_condition(self, db_session):
        """Engine should handle LIKE conditions."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Task", title="Auth bug", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Task", title="Login feature", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        engine = QueryEngine(db_session)
        results = engine.query("Task WHERE title LIKE auth")

        assert len(results) == 1
        assert "auth" in results[0]["title"].lower()

    def test_query_limit(self, db_session):
        """Engine should respect limit."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        for i in range(10):
            e = Entry(weave_file_id=f.id, entry_type="Task", title=f"T{i}", content="C")
            db_session.add(e)
        db_session.commit()

        engine = QueryEngine(db_session)
        results = engine.query("Task", limit=5)

        assert len(results) == 5

    def test_workspace_status(self, db_session):
        """Engine should return workspace overview."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        engine = QueryEngine(db_session)
        status = engine.workspace_status()

        assert status["total_files"] == 1
        assert status["total_entries"] == 2
        assert status["active_files"] == 1
        assert status["type_breakdown"]["Decision"] == 1
        assert status["type_breakdown"]["Task"] == 1

    def test_search(self, db_session):
        """Engine should search entries by text."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e = Entry(weave_file_id=f.id, entry_type="Task", title="JWT auth", content="Implement JWT")
        db_session.add(e)
        db_session.commit()

        engine = QueryEngine(db_session)
        results = engine.search("JWT")

        assert len(results) == 1
        assert results[0]["title"] == "JWT auth"

    def test_dependency_graph(self, db_session):
        """Engine should return dependency graph for entry."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        engine = QueryEngine(db_session)
        graph = engine.dependency_graph(str(e1.id))

        assert "entry" in graph
        assert graph["entry"]["title"] == "T1"

    def test_query_not_found_type(self, db_session):
        """Engine should return empty for non-existent type."""
        engine = QueryEngine(db_session)
        results = engine.query("NonExistent")
        assert results == []

    def test_search_no_matches(self, db_session):
        """Engine should return empty for non-matching search."""
        engine = QueryEngine(db_session)
        results = engine.search("xyznonexistent")
        assert results == []
