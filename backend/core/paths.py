"""Filesystem path helpers for app data."""

from __future__ import annotations

import os


def resolve_data_root() -> str:
    """Return the root directory for persisted app data."""
    data_dir = os.getenv("ADHD_DATA_DIR")
    if data_dir:
        return os.path.abspath(data_dir)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "adhd_brain")
