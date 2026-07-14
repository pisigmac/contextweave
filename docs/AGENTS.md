# Agents

ContextWeave is designed for AI agent consumption.

## Agent Protocol

1. **Read workspace status** — `GET /api/v1/workspace/status`
2. **Query relevant entries** — `POST /api/v1/query` with `{"query": "Decision WHERE outcome=Pending"}`
3. **Follow blocking chains** — `GET /api/v1/entries/{id}/blocking-chain`
4. **Get context** — `POST /api/v1/search` for full-text search

## Why Agents Love ContextWeave

| Feature | Agent Benefit |
|---------|--------------|
| Typed headers | Know entry semantics instantly |
| Outcome field | Know if decision is settled |
| Status field | Know task state |
| Blocked by | Understand dependencies |
| Cross-file refs | Navigate across projects |

## Example Agent Prompt

```
You are managing the Payment Gateway project.

Current decisions: weave query "Decision WHERE outcome=Pending"
Blocked tasks: weave query "Task WHERE status=Blocked"
Blocking chain: weave chain <task_id>
```
