# 藏宝阁 UI 自动化测试框架 (CBG UI Automation)

基于 **Python + Playwright + Pytest + YAML** 构建的纯 UI 自动化测试框架。旨在通过浏览器页面元素获取数据，进行分类对比、断言验证，并支持通过 YAML 文件编写零代码测试用例。

---

## 📖 核心特性

- **纯 UI 取数**：不依赖任何接口，完全模拟真实用户在浏览器中的点击、输入和页面元素解析。
- **登录态保持**：通过 `storage_state` 保存并复用登录 Cookie，只需扫码一次，后续测试全程免登录。
- **YAML 数据驱动**：测试用例与代码解耦，支持步骤定义、变量提取、动态断言和数据驱动参数化。
- **精准表格提取**：支持按列配置提取 DOM 属性（如 `data-*`）或文本，轻松抓取复杂列表数据。
- **自动防误判等待**：内置等待机制，有效处理异步加载（如“努力加载中”）和懒加载。
- **数据自动保存**：测试结束后，可将页面提取到的数据自动导出为 JSON 格式，方便后续对账。

---

## 🛠️ 环境准备

### 1. 安装依赖

确保你的 Python 版本在 `3.8+`，执行以下命令安装所需库：

```bash
pip install pytest playwright pyyaml pytest-html pandas
```

### 2. 安装浏览器内核

```bash
playwright install chromium
```

---

## 📂 项目目录结构

```text
cbg_test/
├── run.py                          # 启动入口：建目录 -> 处理参数 -> 调 pytest
├── pytest.ini                      # pytest 配置文件
├── config.py                       # 全局配置（域名、超时时间、有头/无头开关）
├── conftest.py                     # 全局 fixture（前置登录拦截、复用登录态）
├── test_data_validation.py         # 纯 UI 数据对比用例（如：列表页 vs 详情页）
├── test_yaml_cases.py              # YAML 驱动执行入口
│
├── yaml_cases/                     # 测试用例存放目录
│   └── case_sold_list.yaml         # 示例用例
│
├── scripts/
│   └── auth_setup.py               # 强制有头登录脚本（生成 auth-state.json）
│
├── utils/                          # 核心工具层
│   ├── ui_actions.py               # ★ UI动作执行、表格提取核心代码
│   ├── case_model.py               # YAML 用例 Dataclass 模型
│   ├── yaml_loader.py              # YAML 加载与字段校验
│   ├── case_runner.py              # 步骤执行器与变量替换
│   └── case_validator.py           # 断言执行器
│
├── data/output/                    # 自动化导出的 JSON 数据存放处
├── reports/                        # HTML 测试报告输出
└── auth-state.json                 # 运行后自动生成的登录态凭证
```

---

## ⚙️ 核心配置说明

### 1. 有头 / 无头模式切换
在 `config.py` 中由环境变量 `CBG_HEADLESS` 控制：
- **无头模式（默认）**：适合在服务器、CI/CD 环境或后台静默运行。
- **有头模式**：适合本地调试脚本、观察页面交互和抓取元素。

**如何开启有头模式？**
```bash
# Windows CMD
set CBG_HEADLESS=0
python run.py

# Mac / Linux
CBG_HEADLESS=0 python run.py
```
*注：`scripts/auth_setup.py` 中的登录步骤强制采用有头模式，以确保能人工扫码。*

### 2. 统一域名配置
藏宝阁的域名必须严格统一，在 `config.py` 中已配置为标准域名：
```python
BASE_URL = "https://xyq.cbg.163.com"
```

---

### 🚀 框架详细执行顺序与生命周期

当你在命令行输入 `python run.py` 时，整个框架的运转分为 **5 个核心阶段**。了解这套顺序有助于你在遇到报错时，快速定位问题发生的阶段。

#### 第一阶段：启动入口与预处理 (`run.py`)
1. **解析参数**：检查命令行是否携带了 `--relogin` 参数。如果有，设置环境变量 `CBG_FORCE_RELOGIN=1`（强制重新登录）。
2. **环境准备**：自动创建 `reports/` 目录，用于存放之后的测试报告和报错截图。
3. **拉起 Pytest**：通过 `subprocess` 启动 `pytest` 核心引擎，并将命令行参数透传过去。

