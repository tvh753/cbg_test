# -*- coding: utf-8 -*-
# @Time    : 26/10/21 18:44
# @Author  : yy
# @File    : config.py.py
# @Software: cbg_test

# config.py
import base64
import os
import tempfile
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent

# ---------- 浏览器模式 ----------
CBG_HEADLESS = 0
HEADLESS = os.getenv("CBG_HEADLESS", "1") == "1"

# ---------- 真实 URL 配置 ----------
BASE_URL = "https://xyq.cbg.163.com"

# ---------- 大区 / 服务器（写中文即可，拼 URL 时自动做 UTF-8 百分号编码） ----------
# 四川1区 / 嘉陵江  ->  area_name=%E5%9B%9B%E5%B7%9D1%E5%8C%BA&server_name=%E5%98%89%E9%99%B5%E6%B1%9F
AREA_ID = 34
AREA_NAME = "四川1区"
SERVER_ID = 263
SERVER_NAME = "嘉陵江"

LOGIN_ENDPOINT = f"{BASE_URL}/cgi-bin/show_login.py"


def encode_cn_params(encoding: str = "utf-8", **params) -> str:
    """把中文参数按指定编码拼成 query string。

    urlencode 默认 UTF-8 + quote_plus，和 %E5%9B%9B%E5%B7%9D1%E5%8C%BA 一致。
    老页面（query.py）用的是 GBK，需要显式传 encoding="gbk"。
    """
    # 过滤掉 None，避免拼出 xxx=None 这种脏参数
    clean = {k: v for k, v in params.items() if v is not None}
    return urlencode(clean, encoding=encoding)


def build_login_url(
        area_id: int = AREA_ID,
        area_name: str = AREA_NAME,
        server_id: int = SERVER_ID,
        server_name: str = SERVER_NAME,
        endpoint: str = LOGIN_ENDPOINT,
) -> str:
    """用中文大区名 / 服务器名生成登录页 URL（id 一并带上）。"""
    query = encode_cn_params(
        act="show_login",
        area_id=area_id,
        area_name=area_name,
        server_id=server_id,
        server_name=server_name,
    )
    return f"{endpoint}?{query}"


# ---------- 列表 / 查询页 URL ----------
QUERY_ENDPOINT = f"{BASE_URL}/cgi-bin/query.py"

# 装备列表页用的 server_id 与登录页不同（原写死值 263），这里显式区分
LIST_SERVER_ID = 263


def _b64(text: str) -> str:
    """藏宝阁 query.py 的 search_text 是 UTF-8 明文的 base64。"""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def build_type_query_url(
        server_id: int = LIST_SERVER_ID,
        area_id: int = AREA_ID,
        server_name: str = SERVER_NAME,
        search_text: str = "高级必杀",
        page: int = 1,
        endpoint: str = QUERY_ENDPOINT,
) -> str:
    """已售 / 分类列表页 URL。

    注意：query.py 这套老页面吃的是 **GBK** 编码的 server_name，
    所以这里显式 encoding="gbk"；search_text 则是 base64 后放进 URL。
    """
    query = encode_cn_params(
        "gbk",
        act="type_query",
        server_id=server_id,
        areaid=area_id,
        server_name=server_name,
        page=page,
        search_text=_b64(search_text),
    )
    return f"{endpoint}?{query}"


# 等价于原来写死的长 URL，但源文件里看到的是中文
LOGIN_URL = build_login_url()

# 装备列表页（server_id=263，与登录页不同）
EQUIP_LIST_URL = build_login_url(server_id=LIST_SERVER_ID)

# 已售列表页
SOLD_LIST_URL = build_type_query_url()

# 登录成功后必定跳转的页面（推荐页）
SUCCESS_URL = f"{QUERY_ENDPOINT}?act=recommend_search&recommend_type=1"

# 用例 YAML 里可以写 url: "@login"，由 ui_actions 解析成下面的真实地址
URL_PRESETS = {
    "login": LOGIN_URL,
    "equip_list": EQUIP_LIST_URL,
    "sold_list": SOLD_LIST_URL,
    "success": SUCCESS_URL,
}

# ---------- 登录判定 ----------
LOGIN_PAGE_KEYWORD = "show_login"  # URL 里包含这个就是未登录
SUCCESS_PAGE_KEYWORD = "query.py"  # URL 里包含这个就是已登录

# ---------- 超时与路径 ----------
DEFAULT_TIMEOUT = 15000
LOGIN_TIMEOUT_SEC = 180
AUTH_STATE = ROOT / "auth-state.json"
REPORTS_DIR = ROOT / "reports"

# ---------- 临时目录（必须在启动 Playwright 驱动前设置） ----------
# Playwright 启动浏览器时会在系统临时目录 mkdtemp("playwright-artifacts-XXXXXX")。
# 在受限环境（DSH 沙箱 / CI / 安全软件策略）下系统 Temp 不可写，会直接抛：
#   EPERM: operation not permitted,
#   mkdtemp 'C:\\Users\\...\\Temp\\playwright-artifacts-XXXXXX'
# 这里把 TMPDIR/TEMP/TMP 重定向到项目内 .tmp（已加入 .gitignore），
# 并把同一份环境显式传给浏览器子进程，保证驱动和浏览器都写工作区。
TMP_DIR = ROOT / ".tmp"


def _redirect_temp_to_workspace() -> None:
    """把进程级临时目录指向工作区内的 .tmp，避免系统 Temp 只读导致启动失败。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    for var in ("TMPDIR", "TEMP", "TMP"):
        os.environ[var] = str(TMP_DIR)
    # 本进程若已调用过 tempfile.gettempdir()，模块会缓存旧路径，这里一并覆盖
    tempfile.tempdir = str(TMP_DIR)


_redirect_temp_to_workspace()


def browser_env() -> dict:
    """浏览器子进程环境：沿用当前环境，但临时目录固定到工作区。"""
    env = dict(os.environ)
    env.update({"TMPDIR": str(TMP_DIR), "TEMP": str(TMP_DIR), "TMP": str(TMP_DIR)})
    return env
