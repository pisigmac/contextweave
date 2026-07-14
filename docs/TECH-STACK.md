# Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Web | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (WAL mode) |
| Search | SQLite FTS5 |
| CLI | Click + Rich |
| File Watch | Watchdog |
| Test | pytest + pytest-cov |

## Extensibility

- SQLite → PostgreSQL: Change connection string
- Add entry types: Extend VALID_TYPES in parser
- Add query operators: Extend VALID_OPS in query engine
