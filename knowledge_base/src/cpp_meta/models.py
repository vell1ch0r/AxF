from __future__ import annotations

from dataclasses import dataclass


KIND = {
    2: "struct",
    3: "union",
    4: "enum",
    8: "enumerator",
    9: "parameter",
    21: "typedef",
    27: "function",
    28: "variable",
    37: "macro_define",
}

INTERESTING_KINDS = (2, 3, 4, 8, 21, 28, 37)
TYPE_DEP_KINDS = (2, 3, 4, 21)
DEPENDENCY_GROUP_NAMES = (
    "structures",
    "typedefs",
    "enums",
    "constants",
    "global_variables",
    "static_variables",
)
CONTROL_WORDS = {
    "if",
    "for",
    "while",
    "switch",
    "return",
    "sizeof",
    "typeof",
    "__typeof__",
    "__alignof__",
    "alignof",
    "_Generic",
    "case",
}
C_KEYWORDS = {
    "auto",
    "break",
    "case",
    "char",
    "const",
    "continue",
    "default",
    "do",
    "double",
    "else",
    "enum",
    "extern",
    "float",
    "for",
    "goto",
    "if",
    "inline",
    "int",
    "long",
    "register",
    "restrict",
    "return",
    "short",
    "signed",
    "sizeof",
    "static",
    "struct",
    "switch",
    "typedef",
    "union",
    "unsigned",
    "void",
    "volatile",
    "while",
    "__user",
    "__iomem",
    "__init",
    "__exit",
    "__maybe_unused",
}


@dataclass
class CodeItem:
    id: int
    kind: str
    name: str
    type: str | None
    attributes: int
    file: str
    start_line: int
    end_line: int
    start_column: int
    end_column: int
    parent_id: int

    @property
    def span(self) -> int:
        return max(0, self.end_line - self.start_line)


@dataclass
class CallSite:
    line: int
    expression: str
    callee: str
    resolved_file: str | None = None
    resolved_line: int | None = None


@dataclass
class CallerSite:
    caller: CodeItem
    line: int
    text: str


@dataclass
class ParamReport:
    name: str
    type: str | None
    inferred: list[str]
    evidence: list[str]

