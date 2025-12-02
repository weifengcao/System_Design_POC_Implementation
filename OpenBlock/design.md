# OpenBlock System Design

## 1. Problem Statement
CLI developers need a repeatable way to turn ideas into working code without constantly juggling planning, execution, and validation themselves. Existing AI pair-programming tools focus on in-editor assistance, but there is no open-source, automation-friendly agent framework that can ingest a goal, lay out a plan, run shell commands, and summarize results. OpenBlock provides an extensible agent pipeline purpose-built for CLI-driven code projects.

## 2. Objectives
- **Declarative Goals**: Accept a simple YAML/JSON spec describing the desired outcome.
- **Agent Pipeline**: Chain Planner → Executor → Reviewer stages with clear contracts.
- **CLI Native**: Single command (`openblock run plan.yaml`) to execute workflows locally or in CI.
- **Extensible**: Drop-in custom agents, new skills (e.g., Git ops, test runners), and tracing hooks.
- **Observable**: Persist run metadata & logs for auditing and debugging.

## 3. Architecture Overview

```
+---------------------------+
| openblock CLI             |
|  - parses plan            |
|  - orchestrates pipeline  |
+------------+--------------+
             |
             v
+---------------------------+
| Pipeline                  |
|  Planner   Executor   Reviewer  (default agents) |
+--------+----------+------------+
         |          |
  Skills Providers (Shell, Git, Test) -- can be extended
```

### Components
1. **Plan File**: YAML describing project metadata, environment hints, and ordered tasks.
2. **Planner Agent**: Generates a concrete step list per task (e.g., derive TODOs from commands).
3. **Executor Agent**: Runs commands/skills, captures stdout/stderr, emits structured results.
4. **Reviewer Agent**: Evaluates execution output, highlights failures, and suggests follow-ups.
5. **Run Recorder**: Saves combined log + metadata into `.openblock/logs/{timestamp}.json`.

## 4. Data Model

```yaml
project:
  name: "My CLI experiment"
  goal: "Bootstrap a FastAPI server"
environment:
  python: "3.11"
tasks:
  - name: "init"
    description: "Create virtualenv and install deps"
    commands:
      - "python -m venv .venv"
      - ". .venv/bin/activate && pip install fastapi uvicorn"
```

Internally each task becomes:

```python
Task:
  name: str
  description: str
  commands: list[str]
  metadata: dict[str, Any]
```

Execution results:

```python
CommandResult:
  command: str
  exit_code: int
  stdout: str
  stderr: str
```

## 5. Execution Flow
1. CLI loads plan into `ProjectConfig`.
2. `PipelineRunner` instantiates agents (default or custom).
3. For each task:
    - Planner outputs derived steps.
    - Executor executes commands (supports dry-run).
    - Reviewer inspects `CommandResult`s and emits verdict string + severity.
4. Run Recorder persist summary JSON, optionally streaming w/ Rich.

## 6. Extensibility
- Agents registered through entry points (`openblock.agents` group) or config file.
- Skills (helpers for Git, tests, scaffolding) exposed via `SkillRegistry`.
- Observability hooks emit structured events to STDOUT or file.

## 7. AI Coding Agent Extension

To support a fully autonomous AI coding agent:
- **LLM Planner**: Replace heuristic planner with an LLM-powered planner that reads the entire plan & repo context, then emits sub-tasks with reasoning.
- **LLM Executor**: Introduce an agent that can synthesize file edits (diffs) rather than just shell commands. It interacts with the filesystem via a controlled API (read/write/search) to avoid arbitrary shell access.
- **Verification Loop**: After each edit, run tests/lints using the existing Executor to ensure changes are valid.
- **Memory Store**: Persist conversation + decisions so the agent can reference earlier context.

## 8. Future Enhancements
- Integrate LLM backends for richer planning/review (OpenAI, local models).
- Add streaming UI dashboard & VSCode extension.
- Provide declarative skills for Docker, Terraform, Cloud functions.
