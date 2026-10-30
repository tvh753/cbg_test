# -*- coding: utf-8 -*-
# @Time    : 26/10/18 0:17
# @Author  : yy
# @File    : data_organizer.py
# @Software: cbg_test

"""
数据分类整理层：把接口原始数据和页面数据统一成同一套列名、类型，
便于后续逐字段对比。
"""

import pandas as pd


def organize_page_data(raw: list[dict]) -> pd.DataFrame:
    """页面解析数据 -> 结构化 DataFrame（解析层已清洗价格）"""
    df = pd.DataFrame(raw)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["level"] = pd.to_numeric(df["level"], errors="coerce")
    return df.sort_values("name").reset_index(drop=True)