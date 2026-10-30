# -*- coding: utf-8 -*-
# @Time    : 26/10/21 18:08
# @Author  : yy
# @File    : ui_actions.py
# @Software: cbg_test

"""
UI 动作执行层（重点）。

职责：把 YAML steps 里的 action 翻译成 Playwright 的具体调用。
新增一种操作只需在 do_action 里加一个分支，YAML 侧无需改代码。

约定：
- 所有 selector 用 CSS 选择器
- 参数中的 ${var} 已在 case_runner 里替换好，这里拿到的是最终值
"""

import logging

from playwright.sync_api import Page

from config import URL_PRESETS

logger = logging.getLogger(__name__)


def resolve_url(url: str) -> str:
    """把 YAML 里的 '@login' 这类别名换成 config.URL_PRESETS 里的真实地址。

    普通完整 URL 原样返回，所以旧的写法照样能用。
    """
    if isinstance(url, str) and url.startswith("@"):
        name = url[1:]
        if name not in URL_PRESETS:
            raise KeyError(
                f"未知 URL 别名: {url}，可用: {sorted(URL_PRESETS)}"
            )
        return URL_PRESETS[name]
    return url


def do_action(page: Page, action: str, params: dict) -> None:
    """
    执行单个 UI 动作。

    :param page:   当前页面对象
    :param action: 动作名（与 YAML 的 action 字段一致）
    :param params: 动作参数（已做变量替换）
    """
    # ========== 打开页面 ==========
    if action == "goto":
        # wait_until 可选：load / domcontentloaded / networkidle
        url = resolve_url(params["url"])
        page.goto(
            url,
            wait_until=params.get("wait_until", "networkidle"),
            timeout=params.get("timeout", 30000),
        )
        logger.info("打开页面: %s", url)

    # ========== 输入文本 ==========
    elif action == "fill":
        # 先等元素可见再填，避免渲染未完成导致 fill 失败
        selector = params["selector"]
        page.wait_for_selector(selector, state="visible",
                               timeout=params.get("timeout", 15000))
        page.fill(selector, str(params.get("value", "")))
        logger.info("填充 %s = %r", selector, params.get("value"))

    # ========== 点击 ==========
    elif action == "click":
        selector = params["selector"]
        # 等元素可点击（可见且未 disabled），比裸 click 稳
        page.wait_for_selector(selector, state="visible",
                               timeout=params.get("timeout", 15000))
        page.click(selector)
        logger.info("点击: %s", selector)

    # ========== 鼠标悬停 ==========
    elif action == "hover":
        selector = params["selector"]
        # 悬停常用来触发下拉菜单/浮层，需元素已渲染且可见
        page.wait_for_selector(selector, state="visible",
                               timeout=params.get("timeout", 15000))
        page.hover(
            selector,
            force=params.get("force", False),
            timeout=params.get("hover_timeout", 15000),
        )
        logger.info("悬停: %s", selector)

    # ========== 键盘按键 ==========
    elif action == "press":
        page.press(params["selector"], params["key"])
        logger.info("按键 %s 于 %s", params["key"], params["selector"])

    # ========== 显式等待元素出现 ==========
    elif action == "wait_for_selector":
        # 常用于等异步渲染的列表/表格加载完成
        page.wait_for_selector(
            params["selector"],
            state=params.get("state", "visible"),
            timeout=params.get("timeout", 15000),
        )
        logger.info("等待元素出现: %s", params["selector"])

    # ========== 固定等待（仅用于兜底，优先用 wait_for_selector） ==========
    elif action == "wait_timeout":
        page.wait_for_timeout(params.get("ms", 1000))
        logger.info("固定等待 %d ms", params.get("ms", 1000))

    # ========== 滚动 ==========
    elif action == "scroll_to_bottom":
        # 触发懒加载：向下滚一屏，具体是否加载完由 extract 前再判断
        page.mouse.wheel(0, params.get("y", 20000))
        page.wait_for_timeout(params.get("after_ms", 800))
        logger.info("向下滚动 %d px", params.get("y", 20000))

    # ========== 截图 ==========
    elif action == "screenshot":
        page.screenshot(path=params["path"],
                        full_page=params.get("full_page", False))
        logger.info("截图: %s", params["path"])

    else:
        raise ValueError(f"不支持的 action: {action}")


def extract_by_selector(page: Page, selector: str,
                        index: int = 0, attr: str = "text") -> str | None:
    """
    按选择器提取单个值。
    - attr="text"  取 inner_text
    - attr="value" 取 input_value
    - 其他         取同名 HTML 属性（href / data-id 等）
    """
    loc = page.locator(selector).nth(index)
    try:
        if attr == "text":
            return loc.inner_text().strip()
        if attr == "value":
            return loc.input_value()
        return loc.get_attribute(attr)
    except Exception as e:
        logger.warning("提取失败 selector=%s index=%s attr=%s err=%s",
                       selector, index, attr, e)
        return None


def extract_table(page: Page, selector: str, row_selector: str = "tr",
                  cell_selector: str = "td", headers: list[str] | None = None,
                  columns: list[dict] | None = None) -> list:
    """
    提取表格内容。
    新增 columns 参数，支持按自定义选择器精准提取每一列的文本或属性。
    """
    container = page.locator(selector).first
    rows = container.locator(row_selector)
    total = rows.count()
    logger.info("表格 %s 共 %d 行", selector, total)

    result = []
    for i in range(total):
        row_loc = rows.nth(i)
        if columns:
            # ★ 模式1：按自定义列配置精准提取（推荐）
            row_data = {}
            for col in columns:
                col_name = col["name"]
                col_sel = col["selector"]
                attr = col.get("attr", "text")
                loc = row_loc.locator(col_sel).first
                try:
                    if attr == "text":
                        row_data[col_name] = loc.inner_text().strip()
                    elif attr == "value":
                        row_data[col_name] = loc.input_value()
                    else:
                        # 提取 HTML 属性，如 data-price, href 等
                        row_data[col_name] = loc.get_attribute(attr)
                except Exception:
                    row_data[col_name] = None
            result.append(row_data)
        else:
            # 模式2：退回之前的按 td 顺序提取
            cells = row_loc.locator(cell_selector)
            values = [cells.nth(j).inner_text().strip() for j in range(cells.count())]
            if headers:
                result.append(dict(zip(headers, values + [None] * (len(headers) - len(values)))))
            else:
                result.append(values)
    return result