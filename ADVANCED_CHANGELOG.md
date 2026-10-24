# Advanced harness upgrade

## Implementation plan (recorded before implementation)

1. Preserve beginner entry points; add shared approvers, policy, structured logs, and a mock effect ledger.
2. Add CrewAI pre-tool wrappers, AutoGen Team/state APIs, Pydantic deferred tools, and SDK approval/handoff/RunState.
3. Separate histories and effect/approval checkpoints; support separate prepare/resume processes.
4. Default to native deterministic provider doubles; opt into paid smoke tests with RUN_LIVE=1.
5. Fill the comparison, extend the guide, scan secrets, commit, and push without rewriting history.

## What changed

- Shared typed requests/decisions, automatic and JSON-scripted approvers, allowlist, payload binding, and SQLite audit/effect tables.
- A bounded unattended CLI with persistent script cursor, explicit retry attempts after rejection, and terminal-result replay.
- Four independent adapters use real framework dispatch with model-provider doubles by default.
- AutoGen native Team event streaming; Pydantic native graph-node event streaming.
- Offline structured logs and LAB_TRACE diagnostics; optional FRAMEWORK_TRACE native exporters. No default OTEL_SDK_DISABLED.
- Tests cover pre-effect approval, rejection, timeouts, persistent replay, separate-process recovery, and beginner imports.

## Actual API versions

| Project | Framework | Client | Test runner |
| --- | --- | --- | --- |
| CrewAI | crewai / crewai-core / crewai-cli 1.15.30 | openai 2.54.0 | pytest 9.1.1 |
| AutoGen | autogen-agentchat / autogen-core / autogen-ext 0.7.5 | openai 3.37.0 | pytest 9.1.1 |
| Pydantic AI | pydantic-ai / pydantic-ai-slim 2.61.0 | openai 3.37.0 | pytest 9.1.1 |
| Agents SDK | openai-agents 0.24.0 | openai 3.37.0 | pytest 9.1.1 |

## Deliberate boundaries

- CrewAI resumes an application-owned work item at a task boundary, not an in-flight Crew stack. Its human_input reviews task output; our wrapper instead gates the tool before effects.
- AutoGen restores Team state and sends a new feedback message; it does not suspend a tool frame or wait for UserProxy keyboard input.
- Pydantic restores typed messages and pending IDs. SDK restores native RunState including the active agent after an executed handoff.
- Checkpoints are trusted local harness storage, not authenticated client submissions. One controller owns a state directory; distributed leases and signed approval decisions are out of scope.
- SQLite deduplicates local mock receipts. External services still need downstream idempotency/reconciliation; history alone does not ensure exactly-once effects.
- No real bookings/transfers, VM sandbox, or production identity service. MCP is optional and intentionally omitted.

## Verification

- Final default suite: **42 passed, 4 skipped** across the four isolated projects.
  The skips are the opt-in live smokes. CrewAI emits upstream deprecation warnings.
- All four advanced live smoke tests passed against the configured DeepSeek model.
  The key was read through an external process-only credential loader, never printed
  or copied into this repository.
- Separate-process prepare/resume and terminal replay passed for all four adapters.
- Regression tests cover AutoGen user-sentinel scoping and SDK input/output guardrails.
- Live integration fixes: CrewAI resume explicitly distinguishes current policy from
  historical pending output; AutoGen termination inspects reviewer final content and
  the actual ledger outcome; SDK uses explicit tool choice and disables DeepSeek
  thinking where named/required tool selection is needed.

## Acceptance checklist before publication

- [x] Four beginner entry points import and preserve the original business demos.
- [x] All four advanced auto_approve entries execute native framework paths.
- [x] High-risk effects stay blocked until approval; reject/timeout paths create no effect.
- [x] All four adapters persist pending work and resume in a new process.
- [x] SDK executes a native handoff, interruption, approve/reject, and RunState restore.
- [x] AutoGen uses a Team and explicit, bounded termination.
- [x] Pydantic retains typed output and native deferred approval; DI injects the runtime.
- [x] Conversation/session and approval/effect records are separate.
- [x] AutoGen/Pydantic native event streams and structured observability are implemented.
- [x] COMPARISON is filled; GUIDE has the 90-minute path and interview answers.
- [x] The root test runner passes without a key; live tests require RUN_LIVE=1.
- [x] English-only, Python syntax, no input(), local links, and secret-pattern checks pass.

Publication follows the user's requested concise commit message. The final response
provides the verified commit URL after a successful non-force push.

## Follow-up: direct DeepSeek loading for beginner demos

- Fixed the gap between shell-local assignments and child-process environments:
  all beginner entry points now call the shared provider loader at runtime.
- The loader reads only literal DeepSeek key/base/model assignments from `~/.zshrc`
  as a fallback, without executing shell configuration or logging values.
- Explicit environment/.env provider settings retain priority. Advanced mock
  runs remain independent of local credentials; gated live paths share the fallback.
- All four beginner demos were run for Beijing with inherited provider variables
  removed and completed real DeepSeek model/tool calls successfully.
- Follow-up regression suite: **49 passed, 4 skipped**; seven provider-loading tests cover literal assignments, precedence, placeholders, missing files, and non-execution of shell commands.
