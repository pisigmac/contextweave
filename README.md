# ContextWeave

**Workspace-level knowledge graph with typed headers and cross-file queries for the AI era.**

ContextWeave solves the problem every developer with multiple projects faces: your READMEs don't talk to each other. Your API docs reference auth patterns in another repo. Your todos have tasks blocked by decisions in a third. The information exists — it's just trapped in silos.

## The Format: `.weave.md`

```markdown
# Project: Payment Gateway
# Status: Build

# Decision: Use Postgres
Because: ACID compliance and complex queries
Risk: Operational overhead
Outcome: Pending
Tags: database, architecture

# Task: Set up schema
Status: In Progress
Owner: @user

# Requirement: Handle 1000 req/s
Scope: Active
Blocked by: #Decision-3 in ../event-bus.weave.md
```

A standard markdown renderer shows this perfectly. ContextWeave sees a queryable knowledge graph.

## Quick Start

```bash
# Install
pip install -e .

# Initialize workspace
weave init "Payment Gateway"

# Parse and view
weave parse ./payment-gateway.weave.md

# Query across all projects
weave query "Decision WHERE outcome=revisit"
weave query "Task WHERE status='In Progress'"

# Full-text search
weave search "Postgres"

# View workspace status
weave status

# View knowledge graph
weave graph

# Sync directory
weave sync ./projects --watch
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    CLI      │────▶│  API        │────▶│  Parser     │
│  (Click)    │     │  (FastAPI)  │     │  (Typed     │
└─────────────┘     └─────────────┘     │   Headers)  │
                           │              └─────────────┘
                           ▼                    │
                    ┌─────────────┐     ┌──────▼──────┐
                    │   Query     │     │   Sync      │
                    │  Engine     │     │  (Watchdog) │
                    │ (FTS5/SQL)  │     └──────┬──────┘
                    └──────┬──────┘            │
                           │            ┌──────▼──────┐
                           └───────────▶│   SQLite    │
                                        │  (WAL mode) │
                                        └─────────────┘
```

## Services

| Service | Purpose |
|---------|---------|
| Parser | Parse `# Type: Title` headers and inline fields |
| Query Engine | Execute queries like `Decision WHERE outcome=revisit` |
| Graph Engine | Manage cross-file links and blocking chains |
| Sync Service | Watch directories for `.weave.md` changes |
| API | FastAPI REST interface |

## Query Language

```bash
# Shorthand
weave query "Decision WHERE outcome=revisit"
weave query "Task WHERE status='In Progress'"
weave query "Requirement WHERE scope=Active"

# Complex queries
weave query "Decision WHERE outcome=Pending AND tags=database"
```

## Commands

| Command | Description |
|---------|-------------|
| `weave init <project>` | Create a new `.weave.md` file |
| `weave parse <file>` | Display parsed structure |
| `weave query <query>` | Query the workspace |
| `weave search <query>` | Full-text search |
| `weave status` | Workspace overview |
| `weave show <id>` | Show entry details |
| `weave chain <id>` | Show blocking chain |
| `weave graph` | Knowledge graph summary |
| `weave link <from> <to>` | Link entries |
| `weave sync <dir>` | Sync directory |
| `weave validate <file>` | Validate `.weave.md` |
| `weave projects` | List all projects |

## License

MIT
