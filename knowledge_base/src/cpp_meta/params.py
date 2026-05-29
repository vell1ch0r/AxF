from __future__ import annotations

import re

from .models import CodeItem, ParamReport
from .parsing import strip_comments_and_strings


def infer_param_constraints(
    function_item: CodeItem, params: list[CodeItem], source: str
) -> list[ParamReport]:
    reports: list[ParamReport] = []
    lines = source.splitlines()
    clean_lines = strip_comments_and_strings(source).splitlines()
    for param in params:
        name = param.name
        inferred: list[str] = []
        evidence: list[str] = []
        ptype = param.type
        if not name:
            reports.append(ParamReport(name="<anonymous>", type=ptype, inferred=[], evidence=[]))
            continue
        if ptype:
            if "*" in ptype:
                inferred.append("指针参数；需要调用者提供有效地址，除非函数显式允许 NULL。")
            if "__user" in ptype:
                inferred.append("用户态指针；通常需要配合 access_ok/copy_*_user 等检查。")
            if ptype.strip().startswith("const ") or " const " in ptype:
                inferred.append("只读语义；函数不应修改该入参指向的数据。")

        for idx, clean_line in enumerate(clean_lines):
            if not re.search(rf"\b{re.escape(name)}\b", clean_line):
                continue
            original = lines[idx].rstrip()
            lineno = function_item.start_line + idx
            interesting = False
            if re.search(r"\b(if|while|WARN_ON|BUG_ON|BUILD_BUG_ON|likely|unlikely)\b", clean_line):
                interesting = True
                cond = clean_line.strip()
                if re.search(rf"!\s*{re.escape(name)}\b", cond) or re.search(
                    rf"\b{re.escape(name)}\b\s*==\s*NULL", cond
                ):
                    inferred.append("存在 NULL/空值检查。")
                if re.search(rf"\b{re.escape(name)}\b\s*(?:[<>]=?|==|!=)", cond):
                    inferred.append("存在数值或状态比较约束。")
            if re.search(rf"\baccess_ok\s*\([^;]*\b{re.escape(name)}\b", clean_line):
                interesting = True
                inferred.append("通过 access_ok 校验可访问范围。")
            if re.search(rf"\bcopy_(?:to|from)_user\s*\([^;]*\b{re.escape(name)}\b", clean_line):
                interesting = True
                inferred.append("参与 copy_to_user/copy_from_user，入参格式受用户态缓冲区约束。")
            if idx > 0 and re.search(rf"\b{re.escape(name)}\b\s*=", clean_line):
                interesting = True
                inferred.append("函数内部会重写该参数的局部值。")
            if idx > 0 and (
                re.search(rf"\b{re.escape(name)}\s*->", clean_line) or re.search(
                rf"\*\s*{re.escape(name)}\b", clean_line
                )
            ):
                interesting = True
                inferred.append("函数会解引用该参数。")
            if interesting:
                evidence.append(f"{lineno}: {original}")

        deduped: list[str] = []
        for text in inferred:
            if text not in deduped:
                deduped.append(text)
        reports.append(ParamReport(name=name, type=ptype, inferred=deduped, evidence=evidence[:20]))
    return reports

