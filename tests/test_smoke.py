import sys
from pathlib import Path

def test_imports():
    # Add repo root to sys.path so imports work in CI and local runs
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    import src.agent
    import src.engine.orchestrator
    import src.storage

    assert True
