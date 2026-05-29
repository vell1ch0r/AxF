from __future__ import annotations

from .base import CppMetaCommand, QueryOptions
from .engine import CallerSite, build_upstream_call_chains
from .renderer import relpath


class CallChainCommand(CppMetaCommand):
    """Feature 2: print upstream caller chains ending at the target function."""

    def print(
        self,
        function: str,
        *,
        max_depth: int = 5,
        max_chains: int = 200,
        max_callers_per_level: int = 80,
    ) -> None:
        repo_path, con = self.open_context()
        try:
            target, _candidates = self.select_function(con, function)
            chains = build_upstream_call_chains(
                con,
                repo_path,
                target,
                max_depth=max_depth,
                max_chains=max_chains,
                max_callers_per_level=max_callers_per_level,
            )
            print(
                f"Target: {target.name} ({relpath(target.file)}:{target.start_line}-{target.end_line})"
            )
            if not chains:
                print("No upstream callers found.")
                return
            for idx, chain in enumerate(chains, start=1):
                print(f"{idx}. " + " -> ".join(site.caller.name for site in chain))
                detail = self._chain_detail(chain)
                if detail:
                    print(f"   {detail}")
        finally:
            con.close()

    @staticmethod
    def _chain_detail(chain: list[CallerSite]) -> str:
        return " | ".join(
            f"{site.caller.name}@{relpath(site.caller.file)}:{site.line}"
            for site in chain[:-1]
        )


def print_function_call_sequence(
    function: str,
    *,
    repo: str = ".",
    db: str | None = None,
    file_filter: str | None = None,
    include_macros: bool = True,
    max_depth: int = 5,
    max_chains: int = 200,
    max_callers_per_level: int = 80,
    max_candidates: int = 12,
) -> None:
    """API 2: print upstream caller chains ending at the target function."""
    command = CallChainCommand(
        QueryOptions(
            repo=repo,
            db=db,
            file_filter=file_filter,
            include_macros=include_macros,
            max_candidates=max_candidates,
        )
    )
    command.print(
        function,
        max_depth=max_depth,
        max_chains=max_chains,
        max_callers_per_level=max_callers_per_level,
    )

