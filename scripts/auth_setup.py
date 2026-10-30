# -*- coding: utf-8 -*-
# @Time    : 26/10/17 23:13
# @Author  : yy
# @File    : auth_setup.py
# @Software: cbg_test

# scripts/auth_setup.py
"""
登录脚本：必须用有头浏览器（人工登录需要看到页面）。
登录成功后保存 storageState，供 conftest 的 browser_context 复用。
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (AUTH_STATE, LOGIN_URL, LOGIN_TIMEOUT_SEC, SUCCESS_PAGE_KEYWORD,
                    browser_env)


def wait_login_success(page, timeout: int = LOGIN_TIMEOUT_SEC) -> bool:
    """
    轮询判断登录是否成功。
    ★ 严格判定：必须跳转到 query.py 或者页面出现了网易通行证的已登录标志
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            # 条件1：URL 到达了登录后的页面
            if SUCCESS_PAGE_KEYWORD in page.url:
                return True
            # 条件2：或者页面出现用户头像（备用判定，视实际DOM而定）
            if page.locator(".user-info, .header-user").count() > 0:
                return True
        except Exception:
            pass
        page.wait_for_timeout(1000)
    return False


def do_login_and_save() -> Path:
    with sync_playwright() as p:
        # ★ 必须是有头模式，人工扫码
        browser = p.chromium.launch(headless=False, env=browser_env())
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL)
        print("请在弹出的浏览器中扫码登录，脚本会自动检测跳转...")

        if not wait_login_success(page):
            browser.close()
            raise RuntimeError("登录超时或未跳转至成功页面，未保存登录态")

        # 故意多等 2 秒，确保网易的跨域单点登录（SSO）Cookie 全部写入完毕
        print("检测到登录成功，正在等待 Cookie 同步...")
        page.wait_for_timeout(2000)

        context.storage_state(path=str(AUTH_STATE))
        browser.close()
        print(f"登录状态已保存到: {AUTH_STATE}")
        return AUTH_STATE
