# -*- coding: utf-8 -*-
# @Time    : 26/10/19 22:02
# @Author  : yy
# @File    : case_runner.py
# @Software: cbg_test

"""
用例执行器（纯 UI 版，重点）。

流程：
  1. 按 steps 顺序执行 UI 动作（动作实现在 ui_actions.do_action）
  2. 全部步骤完成后，按 extract 规则从当前页面提取变量
  3. 返回变量上下文，交给 case_validator 断言

extract 支持两种规则：
  A. 单元素：{selector, index?, attr?}
  B. 表格：  {type: table, selector, row_selector?, cell_selector?, headers?}
"""

import logging
import re

from playwright.sync_api import Page

from utils.ui_actions import do_action, extract_by_selector, extract_table

logger = logging.getLogger(__name__)


def _subst(value, vars_ctx: dict):
    """
    递归替换参数中的 ${var} 占位符。
    - 字符串：替换所有 ${k} 为 vars_ctx[k]
    - dict/list：递归处理
    - 其他：原样返回
    """
    if isinstance(value, str):
        for k, v in vars_ctx.items():
            value = value.replace(f"${{{k}}}", str(v))
        return value
    if isinstance(value, dict):
        return {k: _subst(v, vars_ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_subst(v, vars_ctx) for v in value]
    return value


def run_steps(page: Page, steps: list[dict], vars_ctx: dict) -> None:
    """
    ★ 顺序执行 UI 步骤。

    每一步：
      1. 取出 action
      2. 把其余参数做 ${var} 替换
      3. 调 do_action 执行
      4. 失败时自动截图并抛错，定位是哪一步挂的
    """
    for i, step in enumerate(steps):
        action = step["action"]
        # 替换该步骤所有参数里的变量
        params = {k: _subst(v, vars_ctx) for k, v in step.items() if k != "action"}
        logger.info("步骤%d: %s %s", i + 1, action, params)

        try:
            do_action(page, action, params)
        except Exception as e:
            # 失败现场截图，报告里能直接看到
            shot = f"reports/step_{i+1}_failed.png"
            try:
                page.screenshot(path=shot, full_page=True)
            except Exception:
                shot = "(截图失败)"
            raise AssertionError(
                f"步骤{i+1} [{action}] 执行失败: {e}，截图: {shot}"
            ) from e


def run_extract(page: Page, extract_rules: dict) -> dict:
    """
    ★ 按 extract 规则从当前页面提取变量。

    规则分支：
      - type == "table"  -> 调 extract_table，提取整表
      - 否则             -> 调 extract_by_selector，提取单元素
    """
    vars_ = {}
    for name, rule in (extract_rules or {}).items():
        if rule.get("type") == "table":
            vars_[name] = extract_table(
                page,
                selector=rule["selector"],
                row_selector=rule.get("row_selector", "tr"),
                cell_selector=rule.get("cell_selector", "td"),
                headers=rule.get("headers"),
                columns=rule.get("columns"),  # ★ 传入 columns
            )
        else:
            # 单元素提取
            vars_[name] = extract_by_selector(
                page,
                selector=rule["selector"],
                index=rule.get("index", 0),
                attr=rule.get("attr", "text"),
            )
        logger.info("提取变量 %s = %r", name, vars_[name])
    return vars_


def _page_position(page: Page, info_selector: str | None):
    """解析 “1/5” 这类页码文本，返回 (当前页, 总页数)；解析失败返回 (None, None)"""
    if not info_selector:
        return None, None
    try:
        text = page.locator(info_selector).first.inner_text()
    except Exception:
        return None, None
    m = re.search(r"(\d+)\s*/\s*(\d+)", text)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _wait_page_rendered(page: Page, rules: dict, prev_page: int | None) -> None:
    """
    点击下一页后等待新一页真正渲染：
      1) 页码文本变化；2) 列表行重新出现；3) 兜底等 wait_after_ms
    """
    timeout = rules.get("page_timeout", 15000)
    info_sel = rules.get("page_info_selector")
    if info_sel and prev_page is not None:
        try:
            page.wait_for_function(
                """([sel, prev]) => {
                    const el = document.querySelector(sel);
                    if (!el) return false;
                    const m = (el.innerText || '').match(/(\\d+)\\s*\\/\\s*(\\d+)/);
                    return !!m && Number(m[1]) !== prev;
                }""",
                arg=[info_sel, prev_page],
                timeout=timeout,
            )
        except Exception:
            logger.warning("分页: 等待页码从 %s 变化超时，按兜底继续", prev_page)

    row_sel = rules.get("row_selector")
    if row_sel:
        page.wait_for_selector(row_sel, state="visible", timeout=timeout)

    page.wait_for_timeout(rules.get("wait_after_ms", 800))


def run_pagination(page: Page, case, ctx: dict) -> dict:
    """
    ★ 翻页抓取：依次点“下一页”，把每页 extract 结果合并进 ctx。
      - list 类型（表格）：追加
      - 单值类型：保留第一页的值
    """
    rules = getattr(case, "pagination", None) or {}
    if not rules or rules.get("enabled", True) is False or not getattr(case, "extract", None):
        return ctx

    next_sel = rules["next_selector"]
    info_sel = rules.get("page_info_selector")
    max_pages = int(rules.get("max_pages", 20))

    cur, total = _page_position(page, info_sel)
    limit = min(total, max_pages) if total else max_pages
    logger.info("分页: 起始 %s/%s，本次最多抓 %d 页", cur, total, limit)

    fetched = 1
    while fetched < limit:
        btn = page.locator(next_sel).first
        if btn.count() == 0:
            logger.info("分页: 未找到下一页按钮，结束")
            break
        if "disabled" in (btn.get_attribute("class") or ""):
            logger.info("分页: 下一页按钮已禁用，结束")
            break

        btn.click()
        _wait_page_rendered(page, rules, cur)

        new_cur, _ = _page_position(page, info_sel)
        if cur is not None and new_cur == cur:
            logger.warning("分页: 页码未前进(cur=%s)，结束避免死循环", cur)
            break
        if new_cur is not None:
            cur = new_cur
        fetched += 1

        page_data = run_extract(page, case.extract)
        for k, v in page_data.items():
            if isinstance(ctx.get(k), list) and isinstance(v, list):
                ctx[k].extend(v)
            elif k not in ctx:
                ctx[k] = v
        sizes = {k: len(v) for k, v in ctx.items() if isinstance(v, list)}
        logger.info("分页: 第 %s 页抓完，累计 %s", cur, sizes)

    return ctx


def run_case(page: Page, case, vars_ctx: dict | None = None) -> dict:
    """
    执行单条用例：
      1. 初始变量（数据驱动注入）
      2. 跑完所有 steps
      3. 提取变量并入上下文
      4. 返回最终变量上下文
    """
    ctx = dict(vars_ctx or {})
    run_steps(page, case.steps, ctx)          # 执行动作
    extracted = run_extract(page, case.extract)  # 步骤结束后取元素
    ctx.update(extracted)
    return run_pagination(page, case, ctx)