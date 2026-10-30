# -*- coding: utf-8 -*-
# @Time    : 26/10/17 22:58
# @Author  : yy
# @File    : conftest.py
# @Software: cbg_test

"""
全局 fixture：
1. ensure_login（session autouse）：前置登录，纯 UI 检测登录态
2. browser_context（session）：加载 auth-state.json，
   从这里 new_page() 的页面都带登录 Cookie —— 这就是"保持登录态"的核心
"""

import logging
import os
import time

import pytest
from playwright.sync_api import sync_playwright

from config import (AUTH_STATE, DEFAULT_TIMEOUT, HEADLESS, LOGIN_PAGE_KEYWORD,
                    SUCCESS_URL, TMP_DIR, browser_env)
from scripts.auth_setup import do_login_and_save

logger = logging.getLogger(__name__)

# ★ 未登录时站点不会自动 302 回登录页，而是先弹一个“去登录”对话框，
#   必须点击其中的按钮才会跳转 show_login —— 所以只判断 URL 会误判为“已登录”。
#   这里把按钮选择器集中管理：语义化选择器在前（抗页面层级变化），原始路径兜底。
LOGIN_DIALOG_BUTTON_SELECTORS = (
    ".dialogCont .js_buttons_warp a",
    "body > div:nth-child(71) > div > div.dialogCont > div > div.js_buttons_warp > div > a",
)


def _find_login_dialog_button(page, timeout_ms: int = 5000):
    """
    轮询等待登录引导对话框里的“去登录”按钮出现（弹窗是异步渲染的）。
    ★ 不按文案过滤：漏判（把已失效当有效）的代价远大于误判，
      只要求按钮可见，并把文案打到日志里便于排查。
    返回 (locator, selector)；超时仍未出现返回 (None, None)。
    """
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for selector in LOGIN_DIALOG_BUTTON_SELECTORS:
            try:
                loc = page.locator(selector).first
                if not loc.is_visible():
                    continue
                logger.info("命中登录引导按钮 %s 文案=%r",
                            selector, loc.inner_text().strip())
                return loc, selector
            except Exception:
                continue
        page.wait_for_timeout(300)
    return None, None


def _is_auth_valid(context) -> bool:
    """
    校验登录态是否有效：
    ★ 访问需要登录的推荐页，出现以下任一情况即判定“无效”：
      1) URL 被重定向回 show_login；
      2) URL 没变，但页面弹出了“去登录”对话框（未登录时不会自动跳转）。
    只有在既没跳转、也没有登录弹窗时才认为 Cookie 仍然有效。
    """
    page = context.new_page()
    try:
        # 访问推荐页，已登录则不会弹出登录引导
        page.goto(SUCCESS_URL, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
        page.wait_for_timeout(2000)          # 等站点异步校验完登录态

        # 情况1：URL 已经被踢回登录页
        if LOGIN_PAGE_KEYWORD in page.url:
            logger.info("校验登录态: URL 已跳转登录页，Cookie 已失效")
            return False

        # 情况2：URL 没变，但弹出了“去登录”对话框 —— 同样是未登录
        button, selector = _find_login_dialog_button(page)
        if button is not None:
            logger.info("校验登录态: 出现登录弹窗按钮(%s)，Cookie 已失效", selector)
            # 顺手点一下，确认确实会跳登录页；点不动也不影响“无效”的结论
            try:
                button.click(timeout=3000)
                page.wait_for_timeout(1500)
                if LOGIN_PAGE_KEYWORD in page.url:
                    logger.info("校验登录态: 点击后已跳转登录页，确认失效")
            except Exception as e:
                logger.debug("点击登录按钮失败(忽略): %s", e)
            return False

        logger.info("校验登录态: 未出现登录弹窗，登录态有效")
        return True
    except Exception as e:
        logger.warning(f"校验异常: {e}")
        return False
    finally:
        page.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_login():
    """前置登录：强制 / 缺失 / 失效时触发 auth_setup"""
    if os.environ.get("CBG_FORCE_RELOGIN") == "1":
        logger.info("收到强制重新登录指令")
        do_login_and_save()
        yield AUTH_STATE
        return

    need_login = not AUTH_STATE.exists()

    if not need_login:
        with sync_playwright() as p:
            # ★ 显式传 env：把 TMPDIR/TEMP/TMP 固定到工作区 .tmp，
            #   否则系统 Temp 不可写时驱动会在 mkdtemp 阶段 EPERM 直接启动失败。
            browser = p.chromium.launch(headless=True, env=browser_env())   # 校验用无头即可
            context = browser.new_context(storage_state=str(AUTH_STATE))
            valid = _is_auth_valid(context)
            browser.close()
        if not valid:
            logger.info("登录态已失效，重新登录")
            need_login = True

    if need_login:
        if os.environ.get("CI"):
            pytest.skip("CI 环境无登录态，请提前注入 auth-state.json")
        logger.info("开始前置登录...")
        do_login_and_save()
    else:
        logger.info("复用有效登录态: %s", AUTH_STATE)

    yield AUTH_STATE


@pytest.fixture(scope="session")
def browser_context(ensure_login):
    """
    ★ 登录态保持的核心：
    - session 级，全程只建一次
    - new_context(storage_state=...) 加载登录 Cookie
    - 用例从这里 new_page()，页面天然是已登录状态
    - headless 由 config.HEADLESS 控制（环境变量 CBG_HEADLESS）
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, env=browser_env())   # ← 无头/有头在此生效
        context = browser.new_context(storage_state=str(AUTH_STATE))
        yield context
        browser.close()