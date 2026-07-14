"""Tests for the WeaveParser."""
import pytest
from pathlib import Path

from services.parser.parser import WeaveParser, ParsedWeaveFile, ParsedEntry


class TestWeaveParser:
    """Test suite for .weave.md parsing."""

    def test_parse_valid_weave_file(self, parser, sample_weave_text):
        """Parser should extract project, entries, and fields."""
        parsed = parser.parse_text(sample_weave_text, "test.weave.md")

        assert parsed.project_name == "Payment Gateway"
        assert parsed.status == "active"  # normalized to lowercase
        assert len(parsed.entries) == 3

    def test_parse_decision_entry(self, parser, sample_weave_text):
        """Parser should extract Decision with outcome and tags."""
        parsed = parser.parse_text(sample_weave_text)

        decision = [e for e in parsed.entries if e.entry_type == "Decision"][0]
        assert decision.title == "Use Postgres"
        assert decision.outcome == "Pending"
        assert "database" in decision.tags
        assert "architecture" in decision.tags

    def test_parse_task_entry(self, parser, sample_weave_text):
        """Parser should extract Task with status and owner."""
        parsed = parser.parse_text(sample_weave_text)

        task = [e for e in parsed.entries if e.entry_type == "Task"][0]
        assert task.title == "Set up schema"
        assert task.status == "In Progress"
        assert task.owner == "@user"

    def test_parse_requirement_with_reference(self, parser, sample_weave_text):
        """Parser should extract cross-file reference."""
        parsed = parser.parse_text(sample_weave_text)

        req = [e for e in parsed.entries if e.entry_type == "Requirement"][0]
        assert req.title == "Handle 1000 req/s"
        assert req.scope == "Active"
        assert req.source_ref == "#Decision-1 in ../auth-service"

    def test_parse_file_from_disk(self, parser, tmp_path):
        """Parser should read from file path."""
        file_path = tmp_path / "test.weave.md"
        file_path.write_text("""# Project: File Test
# Status: Active

# Decision: Test decision
Outcome: Accepted
""")
        parsed = parser.parse_file(file_path)
        assert parsed.project_name == "File Test"
        assert len(parsed.entries) == 1
        assert parsed.file_path == str(file_path)

    def test_parse_without_project_header(self, parser):
        """Parser should use filename as project name if no # Project header."""
        text = "# Decision: Something\n\nContent here."
        parsed = parser.parse_text(text, "/path/to/my-project.weave.md")
        assert parsed.project_name == "my-project"

    def test_validate_valid_file(self, parser, sample_weave_text):
        """Validation should return no errors for valid file."""
        errors = parser.validate(sample_weave_text)
        assert errors == []

    def test_validate_missing_project(self, parser):
        """Validation should catch missing project header."""
        text = "# Decision: Something\n\nContent."
        errors = parser.validate(text)
        assert any("Missing # Project" in e for e in errors)

    def test_validate_no_entries(self, parser):
        """Validation should catch missing typed entries."""
        text = "# Project: Test\n\nJust some content."
        errors = parser.validate(text)
        assert any("No typed entries" in e for e in errors)

    def test_validate_short_title(self, parser):
        """Validation should catch short entry titles."""
        text = "# Project: Test\n\n# Decision: AB\n\nContent."
        errors = parser.validate(text)
        assert any("too short" in e for e in errors)

    def test_summary(self, parser, sample_weave_text):
        """Summary should provide accurate overview."""
        summary = parser.get_summary(sample_weave_text)

        assert summary["project_name"] == "Payment Gateway"
        assert summary["entry_count"] == 3
        assert summary["has_blockers"] is True
        assert "Decision" in summary["types"]
        assert "Task" in summary["types"]

    def test_to_markdown_roundtrip(self, parser, sample_weave_text):
        """Serializing and re-parsing should preserve data."""
        parsed = parser.parse_text(sample_weave_text)
        md = parser.to_markdown(parsed)
        reparsed = parser.parse_text(md)

        assert reparsed.project_name == parsed.project_name
        assert len(reparsed.entries) == len(parsed.entries)
        assert reparsed.entries[0].entry_type == parsed.entries[0].entry_type
        assert reparsed.entries[0].title == parsed.entries[0].title

    def test_parse_tags_comma_separated(self, parser):
        """Parser should handle comma-separated tags."""
        text = """# Project: Tags Test
# Status: Active

# Decision: Something
Tags: tag1, tag2, tag3
"""
        parsed = parser.parse_text(text)
        entry = parsed.entries[0]
        assert "tag1" in entry.tags
        assert "tag2" in entry.tags
        assert "tag3" in entry.tags

    def test_parse_content_cleaning(self, parser):
        """Parser should remove field lines from content body."""
        text = """# Project: Clean Test
# Status: Active

# Decision: Something
Because: This is why
Risk: This is the risk
Outcome: Pending

This is the actual narrative content.
"""
        parsed = parser.parse_text(text)
        entry = parsed.entries[0]
        assert "This is the actual narrative content" in entry.content
        assert "Because:" not in entry.content
        assert "Risk:" not in entry.content


class TestParsedWeaveFile:
    """Tests for ParsedWeaveFile dataclass."""

    def test_defaults(self):
        """ParsedWeaveFile should have sensible defaults."""
        pwf = ParsedWeaveFile(project_name="Test", file_path="test.md")
        assert pwf.status == "active"
        assert pwf.entries == []


class TestParsedEntry:
    """Tests for ParsedEntry dataclass."""

    def test_defaults(self):
        """ParsedEntry should have sensible defaults."""
        pe = ParsedEntry(entry_type="Task", title="Test", content="Content")
        assert pe.tags == []
        assert pe.outcome is None
        assert pe.status is None
        assert pe.owner is None