#### 第二阶段：框架初始化与前置登录 (`conftest.py`)
Pytest 启动后，最先加载的是全局配置和 `conftest.py`：
1. **加载配置**：读取 `pytest.ini`（测试发现规则、标记）和 `config.py`（域名、有头/无头开关）。
2. **触发前置登录 (`ensure_login` fixture)**：这是最高优先级（session 级、autouse）的动作：
   - **情形 A（强制登录/无凭证）**：如果没有 `auth-state.json` 或带了 `--relogin`，调用 `scripts/auth_setup.py`。它会弹出一个**有头浏览器**，轮询等待你手动扫码登录。登录成功后，把 Cookie 写入 `auth-state.json`。
   - **情形 B（有凭证校验）**：如果文件存在，启动一个**无头浏览器**访问目标页面，判断是否被踢回登录页。如果失效，转入情形 A。
   - **情形 C（有效凭证）**：校验通过，直接放行。
3. **初始化上下文 (`browser_context` fixture)**：登录态确认后，启动一个 Session 级别的浏览器实例，加载保存的 `auth-state.json`。**这就保证了后续所有测试用例一打开页面就是已登录状态。**

#### 第三阶段：用例收集与校验 (`yaml_loader.py`)
进入用例收集阶段（Collection）：
1. **扫描目录**：`test_yaml_cases.py` 在模块加载时，会调用 `load_cases()` 扫描 `yaml_cases/` 目录下的所有 YAML 文件。
2. **强校验拦截**：对每个 YAML 的字段是否存在、类型是否正确、`action` 是否合法进行**校验**。如果格式写错（比如少写了 `steps`），会在这里直接抛错阻断，不浪费时间去跑浏览器。
3. **生成 CaseInfo**：将合法的 YAML 转成 `CaseInfo` 对象（`utils/case_model.py`）。
4. **数据驱动展开**：如果 YAML 配了 `parametrize`，框架会在这里做笛卡尔积展开，把 1 个 YAML 文件裂变成 N 个具体的测试用例。

#### 第四阶段：用例执行 (`test_yaml_cases.py` -> `case_runner.py`)
开始执行每一个参数化后的具体用例：
1. **分配页面**：从 `browser_context` 中新开一个 `page` 标签页。
2. **执行 UI 动作 (`run_steps`)**：
   - 按顺序读取 YAML 的 `steps`。
   - 解析参数中的 `${变量}` 占位符（如果该变量来自前置提取或 `parametrize`）。
   - 调用 `ui_actions.do_action` 执行操作（如 `goto`、`fill`、`click`）。
   - **异常处理**：如果某一步报错（如超时未找到元素），立刻截图保存到 `reports/`，并中断该用例，标记为失败。
3. **提取数据 (`run_extract`)**：步骤全跑完后，按照 YAML 的 `extract` 规则，从当前页面提取 DOM 元素或整个表格（`#soldList > tbody`）。
4. **保存数据**：将提取到的结构化数据自动导出为 JSON 存入 `data/output/`。
5. **断言校验 (`run_validate`)**：将提取的变量与 YAML 中的 `validate` 预期结果进行比对（如 `length_greater` 或 `contains`）。
6. **清理现场**：断言结束或失败后，关闭当前的 `page`。

#### 第五阶段：生成报告
1. 所有的用例跑完，释放 `browser_context`（关闭浏览器）。
2. `pytest-html` 插件汇总所有成功/失败的数据，并在 `reports/report.html` 生成可视化报告。

---

**一句话总结执行流**：
`run.py` 启动 → `conftest` 拦截并检查/刷新登录态 → `yaml_loader` 扫描并严格校验 YAML 格式 → 按步骤派发 `browser page` 模拟操作并抓取 DOM → 自动存 JSON 并断言 → 产出 HTML 报告。

--- 

## 🚀 快速开始

### 第一次运行：触发登录
首次运行直接执行主入口，如果未找到 `auth-state.json`，程序会自动弹出一个有头浏览器让你扫码。

```bash
python run.py
```
**操作步骤**：
1. 屏幕会自动弹出一个 Chrome 浏览器，显示网易藏宝阁登录页。
2. 请使用网易大神 App 或微信扫码登录。
3. 脚本检测到登录成功后（URL 跳转至 `query.py`），会自动保存 Cookie，**关闭浏览器**。
4. 随后 pytest 会接管，进入无头模式（如果你没改环境变量）执行测试并生成报告。

> **💡 提示**：如果登录过期，或者你想重新更换账号，请执行 `python run.py --relogin`。

---

## 📝 YAML 用例编写指南

在 `yaml_cases/` 目录下新建 `.yaml` 文件，框架启动时会自动扫描并执行。

