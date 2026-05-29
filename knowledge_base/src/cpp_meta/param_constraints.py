from __future__ import annotations

from .base import CppMetaCommand, QueryOptions
from .engine import analyze_report
from .renderer import print_param_constraints


class ParamConstraintsCommand(CppMetaCommand):
    """Feature 3: print inferred parameter constraints."""

    def print(self, function: str) -> None:
        report = analyze_report(
            function,
            repo=self.options.repo,
            db=self.options.db,
            file_filter=self.options.file_filter,
            include_macros=self.options.include_macros,
            max_deps=self.options.max_deps,
            max_candidates=self.options.max_candidates,
            max_snippet_lines=self.options.max_snippet_lines,
        )
        print_param_constraints(report)


def print_function_param_constraints(
    function: str,
    *,
    repo: str = ".",
    db: str | None = None,
    file_filter: str | None = None,
    include_macros: bool = True,
    max_deps: int = 20,
    max_candidates: int = 12,
    max_snippet_lines: int = 80,
) -> None:
    """API 3: print inferred parameter constraints for one function."""
    command = ParamConstraintsCommand(
        QueryOptions(
            repo=repo,
            db=db,
            file_filter=file_filter,
            include_macros=include_macros,
            max_deps=max_deps,
            max_candidates=max_candidates,
            max_snippet_lines=max_snippet_lines,
        )
    )
    command.print(function)

