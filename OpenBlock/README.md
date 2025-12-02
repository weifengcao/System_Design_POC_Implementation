# OpenBlock

OpenBlock is an open-source AI agent CLI that helps developers go from an idea to working code. You describe the goal in a declarative plan file and OpenBlock orchestrates a Planner → Executor → Reviewer pipeline to carry out the work, capture logs, and summarize the outcome.

> Think of it as an automation-friendly version of tools like OpenBlock Labs, but runnable entirely from your terminal or CI jobs.

## Features
- **Declarative plans** written in YAML (project metadata + ordered tasks).
- **Pluggable agents** with sane defaults (Planner, Executor, Reviewer).
- **AI Coder agent** that materializes files from templates defined in a plan.
- **Use existing tools** via shell commands or custom skills.
- **Dry-run mode** to validate plans without changing the filesystem.
- **Run artifacts** stored under `.openblock/logs`.

## Quickstart
```bash
cd OpenBlock
python -m venv .venv && source .venv/bin/activate
pip install -e .

openblock run examples/hello_plan.yaml
```

Example plan (`examples/hello_plan.yaml`):
```yaml
project:
  name: "hello"
  goal: "Print diagnostics"
tasks:
  - name: greet
    description: "Say hello"
    commands:
      - "echo 'Hello from OpenBlock!'"
```

## AI Coding Agent
Define `code` artifacts inside a task to let the AI Coder agent materialize files before executing shell commands. Templates support Python `str.format` variables derived from the project, task metadata, and custom context.

```yaml
tasks:
  - name: scaffold
    description: "Create FastAPI app"
    code:
      - path: "app/main.py"
        template: |
          from fastapi import FastAPI
          app = FastAPI(title="{project_name}")
          @app.get("/health")
          def health():
              return {{"status": "ok"}}
    commands:
      - "python -m compileall app"
```

Running `openblock run examples/agent_plan.yaml` will generate the files and then execute the commands. The CLI summary now includes how many files were produced per task.

## CLI
```
Usage: openblock run [PLAN] [--dry-run] [--log-dir PATH] [--workspace PATH]
```
- `PLAN`: path to YAML/JSON plan (defaults to `openblock.yaml`).
- `--dry-run`: skip executing commands while still running planner/reviewer.
- `--log-dir`: override log output directory.
- `--workspace`: directory where files and commands run (defaults to plan directory).

## Project Structure
```
openblock/
  agents/            # Planner / Executor / Reviewer implementations
  cli.py             # Typer CLI entrypoint
  config.py          # Plan parser & dataclasses
  pipeline.py        # PipelineRunner
examples/
  hello_plan.yaml
design.md            # Architecture doc
README.md
pyproject.toml
```

## Roadmap
- Integrate additional skills (Git, tests, Docker).
- Attach LLM backends for richer planning/review + coding.
- Add VS Code extension & REST API surface.
