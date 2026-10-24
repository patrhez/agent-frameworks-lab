# Shared unattended harness

| Module | Responsibility |
| --- | --- |
| `hitl.py` | Immutable ApprovalRequest/Decision, automatic and scripted approvers |
| `dependencies.py` | Per-run AppDeps and in-memory weather/cache; no HTTP |
| `runtime.py` | Allowlist, operation payload binding, SQLite decision/effect boundary |
| `cli.py` | Finite prepare/decide/resume lifecycle and terminal replay |
| `storage.py` | Atomic JSON checkpoint replacement |
| `providers.py` | Environment/.env/literal zshrc fallback; live gate; no credential serialization |
| `tools_mock.py` | Low/high-risk mock definitions; no external side effects |
| `logging_util.py` | Structured boundary logs and optional LAB_TRACE diagnostics |
| `testing/contracts.py` | Cross-framework behavioral tests in independent environments |

## Script schema

```json
{"steps": [
  {"operation_id": "*", "tool_name": "book_flight", "status": "rejected", "reason": "Review"},
  {"operation_id": "*", "tool_name": "book_flight", "status": "approved", "reason": "New attempt"}
]}
```

Omitted match fields mean `*`. Matching steps are selected using the persisted
number of decisions for that operation. A missing/exhausted script rejects.
`status: timeout` immediately produces a rejection; no wall-clock wait is needed.
Low-risk requests pass automatically. All-mode retries only when another matching
step exists, with a finite ten-attempt budget. Prepare/resume mode performs one
decision; a terminal rejection stays terminal when the directory is reused.

## State boundary

Approvals bind operation ID, tool, actual validated arguments, risk, and agent.
The ledger rejects reuse of an operation ID with different arguments or agent.
Only the application writes decisions; a model response cannot authorize itself.
The mock receipt and its local effect record commit in one SQLite transaction.
This is not a promise of exactly-once execution at an external API boundary.

Checkpoints are trusted local files owned by one controller process. No VM,
distributed coordination, authenticated approval service, or MCP server is included.
