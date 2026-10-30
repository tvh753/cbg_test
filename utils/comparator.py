# -*- coding: utf-8 -*-
# @Time    : 26/10/18 0:18
# @Author  : yy
# @File    : comparator.py
# @Software: cbg_test

"""
对比层：
- compare_records：单条 dict 逐字段对比（列表 vs 详情常用）
- compare_dataframes：多行 DataFrame 对齐对比
"""

import pandas as pd


def compare_records(
    left: dict,
    right: dict,
    cols: list[str],
    left_label: str = "list",
    right_label: str = "detail",
) -> list[dict]:
    """
    单条记录对比，返回差异列表。
    每条差异：{field, left_label: 值, right_label: 值}
    """
    diffs = []
    for col in cols:
        lv, rv = left.get(col), right.get(col)
        # 宽松比较：'100' 与 100 视为相等
        if str(lv) != str(rv):
            diffs.append({ "field": col, left_label: lv, right_label: rv })
    return diffs


def compare_dataframes(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    key_col: str = "name",
    compare_cols: list[str] | None = None,
    left_label: str = "left",
    right_label: str = "right",
) -> dict:
    """多行对比：主键对齐 + 逐字段找差异"""
    if compare_cols is None:
        compare_cols = ["price", "level", "server"]

    merged = pd.merge(
        left_df, right_df, on=key_col, how="outer",
        suffixes=(f"_{left_label}", f"_{right_label}"),
        indicator=True,
    )

    diffs = {"missing_in_right": [], "missing_in_left": [], "field_mismatch": []}
    diffs["missing_in_right"] = merged[merged["_merge"] == "left_only"][key_col].tolist()
    diffs["missing_in_left"] = merged[merged["_merge"] == "right_only"][key_col].tolist()

    both = merged[merged["_merge"] == "both"]
    for col in compare_cols:
        lc, rc = f"{col}_{left_label}", f"{col}_{right_label}"
        mismatch = both[both[lc] != both[rc]]
        for _, row in mismatch.iterrows():
            diffs["field_mismatch"].append({
                "name": row[key_col], "field": col,
                left_label: row[lc], right_label: row[rc],
            })
    return diffs