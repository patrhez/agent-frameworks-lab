# A Go developer's guide to uv and four agent frameworks

Start with [README.md](README.md) to run the lab. This guide explains the tools,
reads the four implementations, and answers the three self-check questions.
All four demos were tested against the same configured DeepSeek model,
`deepseek-flash`, on 2026-10-24. Only weather data is mocked; model calls are real.

## Return-from-away: a 90-minute advanced path

Read this before the original beginner tutorial below. Advanced commands default
to native-framework model doubles and run unattended.

| Time | Read and run | Three symbols to follow |
| --- | --- | --- |
| 0–10 min | Read the filled COMPARISON and state-file distinctions | `ApprovalRequest`, `ToolRuntime`, `execute` |
| 10–25 min | CrewAI beginner -> advanced module -> approve/reject | `execute_crew`, wrapped `book_flight`, `resume` |
| 25–40 min | LangGraph beginner -> conditional graph -> `--stream` | `build_graph`, nested `approval`, `Command(resume=...)` in `drive` |
| 40–55 min | Pydantic beginner -> deferred module -> prepare/resume | `build_agent`, `prepare`, `DeferredToolResults` in `resume` |
| 55–70 min | SDK beginner -> native approval and handoff | `build_agents`, `require_approval`, `RunState.from_json` in `resume` |
| 70–80 min | Run separate prepare/resume processes; inspect SQLite effects | `--phase prepare`, `--phase resume`, `effect_count` |
| 80–90 min | Explain the three interview answers aloud | HITL location, session vs checkpoint, when to keep Go |

Each project's README has a module map. Stable symbols replace fragile line
ranges. Follow `advanced/run.py` -> `shared.cli.execute` -> adapter `prepare` ->
persisted decision -> adapter `resume` -> `ToolRuntime.book`.

### Inspect each boundary

1. Before approval the request is pending, effects are empty, and framework
   history may already contain proposed tool calls.
2. The simulator writes approved/rejected with a reason. JSON scripts match by
   operation ID/tool. The persisted audit count selects the next step.
3. SDK/Pydantic resume native pending tools. LangGraph restores its SQLite graph
   checkpoint and resumes an interrupted approval node. CrewAI recreates a task using a saved application work item.
4. The effect boundary checks policy, payload binding, and approval again.
   Changing city under the same operation ID fails. Local mock receipts deduplicate.
5. Reusing a completed directory returns its saved result. Choose a new directory
   for another operation or another approval mode.

### Recovery is narrower than universal crash safety

Separate-process tests stop at pending approval and reconstruct new framework
instances. CrewAI recovers at a task boundary, not an in-flight stack. LangGraph
restarts its interrupted node, so registration before the interrupt must be idempotent
and booking effects must remain in a separate downstream node. SDK RunState
and Pydantic deferred results explicitly represent pending tool execution.

Rejection is terminal unless scripted all-mode explicitly starts a new attempt.
Timeout immediately rejects. Real approval services still need authenticated
reviewers, trusted storage, deadlines, leases, and downstream idempotency.

### Interview answers grounded in the advanced code

- **Where is HITL?** Before the side effect: a CrewAI tool wrapper, LangGraph
  `interrupt` and conditional routing, Pydantic `requires_approval`, or SDK `needs_approval`. Task-output review is later and
  cannot prevent an already-completed effect. The shared runtime gate remains.
- **Why session is not checkpoint?** History informs the next model; pending
  state identifies waiting work; the effect ledger records committed mock work.
  A real downstream service still needs a stable idempotency key and reconciliation.
- **When keep Go?** Keep your harness when existing identity/policy, cancellation,
  durable workflow coordination, and side-effect semantics outweigh orchestration
  savings. Frameworks help when their contracts/coordination reduce maintained code.

These Python decorators do not provision a VM. Execution isolation belongs to
harness/sandbox infrastructure. MCP is optional and intentionally omitted here.

## 1. Use uv as a project manager

