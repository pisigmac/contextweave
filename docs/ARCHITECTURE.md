# Architecture

## Service-Oriented Design

```
Client → API Gateway → Services → SQLite
```

| Service | Responsibility | State |
|---------|---------------|-------|
| Parser | Parse `.weave.md` files | Stateless |
| Query Engine | Execute queries | Stateless |
| Graph Engine | Manage relationships | Stateless |
| Sync Service | File system watcher | Stateful |
| API | HTTP interface | Stateless |

## Data Flow

1. `.weave.md` → Parser → ParsedWeaveFile
2. Sync Service → Database + FTS5 index
3. Query Engine → SQL → Results
4. Graph Engine → Link resolution → Graph

## Database Schema

- `weave_files` — Project files
- `entries` — Typed entries (Decision, Task, etc.)
- `tags` — Entry tags
- `entry_tags` — Many-to-many junction
- `entry_links` — Entry relationships
- `entry_search` — FTS5 virtual table
