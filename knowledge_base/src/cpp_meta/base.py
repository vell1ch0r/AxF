from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .engine import CodeItem, find_functions, open_db, resolve_repo_and_db


@dataclass
class QueryOptions:
    repo: str | Path = "."
    db: str | Path | None = None
    file_filter: str | None = None
    include_macros: bool = True
    max_deps: int = 20
    max_candidates: int = 12
    max_snippet_lines: int = 80


class CppMetaCommand:
    """Shared source tree, database, and function-selection behavior for commands."""

    def __init__(self, options: QueryOptions | None = None) -> None:
        self.options = options or QueryOptions()

    def open_context(self) -> tuple[Path, sqlite3.Connection]:
        repo_path, db_path = resolve_repo_and_db(self.options.repo, self.options.db)
        return repo_path, open_db(db_path)

    def select_function(self, con: sqlite3.Connection, function: str) -> tuple[CodeItem, list[CodeItem]]:
        candidates = find_functions(con, function, self.options.file_filter)
        if not candidates:
            raise SystemExit(f"未找到函数: {function}")
        return candidates[0], candidates[1 : self.options.max_candidates]

