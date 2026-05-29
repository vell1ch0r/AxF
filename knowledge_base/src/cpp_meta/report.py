from __future__ import annotations

import json

from .base import CppMetaCommand, QueryOptions
from .engine import analyze_report
from .renderer import print_markdown


class ReportCommand(CppMetaCommand):
    """Compatibility report command combining source, dependencies, calls, and params."""

    def build(self, function: str) -> dict[str, object]:
        return analyze_report(
            function,
            repo=self.options.repo,
            db=self.options.db,
            file_filter=self.options.file_filter,
            include_macros=self.options.include_macros,
            max_deps=self.options.max_deps,
            max_candidates=self.options.max_candidates,
            max_snippet_lines=self.options.max_snippet_lines,
        )

    def print(self, function: str, *, output_format: str = "markdown") -> None:
        report = self.build(function)
        if output_format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_markdown(report)

