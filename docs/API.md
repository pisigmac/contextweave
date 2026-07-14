# API Documentation

## Base URL
`http://localhost:8000/api/v1`

## Endpoints

### Weave Files
- `GET /files` — List files
- `GET /files/{id}` — Get file with entries
- `POST /files` — Create file
- `DELETE /files/{id}` — Delete file

### Entries
- `GET /entries` — List entries (filter by type, status, outcome, tag)
- `GET /entries/{id}` — Get entry
- `PATCH /entries/{id}` — Update entry
- `DELETE /entries/{id}` — Delete entry

### Query
- `POST /query` — Execute weave query
- `POST /search` — Full-text search

### Graph
- `POST /links` — Create link
- `GET /entries/{id}/links` — Get entry links
- `GET /entries/{id}/blocking-chain` — Get blocking chain
- `GET /graph` — Workspace graph

### Workspace
- `GET /workspace/status` — Workspace overview
- `POST /sync` — Trigger sync
- `GET /tags` — List tags
