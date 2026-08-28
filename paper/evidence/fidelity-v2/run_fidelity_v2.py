#!/usr/bin/env python3
"""Entry point for the frozen fidelity-v2 evaluator."""

from __future__ import annotations

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from evaluator.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
