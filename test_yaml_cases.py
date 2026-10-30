# -*- coding: utf-8 -*-
# @Time    : 26/10/19 22:04
# @Author  : yy
# @File    : test_yaml_cases.py
# @Software: cbg_test

"""
YAML 用例驱动入口：
- 启动时扫描 yaml_cases 并全量校验
- parametrize 逐条执行，支持数据驱动展开
"""

from itertools import product
import json
from pathlib import Path
import pytest

from utils.case_runner import run_case
from utils.case_validator import run_validate
from utils.yaml_loader import load_cases

CASE_DIR = Path(__file__).resolve().parent / "yaml_cases"

# 启动时加载并校验，格式错误直接失败
CASES = load_cases(CASE_DIR)


def _expand_parametrize(cases):
    """parametrize 展开成多组参数（笛卡尔积）"""
    expanded = []
    for case in cases:
        if not case.parametrize:
            expanded.append((case, {}))
            continue
        keys = list(case.parametrize.keys())
        lists = [case.parametrize[k] for k in keys]
        for combo in product(*lists):
            expanded.append((case, dict(zip(keys, combo))))
    return expanded


EXPANDED = _expand_parametrize(CASES)


@pytest.mark.regression
@pytest.mark.parametrize(
    "case,param",
    EXPANDED,
    ids=[f"{c.name}-{p or 'default'}" for c, p in EXPANDED],
)
def test_yaml_case(browser_context, case, param):
    page = browser_context.new_page()
    try:
        vars_ctx = run_case(page, case, dict(param))

        # ★ 新增：保存提取到的数据到 JSON 文件
        data_dir = Path(__file__).resolve().parent / "data" / "output"
        data_dir.mkdir(parents=True, exist_ok=True)
        # 提取用例的英文名防乱码
        safe_name = case.name.replace(" ", "_").replace("/", "_")
        save_path = data_dir / f"{safe_name}.json"

        # 如果有提取数据，保存下来
        if vars_ctx:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(vars_ctx, f, ensure_ascii=False, indent=2)
            print(f"\n[已保存] 提取数据已保存至: {save_path}")

        # 断言
        run_validate(case.name, case.validate, vars_ctx)
    except Exception:
        page.screenshot(path=f"reports/fail_{case.name}.png", full_page=True)
        raise
    finally:
        page.close()