### 基础模板
```yaml
name: 搜索高级必杀并抓取数据

# 1. UI 操作步骤序列
steps:
  - action: goto
    url: https://xyq.cbg.163.com/cgi-bin/query.py?act=recommend_search&recommend_type=1

  - action: fill
    selector: "input.search-input" 
    value: "高级必杀"

  - action: click
    selector: ".search-btn"

  # 2. 处理动态加载：等待“努力加载中”消失
  - action: wait_for_selector
    selector: "text=努力加载中"
    state: hidden
    timeout: 15000

  # 3. 等待数据表格渲染完毕
  - action: wait_for_selector
    selector: "#soldList > tbody tr"
    timeout: 15000

# 2. 数据提取（执行完上述步骤后，从页面拿数据）
extract:
  sold_rows:
    type: table
    selector: "#soldList > tbody"
    row_selector: "tr"
    # 按列精准提取属性，避免 td 错位
    columns:
      - name: equip_name
        selector: "td:first-child img"
        attr: "data-equip_name"
      - name: price
        selector: "td:first-child img"
        attr: "data_price"

# 3. 断言验证
validate:
  length_greater:
    列表有数据: ['${sold_rows}', 0]
```

### 支持的 `action` 动作清单
| Action | 参数 | 说明 |
|---|---|---|
| `goto` | `url` | 打开网页 |
| `fill` | `selector`, `value` | 输入文本，支持 `${var}` 引用变量 |
| `click` | `selector`, `force` | 点击元素；`force: true` 跳过遮挡/指针事件检查 |
| `hover` | `selector`, `force`, `hover_timeout` | 鼠标悬停；菜单展开后盖住触发元素时用 `force: true` |
| `wait_for_selector`| `selector`, `state` (visible/hidden), `timeout` | 等待元素出现或消失 |
| `wait_timeout` | `ms` | 硬等待毫秒数（不建议常用） |
| `scroll_to_bottom` | `y` | 向下滚动网页 |

### 支持的 `validate` 断言清单
- `epuals` / `equals`：相等对比（支持类型宽松转换，如 `'0'` 和 `0` 视为相等）
- `not_equals`：不相等对比
- `contains`：包含某字段（对于列表类型，匹配任意一行）
- `length_greater`：列表长度大于指定值

### 数据驱动（参数化）
通过 `parametrize` 注入变量，`fill` 的 `value` 中用 `${变量名}` 接收：
```yaml
# 定义测试参数（笛卡尔积）
parametrize:
  username: [test1, test2]
  password: ["123456", "654321"]

steps:
  - action: fill
    selector: "input[name='username']"
    value: "${username}"  # 被替换为 test1 或 test2
  - action: fill
    selector: "input[name='password']"
    value: "${password}"
```

---

## 📊 数据结果导出

每次测试执行完毕后，`extract` 提取到的所有变量（如 `sold_rows` 表格数据）会自动保存到 `data/output/{用例名称}.json` 中。你可以直接打开查看抓取到的结构化数据，用于后续的离线数据比对。

同时，完整的 HTML 测试报告会生成在 `reports/report.html`。

---

## ❓ 常见问题 (FAQ)

**1. 提示 `Timeout waiting for selector "#soldList > tbody tr"` 怎么办？**
- 页面可能还在加载，请确保在 YAML 的 `wait_for_selector` 表格之前，先等“努力加载中”消失。
- 如果搜索动作触发了**新标签页**，当前脚本可能还在旧标签页上。请在 YAML 最后一部加上跳转新网址的 `goto`，或者放弃点击搜索，直接 `goto` 搜索完成后的带参 URL。

**2. 运行过程中报错 `变量 ${xxx} 未定义`？**
- 确保在 `extract` 中已经提取了该变量。
- 如果是数据驱动注入的变量，检查 YAML 末尾是否正确配置了 `parametrize`。

**3. 页面提取数据出现错位或空值？**
- 强烈建议使用 `columns` 配置模式，利用 HTML 中的 `data-*` 属性（如 `data-price`）精准提取，不要依赖 `td` 的第几列去猜。

**4. 自动化脚本被网易识别拦截了怎么办？**
- 藏宝阁存在一定的反爬策略。如果在无头模式下卡住加载不出数据，请在 `conftest.py` 的 `new_context` 中强制加入真实的 User-Agent，或通过 `CBG_HEADLESS=0` 切换有头模式运行。