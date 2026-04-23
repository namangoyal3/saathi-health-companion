"""Filesystem memory adapter for the Anthropic memory_20250818 tool.

Path isolation: every operation resolves to MEMORY_ROOT/{user_id}/ and
raises MemoryAccessError if the resolved path escapes that root.
No beta header required for the memory tool on Claude 4 models.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


class MemoryAccessError(Exception):
    pass


def _authorized_root(user_id: uuid.UUID) -> Path:
    root = (settings.memory_root / str(user_id)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(user_id: uuid.UUID, relative: str) -> Path:
    root = _authorized_root(user_id)
    candidate = (root / relative).resolve()
    if not str(candidate).startswith(str(root)):
        raise MemoryAccessError(f"Path traversal attempt: {relative!r} resolves outside {root}")
    return candidate


def handle_memory_tool(
    user_id: uuid.UUID,
    command: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch a memory tool command from the Anthropic SDK tool_use block."""
    dispatch = {
        "view": _view,
        "create": _create,
        "str_replace": _str_replace,
        "insert": _insert,
        "delete": _delete,
        "rename": _rename,
    }
    handler = dispatch.get(command)
    if handler is None:
        return {"error": f"Unknown memory command: {command!r}"}
    try:
        return handler(user_id, params)
    except MemoryAccessError as e:
        log.error("memory_access_denied", user_id=str(user_id), command=command, error=str(e))
        return {"error": str(e)}
    except Exception as e:
        log.error("memory_error", user_id=str(user_id), command=command, error=str(e))
        return {"error": str(e)}


def _view(user_id: uuid.UUID, params: dict[str, Any]) -> dict[str, Any]:
    path_str: str = params.get("path", "")
    target = _safe_path(user_id, path_str) if path_str else _authorized_root(user_id)

    if target.is_dir():
        entries = sorted(target.iterdir())
        listing = "\n".join(f"{'d' if e.is_dir() else 'f'} {e.name}" for e in entries)
        return {"content": listing or "(empty directory)"}

    if target.is_file():
        lines = target.read_text(encoding="utf-8").splitlines()
        numbered = "\n".join(f"{i + 1}\t{line}" for i, line in enumerate(lines))
        return {"content": numbered}

    return {"error": f"Path not found: {path_str!r}"}


def _create(user_id: uuid.UUID, params: dict[str, Any]) -> dict[str, Any]:
    path_str: str = params["path"]
    content: str = params.get("content", "")
    target = _safe_path(user_id, path_str)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"created": path_str}


def _str_replace(user_id: uuid.UUID, params: dict[str, Any]) -> dict[str, Any]:
    path_str: str = params["path"]
    old: str = params["old_str"]
    new: str = params["new_str"]
    target = _safe_path(user_id, path_str)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        return {"error": f"old_str not found in {path_str!r}"}
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return {"replaced": path_str}


def _insert(user_id: uuid.UUID, params: dict[str, Any]) -> dict[str, Any]:
    path_str: str = params["path"]
    after_line: int = int(params["insert_line"])
    new_content: str = params["new_str"]
    target = _safe_path(user_id, path_str)
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    lines.insert(after_line, new_content if new_content.endswith("\n") else new_content + "\n")
    target.write_text("".join(lines), encoding="utf-8")
    return {"inserted_after_line": after_line, "path": path_str}


def _delete(user_id: uuid.UUID, params: dict[str, Any]) -> dict[str, Any]:
    path_str: str = params["path"]
    target = _safe_path(user_id, path_str)
    if target.is_file():
        target.unlink()
        return {"deleted": path_str}
    return {"error": f"File not found: {path_str!r}"}


def _rename(user_id: uuid.UUID, params: dict[str, Any]) -> dict[str, Any]:
    old_str: str = params["old_path"]
    new_str: str = params["new_path"]
    src = _safe_path(user_id, old_str)
    dst = _safe_path(user_id, new_str)
    src.rename(dst)
    return {"renamed": {"from": old_str, "to": new_str}}
