"""End-to-end integration tests for ContextWeave."""
import pytest
from pathlib import Path

from services.parser.parser import WeaveParser
from services.shared.models import WeaveFile, Entry, Tag, EntryLink, init_db, SessionLocal
from services.query.engine import QueryEngine
from services.graph.engine import GraphEngine
from services.sync.watcher import WeaveSyncService


class TestEndToEnd:
    """Full workflow integration tests."""

    def test_full_workflow_parse_sync_query(self, db_session, tmp_path):
        """Complete workflow: create file -> sync -> query -> search."""
        # 1. Create .weave.md files
        f1 = tmp_path / "auth-service.weave.md"
        f1.write_text("""# Project: Auth Service
# Status: Active

# Decision: Use JWT tokens
Because: Stateless auth
Risk: Token revocation
Outcome: Accepted
Tags: auth, security

# Task: Implement refresh tokens
Status: In Progress
Owner: @alice
""")

        f2 = tmp_path / "payment-service.weave.md"
        f2.write_text("""# Project: Payment Service
# Status: Build

# Requirement: PCI compliance
Scope: Active
Tags: security, compliance
Blocked by: #Decision-1 in ./auth-service

# Decision: Use Stripe
Because: Reduce compliance scope
Outcome: Accepted
Tags: payments
""")

        # 2. Sync
        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        count = service.initial_sync()
        assert count == 2

        # 3. Query by type
        engine = QueryEngine(db_session)
        decisions = engine.query("Decision")
        assert len(decisions) == 2

        # 4. Query with WHERE
        accepted = engine.query("Decision WHERE outcome=Accepted")
        assert len(accepted) == 2

        # 5. Query by status
        in_progress = engine.query("Task WHERE status='In Progress'")
        assert len(in_progress) == 1
        assert in_progress[0]["title"] == "Implement refresh tokens"

    def test_workspace_status_after_sync(self, db_session, tmp_path):
        """Sync files and verify workspace status."""
        f = tmp_path / "project.weave.md"
        f.write_text("""# Project: Test
# Status: Active

# Decision: D1
Outcome: Accepted

# Task: T1
Status: Done

# Task: T2
Status: In Progress

# Requirement: R1
Scope: Active
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        service.initial_sync()

        engine = QueryEngine(db_session)
        status = engine.workspace_status()

        assert status["total_files"] == 1
        assert status["total_entries"] == 4
        assert status["active_files"] == 1
        assert status["type_breakdown"]["Decision"] == 1
        assert status["type_breakdown"]["Task"] == 2
        assert status["type_breakdown"]["Requirement"] == 1

    def test_graph_links_after_sync(self, db_session, tmp_path):
        """Sync files and verify graph links are resolved."""
        f = tmp_path / "project.weave.md"
        f.write_text("""# Project: Test
# Status: Active

# Decision: Architecture
Outcome: Accepted

# Task: Implementation
Status: In Progress
Blocked by: Architecture
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        service.initial_sync()

        # Verify links were created
        links = db_session.query(EntryLink).all()
        assert len(links) == 1

        # Verify graph
        engine = GraphEngine(db_session)
        graph = engine.get_workspace_graph()
        assert graph["edge_count"] == 1

    def test_blocking_chain(self, db_session, tmp_path):
        """Create entries with blockers and trace chain."""
        f = tmp_path / "project.weave.md"
        f.write_text("""# Project: Test
# Status: Active

# Decision: Use microservices
Outcome: Accepted

# Decision: Use Kubernetes
Outcome: Accepted

# Task: Deploy to K8s
Status: Blocked
Blocked by: Use Kubernetes
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        service.initial_sync()

        # Find the task entry
        task = db_session.query(Entry).filter(Entry.title == "Deploy to K8s").first()
        assert task is not None

        engine = GraphEngine(db_session)
        chain = engine.get_blocking_chain(str(task.id))

        assert len(chain) >= 1
        assert chain[0]["title"] == "Deploy to K8s"

    def test_tags_synced(self, db_session, tmp_path):
        """Tags from .weave.md files should be created."""
        f = tmp_path / "project.weave.md"
        f.write_text("""# Project: Test
# Status: Active

# Decision: Use Redis
Outcome: Accepted
Tags: cache, performance, infrastructure

# Task: Set up cluster
Status: In Progress
Tags: infrastructure, devops
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        service.initial_sync()

        tags = db_session.query(Tag).all()
        tag_names = {t.name for t in tags}

        assert "cache" in tag_names
        assert "performance" in tag_names
        assert "infrastructure" in tag_names
        assert "devops" in tag_names

    def test_parser_to_db_roundtrip(self, db_session, tmp_path):
        """Parse file, save to DB, retrieve, serialize back."""
        parser = WeaveParser()

        # Create file
        file_path = tmp_path / "roundtrip.weave.md"
        file_path.write_text("""# Project: Roundtrip Test
# Status: Active

# Decision: Test decision
Because: Testing
Outcome: Pending
Tags: test
""")

        # Parse
        parsed = parser.parse_file(file_path)

        # Save to DB
        weave_file = WeaveFile(
            file_path=str(file_path),
            project_name=parsed.project_name,
            status=parsed.status,
        )
        db_session.add(weave_file)
        db_session.flush()

        for parsed_entry in parsed.entries:
            entry = Entry(
                weave_file_id=weave_file.id,
                entry_type=parsed_entry.entry_type,
                title=parsed_entry.title,
                content=parsed_entry.content,
                outcome=parsed_entry.outcome,
            )
            db_session.add(entry)
        db_session.commit()

        # Retrieve and verify
        retrieved = db_session.query(WeaveFile).filter(WeaveFile.id == weave_file.id).first()
        assert retrieved.project_name == "Roundtrip Test"
        assert len(retrieved.entries) == 1
        assert retrieved.entries[0].entry_type == "Decision"

        # Serialize back
        md = parser.to_markdown(parsed)
        assert "Roundtrip Test" in md
        assert "Decision: Test decision" in md

    def test_multiple_projects_query(self, db_session, tmp_path):
        """Query across multiple projects."""
        # Create multiple project files
        for i, name in enumerate(["Alpha", "Beta", "Gamma"]):
            f = tmp_path / f"{name.lower()}.weave.md"
            f.write_text(f"""# Project: {name}
# Status: Active

# Decision: Decision {i}
Outcome: Accepted
Tags: project-{name.lower()}

# Task: Task {i}
Status: {'Done' if i == 0 else 'In Progress'}
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        service.initial_sync()

        # Query all decisions
        engine = QueryEngine(db_session)
        all_decisions = engine.query("Decision")
        assert len(all_decisions) == 3

        # Query done tasks
        done_tasks = engine.query("Task WHERE status=Done")
        assert len(done_tasks) == 1

    def test_reference_resolution_cross_project(self, db_session, tmp_path):
        """References between projects should be resolved."""
        f1 = tmp_path / "auth.weave.md"
        f1.write_text("""# Project: Auth Service
# Status: Active

# Decision: OAuth2 flow
Outcome: Accepted
""")

        f2 = tmp_path / "api.weave.md"
        f2.write_text("""# Project: API Gateway
# Status: Build

# Task: Implement auth middleware
Status: Blocked
Blocked by: OAuth2 flow
""")

        service = WeaveSyncService(watch_dirs=[str(tmp_path)])
        service.initial_sync()

        # Check that reference was resolved
        links = db_session.query(EntryLink).all()
        assert len(links) >= 1

        # Verify blocking chain
        task = db_session.query(Entry).filter(Entry.title == "Implement auth middleware").first()
        engine = GraphEngine(db_session)
        chain = engine.get_blocking_chain(str(task.id))
        assert len(chain) >= 1