Think of `pyproject.toml` as the dependency declaration, `uv.lock` as the resolved
dependency graph, and `.venv` as the project's isolated Python installation area.
This analogy is useful for Go developers, but a virtual environment also isolates
installed packages: Python does not have Go's compiled-binary dependency model.

| File | Purpose | Commit? |
| --- | --- | --- |
| `pyproject.toml` | Project metadata, Python requirement, direct dependencies | Yes |
| `uv.lock` | Exact dependency resolution | Yes |
| `.python-version` | Interpreter selection for local commands | Yes |
| `.venv/` | Installed interpreter environment and packages | No |
| `.env` | Local application settings and credentials | No |

Use these commands inside one subproject:

```sh
cd langgraph
uv sync                     # Install the locked project environment
uv run main.py              # Sync as needed, then execute inside that environment
uv run main.py "What is the weather in Beijing?"
uv run python --version     # Inspect the project's interpreter
uv tree                     # Inspect the dependency graph
uv pip freeze               # Inspect what is actually installed
```

`uv run` means you normally do not need to activate `.venv` manually. Avoid a bare
`python main.py` unless you deliberately selected the same interpreter.

For a separate scratch experiment, the dependency workflow is:

```sh
uv init --bare --name weather-scratch --python 3.11 weather-scratch
cd weather-scratch
uv python pin 3.11
uv add python-dotenv         # Update declaration, lockfile, and environment
uv add --dev pytest          # Add an optional development dependency
uv remove pytest --dev      # Remove that development dependency
uv lock --upgrade           # Deliberately refresh the resolution
uv sync --locked            # Fail if the lockfile needs to change
```

