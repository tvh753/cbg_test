# -*- coding: utf-8 -*-
# @Time    : 26/10/18 0:17
# @Author  : yy
# @File    : page_parser.py
# @Software: cbg_test

"""
页面数据提取层（重点）：

- parse_equipment_list：打开列表页，滚动加载全量，逐项解析
- parse_equipment_detail：解析当前详情页字段
- open_detail_by_index：从列表页点击第 N 条进入详情
- extract_by_schema：按 {字段名: (选择器, 属性)} 通用提取

所有选择器集中在顶部常量，便于统一替换。
"""

import logging
from typing import Any

from playwright.sync_api import Page, TimeoutError as PWTimeout

from config import EQUIP_LIST_URL

logger = logging.getLogger(__name__)

# ---------- 列表页 ----------
# 由 config 用中文大区名/服务器名拼出来，换服务器只改 config 里那两行
LIST_URL = EQUIP_LIST_URL

SEL_ITEM = ".equipment-list .item"        # 列表项容器
SEL_NAME = ".equip-name"
SEL_PRICE = ".equip-price"
SEL_LEVEL = ".equip-level"
SEL_SERVER = ".equip-server"

# ---------- 详情页 ----------
SEL_DETAIL_NAME = ".detail-name"
SEL_DETAIL_PRICE = ".detail-price"
SEL_DETAIL_LEVEL = ".detail-level"
SEL_DETAIL_SERVER = ".detail-server"


def _clean_price(text: str) -> str:
    """价格清洗：去 ￥、逗号、空格"""
    return text.replace("￥", "").replace(",", "").replace(" ", "").strip()


def _safe_text(locator, default: str = "") -> str:
    """安全取文本，元素不存在时返回默认值而非抛错"""
    try:
        return locator.inner_text().strip()
    except Exception:
        return default


# ---------- 通用：按 schema 提取 ----------
def extract_by_schema(page: Page, schema: dict[str, tuple[str, str]]) -> dict[str, Any]:
    """
    按 {字段名: (选择器, 属性)} 通用提取。
    属性支持 text / value / 任意 HTML attribute（如 href、data-id）。
    """
    result = {}
    for field, (selector, attr) in schema.items():
        loc = page.locator(selector).first
        try:
            if attr == "text":
                result[field] = loc.inner_text().strip()
            elif attr == "value":
                result[field] = loc.input_value()
            else:
                result[field] = loc.get_attribute(attr)
        except Exception as e:
            logger.warning("字段 %s 提取失败: %s", field, e)
            result[field] = None
    return result


# ---------- 列表页：解析单项 ----------
def _parse_list_item(item) -> dict:
    return {
        "name": _safe_text(item.locator(SEL_NAME)),
        "price": _clean_price(_safe_text(item.locator(SEL_PRICE))),
        "level": _safe_text(item.locator(SEL_LEVEL)),
        "server": _safe_text(item.locator(SEL_SERVER)),
    }


# ---------- 列表页：滚动加载 + 全量解析 ----------
def parse_equipment_list(
    page: Page,
    url: str = LIST_URL,
    max_scroll: int = 30,
) -> list[dict]:
    """
    打开列表页 -> 等待渲染 -> 滚动懒加载 -> 逐项解析。
    返回列表页展示的装备数据。
    """
    page.goto(url, wait_until="networkidle")
    try:
        page.wait_for_selector(SEL_ITEM, timeout=15000)
    except PWTimeout:
        page.screenshot(path="reports/list_load_failed.png", full_page=True)
        raise AssertionError(
            f"列表未渲染，选择器={SEL_ITEM}，截图见 reports/list_load_failed.png"
        )

    # 滚动到数量不再增长
    last_count = -1
    for i in range(max_scroll):
        cur = page.locator(SEL_ITEM).count()
        if cur == last_count:
            break
        last_count = cur
        page.mouse.wheel(0, 20000)
        page.wait_for_timeout(800)
        logger.info("滚动第%d次，已加载 %d 条", i + 1, cur)

    items = page.locator(SEL_ITEM)
    result = []
    for idx in range(items.count()):
        try:
            result.append(_parse_list_item(items.nth(idx)))
        except Exception as e:
            logger.warning("第%d项解析失败: %s", idx, e)

    logger.info("列表页共解析出 %d 条", len(result))
    return result


# ---------- 详情页：从列表点击第 N 条进入 ----------
def open_detail_by_index(page: Page, index: int = 0) -> None:
    """从列表页点击第 index 条进入详情，等待详情元素出现"""
    items = page.locator(SEL_ITEM)
    if items.count() <= index:
        raise AssertionError(f"列表只有 {items.count()} 条，无法进入第 {index} 条详情")
    items.nth(index).click()
    try:
        page.wait_for_selector(SEL_DETAIL_NAME, timeout=15000)
    except PWTimeout:
        page.screenshot(path="reports/detail_load_failed.png", full_page=True)
        raise AssertionError(
            f"详情页未渲染，选择器={SEL_DETAIL_NAME}，截图见 reports/detail_load_failed.png"
        )
    logger.info("已进入第 %d 条详情页", index)


# ---------- 详情页：解析当前页字段 ----------
def parse_equipment_detail(page: Page) -> dict:
    """解析当前详情页的装备字段"""
    return {
        "name": _safe_text(page.locator(SEL_DETAIL_NAME).first),
        "price": _clean_price(_safe_text(page.locator(SEL_DETAIL_PRICE).first)),
        "level": _safe_text(page.locator(SEL_DETAIL_LEVEL).first),
        "server": _safe_text(page.locator(SEL_DETAIL_SERVER).first),
    }