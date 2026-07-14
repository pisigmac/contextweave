"""Tests for the GraphEngine."""
import pytest

from services.graph.engine import GraphEngine
from services.shared.models import WeaveFile, Entry, EntryLink


class TestGraphEngine:
    """Test suite for graph operations."""

    def test_create_link(self, db_session):
        """Engine should create links between entries."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        engine = GraphEngine(db_session)
        result = engine.create_link(str(e1.id), str(e2.id), "blocks")

        assert result is not None
        assert result["link_type"] == "blocks"

    def test_create_link_invalid_ids(self, db_session):
        """Engine should return None for invalid IDs."""
        engine = GraphEngine(db_session)
        result = engine.create_link("invalid", "invalid", "blocks")
        assert result is None

    def test_get_workspace_graph(self, db_session):
        """Engine should return workspace graph."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        link = EntryLink(from_entry_id=e1.id, to_entry_id=e2.id, link_type="references")
        db_session.add(link)
        db_session.commit()

        engine = GraphEngine(db_session)
        graph = engine.get_workspace_graph()

        assert graph["node_count"] == 2
        assert graph["edge_count"] == 1
        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1

    def test_get_blocking_chain(self, db_session):
        """Engine should trace blocking chain."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C", source_ref="#Decision-1")
        db_session.add_all([e1, e2])
        db_session.commit()

        engine = GraphEngine(db_session)
        chain = engine.get_blocking_chain(str(e2.id))

        assert len(chain) >= 1
        assert chain[0]["title"] == "T1"

    def test_delete_link(self, db_session):
        """Engine should delete links."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        link = EntryLink(from_entry_id=e1.id, to_entry_id=e2.id, link_type="references")
        db_session.add(link)
        db_session.commit()

        engine = GraphEngine(db_session)
        result = engine.delete_link(str(link.id))

        assert result is True
        assert db_session.query(EntryLink).count() == 0

    def test_delete_nonexistent_link(self, db_session):
        """Engine should return False for non-existent link."""
        engine = GraphEngine(db_session)
        result = engine.delete_link("00000000-0000-0000-0000-000000000000")
        assert result is False

    def test_resolve_references(self, db_session):
        """Engine should resolve implicit references."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Decision", title="Auth approach", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Task", title="Implement", content="C", source_ref="Auth approach")
        db_session.add_all([e1, e2])
        db_session.commit()

        engine = GraphEngine(db_session)
        resolved = engine.resolve_references(str(f.id))

        assert len(resolved) == 1
        assert resolved[0]["from_title"] == "Implement"
        assert resolved[0]["to_title"] == "Auth approach"

    def test_empty_graph(self, db_session):
        """Engine should handle empty workspace."""
        engine = GraphEngine(db_session)
        graph = engine.get_workspace_graph()

        assert graph["node_count"] == 0
        assert graph["edge_count"] == 0
