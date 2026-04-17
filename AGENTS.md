# Arxiv Daily Agent — 项目指南

> 本文件面向 AI 编程助手。如果你第一次接触这个项目，请先阅读本文档，再修改代码。

---

## 项目概述

Arxiv Daily Agent 是一个**零本地部署**的 Python 自动化脚本，通过 **GitHub Actions** 定时运行。

它的核心流程是：
1. 每天从 arXiv 抓取 `cs.AR` 和 `cs.RO` 类别最近 24 小时的新论文。
2. 调用 **Kimi (Moonshot) API** 对论文进行中文总结，并根据用户的研究方向打分、高亮推荐。
3. 通过 **QQ 邮箱 SMTP** 发送精美的 HTML 邮件到指定收件箱。

项目非常简单，所有业务逻辑都集中在单个 Python 文件中，没有使用 Web 框架或数据库。

---

## 技术栈

- **语言**: Python 3.11
- **核心依赖**:
  - `arxiv==2.1.0` — 用于查询 arXiv API
  - `requests>=2.31.0` — 用于调用 Moonshot API
  - `legacy-cgi>=2.6` — 兼容性依赖
- **运行平台**: GitHub Actions (`ubuntu-latest`)
- **邮件服务**: QQ 邮箱 SMTP (端口 465，SSL)

---

## 项目结构

```
.
├── .github/workflows/daily-arxiv.yml   # GitHub Actions 定时工作流配置
├── main.py                              # 核心脚本（抓取 + AI总结 + 邮件发送）
├── requirements.txt                     # Python 依赖列表
├── README.md                            # 面向用户的部署说明（中文）
└── AGENTS.md                            # 本文件
```

**没有测试目录、没有多模块分包、没有构建产物。** 代码组织完全扁平化。

---

## 代码组织与关键模块

所有功能都在 `main.py` 中，按以下函数划分：

| 函数 | 职责 |
|------|------|
| `fetch_papers()` | 使用 `arxiv` 库查询 `cs.AR OR cs.RO`，返回最近 24h 的论文列表 |
| `build_prompt(papers)` | 为 Kimi API 构造 Prompt，要求返回固定格式的 JSON Array |
| `call_kimi(prompt)` | 调用 Moonshot `/chat/completions` 接口，解析并清洗返回的 JSON |
| `analyze_papers(papers)` | 分批（每批 `BATCH_SIZE=10`）调用 `call_kimi`，有异常时降级为简单信息 |
| `build_email_html(analyzed, date_str)` | 根据分析结果渲染 HTML 邮件正文，区分"推荐关注"和"其他论文" |
| `send_email(subject, html_body)` | 通过 QQ SMTP 发送 HTML 邮件 |
| `send_alert_email(subject, body)` | 发送纯文本告警/通知邮件 |
| `main()` | 主控流程：检查环境变量 → 抓论文 → AI 总结 → 发邮件，包含多级降级处理 |

### 顶部配置常量

在 `main.py` 顶部，有一组从环境变量读取的配置和硬编码常量：

- `MOONSHOT_API_KEY` / `MOONSHOT_BASE_URL` / `MODEL_NAME` — Kimi API 配置
- `EMAIL_USER` / `EMAIL_PASSWORD` / `EMAIL_TO` — 邮件配置
- `RESEARCH_AREAS` — 研究方向关键词（默认：AI芯片、机器人芯片、具身智能、Neuro-Symbolic AI）
- `MAX_RESULTS = 50` — 每次从 arXiv 最多抓取的论文数
- `BATCH_SIZE = 10` — 每批送给 Kimi 分析的论文数量

> 注意：当前代码中的 `fetch_papers()` 实际查询条件是 `cat:cs.AR OR cat:cs.RO`，与 README 中只写 `cs.AR` 略有差异。修改时以 `main.py` 中的 query 字符串为准。

---

## 运行与部署

### GitHub Actions 工作流

文件：`.github/workflows/daily-arxiv.yml`

- **触发方式**: 
  - `schedule: cron("0 0 * * *")` — 每天 UTC 00:00 自动运行（北京时间 08:00）
  - `workflow_dispatch` — 支持在 GitHub 网页上手动触发
