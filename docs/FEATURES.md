# Features

## Core Features

### Typed Headers
- `# Decision:`, `# Task:`, `# Requirement:`, `# Session:`, `# Note:`, `# Bug:`, `# Feature:`
- Extensible type system
- Human-writeable, machine-parseable

### Implicit Links
- `Blocked by: #Decision-3 in ../auth-service`
- Auto-resolved to database relationships
- Bidirectional link tracking

### Query Engine
- Shorthand: `Decision WHERE outcome=revisit`
- Full SELECT syntax support
- LIKE, IN, =, != operators

### Full-Text Search
- SQLite FTS5 virtual table
- Sub-second search across workspace
- Tag-based filtering

### Knowledge Graph
- Entry-to-entry relationships
- Blocking chain analysis
- Workspace-wide graph view

### File System Sync
- Watch directories for `.weave.md` files
- Auto-import on create/modify/delete
- Hash-based change detection

### Cross-Project
- Workspace-level queries across all projects
- Cross-file reference resolution
- Unified knowledge graph
