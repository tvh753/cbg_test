# -*- coding: utf-8 -*-
# @Time    : 26/10/19 20:14
# @Author  : yy
# @File    : yaml_loader.py
# @Software: cbg_test

"""
YAML 用例加载器（纯 UI 版）：
1. 扫描目录
2. 字段是否存在校验
3. 字段是否正确校验（steps / extract / validate / parametrize）
4. 转 CaseInfo
"""

import logging
from pathlib import Path

import yaml

from utils.case_model import CaseInfo

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["name", "steps", "validate"]

# 支持的 UI 操作
VALID_ACTIONS = {
    "goto", "fill", "click", "hover", "press",
    "wait_for_selector", "wait_timeout",
    "scroll_to_bottom", "screenshot",
}

# 支持的断言类型
VALID_VALIDATE_KEYS = {"epuals", "equals", "contains", "not_equals", "length_greater"}


class CaseFormatError(Exception):
    """用例格式错误"""


def _check_required_fields(data: dict, source: str) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in data or data[f] in (None, "", [])]
    if missing:
        raise CaseFormatError(f"[{source}] 缺少必填字段: {missing}")


def _check_steps(data: dict, source: str) -> None:
    steps = data["steps"]
    if not isinstance(steps, list) or not steps:
        raise CaseFormatError(f"[{source}] steps 必须是非空 list")

    for i, step in enumerate(steps):
        if not isinstance(step, dict) or "action" not in step:
            raise CaseFormatError(f"[{source}] steps[{i}] 必须是含 action 的 dict")
        action = step["action"]
        if action not in VALID_ACTIONS:
            raise CaseFormatError(
                f"[{source}] steps[{i}].action 非法: {action}，支持 {VALID_ACTIONS}"
            )
        # 按 action 校验必填参数
        if action == "goto" and not step.get("url"):
            raise CaseFormatError(f"[{source}] steps[{i}] goto 缺少 url")
        if action in ("fill", "click", "press", "wait_for_selector", "screenshot"):
            if not step.get("selector") and not step.get("path"):
                raise CaseFormatError(f"[{source}] steps[{i}] {action} 缺少 selector/path")
        if action == "fill" and "value" not in step:
            raise CaseFormatError(f"[{source}] steps[{i}] fill 缺少 value")


def _check_validate(data: dict, source: str) -> None:
    val = data["validate"]
    if not isinstance(val, dict) or not val:
        raise CaseFormatError(f"[{source}] validate 必须是非空 dict")

    unknown = set(val.keys()) - VALID_VALIDATE_KEYS
    if unknown:
        raise CaseFormatError(
            f"[{source}] validate 含不支持的断言类型: {unknown}，支持 {VALID_VALIDATE_KEYS}"
        )
    for k, v in val.items():
        if not isinstance(v, dict):
            raise CaseFormatError(f"[{source}] validate.{k} 必须是 dict")


def _check_extract(data: dict, source: str) -> None:
    """校验 extract：支持单元素规则和 table 规则"""
    ext = data.get("extract")
    if ext in (None, ""):
        data["extract"] = {}
        return
    if not isinstance(ext, dict):
        raise CaseFormatError(f"[{source}] extract 必须是 dict")

    for name, rule in ext.items():
        if not isinstance(rule, dict) or not rule.get("selector"):
            raise CaseFormatError(
                f"[{source}] extract.{name} 必须是含 selector 的 dict，实际 {rule}"
            )

        # 表格规则：type=table 时 headers 可选，但必须是 list
        if rule.get("type") == "table":
            if "headers" in rule and not isinstance(rule["headers"], list):
                raise CaseFormatError(f"[{source}] extract.{name}.headers 必须是 list")
        else:
            # 单元素规则：index 是 int，attr 是 str
            if "index" in rule and not isinstance(rule["index"], int):
                raise CaseFormatError(f"[{source}] extract.{name}.index 必须是 int")
            if "attr" in rule and not isinstance(rule["attr"], str):
                raise CaseFormatError(f"[{source}] extract.{name}.attr 必须是 str")


def _check_parametrize(data: dict, source: str) -> None:
    para = data.get("parametrize")
    if para in (None, ""):
        data["parametrize"] = {}
        return
    if not isinstance(para, dict):
        raise CaseFormatError(f"[{source}] parametrize 必须是 dict")


def _check_pagination(data: dict, source: str) -> None:
    """校验 pagination：next_selector 必填，max_pages 必须是 int"""
    pag = data.get("pagination")
    if pag in (None, ""):
        data["pagination"] = {}
        return
    if not isinstance(pag, dict):
        raise CaseFormatError(f"[{source}] pagination 必须是 dict")
    if not pag.get("next_selector"):
        raise CaseFormatError(f"[{source}] pagination 缺少 next_selector")
    if "max_pages" in pag and not isinstance(pag["max_pages"], int):
        raise CaseFormatError(f"[{source}] pagination.max_pages 必须是 int")


def validate_and_build(data: dict, source: str) -> CaseInfo:
    """全量校验并转 CaseInfo"""
    _check_required_fields(data, source)
    _check_steps(data, source)
    _check_validate(data, source)
    _check_extract(data, source)
    _check_parametrize(data, source)
    _check_pagination(data, source)

    return CaseInfo(
        name=data["name"],
        steps=data["steps"],
        validate=data["validate"],
        feature=data.get("feature", "默认模块"),
        story=data.get("story", "默认功能"),
        title=data.get("title", ""),
        extract=data.get("extract", {}),
        parametrize=data.get("parametrize", {}),
        pagination=data.get("pagination", {}),
    )


def load_cases(case_dir: Path) -> list[CaseInfo]:
    """扫描目录，读取并校验全部 YAML"""
    cases = []
    files = sorted(list(case_dir.glob("*.yaml")) + list(case_dir.glob("*.yml")))
    if not files:
        logger.warning("用例目录 %s 下没有 YAML 文件", case_dir)
        return cases

    for f in files:
        with open(f, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp)
        if not isinstance(data, dict):
            raise CaseFormatError(f"[{f.name}] YAML 顶层必须是 dict")
        info = validate_and_build(data, source=f.name)
        logger.info("加载用例: %s (%s)", info.name, f.name)
        cases.append(info)

    return cases
