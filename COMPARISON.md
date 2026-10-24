# Agent framework comparison

Levels describe the surfaces used here, not benchmark rankings. Advanced entries mock
only the model provider by default; native loops, tools, and state APIs execute.

| Framework | Abstraction level | Who controls the loop | Where state lives | Permissions / guardrails | Persistence | HITL | Suitable JD / scenarios | vs handwritten Go harness (saves / hides) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CrewAI | High: roles/tasks/crews | Crew task scheduler and agent loop | Task output and application work item | Shared allowlist + pre-tool wrapper; task review is later | crew-session.json + work-item checkpoint.json + approvals.sqlite | Simulator gates tool; task-boundary replay | Workflow/AI solutions; research/report automation | Saves role/task orchestration; hides prompt/loop details; app owns policy/recovery |
| LangChain / LangGraph | Medium create_agent factory; explicit advanced workflow | create_agent owns the basic loop; advanced graph owns custom approval routes | Beginner thread messages with InMemorySaver; advanced graph task and thread ID | Native interrupt plus shared allowlist, payload binding and pre-effect ledger check | Beginner in-memory history; advanced graph.sqlite checkpoints, session.json view, approvals.sqlite ledger | Advanced interrupt(request) -> simulator decision -> Command(resume=...) on the same thread | Agent platform/workflow/backend; custom routing and persistent approval | Saves the ordinary loop through create_agent; custom advanced routes remain explicit; app owns authorization and downstream idempotency |
| Pydantic AI | Medium, typed application code | Agent graph, tools and validation retries | Typed message history, deps, deferred tool-call ID | Contracts + application allowlist and effect gate | messages.json + deferred checkpoint.json + approvals.sqlite | requires_approval -> DeferredToolRequests -> DeferredToolResults | Python backend/applied AI; typed business integration | Saves schemas/validation/deferred protocol; hides graph turns/retries; app persists decisions |
| OpenAI Agents SDK | Medium, runtime primitives | Runner + Router-to-Booking handoff | SQLiteSession history + native RunState | Input/output guardrails, needs_approval, shared policy | session.sqlite + native checkpoint.json + approvals.sqlite | interruptions -> approve/reject -> serialized resume | Agent platform/product; assistants, routing and approval | Saves handoff/session/interruption plumbing; hides internal state handling; app owns identity and idempotency |

## Capability evidence

| Capability | CrewAI | LangGraph | Pydantic AI | Agents SDK |
| --- | --- | --- | --- | --- |
| Pre-tool gate | Custom native tool wrapper | Native interrupt and policy-checked branch | Native deferred approval | Native needs_approval |
| Persistent recovery | Application task replay | SqliteSaver + same thread ID + Command | Message restore + deferred IDs | RunState JSON restore |
| Nontrivial orchestration | Flow/hierarchy documented, not implemented | Planner/reviewer roles, conditional approve/reject branches | Deferred-tool orchestration, one Agent | Executed two-agent handoff |
| Streaming | Not implemented | Native graph updates including interrupts | Native graph-node events, not tokens | Not implemented in this adapter |
| Observability | Structured logs; optional native tracing | Structured logs + events | Structured logs + graph events | Structured logs; optional native tracing |
| Sandbox / MCP | No VM / omitted | No VM / omitted | No VM / omitted | No VM / omitted |

## Self-check questions

1. How do abstraction levels differ, and which JD/scenarios fit each?
2. Compared with a Go harness, what is saved or hidden in loop, state, permissions, and HITL?
3. When should you keep a handwritten harness?

Answer drafts: [GUIDE.md](GUIDE.md#4-self-check-answers). The advanced reading path
adds concrete answers about pre-tool approval, history versus checkpoint, and local
mock receipts versus external idempotency.

## Dependency injection in the running demos

| Framework | Per-run injection | Model-visible tool arguments |
| --- | --- | --- |
| CrewAI | Tool instance `deps` field, excluded from serialization | city only |
| LangChain / LangGraph | context_schema + injected ToolRuntime; Runtime for advanced nodes | city only |
| Pydantic AI | deps_type + RunContext + @agent.tool; advanced keeps ToolRuntime deps | city only |
| Agents SDK | Runner context + RunContextWrapper, rebuilt on checkpoint restore | city only |

All services are mock/in-memory and log `[deps.weather]`. Dependency substitution
is tested without provider keys; no weather HTTP endpoint is contacted.
