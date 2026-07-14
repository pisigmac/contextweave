"""Graph engine for managing entry relationships and cross-file links."""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from services.shared.models import Entry, EntryLink, WeaveFile


class GraphEngine:
    """Manage the knowledge graph of linked entries."""

    def __init__(self, db: Session):
        self.db = db

    def create_link(self, from_entry_id: str, to_entry_id: str,
                    link_type: str = "references") -> Optional[Dict[str, Any]]:
        """Create a link between two entries."""
        # IDs are stored as strings
        from_id_str = str(from_entry_id)
        to_id_str = str(to_entry_id)

        # Check entries exist
        from_entry = self.db.query(Entry).filter(Entry.id == from_id_str).first()
        to_entry = self.db.query(Entry).filter(Entry.id == to_id_str).first()

        if not from_entry or not to_entry:
            return None

        link = EntryLink(
            from_entry_id=from_id_str,
            to_entry_id=to_id_str,
            link_type=link_type,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)

        return link.to_dict()

    def resolve_references(self, weave_file_id: str) -> List[Dict[str, Any]]:
        """Resolve implicit references in a weave file's entries."""
        entries = self.db.query(Entry).filter(
            Entry.weave_file_id == weave_file_id
        ).all()

        resolved = []
        for entry in entries:
            if entry.source_ref:
                # Try to find referenced entry
                ref_entry = self._find_referenced_entry(entry.source_ref, exclude_id=str(entry.id))
                if ref_entry:
                    resolved.append({
                        'from_entry': str(entry.id),
                        'from_title': entry.title,
                        'to_entry': str(ref_entry.id),
                        'to_title': ref_entry.title,
                        'reference': entry.source_ref,
                    })

                    # Auto-create link if not exists
                    existing = self.db.query(EntryLink).filter(
                        EntryLink.from_entry_id == entry.id,
                        EntryLink.to_entry_id == ref_entry.id
                    ).first()

                    if not existing:
                        link = EntryLink(
                            from_entry_id=entry.id,
                            to_entry_id=ref_entry.id,
                            link_type="references",
                        )
                        self.db.add(link)

        if resolved:
            self.db.commit()

        return resolved

    def _find_referenced_entry(self, source_ref: str, exclude_id: str = None) -> Optional[Entry]:
        """Find an entry by its source reference string."""
        # Try matching by title first (most common)
        query = self.db.query(Entry).filter(Entry.title.ilike(f"%{source_ref}%"))
        if exclude_id:
            query = query.filter(Entry.id != exclude_id)
        entry = query.first()
        if entry:
            return entry

        # Try matching by source_ref field
        entry = self.db.query(Entry).filter(Entry.source_ref == source_ref).first()
        if entry and (not exclude_id or entry.id != exclude_id):
            return entry

        # Try parsing as #Type-N format
        if '#' in source_ref:
            parts = source_ref.replace('#', '').split('-')
            if len(parts) == 2:
                entry_type, num = parts[0], parts[1]
                entries = self.db.query(Entry).filter(
                    Entry.entry_type.ilike(entry_type)
                ).order_by(Entry.created_at).all()
                try:
                    idx = int(num) - 1
                    if 0 <= idx < len(entries):
                        return entries[idx]
                except ValueError:
                    pass

        return None

    def get_workspace_graph(self) -> Dict[str, Any]:
        """Get the entire workspace graph."""
        files = self.db.query(WeaveFile).all()
        links = self.db.query(EntryLink).all()

        nodes = []
        for f in files:
            for e in f.entries:
                nodes.append({
                    'id': str(e.id),
                    'type': e.entry_type,
                    'title': e.title,
                    'file': f.file_path,
                    'project': f.project_name,
                })

        edges = []
        for l in links:
            edges.append({
                'from': str(l.from_entry_id),
                'to': str(l.to_entry_id),
                'type': l.link_type,
            })

        return {
            'nodes': nodes,
            'edges': edges,
            'node_count': len(nodes),
            'edge_count': len(edges),
        }

    def get_blocking_chain(self, entry_id: str) -> List[Dict[str, Any]]:
        """Get the chain of blockers for an entry."""
        chain = []
        visited = set()

        current_id = entry_id
        while current_id and current_id not in visited:
            visited.add(current_id)

            entry = self.db.query(Entry).filter(Entry.id == current_id).first()
            if not entry:
                break

            chain.append({
                'id': str(entry.id),
                'title': entry.title,
                'type': entry.entry_type,
                'status': entry.status,
                'blocked_by': entry.source_ref,
            })

            # Find next in chain via source_ref or links
            if entry.source_ref:
                ref = self._find_referenced_entry(entry.source_ref, exclude_id=current_id)
                if ref:
                    current_id = str(ref.id)
                    continue

            # Try via explicit links
            incoming = self.db.query(EntryLink).filter(
                EntryLink.to_entry_id == current_id,
                EntryLink.link_type.in_(['blocks', 'references'])
            ).first()

            if incoming:
                current_id = str(incoming.from_entry_id)
            else:
                break

        return chain

    def delete_link(self, link_id: str) -> bool:
        """Delete a link."""
        link = self.db.query(EntryLink).filter(EntryLink.id == link_id).first()
        if link:
            self.db.delete(link)
            self.db.commit()
            return True
        return False
