"""Real GPU inventory via nvidia-smi, with a graceful fallback for hosts
that don't have one (dev laptops, control-plane boxes) so the console still
renders something sensible."""
from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("meridian.gpu")


def detect_gpus() -> list[dict] | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    except Exception:
        logger.debug("nvidia-smi invocation failed", exc_info=True)
        return None

    if result.returncode != 0:
        return None

    gpus = []
    for row in result.stdout.splitlines():
        row = row.strip()
        if not row:
            continue
        parts = [p.strip() for p in row.split(",")]
        try:
            index = int(parts[0])
        except (ValueError, IndexError):
            continue
        gpus.append({"index": index, "name": parts[1] if len(parts) > 1 else "GPU"})
    return gpus or None
