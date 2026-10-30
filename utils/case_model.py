# -*- coding: utf-8 -*-
# @Time    : 26/10/19 20:13
# @Author  : yy
# @File    : case_model.py
# @Software: cbg_test

"""
用例数据模型：与 YAML 结构一一对应，做字段校验的落点。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CaseInfo:
    # ---- 必填 ----
    name: str
    steps: list[dict]  # UI 操作步骤序列
    validate: dict  # 断言

    # ---- 选填 ----
    feature: str = "默认模块"
    story: str = "默认功能"
    title: str = ""
    extract: Optional[dict] = field(default_factory=dict)  # 页面元素提取
    parametrize: Optional[dict] = field(default_factory=dict)  # 数据驱动
    pagination: Optional[dict] = field(default_factory=dict)  # 翻页抓取配置
