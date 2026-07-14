"""Tests for the ContextWeave API."""
import pytest
from fastapi.testclient import TestClient

from services.api.main import create_app
from services.shared.models import get_db, WeaveFile, Entry, Tag, EntryLink, init_db, configure_engine


@pytest.fixture
def client(db_session):
    """Create a test client."""
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


class TestWeaveFileCRUD:
    """Test CRUD for weave files."""

    def test_create_file(self, client):
        """POST /files should create a weave file."""
        response = client.post("/api/v1/files", json={
            "file_path": "./test.weave.md",
            "project_name": "Test Project",
            "status": "active",
            "entries": [
                {
                    "entry_type": "Decision",
                    "title": "Use SQLite",
                    "content": "Simple and fast",
                    "outcome": "Accepted",
                }
            ],
        })

        assert response.status_code == 201
        data = response.json()
        assert data["project_name"] == "Test Project"
        assert data["entry_count"] == 1

    def test_list_files(self, client, db_session):
        """GET /files should list all files."""
        f1 = WeaveFile(file_path="./a.weave.md", project_name="A")
        f2 = WeaveFile(file_path="./b.weave.md", project_name="B")
        db_session.add_all([f1, f2])
        db_session.commit()

        response = client.get("/api/v1/files")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_file(self, client, db_session):
        """GET /files/{id} should return file with entries."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e = Entry(weave_file_id=f.id, entry_type="Task", title="Do thing", content="Details")
        db_session.add(e)
        db_session.commit()

        response = client.get(f"/api/v1/files/{f.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["project_name"] == "Test"
        assert len(data["entries"]) == 1

    def test_delete_file(self, client, db_session):
        """DELETE /files/{id} should remove file."""
        f = WeaveFile(file_path="./delete.weave.md", project_name="Delete")
        db_session.add(f)
        db_session.commit()

        response = client.delete(f"/api/v1/files/{f.id}")
        assert response.status_code == 204

        response = client.get(f"/api/v1/files/{f.id}")
        assert response.status_code == 404


class TestEntryCRUD:
    """Test CRUD for entries."""

    def test_list_entries(self, client, db_session):
        """GET /entries should list entries."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Task", title="Task 1", content="C1")
        e2 = Entry(weave_file_id=f.id, entry_type="Decision", title="Decision 1", content="C2")
        db_session.add_all([e1, e2])
        db_session.commit()

        response = client.get("/api/v1/entries")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_entries_by_type(self, client, db_session):
        """GET /entries?entry_type=Task should filter."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        response = client.get("/api/v1/entries?entry_type=task")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["entry_type"] == "Task"

    def test_get_entry(self, client, db_session):
        """GET /entries/{id} should return entry."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e = Entry(weave_file_id=f.id, entry_type="Bug", title="Crash bug", content="Details")
        db_session.add(e)
        db_session.commit()

        response = client.get(f"/api/v1/entries/{e.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Crash bug"

    def test_update_entry(self, client, db_session):
        """PATCH /entries/{id} should update entry."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e = Entry(weave_file_id=f.id, entry_type="Task", title="Old", content="Old content")
        db_session.add(e)
        db_session.commit()

        response = client.patch(f"/api/v1/entries/{e.id}", json={
            "entry_type": "Task",
            "title": "New",
            "content": "New content",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New"

    def test_delete_entry(self, client, db_session):
        """DELETE /entries/{id} should remove entry."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e = Entry(weave_file_id=f.id, entry_type="Task", title="Delete me", content="C")
        db_session.add(e)
        db_session.commit()

        response = client.delete(f"/api/v1/entries/{e.id}")
        assert response.status_code == 204


class TestQuery:
    """Test query endpoint."""

    def test_query_by_type(self, client, db_session):
        """POST /query should filter by entry type."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C", outcome="Pending")
        e2 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        response = client.post("/api/v1/query", json={"query": "Decision", "limit": 10})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["entry_type"] == "Decision"

    def test_query_with_where(self, client, db_session):
        """POST /query should handle WHERE conditions."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C", outcome="Pending")
        e2 = Entry(weave_file_id=f.id, entry_type="Decision", title="D2", content="C", outcome="Accepted")
        db_session.add_all([e1, e2])
        db_session.commit()

        response = client.post("/api/v1/query", json={
            "query": "Decision WHERE outcome=Pending",
            "limit": 10,
        })

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "D1"


class TestGraph:
    """Test graph/link endpoints."""

    def test_create_link(self, client, db_session):
        """POST /links should create a link."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e1 = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        e2 = Entry(weave_file_id=f.id, entry_type="Decision", title="D1", content="C")
        db_session.add_all([e1, e2])
        db_session.commit()

        response = client.post("/api/v1/links", json={
            "from_entry_id": str(e1.id),
            "to_entry_id": str(e2.id),
            "link_type": "blocks",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["link_type"] == "blocks"

    def test_get_entry_links(self, client, db_session):
        """GET /entries/{id}/links should return links."""
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

        response = client.get(f"/api/v1/entries/{e1.id}/links")
        assert response.status_code == 200
        data = response.json()
        assert len(data["outgoing"]) == 1

    def test_workspace_graph(self, client, db_session):
        """GET /graph should return workspace graph."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        db_session.add(e)
        db_session.commit()

        response = client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()
        assert data["node_count"] >= 1


class TestWorkspace:
    """Test workspace endpoints."""

    def test_workspace_status(self, client, db_session):
        """GET /workspace/status should return overview."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        db_session.add(e)
        db_session.commit()

        response = client.get("/api/v1/workspace/status")
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 1
        assert data["total_entries"] == 1

    def test_list_tags(self, client, db_session):
        """GET /tags should list tags."""
        f = WeaveFile(file_path="./test.weave.md", project_name="Test")
        db_session.add(f)
        db_session.flush()

        e = Entry(weave_file_id=f.id, entry_type="Task", title="T1", content="C")
        db_session.add(e)
        db_session.flush()

        tag = Tag(name="important")
        db_session.add(tag)
        db_session.commit()
        e.tags.append(tag)
        db_session.commit()

        response = client.get("/api/v1/tags")
        assert response.status_code == 200
        data = response.json()
        assert any(t["name"] == "important" for t in data)


class TestHealth:
    """Test health endpoint."""

    def test_health(self, client):
        """GET /health should return ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