These examples are instructions, not extra dependencies added to this lab.
`uv pip install` is a lower-level environment operation; use `uv add` when a
dependency should remain declared and reproducible. See the official
[project guide](https://docs.astral.sh/uv/guides/projects/).

### Why four projects?

Each command runs in one directory and uses that directory's environment.
CrewAI resolved `openai==2.54.0`; the other projects resolved `openai==3.37.0`.
That concrete version difference shows why a single shared environment would
introduce an unrelated compatibility exercise. This is a Git monorepo containing
four independent Python projects, rather than a uv workspace.

### Pass credentials through the environment

The beginner demos use `shared.providers.configure_beginner_environment`.
It first loads the root `.env`, preserving inherited environment values. When no
usable provider key is available, it parses only the three literal DeepSeek
assignments from `~/.zshrc`, including assignments without `export`. The same
fallback is used by explicitly gated advanced live runs.

The loader never sources shell configuration or executes substitutions. If values
are computed by shell commands or variable expansion, export them normally:

```sh
export DEEPSEEK_API_KEY DEEPSEEK_API_BASE_URL DEEPSEEK_DEFAULT_MODEL
```

For literal settings already in `~/.zshrc`, no manual export is required. Explicit
environment/root `.env` keys take priority; an explicit usable OpenAI key keeps
its provider selection instead of silently switching to a shell-only DeepSeek key.
The key remains a client credential, never a user message, tool result, log field,
or saved checkpoint. Defaults and placeholders in `.env.example` contain no key.

## 2. Recognize the loop you already know

A minimal harness repeatedly asks the model what to do, executes requested tools,
adds results to conversation state, and stops at a final answer. This Go-shaped
pseudocode names responsibilities rather than depending on a particular Go SDK:

```go
messages := []Message{User(question)}
for turn := 0; turn < maxTurns; turn++ {
    reply := model.Generate(ctx, messages, toolSchemas)
    messages = append(messages, reply.Message)
    if len(reply.ToolCalls) == 0 {
        return reply.Text
    }
    for _, call := range reply.ToolCalls {
        args := validateArguments(call)
        authorize(actor, call.Name, args)
        if needsApproval(call) {
            checkpointAndPause(messages, call)
            return "waiting for approval"
        }
        result := tools.Execute(ctx, call.Name, args)
        messages = append(messages, ToolResult(call.ID, result))
    }
    saveCheckpoint(messages)
}
return "turn budget exhausted"
```

All four frameworks replace substantial parts of this loop. None makes your
authorization rules, tool idempotency, storage choices, or failure semantics
disappear. A model's proposed action and permission to execute it remain separate.

## 3. Read each framework through its building blocks

The following Python blocks are excerpts, not standalone programs. They omit
imports, client configuration, logging, and error checks. The linked `main.py`
files contain the complete executable versions.

### CrewAI: describe roles and assigned work

**Building blocks:** Agent, Task, Crew, Process, Tool. The lab's researcher has
the tool; its writer consumes the research result. A task is an assigned work item;
an agent is the role that performs it. The crew coordinates both.

```python
researcher = Agent(role="Researcher", goal="Fetch weather",
                   backstory="Use tools", tools=[get_weather], llm=llm)
writer = Agent(role="Writer", goal="Explain weather",
               backstory="Write concisely", llm=llm)
research = Task(description="Call get_weather for Shanghai",
                expected_output="Mock weather facts", agent=researcher)
write = Task(description="Explain those facts",
             expected_output="One sentence", agent=writer, context=[research])
result = Crew(agents=[researcher, writer], tasks=[research, write],
              process=Process.sequential).kickoff()
```

Read [crewai/main.py](crewai/main.py). Locate the extra orchestration layer:
research task first, writing task second, with an internal model/tool loop for
the researcher. Role descriptions are prompts, not Go interface implementations.
Splitting this tiny task into two agents is a teaching choice and adds model work.
See the official [quickstart](https://docs.crewai.com/en/quickstart).

### LangGraph: make state transitions explicit

**Building blocks:** StateGraph, state/reducers, nodes, conditional edges, ToolNode,
and a checkpointer. The beginner graph defines the model/tool loop directly;
the advanced graph adds planner and reviewer model roles with approval/rejection branches.

```python
graph = StateGraph(MessagesState)
graph.add_node("model", ask_model)
graph.add_node("tools", ToolNode([get_weather]))
graph.add_edge(START, "model")
graph.add_conditional_edges("model", tools_condition,
                            {"tools": "tools", END: END})
graph.add_edge("tools", "model")
app = graph.compile()
result = app.invoke({"messages": [HumanMessage(content=question)]})
```

Read [langgraph/main.py](langgraph/main.py), then
[advanced/hitl_graph.py](langgraph/advanced/hitl_graph.py). You own the topology and
routing; the runtime executes nodes, applies state reducers, and saves checkpoints.
In advanced, `interrupt(request)` suspends before booking; the simulator writes its
decision and `Command(resume={"approved": True})` resumes the same thread ID.
An approved native resume value alone cannot bypass the separate application ledger.
The interrupted node restarts from its beginning, so side effects belong after the
approval branch, not before `interrupt`. A reviewer summarizes both approve/reject outcomes.
See the official [quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)
and [interrupt guide](https://docs.langchain.com/oss/python/langgraph/interrupts).

### Pydantic AI: make inputs and outputs typed contracts

**Building blocks:** Agent, typed function tool, Pydantic output model, model/provider,
and usage limits. Optional dependencies use `RunContext[Deps]`; this lab instead
demonstrates a structured final result.

```python
class WeatherAnswer(BaseModel):
    city: str
    answer: str
    is_mock: bool

agent = Agent(model, output_type=WeatherAnswer)

@agent.tool_plain
def get_weather(city: str) -> str:
    return f"{city}: sunny, 22 C (mock data)."

result = agent.run_sync(question, usage_limits=UsageLimits(request_limit=6))
print(result.output.answer)
```

Read [pydantic_ai/main.py](pydantic_ai/main.py). Function annotations describe tool
arguments; `WeatherAnswer` describes the validated final object. Pydantic checks
shape and constraints, not whether a claim is true or an action is authorized.
This run uses an output tool to obtain structured data, which is distinct from
the business tool that retrieves weather. See the official
[tools](https://ai.pydantic.dev/tools/) and [output](https://ai.pydantic.dev/output/) guides.

The live DeepSeek test exposed a useful integration boundary: its thinking mode
rejects required/named tool choice. This demo disables thinking for DeepSeek and
disables server-side strict tool definitions while retaining local validation.
That is a provider setting, not a different agent architecture. See the
[DeepSeek API reference](https://api-docs.deepseek.com/api/create-chat-completion/).

### OpenAI Agents SDK: compose an agent around Runner

**Building blocks:** Agent, Runner, function tool, session, guardrail, and optional
handoff. The SDK package can use an OpenAI-compatible Chat Completions model;
using this SDK does not require using an OpenAI-hosted model in this lab.

```python
agent = Agent(
    name="Weather assistant", model=model,
    tools=[get_weather], input_guardrails=[short_input],
)
session = SQLiteSession("weather-lab", ":memory:")
result = await Runner.run(agent, question, session=session, max_turns=6)
print(result.final_output)
```

Read [openai_agents/main.py](openai_agents/main.py). Runner owns execution; Agent
is its configuration. The input guardrail rejects empty/oversized messages before
model execution. Session stores conversation items. A handoff changes the active
agent, its instructions, and tools; it is different from calling a helper and
returning control to a manager. See the official
[runtime guide](https://developers.openai.com/api/docs/guides/agents/running-agents).

Try persistence with the commands in [the project README](openai_agents/README.md).
An in-memory SQLite session disappears when the process exits. A file-backed
session preserves history, but is not by itself a durable tool-execution checkpoint.

## 4. Self-check answers

### Question 1: How do abstraction levels differ, and which JDs/scenarios fit?

This ranking is an interpretation of the APIs used here, not a universal
benchmark. LangGraph exposes topology and state transitions more directly;
CrewAI emphasizes assigned work, while Pydantic AI and the SDK package common agent loops.

| Framework | Relative level in this lab | Main organizing idea | Example JD / scenario fit |
| --- | --- | --- | --- |
| CrewAI | High | Roles, tasks, and coordinated crews | Workflow automation or AI solutions roles; staged research/report pipelines |
| LangGraph | Low to medium; explicit state-machine orchestration | Nodes, reducers, conditional edges, and checkpoints | Agent platform/workflow/backend roles; custom branching, durable approval, and graph recovery |
| Pydantic AI | Medium, close to application code | Typed tools, dependencies, and validated results | Python backend or applied AI roles; schema-driven extraction and business integrations |
| OpenAI Agents SDK | Medium, focused runtime primitives | Runner, tools, handoffs, sessions, guardrails | Agent platform or product integration roles; assistants needing routing and policy attachment points |

If a JD emphasizes Python schemas and service dependencies, inspect Pydantic AI
first. If it emphasizes explicit state transitions or durable approval, inspect LangGraph;
for role/task coordination, inspect CrewAI. If it emphasizes assistant runtime composition, inspect Runner and handoffs.
These are engineering-fit examples, not claims about current hiring demand.

### Question 2: What do they save or hide versus a Go harness?

| Framework | Loop: saves / hides | State: saves / hides | Permissions: saves / hides | HITL: saves / hides |
| --- | --- | --- | --- | --- |
| CrewAI | Schedules tasks and internal tool loops / prompts, intermediate work, and retry details become less visible | Passes task context / what is carried forward depends on task and memory configuration | Provides tools and validation hooks / roles and task guardrails do not enforce resource authorization | Offers task review points / review of a task result is different from approval before each side effect |
| LangGraph | Executes explicit nodes and routes / you still design topology, budgets, and tool policy | Applies reducers and native checkpoints / thread IDs and replay semantics need care | Provides tool nodes and routing hooks / allowlists and approval authority remain app-owned | Native interrupt/Command protocol / app still supplies trusted decisions and handles node restarts |
| Pydantic AI | Executes tools and validates/retries output / graph transitions and validation can add requests | Exposes message history and typed dependencies / dependency objects are not automatically persisted | Validates argument/output shape / valid data can still describe a forbidden action | Supports deferred approval requests/results / the app still stores pending work and routes human decisions |
| Agents SDK | Runner handles tools and handoffs / a turn can contain more than one tool action | Session handles conversation history / history storage differs from resumable execution state | Provides input/output/tool guardrail attachment points / policy and OS/network enforcement remain external | Supports approval interruptions and resumable state / the app owns approver identity, storage, and resume delivery |

The permission column distinguishes validation from authorization. A string field
containing a city is a contract. Deciding which customer may invoke a billing tool
is an authorization rule. A prompt saying “ask permission” is not enforcement.

The advanced demos execute mock booking approvals and recovery. The mechanisms
differ; distinguish the implemented boundaries from optional framework capabilities:

- **CrewAI:** task human review via `human_input=True`. Review timing matters;
  completed-task review is not automatically a pre-tool approval.
  [Human input guide](https://docs.crewai.com/en/learn/human-input-on-execution).
- **LangGraph:** `interrupt` saves a pending node through a checkpointer; resume
  the same thread using `Command`. This is implemented in advanced with SQLite.
  [Interrupt guide](https://docs.langchain.com/oss/python/langgraph/interrupts).
- **Pydantic AI:** deferred tools and approval results separate proposed work
  from approved execution. [Deferred tools guide](https://ai.pydantic.dev/deferred-tools/).
- **Agents SDK:** a function tool can require approval, returning interruptions;
  approve/reject through run state and resume. [Guardrails and approvals](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals).

#### Persistence and checkpoints need separate questions

Ask what happens if the process dies after a tool charges a card but before its
result is saved. Replaying conversation history could charge again. You need a
stable operation ID, an idempotent tool boundary, and a record of completed work.
Neither a SQLite history file nor a JSON message dump guarantees exactly-once
side effects. Inspect the framework's durable execution integration before relying
on it; otherwise keep that coordination in your service or workflow engine.

### Question 3: When should you keep a handwritten harness?

Keep your Go harness when its explicit control is valuable enough to justify
maintaining it. Strong reasons include:

1. **Existing service integration:** Go identity, middleware, cancellation,
   deployment, and observability already form the right execution environment.
2. **Strict action policy:** every tool must pass your authorization and approval
   system with an auditable order of checks and side effects.
3. **Durable execution requirements:** you need to own checkpoints, replay,
   idempotency, compensation, and recovery across human delays or process crashes.
4. **A small stable workflow:** one model and a few tools need little orchestration;
   a framework migration would add more dependency/API surface than it removes.
5. **Precise protocol or performance control:** you need custom transports, budgets,
   concurrency, or provider behavior that the framework's defaults obscure.

A framework is useful when repeated orchestration, validation, coordination, or
session handling is consuming more engineering effort than the abstraction costs.
You can also adopt only part of one: typed output validation does not require
outsourcing your entire policy or persistence layer. Decide by tracing the actual
failure and recovery paths, not by counting how few lines the happy path uses.

## 5. Experiments to make the distinctions concrete

1. Run every demo for a second city and trace the same four log markers.
2. In CrewAI, identify exactly which task result the writer sees.
3. In LangGraph, inspect approved/rejected edges and confirm the interrupt node restarts on resume.
4. In Pydantic AI, add an output field and inspect the contract and validation.
5. In Agents SDK, persist two turns; then send a message longer than 500 characters
   and observe that the blocking guardrail prevents a tool call.
6. For each framework, sketch how you would approve a side effect and recover
   after a crash. Explain [COMPARISON.md](COMPARISON.md) in your own words.

The comparison is now filled. Connect each cell to an API call and test result
rather than memorizing the table.
