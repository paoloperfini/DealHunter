import sys
from pathlib import Path


def test_imports():
    repo_root = Path(__file__).resolve().parents[1]
    print("Repo root:", repo_root)

    print("Directory listing of repo root:")
    for p in repo_root.iterdir():
        print(" -", p.name)

    src_path = repo_root / "src"
    print("Does src exist?", src_path.exists())

    # Add repo root to sys.path
    sys.path.insert(0, str(repo_root))

    print("sys.path[0]:", sys.path[0])

    import src
    print("Imported src successfully")

    assert True
