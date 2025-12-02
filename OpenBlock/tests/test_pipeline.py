from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from openblock.pipeline import PipelineRunner


def test_pipeline_dry_run(tmp_path):
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        """
project:
  name: integ
  goal: dry run
tasks:
  - name: noop
    description: "just testing"
    commands:
      - "echo test"
""",
        encoding="utf-8",
    )
    runner = PipelineRunner.from_file(plan_path=plan, dry_run=True, log_dir=tmp_path / "logs")
    runs = runner.execute()
    assert runs[0].execution.dry_run is True
    log_files = list((tmp_path / "logs").glob("run-*.json"))
    assert log_files, "should persist run log"


def test_pipeline_ai_coder(tmp_path):
    plan = PACKAGE_ROOT / "examples" / "agent_plan.yaml"
    runner = PipelineRunner.from_file(
        plan_path=plan,
        dry_run=True,
        log_dir=tmp_path / "logs",
        workspace=tmp_path,
    )
    runs = runner.execute()
    assert runs[0].coding is not None
    assert runs[0].coding.success()
    generated_file = tmp_path / "todo_api" / "main.py"
    assert generated_file.exists()
