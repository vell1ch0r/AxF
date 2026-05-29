from __future__ import annotations

from pathlib import Path

from .base import CppMetaCommand, QueryOptions
from .engine import analyze_report
from .renderer import default_bundle_path, render_c_bundle


class SourceBundleCommand(CppMetaCommand):
    """Feature 1: export one function and related snippets into a .c bundle."""

    def analyze(self, function: str, *, max_nesting_depth: int = 4) -> dict[str, object]:
        return analyze_report(
            function,
            repo=self.options.repo,
            db=self.options.db,
            file_filter=self.options.file_filter,
            include_macros=self.options.include_macros,
            max_deps=self.options.max_deps,
            max_candidates=self.options.max_candidates,
            max_snippet_lines=self.options.max_snippet_lines,
            expand_nested_types=True,
            max_nesting_depth=max_nesting_depth,
        )

    def export(
        self,
        function: str,
        output: str | Path | None = None,
        *,
        max_nesting_depth: int = 4,
    ) -> Path:
        report = self.analyze(function, max_nesting_depth=max_nesting_depth)
        output_path = Path(output) if output else default_bundle_path(report)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_c_bundle(report), encoding="utf-8")
        return output_path


def analyze_function(
    function: str,
    *,
    repo: str = ".",
    db: str | None = None,
    file_filter: str | None = None,
    include_macros: bool = True,
    max_deps: int = 20,
    max_candidates: int = 12,
    max_snippet_lines: int = 80,
    expand_nested_types: bool = False,
    max_nesting_depth: int = 4,
) -> dict[str, object]:
    """Return the complete analysis report for one function name."""
    return analyze_report(
        function,
        repo=repo,
        db=db,
        file_filter=file_filter,
        include_macros=include_macros,
        max_deps=max_deps,
        max_candidates=max_candidates,
        max_snippet_lines=max_snippet_lines,
        expand_nested_types=expand_nested_types,
        max_nesting_depth=max_nesting_depth,
    )


def export_source_bundle(
    function: str,
    output: str | Path | None = None,
    *,
    repo: str = ".",
    db: str | None = None,
    file_filter: str | None = None,
    include_macros: bool = True,
    max_deps: int = 200,
    max_candidates: int = 12,
    max_snippet_lines: int = 80,
    max_nesting_depth: int = 4,
) -> Path:
    """API 1: write function source and related snippets into a .c file."""
    command = SourceBundleCommand(
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
    return command.export(function, output, max_nesting_depth=max_nesting_depth)

