from __future__ import annotations

import argparse
from typing import Any, Dict, Optional

import yaml

from .engine.orchestrator import Orchestrator


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--config", default="config/config.yaml")
    ap.add_argument("--imap-config", default="config/imap.yaml")
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    imap_cfg: Optional[Dict[str, Any]] = None

    if cfg.get("subito_ingest", {}).get("imap_enabled"):
        imap_cfg = load_yaml(args.imap_config)

    orch = Orchestrator(cfg=cfg, imap_cfg=imap_cfg)

    if args.once:
        orch.run_once()
        return

    loop_minutes = int(cfg["settings"].get("loop_minutes", 180))
    orch.run_forever(loop_minutes)


if __name__ == "__main__":
    main()
