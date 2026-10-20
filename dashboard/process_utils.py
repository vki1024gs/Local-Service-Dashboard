"""Cross-platform subprocess options shared by Dashboard runtime modules."""

from __future__ import annotations

import os
import subprocess


def hidden_process_kwargs(*, new_process_group: bool = False) -> dict[str, int]:
    """Keep Windows child processes console-free while preserving group control."""
    if os.name != "nt":
        return {}
    flags = subprocess.CREATE_NO_WINDOW
    if new_process_group:
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return {"creationflags": flags}