- **运行步骤**: 
  1. `actions/checkout@v4` 检出代码
  2. `actions/setup-python@v5` 设置 Python 3.11
  3. `pip install -r requirements.txt` 安装依赖
  4. `python main.py` 执行脚本

### 本地运行（调试用）

如果你想在本地测试，需要导出必要的环境变量，然后直接运行：

```bash
export MOONSHOT_API_KEY="your-key"
export EMAIL_USER="123456789@qq.com"
export EMAIL_PASSWORD="your-smtp-password"
export EMAIL_TO="xxx@foxmail.com"

python main.py
```

可选环境变量（都有默认值，非必填）：
- `MOONSHOT_BASE_URL`（默认 `https://api.moonshot.cn/v1`）
- `MODEL_NAME`（默认 `moonshot-v1-32k`）

---

## 开发约定

- **单文件原则**: 目前所有逻辑都在 `main.py`。新增功能时，如果改动不大，继续放在 `main.py` 中；只有当逻辑显著复杂化时，才考虑拆分为模块。
- **中文注释**: 代码中的注释和文档均使用中文。保持这一风格。
- **降级机制**: 任何外部依赖（arXiv、Kimi API、SMTP）失败时，都应提供降级方案（如发送告警邮件或原始列表），确保用户不会完全收不到信息。添加新功能时请继承这一设计哲学。
- **环境变量驱动**: 所有可能因用户/环境而变化的配置，都应通过环境变量注入，而不是硬编码。GitHub Actions 中通过 `secrets` 传入。

---

## 测试策略

**当前项目没有单元测试或集成测试。**

由于项目规模极小且依赖外部 API（arXiv + Moonshot），最可靠的"测试"方式是：
1. 在本地设置环境变量后运行 `python main.py`。
2. 检查邮件是否收到、内容格式是否正确。
3. 在 GitHub Actions 中使用 `workflow_dispatch` 手动触发一次工作流，验证 CI 环境是否正常。

如果你要添加测试，建议：
- 为 `build_prompt()` 和 `build_email_html()` 这类纯函数编写简单的 `unittest` 或 `pytest`。
- 对涉及网络请求的部分使用 `unittest.mock` 进行 Mock。

---

## 安全注意事项

1. **Secrets 管理**: `MOONSHOT_API_KEY` 和 `EMAIL_PASSWORD` 是敏感信息，必须存储在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 中，绝不要提交到代码仓库。
2. **QQ 邮箱密码**: `EMAIL_PASSWORD` 不是 QQ 登录密码，而是 QQ 邮箱的 **SMTP 授权码**。
3. **Prompt 注入**: `build_prompt()` 直接将论文标题和摘要拼接到 Prompt 中。由于内容来自可信的 arXiv 官方源，当前风险可控，但如未来引入不可信输入源，需注意 Prompt 注入问题。
4. **API 超时**: `call_kimi()` 中设置了 `timeout=180`，`send_email()` 中设置了 `timeout=30`。调整时请勿设置过长，以免 GitHub Actions  Runner 被长时间挂起。

---

## 常见修改场景

| 场景 | 修改位置 |
|------|----------|
| 调整研究方向关键词 | `main.py` 顶部的 `RESEARCH_AREAS` |
| 增加/减少搜索的 arXiv 类别 | `main.py` 中 `fetch_papers()` 的 `query` 参数 |
| 修改每日推送时间 | `.github/workflows/daily-arxiv.yml` 中的 `cron` 表达式 |
| 更换邮件服务商 | `main.py` 中 `send_email()` / `send_alert_email()` 的 SMTP 服务器和端口 |
| 调整每批分析的论文数量 | `main.py` 顶部的 `BATCH_SIZE` |

---

## 外部链接

- [Moonshot 开放平台](https://platform.moonshot.cn/) — 获取 Kimi API Key
- [arXiv API 文档](https://info.arxiv.org/help/api/index.html)
- [QQ 邮箱 SMTP 设置说明](https://service.mail.qq.com/)
