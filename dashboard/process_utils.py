"""Cross-platform subprocess options shared by Dashboard runtime modules."""

from __future__ import annotations

import os
import subprocess
from typing import Any


def hidden_process_kwargs(*, new_process_group: bool = False) -> dict[str, Any]:
    """Keep Windows child processes console-free while preserving group control.

    CREATE_NO_WINDOW suppresses the console allocation. STARTUPINFO is retained as
    a second guard for executable wrappers and tools that create a normal window.
    """
    if os.name != "nt":
        return {}
    flags = subprocess.CREATE_NO_WINDOW
    if new_process_group:
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": flags, "startupinfo": startupinfo}


def noninteractive_git_environment() -> dict[str, str]:
    """Return a Git environment that cannot open credential or terminal prompts."""
    return {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GCM_INTERACTIVE": "Never",
        "GCM_MODAL_PROMPT": "0",
    }
