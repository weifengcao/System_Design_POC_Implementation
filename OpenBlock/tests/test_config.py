from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from openblock.config import load_config


def test_load_config_examples():
    sample = PACKAGE_ROOT / "examples" / "hello_plan.yaml"
    config = load_config(sample)
    assert config.name == "hello"
    assert config.tasks[0].commands == ["echo 'Hello from OpenBlock!'"]


def test_load_config_code_artifacts():
    sample = PACKAGE_ROOT / "examples" / "agent_plan.yaml"
    config = load_config(sample)
    task = config.tasks[0]
    assert task.code
    artifact = task.code[0]
    assert artifact.path == "todo_api/main.py"
