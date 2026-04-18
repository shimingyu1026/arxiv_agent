# arXiv Daily Agent

每天自动抓取 arXiv **计算机体系结构 (cs.AR)** 与 **机器人学 (cs.RO)** 的最新论文，通过 **Kimi API** 智能总结并高亮与你研究方向相关的文章，最后推送到你的 QQ / Foxmail 邮箱。

**完全零本地部署**，基于 GitHub Actions 定时运行。

---

## ✨ 功能

- 📰 每日自动抓取 `cs.AR` 与 `cs.RO` 最新论文（北京时间每天早上 8:00 推送）
- 🤖 使用 Kimi (Moonshot) API 生成中文总结
- 🔥 根据你的研究方向自动打分并高亮推荐：
  - AI 芯片
  - 机器人芯片
  - 具身智能
  - Neuro-Symbolic AI
- 📧 通过 QQ 邮箱 SMTP 发送精美 HTML 邮件
- 🛡️ 多重降级：API 异常时自动发送原始论文列表，不会漏掉信息

---

## 🚀 快速部署

### 1. 创建 GitHub 仓库

把本代码推送到你的 GitHub 仓库（例如 `yourname/arxiv-daily-agent`）。

### 2. 配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions**，点击 **New repository secret**，添加以下 4 个 secret：

| Secret 名称 | 必填 | 说明 |
|-------------|:--:|------|
| `MOONSHOT_API_KEY` | ✅ | 你的 Kimi API Key（从 [Moonshot 开放平台](https://platform.moonshot.cn/) 获取） |
| `MOONSHOT_BASE_URL` | ❌ | Kimi API Base URL，默认为 `https://api.moonshot.cn/v1` |
| `MODEL_NAME` | ❌ | 使用的模型名称，默认为 `moonshot-v1-32k` |
| `RESEARCH_AREAS` | ❌ | 研究方向关键词，默认为 `AI芯片、机器人芯片、具身智能、Neuro-Symbolic AI` |
| `EMAIL_USER` | ✅ | 发件 QQ 邮箱地址，例如 `123456789@qq.com` |
| `EMAIL_PASSWORD` | ✅ | **QQ 邮箱 SMTP 授权码**（不是 QQ 登录密码！在 QQ 邮箱设置 → 账户 → 开启 SMTP 后获取） |
| `EMAIL_TO` | ✅ | 收件地址，例如 `xxx@foxmail.com` |

### 3. 手动测试

进入仓库 **Actions → Daily arXiv Digest**，点击 **Run workflow**，等几分钟后检查你的收件箱。

### 4. 等待每日自动推送

工作流默认每天早上 **北京时间 08:00** 自动运行。如果某天没有新论文，你会收到一封"今日暂无新论文"的提示邮件。

---

## ⚙️ 自定义配置

研究方向可通过环境变量 `RESEARCH_AREAS` 调整，无需修改代码。默认值：

```
AI芯片、机器人芯片、具身智能、Neuro-Symbolic AI
```

默认搜索范围已包含 `cs.AR` 与 `cs.RO`，如需调整，修改 `fetch_papers()` 中的 query：

```python
query="cat:cs.AR OR cat:cs.RO",
```

---

## 📂 文件说明

```
.
├── .github/workflows/daily-arxiv.yml   # GitHub Actions 定时任务
├── main.py                              # 核心脚本（抓取 + 总结 + 发邮件）
├── requirements.txt                     # Python 依赖
├── README.md                            # 本说明文档
└── AGENTS.md                            # 面向 AI 助手的项目指南
```

---

## 💡 常见问题

**Q: 每天大约消耗多少 Kimi API Token？**  
A: `cs.AR` 与 `cs.RO` 合计通常一天 5–20 篇论文。每篇摘要约几百 Token，加上 Prompt，每天总消耗通常在 5k–30k Token 之间，订阅套餐完全够用。

**Q: 邮件进了垃圾箱怎么办？**  
A: 在 QQ 邮箱或 foxmail 中把发件地址标记为"不是垃圾邮件"，或加入白名单。

**Q: 能否把历史总结存档到仓库里？**  
A: 当前版本设计为"只发邮件不存档"，以保持仓库简洁。如果你需要存档，可以在 `main.py` 中加入写 Markdown 文件并自动 `git commit` 的逻辑。

---

Enjoy your daily arXiv digest! 🎉
