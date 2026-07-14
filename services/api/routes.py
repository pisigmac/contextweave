"""FastAPI routes for ContextWeave API."""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.shared.models import get_db, WeaveFile, Entry, Tag, EntryLink, init_db
from services.parser.parser import WeaveParser, ParsedWeaveFile
from services.query.engine import QueryEngine
from services.graph.engine import GraphEngine
from services.sync.watcher import WeaveSyncService

router = APIRouter()


# Pydantic schemas
class EntryCreate(BaseModel):
    entry_type: str = Field(..., min_length=2, max_length=50)
    title: str = Field(..., min_length=3, max_length=500)
    content: str = Field(..., min_length=1)
    tags: List[str] = Field(default_factory=list)
    outcome: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    source_ref: Optional[str] = None


class WeaveFileCreate(BaseModel):
    file_path: str
    project_name: str
    status: str = "active"
    entries: List[EntryCreate] = Field(default_factory=list)


class LinkCreate(BaseModel):
    from_entry_id: str
    to_entry_id: str
    link_type: str = "references"


class QueryRequest(BaseModel):
    query: str
    limit: int = 50


class SearchRequest(BaseModel):
    query: str
    limit: int = 50


# WeaveFile routes
@router.get("/files", response_model=List[dict])
def list_files(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all weave files in workspace."""
    query = db.query(WeaveFile)
    if status:
        query = query.filter(WeaveFile.status == status)
    files = query.order_by(WeaveFile.updated_at.desc()).offset(offset).limit(limit).all()
    return [f.to_dict() for f in files]


@router.get("/files/{file_id}", response_model=dict)
def get_file(file_id: str, db: Session = Depends(get_db)):
    """Get a weave file with all its entries."""
    try:
        uuid_obj = str(UUID(file_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    file = db.query(WeaveFile).filter(WeaveFile.id == uuid_obj).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    result = file.to_dict()
    result['entries'] = [e.to_dict() for e in file.entries]
    return result


@router.post("/files", response_model=dict, status_code=201)
def create_file(data: WeaveFileCreate, db: Session = Depends(get_db)):
    """Create a weave file with entries."""
    weave_file = WeaveFile(
        file_path=data.file_path,
        project_name=data.project_name,
        status=data.status,
    )
    db.add(weave_file)
    db.flush()

    for entry_data in data.entries:
        entry = Entry(
            weave_file_id=weave_file.id,
            entry_type=entry_data.entry_type,
            title=entry_data.title,
            content=entry_data.content,
            outcome=entry_data.outcome,
            scope=entry_data.scope,
            status=entry_data.status,
            owner=entry_data.owner,
            source_ref=entry_data.source_ref,
        )
        db.add(entry)
        db.flush()

        for tag_name in entry_data.tags:
            tag = db.query(Tag).filter(Tag.name == tag_name.lower()).first()
            if not tag:
                tag = Tag(name=tag_name.lower())
                db.add(tag)
                db.flush()
            entry.tags.append(tag)

    db.commit()
    db.refresh(weave_file)
    return weave_file.to_dict()


@router.delete("/files/{file_id}", status_code=204)
def delete_file(file_id: str, db: Session = Depends(get_db)):
    """Delete a weave file and all its entries."""
    try:
        uuid_obj = str(UUID(file_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    file = db.query(WeaveFile).filter(WeaveFile.id == uuid_obj).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    db.delete(file)
    db.commit()
    return None


# Entry routes
@router.get("/entries", response_model=List[dict])
def list_entries(
    entry_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List entries with filters."""
    query = db.query(Entry)

    if entry_type:
        query = query.filter(Entry.entry_type.ilike(entry_type))
    if status:
        query = query.filter(Entry.status.ilike(status))
    if outcome:
        query = query.filter(Entry.outcome.ilike(outcome))
    if tag:
        query = query.join(Entry.tags).filter(Tag.name == tag.lower())

    entries = query.order_by(Entry.updated_at.desc()).offset(offset).limit(limit).all()
    return [e.to_dict() for e in entries]


@router.get("/entries/{entry_id}", response_model=dict)
def get_entry(entry_id: str, db: Session = Depends(get_db)):
    """Get a single entry."""
    try:
        uuid_obj = str(UUID(entry_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")

    entry = db.query(Entry).filter(Entry.id == uuid_obj).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    return entry.to_dict()


@router.patch("/entries/{entry_id}", response_model=dict)
def update_entry(entry_id: str, data: EntryCreate, db: Session = Depends(get_db)):
    """Update an entry."""
    try:
        uuid_obj = str(UUID(entry_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")

    entry = db.query(Entry).filter(Entry.id == uuid_obj).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    entry.entry_type = data.entry_type
    entry.title = data.title
    entry.content = data.content
    entry.outcome = data.outcome
    entry.scope = data.scope
    entry.status = data.status
    entry.owner = data.owner
    entry.source_ref = data.source_ref

    # Update tags
    entry.tags.clear()
    for tag_name in data.tags:
        tag = db.query(Tag).filter(Tag.name == tag_name.lower()).first()
        if not tag:
            tag = Tag(name=tag_name.lower())
            db.add(tag)
            db.flush()
        entry.tags.append(tag)

    db.commit()
    db.refresh(entry)
    return entry.to_dict()


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: str, db: Session = Depends(get_db)):
    """Delete an entry."""
    try:
        uuid_obj = str(UUID(entry_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")

    entry = db.query(Entry).filter(Entry.id == uuid_obj).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    db.delete(entry)
    db.commit()
    return None


# Query routes
@router.post("/query", response_model=List[dict])
def query_entries(data: QueryRequest, db: Session = Depends(get_db)):
    """Execute a weave query."""
    engine = QueryEngine(db)
    return engine.query(data.query, limit=data.limit)


# Search routes
@router.post("/search", response_model=List[dict])
def search_entries(data: SearchRequest, db: Session = Depends(get_db)):
    """Full-text search entries."""
    engine = QueryEngine(db)
    return engine.search(data.query, limit=data.limit)


# Graph routes
@router.post("/links", response_model=dict, status_code=201)
def create_link(data: LinkCreate, db: Session = Depends(get_db)):
    """Create a link between entries."""
    engine = GraphEngine(db)
    result = engine.create_link(data.from_entry_id, data.to_entry_id, data.link_type)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create link")
    return result


@router.get("/entries/{entry_id}/links")
def get_entry_links(entry_id: str, db: Session = Depends(get_db)):
    """Get links for an entry."""
    try:
        uuid_obj = str(UUID(entry_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entry ID")

    entry = db.query(Entry).filter(Entry.id == uuid_obj).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    return {
        'outgoing': [l.to_dict() for l in entry.outgoing_links],
        'incoming': [l.to_dict() for l in entry.incoming_links],
    }


@router.get("/entries/{entry_id}/blocking-chain")
def get_blocking_chain(entry_id: str, db: Session = Depends(get_db)):
    """Get the blocking chain for an entry."""
    engine = GraphEngine(db)
    return engine.get_blocking_chain(entry_id)


@router.get("/graph")
def get_workspace_graph(db: Session = Depends(get_db)):
    """Get the entire workspace graph."""
    engine = GraphEngine(db)
    return engine.get_workspace_graph()


# Workspace routes
@router.get("/workspace/status")
def workspace_status(db: Session = Depends(get_db)):
    """Get workspace overview."""
    engine = QueryEngine(db)
    return engine.workspace_status()


# Sync routes
@router.post("/sync")
def sync_workspace(path: Optional[str] = None, db: Session = Depends(get_db)):
    """Manually trigger workspace sync."""
    from services.shared.config import config
    watch_dirs = [path] if path else [str(config.workspace_dir)]
    service = WeaveSyncService(watch_dirs=watch_dirs)
    count = service.initial_sync()
    return {"synced_files": count, "directories": watch_dirs}


# Tags
@router.get("/tags")
def list_tags(db: Session = Depends(get_db)):
    """List all tags with counts."""
    tags = db.query(Tag).all()
    return [{"name": t.name, "count": len(t.entries)} for t in tags]
