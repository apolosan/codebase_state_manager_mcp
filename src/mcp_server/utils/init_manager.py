import os
from pathlib import Path

INITIALIZED_FLAG = ".codebase_state_initialized"


def is_initialized(volume_path: str) -> bool:
    flag_path = Path(volume_path) / INITIALIZED_FLAG
    return flag_path.exists()


def set_initialized(volume_path: str, initialized: bool = True) -> bool:
    flag_path = Path(volume_path) / INITIALIZED_FLAG
    try:
        Path(volume_path).mkdir(parents=True, exist_ok=True)
        if initialized:
            flag_path.touch()
        else:
            if flag_path.exists():
                flag_path.unlink()
        return True
    except Exception:
        return False
