from __future__ import annotations

from dataclasses import asdict

from .calls import (
    CALL_RE,
    build_upstream_call_chains,
    collect_downstream_functions,
    discover_calls,
    is_auxiliary_callee,
    order_functions_for_bundle,
)
from .db import (
    find_enclosing_function,
    find_functions,
    function_params,
    open_db,
    resolve_function,
    resolve_repo_and_db,
)
from .dependencies import (
    collect_function_dependencies,
    empty_dependency_groups,
    expand_nested_type_dependencies,
    item_to_dict,
    merge_dependency_groups,
)
from .models import (
    DEPENDENCY_GROUP_NAMES,
    CallSite,
    CallerSite,
    CodeItem,
    ParamReport,
)
from .params import infer_param_constraints
from .parsing import (
    numbered_slice,
    source_slice,
    strip_comments_and_strings,
    tokens_from_source,
)


def analyze_report(
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
    _repo, db_path = resolve_repo_and_db(repo, db)
    con = open_db(db_path)
    try:
        candidates = find_functions(con, function, file_filter)
        if not candidates:
            raise SystemExit(f"Function not found: {function}")
        function_item = candidates[0]
        params = function_params(con, function_item.id)
        source = source_slice(function_item)
        dependencies = collect_function_dependencies(
            con,
            function_item,
            source,
            params,
            expand_nested_types=expand_nested_types,
            max_nesting_depth=max_nesting_depth,
        )
        calls = discover_calls(con, function_item, source, include_macros=include_macros)
        return {
            "selected": asdict(function_item),
            "ambiguous_candidates": [asdict(item) for item in candidates[1:max_candidates]],
            "parameters": [asdict(item) for item in params],
            "source": source,
            "dependencies": {
                name: [item_to_dict(item, max_snippet_lines) for item in items[:max_deps]]
                for name, items in dependencies.items()
            },
            "calls": [asdict(call) for call in calls],
            "param_constraints": [asdict(r) for r in infer_param_constraints(function_item, params, source)],
            "notes": [
                "BROWSE.VC.DB may not contain complete symbol relation tables; calls and constraints use source heuristics.",
                "When functions share the same name, use --file to narrow the source path.",
            ],
        }
    finally:
        con.close()

