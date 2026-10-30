# -*- coding: utf-8 -*-
# @Time    : 26/10/18 0:14
# @Author  : yy
# @File    : api_client.py
# @Software: cbg_test

"""
接口数据获取层（重点）。

职责：
- 通过页面上下文中的 request 发请求，自动携带登录 Cookie
- 统一校验业务 code，识别登录失效
- 分页拉全量数据
- 失败重试 + 日志
- 输出统一的原始 dict 结构，交给 data_organizer 清洗

注意：下面 URL、参数、返回结构均为【示例结构】，
实际值必须通过 F12 -> Network 抓包确认后替换。
"""

import time
import logging
from typing import Any
from playwright.sync_api import APIRequestContext

logger = logging.getLogger(__name__)

# 藏宝阁登录失效的常见业务码（抓包确认后按实际值调整）
LOGIN_EXPIRED_CODES = {-101, 401, 1001}

# 单页最大条数、翻页上限（防止死循环）
PAGE_SIZE = 20
MAX_PAGES = 50


class CbgApiError(Exception):
    """接口层自定义异常"""


class CbgApiClient:
    def __init__(self, request_context: APIRequestContext):
        self.req = request_context

    # ---------- 内部：带重试的单次请求 ----------
    def _get(self, url: str, params: dict, retries: int = 3) -> dict:
        """
        发 GET 请求并解析 JSON。
        网络抖动/超时自动重试，业务 code 异常抛错。
        """
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                resp = self.req.get(url, params=params, timeout=15000)
                resp.raise_for_status()          # HTTP 层异常（4xx/5xx）
                data = resp.json()
                return data
            except Exception as e:
                last_err = e
                logger.warning("请求失败(第%d次) url=%s params=%s err=%s",
                               attempt, url, params, e)
                time.sleep(1.5 * attempt)         # 退避等待
        raise CbgApiError(f"请求重试{retries}次仍失败: {url}, err={last_err}")

    # ---------- 内部：业务码校验 ----------
    def _check_code(self, data: dict, scene: str) -> None:
        """校验接口返回业务码；识别登录失效，给出明确提示"""
        code = data.get("code")
        if code in LOGIN_EXPIRED_CODES:
            raise CbgApiError(
                f"[{scene}] 登录已失效(code={code})，"
                f"请重新执行 python run.py --relogin"
            )
        if code != 0:
            raise CbgApiError(f"[{scene}] 业务异常 code={code} msg={data.get('msg')}")

    # ---------- 对外：分页获取全部装备列表 ----------
    def fetch_equipment_list(self, server_name: str) -> list[dict]:
        """
        分页拉取指定服务器的装备列表全量数据。

        :param server_name: 服务器名，如 "建邺城"
        :return: 原始 dict 列表（字段名以实际接口为准）
        """
        url = "/cgi-bin/recommend.py"      # ← 示例，抓包替换
        all_items: list[dict] = []

        for page in range(1, MAX_PAGES + 1):
            params = {
                "server": server_name,
                "page": page,
                "page_size": PAGE_SIZE,
            }
            data = self._get(url, params)
            self._check_code(data, scene=f"装备列表 p{page}")

            # 示例返回结构：{"code":0,"data":{"list":[...], "has_more":true}}
            page_items = (data.get("data") or {}).get("list") or []
            all_items.extend(page_items)
            logger.info("服务器[%s] 第%d页拉取 %d 条", server_name, page, len(page_items))

            # 无数据或已到末页则停止翻页
            has_more = (data.get("data") or {}).get("has_more", False)
            if not page_items or not has_more:
                break

        logger.info("服务器[%s] 接口共获取 %d 条", server_name, len(all_items))
        return all_items

    # ---------- 对外：获取单条详情（可选，用于详情页比对） ----------
    def fetch_equipment_detail(self, equip_id: str) -> dict:
        """按 id 获取单条装备详情，用于详情页字段比对"""
        url = "/cgi-bin/detail.py"          # ← 示例，抓包替换
        data = self._get(url, params={"id": equip_id})
        self._check_code(data, scene=f"装备详情 id={equip_id}")
        return data.get("data") or {}