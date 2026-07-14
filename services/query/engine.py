"""Query engine for ContextWeave — handles !query: directives and workspace queries."""
from typing import List, Dict, Any, Optional
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from services.shared.models import Entry, Tag, WeaveFile


class QueryEngine:
    """Execute queries against the workspace knowledge graph."""

    VALID_OPS = {'=', '!=', '<>', '<', '>', '<=', '>=', 'LIKE', 'NOT LIKE'}

    def __init__(self, db: Session):
        self.db = db

    def query(self, query_str: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Execute a weave query string.

        Query syntax: SELECT <fields> WHERE <conditions> [ORDER BY <field>] [LIMIT <n>]
        Shorthand: <entry_type> WHERE <conditions>
        """
        query_str = query_str.strip()

        # Parse the query
        parsed = self._parse_query(query_str)

        # Build and execute SQL
        return self._execute(parsed, limit)

    def _parse_query(self, query_str: str) -> Dict[str, Any]:
        """Parse a query string into structured components."""
        result = {
            'select': ['*'],
            'from_type': None,
            'where': [],
            'order_by': None,
            'limit': None,
        }

        # Check for shorthand: "decisions WHERE outcome='revisit'"
        # or full: "SELECT * FROM entries WHERE type='Decision'"
        lower = query_str.lower()

        if lower.startswith('select'):
            # Full SQL-like syntax
            parts = query_str.split(None, 2)
            result['select'] = [f.strip() for f in parts[1].split(',')]

            # Parse remaining
            remaining = parts[2] if len(parts) > 2 else ''

            # Check for FROM
            from_match = remaining.lower().find(' from ')
            if from_match >= 0:
                before_from = remaining[:from_match].strip()
                after_from = remaining[from_match + 6:].strip()
                result['select'] = [f.strip() for f in before_from.split(',')]
                remaining = after_from

            # WHERE
            where_match = remaining.lower().find(' where ')
            if where_match >= 0:
                where_clause = remaining[where_match + 7:].strip()
                # Parse conditions
                result['where'] = self._parse_where(where_clause)
                remaining = remaining[:where_match].strip()

                # Re-check FROM after extracting WHERE
                from_match2 = remaining.lower().find(' from ')
                if from_match2 >= 0:
                    result['from_type'] = remaining[from_match2 + 6:].strip()

        else:
            # Shorthand: "type WHERE condition"
            where_idx = lower.find(' where ')
            if where_idx >= 0:
                type_part = query_str[:where_idx].strip()
                result['from_type'] = type_part
                where_clause = query_str[where_idx + 7:].strip()
                result['where'] = self._parse_where(where_clause)
            else:
                # Just a type filter
                result['from_type'] = query_str.strip()

        # ORDER BY
        order_idx = query_str.lower().find(' order by ')
        if order_idx >= 0:
            order_part = query_str[order_idx + 10:].strip()
            limit_idx = order_part.lower().find(' limit ')
            if limit_idx >= 0:
                result['order_by'] = order_part[:limit_idx].strip()
                result['limit'] = int(order_part[limit_idx + 7:].strip())
            else:
                result['order_by'] = order_part

        # LIMIT
        if result['limit'] is None:
            limit_idx = query_str.lower().rfind(' limit ')
            if limit_idx >= 0:
                try:
                    result['limit'] = int(query_str[limit_idx + 7:].strip())
                except ValueError:
                    pass

        return result

    def _parse_where(self, where_clause: str) -> List[Dict[str, str]]:
        """Parse WHERE conditions."""
        conditions = []

        # Split by AND (simple approach)
        parts = where_clause.split(' AND ')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Find operator
            for op in sorted(self.VALID_OPS, key=len, reverse=True):
                if op in part.upper():
                    left, right = part.split(op, 1)
                    left = left.strip()
                    right = right.strip().strip("'\"'")
                    conditions.append({
                        'field': left,
                        'op': op.upper(),
                        'value': right,
                    })
                    break

        return conditions

    def _execute(self, parsed: Dict[str, Any], default_limit: int) -> List[Dict[str, Any]]:
        """Execute parsed query against database."""
        query = self.db.query(Entry)

        # Type filter
        if parsed['from_type']:
            query = query.filter(
                Entry.entry_type.ilike(parsed['from_type'])
            )

        # WHERE conditions
        for cond in parsed['where']:
            field = cond['field']
            op = cond['op']
            value = cond['value']

            column = getattr(Entry, field, None)
            if column is None:
                continue

            if op == '=':
                query = query.filter(column == value)
            elif op in ('!=', '<>'):
                query = query.filter(column != value)
            elif op == 'LIKE':
                query = query.filter(column.ilike(f'%{value}%'))
            elif op == 'NOT LIKE':
                query = query.filter(~column.ilike(f'%{value}%'))
            elif op == 'IN':
                values = [v.strip().strip("'\"") for v in value.split(',')]
                query = query.filter(column.in_(values))

        # ORDER BY
        if parsed['order_by']:
            order_col = getattr(Entry, parsed['order_by'], Entry.updated_at)
            query = query.order_by(order_col.desc())
        else:
            query = query.order_by(Entry.updated_at.desc())

        # LIMIT
        limit = parsed['limit'] or default_limit
        entries = query.limit(limit).all()

        return [e.to_dict() for e in entries]

    def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Full-text search using FTS5 or fallback to LIKE search."""
        # Try FTS5 first
        try:
            fts_query = ' OR '.join(f'"{q}"' for q in query.split())
            sql = sa_text("""
                SELECT rowid FROM entry_search
                WHERE entry_search MATCH :query
                LIMIT :limit
            """)
            fts_results = self.db.execute(sql, {'query': fts_query, 'limit': limit}).fetchall()

            if fts_results:
                # Get entries that match the FTS results by title/content
                matched_entries = []
                for (rowid,) in fts_results:
                    # FTS5 rowid is integer, find matching entries
                    entries = self.db.query(Entry).filter(
                        (Entry.title.contains(query)) | (Entry.content.contains(query))
                    ).limit(limit).all()
                    matched_entries.extend(entries)
                return [e.to_dict() for e in matched_entries[:limit]]
        except Exception:
            pass

        # Fallback: LIKE-based search
        search_pattern = f'%{query}%'
        entries = self.db.query(Entry).filter(
            (Entry.title.ilike(search_pattern)) | (Entry.content.ilike(search_pattern))
        ).limit(limit).all()
        return [e.to_dict() for e in entries]

    def workspace_status(self) -> Dict[str, Any]:
        """Get overall workspace status summary."""
        total_files = self.db.query(WeaveFile).count()
        total_entries = self.db.query(Entry).count()

        # Entry type breakdown
        type_counts = {}
        for entry_type, count in self.db.query(
            Entry.entry_type,
            sa_text('COUNT(*)')
        ).group_by(Entry.entry_type).all():
            type_counts[entry_type] = count

        # Blocked items
        blocked = self.db.query(Entry).filter(Entry.source_ref.isnot(None)).count()

        # Active vs inactive files
        active_files = self.db.query(WeaveFile).filter(WeaveFile.status == 'active').count()

        return {
            'total_files': total_files,
            'total_entries': total_entries,
            'active_files': active_files,
            'type_breakdown': type_counts,
            'blocked_items': blocked,
        }

    def dependency_graph(self, entry_id: str) -> Dict[str, Any]:
        """Get the dependency graph for an entry."""
        entry = self.db.query(Entry).filter(Entry.id == entry_id).first()
        if not entry:
            return {'error': 'Entry not found'}

        return {
            'entry': entry.to_dict(),
            'outgoing': [{
                'id': str(l.to_entry_id),
                'type': l.link_type,
                'title': l.to_entry.title if l.to_entry else None,
            } for l in entry.outgoing_links],
            'incoming': [{
                'id': str(l.from_entry_id),
                'type': l.link_type,
                'title': l.from_entry.title if l.from_entry else None,
            } for l in entry.incoming_links],
        }
