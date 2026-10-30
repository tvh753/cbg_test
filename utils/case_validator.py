# -*- coding: utf-8 -*-
# @Time    : 26/10/19 22:04
# @Author  : yy
# @File    : case_validator.py
# @Software: cbg_test

"""
断言执行器：解析 ${xxx} 并逐条校验。
新增 length_greater，支持对 extract 出的表格 list 做行数断言。
"""

import logging

logger = logging.getLogger(__name__)


def _resolve(value, vars_ctx: dict):
    """'${name}' -> vars_ctx['name']；非占位符原样返回"""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        key = value[2:-1]
        if key not in vars_ctx:
            raise AssertionError(f"变量 ${{{key}}} 未定义，已提取: {list(vars_ctx)}")
        return vars_ctx[key]
    return value


def _assert_equals(actual, expected) -> bool:
    """宽松相等：'0' 与 0 视为相等"""
    if actual == expected:
        return True
    return str(actual) == str(expected)


def _assert_contains(actual, expected) -> bool:
    """
    contains 语义：
    - actual 是 list：任一行 str 形式包含 expected 即通过
    - 其他：字符串包含
    """
    if isinstance(actual, list):
        return any(str(expected) in str(row) for row in actual)
    return str(expected) in str(actual)


def run_validate(case_name: str, validate: dict, vars_ctx: dict) -> None:
    """执行全部断言，任一失败立即抛 AssertionError"""
    for kind, rules in validate.items():
        for desc, pair in rules.items():
            if not isinstance(pair, list) or len(pair) != 2:
                raise AssertionError(
                    f"[{case_name}] 断言 {desc} 必须是 [实际占位符, 期望值]"
                )
            actual = _resolve(pair[0], vars_ctx)
            expected = _resolve(pair[1], vars_ctx)

            if kind in ("epuals", "equals"):
                ok = _assert_equals(actual, expected)
            elif kind == "not_equals":
                ok = not _assert_equals(actual, expected)
            elif kind == "contains":
                ok = _assert_contains(actual, expected)
            elif kind == "length_greater":
                ok = isinstance(actual, list) and len(actual) > int(expected)
            else:
                raise AssertionError(f"[{case_name}] 未知断言类型: {kind}")

            assert ok, (
                f"[{case_name}] 断言失败 [{kind}] {desc}: "
                f"实际={actual!r} 期望={expected!r}"
            )
            logger.info("[%s] 断言通过: %s", case_name, desc)