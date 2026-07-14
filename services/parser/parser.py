"""Parser for .weave.md files with typed headers."""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class ParsedEntry:
    """A single typed entry from a .weave.md file."""
    entry_type: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    outcome: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    source_ref: Optional[str] = None
    references: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ParsedWeaveFile:
    """A parsed .weave.md file."""
    project_name: str
    file_path: str
    status: str = "active"
    entries: List[ParsedEntry] = field(default_factory=list)


class WeaveParser:
    """Parse .weave.md files with typed headers."""

    # Valid typed header patterns: # Type: Title
    HEADER_PATTERN = re.compile(r'^#\s+(\w+):\s+(.*?)$', re.MULTILINE)

    # Inline field patterns within entry content
    FIELD_PATTERNS = {
        'tags': re.compile(r'^Tags?:\s*(.+)$', re.MULTILINE | re.IGNORECASE),
        'outcome': re.compile(r'^Outcome?:\s*(.+)$', re.MULTILINE | re.IGNORECASE),
        'scope': re.compile(r'^Scope?:\s*(.+)$', re.MULTILINE | re.IGNORECASE),
        'status': re.compile(r'^Status?:\s*(.+)$', re.MULTILINE | re.IGNORECASE),
        'owner': re.compile(r'^Owner?:\s*(.+)$', re.MULTILINE | re.IGNORECASE),
        'because': re.compile(r'^Because(?: of)?:\s*(.+)$', re.MULTILINE | re.IGNORECASE),
        'risk': re.compile(r'^Risk(?:s)?:\s*(.+)$', re.MULTILINE | re.IGNORECASE),
        'blocked_by': re.compile(r'^Blocked\s+by:\s*(.+)$', re.MULTILINE | re.IGNORECASE),
        'see': re.compile(r'^See:\s*(.+)$', re.MULTILINE | re.IGNORECASE),
    }

    # Cross-reference pattern: #Type-N in ../path or #Type-N in ./path
    REFERENCE_PATTERN = re.compile(
        r'#(\w+)-(\d+)\s+in\s+(.+?)(?:\s|$)',
        re.MULTILINE
    )

    # Project header: # Project: Name
    PROJECT_PATTERN = re.compile(r'^#\s+Project:\s*(.+)$', re.MULTILINE | re.IGNORECASE)

    # Status header: # Status: Value
    STATUS_PATTERN = re.compile(r'^#\s+Status:\s*(.+)$', re.MULTILINE | re.IGNORECASE)

    VALID_TYPES = {
        'Decision', 'Task', 'Requirement', 'Session', 'Note',
        'Bug', 'Feature', 'Design', 'Question', 'Risk',
        'Metric', 'Goal', 'Milestone', 'Review'
    }

    def parse_file(self, file_path: Path) -> ParsedWeaveFile:
        """Parse a .weave.md file."""
        raw = file_path.read_text(encoding='utf-8')
        return self.parse_text(raw, str(file_path))

    def parse_text(self, text: str, file_path: str = '') -> ParsedWeaveFile:
        """Parse weave markdown text."""
        # Extract project name
        project_match = self.PROJECT_PATTERN.search(text)
        if project_match:
            project_name = project_match.group(1).strip()
        elif file_path:
            # Handle .weave.md extension properly
            p = Path(file_path)
            name = p.stem
            if name.endswith('.weave'):
                project_name = name[:-6]  # Remove .weave suffix
            else:
                project_name = name
        else:
            project_name = "Untitled"

        # Extract status
        status_match = self.STATUS_PATTERN.search(text)
        status = status_match.group(1).strip().lower() if status_match else 'active'

        # Find all typed headers
        headers = list(self.HEADER_PATTERN.finditer(text))

        entries = []
        for i, header in enumerate(headers):
            entry_type = header.group(1)
            title = header.group(2).strip()

            # Skip Project and Status headers
            if entry_type.lower() in ('project', 'status'):
                continue

            # Extract content between this header and the next
            start = header.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            content = text[start:end].strip()

            # Parse inline fields from content
            parsed_entry = self._parse_entry_content(entry_type, title, content)
            entries.append(parsed_entry)

        return ParsedWeaveFile(
            project_name=project_name,
            file_path=file_path,
            status=status,
            entries=entries,
        )

    def _parse_entry_content(self, entry_type: str, title: str, content: str) -> ParsedEntry:
        """Parse inline fields from entry content."""
        # Extract fields
        tags = []
        outcome = None
        scope = None
        status = None
        owner = None
        source_ref = None
        references = []

        # Tags
        tags_match = self.FIELD_PATTERNS['tags'].search(content)
        if tags_match:
            tags_str = tags_match.group(1)
            tags = [t.strip().lower() for t in re.split(r'[,;]', tags_str) if t.strip()]

        # Outcome
        outcome_match = self.FIELD_PATTERNS['outcome'].search(content)
        if outcome_match:
            outcome = outcome_match.group(1).strip()

        # Scope
        scope_match = self.FIELD_PATTERNS['scope'].search(content)
        if scope_match:
            scope = scope_match.group(1).strip()

        # Status
        status_match = self.FIELD_PATTERNS['status'].search(content)
        if status_match:
            status = status_match.group(1).strip()

        # Owner
        owner_match = self.FIELD_PATTERNS['owner'].search(content)
        if owner_match:
            owner = owner_match.group(1).strip()

        # Cross-references
        for ref_match in self.REFERENCE_PATTERN.finditer(content):
            references.append({
                'ref_type': ref_match.group(1),
                'ref_number': ref_match.group(2),
                'ref_path': ref_match.group(3).strip(),
            })

        # Source ref from blocked_by or see
        blocked_match = self.FIELD_PATTERNS['blocked_by'].search(content)
        if blocked_match:
            source_ref = blocked_match.group(1).strip()

        see_match = self.FIELD_PATTERNS['see'].search(content)
        if see_match:
            source_ref = see_match.group(1).strip()

        # Clean content (remove parsed field lines to get clean body)
        clean_content = self._clean_content(content)

        return ParsedEntry(
            entry_type=entry_type,
            title=title,
            content=clean_content,
            tags=tags,
            outcome=outcome,
            scope=scope,
            status=status,
            owner=owner,
            source_ref=source_ref,
            references=references,
        )

    def _clean_content(self, content: str) -> str:
        """Remove parsed field lines from content, keeping narrative."""
        lines = content.split('\n')
        clean_lines = []
        for line in lines:
            is_field = False
            for pattern in self.FIELD_PATTERNS.values():
                if pattern.match(line):
                    is_field = True
                    break
            if not is_field:
                clean_lines.append(line)
        return '\n'.join(clean_lines).strip()

    def validate(self, text: str) -> List[str]:
        """Validate a .weave.md file and return errors."""
        errors = []

        # Check for project header
        if not self.PROJECT_PATTERN.search(text):
            errors.append("Missing # Project: header")

        # Check for typed entries
        headers = list(self.HEADER_PATTERN.finditer(text))
        typed_entries = [h for h in headers if h.group(1) not in ('Project', 'Status')]

        if not typed_entries:
            errors.append("No typed entries found (e.g., # Decision:, # Task:)")

        # Validate each entry
        for i, header in enumerate(typed_entries):
            entry_type = header.group(1)
            title = header.group(2).strip()

            if len(title) < 3:
                errors.append(f"Entry {i+1} title too short (min 3 chars)")

            if len(title) > 500:
                errors.append(f"Entry {i+1} title too long (max 500 chars)")

        return errors

    def get_summary(self, text: str) -> Dict[str, Any]:
        """Get a quick summary of a .weave.md file."""
        parsed = self.parse_text(text)

        type_counts = {}
        for entry in parsed.entries:
            type_counts[entry.entry_type] = type_counts.get(entry.entry_type, 0) + 1

        return {
            'project_name': parsed.project_name,
            'status': parsed.status,
            'entry_count': len(parsed.entries),
            'types': type_counts,
            'has_blockers': any(e.source_ref for e in parsed.entries),
        }

    def to_markdown(self, parsed_file: ParsedWeaveFile) -> str:
        """Serialize a parsed weave file back to markdown."""
        lines = [f"# Project: {parsed_file.project_name}"]
        lines.append(f"# Status: {parsed_file.status}")
        lines.append("")

        for entry in parsed_file.entries:
            lines.append(f"# {entry.entry_type}: {entry.title}")
            lines.append("")

            if entry.tags:
                lines.append(f"Tags: {', '.join(entry.tags)}")

            if entry.outcome:
                lines.append(f"Outcome: {entry.outcome}")

            if entry.scope:
                lines.append(f"Scope: {entry.scope}")

            if entry.status:
                lines.append(f"Status: {entry.status}")

            if entry.owner:
                lines.append(f"Owner: {entry.owner}")

            if entry.source_ref:
                lines.append(f"Blocked by: {entry.source_ref}")

            if entry.content:
                lines.append(entry.content)

            lines.append("")

        return '\n'.join(lines)
