import os
import sys
import json
import re
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
import arxiv

# ==================== 配置 ====================
MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")
MOONSHOT_BASE_URL = os.environ.get("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "moonshot-v1-32k")
EMAIL_USER = os.environ.get("EMAIL_USER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")

RESEARCH_AREAS = "AI芯片、机器人芯片、具身智能、Neuro-Symbolic AI"
MAX_RESULTS = 50
BATCH_SIZE = 10


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fetch_papers():
    """抓取 arxiv cs.AR 最近 24h 的论文"""
    client = arxiv.Client(page_size=50, delay_seconds=3, num_retries=3)
    search = arxiv.Search(
        query="cat:cs.AR OR cat:cs.RO",
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
        max_results=MAX_RESULTS,
    )
    results = list(client.results(search))

    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    papers_24h = [r for r in results if _ensure_utc(r.published) >= cutoff_24h]
    return papers_24h


def build_prompt(papers):
    """为 Kimi 构造 Prompt"""
    lines = [
        f"你是一位计算机体系结构领域的研究助理。请阅读以下论文列表，对每篇论文进行分析。",
        f"用户的研究方向是：{RESEARCH_AREAS}。",
        "",
        "请严格输出 JSON Array 格式，不要包含 markdown 代码块标记（如 ```json），只输出纯 JSON 文本：",
        json.dumps(
            [
                {
                    "title": "原文标题",
                    "authors": "作者1, 作者2, 作者3 et al.",
                    "arxiv_url": "https://arxiv.org/abs/xxxx.xxxxx",
                    "summary": "中文总结（2-3句话，说明解决了什么问题、核心方法/结果）",
                    "contributions": ["贡献1", "贡献2"],
                    "score": 8,
                    "highlight": True,
                    "reason": "为什么与用户研究方向高度相关",
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "评分标准：",
        "- 10分：直接属于 AI 芯片 / 机器人芯片 / 具身智能 / Neuro-Symbolic AI 的体系结构工作",
        "- 7-9分：密切相关（如新型加速器、存算一体、边缘智能芯片、机器人感知计算等）",
        "- 4-6分：有一定关联的体系结构/系统工作",
        "- 1-3分：关联较弱或纯理论",
        "",
        "注意：",
        "1. 必须返回合法的 JSON Array，可以直接被 Python json.loads 解析。",
        "2. 每篇论文都要有完整字段。",
        "3. 如果 highlight 为 true，score 应 >= 7，且必须填写 reason。",
        "4. 保持 authors 字段简洁，最多列出前3位作者，后面加 et al.。",
        "",
        "论文数据如下：",
    ]

    for idx, paper in enumerate(papers, 1):
        authors = ", ".join([a.name for a in paper.authors[:3]])
        if len(paper.authors) > 3:
            authors += " et al."
        lines.append(f"[{idx}] 标题: {paper.title}")
        lines.append(f"    作者: {authors}")
        lines.append(f"    链接: {paper.entry_id.replace('http://', 'https://')}")
        # 摘要可能有多行，缩进一下
        abstract = paper.summary.replace("\n", " ")
        lines.append(f"    摘要: {abstract}")
        lines.append("")

    return "\n".join(lines)


def call_kimi(prompt: str) -> list:
    """调用 Moonshot API，返回 JSON list"""
    url = f"{MOONSHOT_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {MOONSHOT_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "你是计算机体系结构专家，擅长精准提炼论文贡献并判断其与特定研究方向的关联度。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    # 去掉可能的 markdown 代码块
    content = re.sub(r"^```json\s*", "", content.strip())
    content = re.sub(r"^```\s*", "", content.strip())
    content = re.sub(r"\s*```$", "", content.strip())

    return json.loads(content)


def analyze_papers(papers):
    """分批调用 Kimi 分析论文"""
    if not papers:
        return []

    all_results = []
    for i in range(0, len(papers), BATCH_SIZE):
        batch = papers[i : i + BATCH_SIZE]
        prompt = build_prompt(batch)
        try:
            results = call_kimi(prompt)
            if isinstance(results, list):
                all_results.extend(results)
            else:
                print(f"Warning: unexpected response type: {type(results)}", file=sys.stderr)
        except Exception as e:
            print(f"Kimi API batch {i//BATCH_SIZE + 1} failed: {e}", file=sys.stderr)
            # 这批降级处理
            for p in batch:
                authors = ", ".join([a.name for a in p.authors[:3]])
                if len(p.authors) > 3:
                    authors += " et al."
                all_results.append(
                    {
                        "title": p.title,
                        "authors": authors,
                        "arxiv_url": p.entry_id,
                        "summary": "（Kimi API 调用失败，未生成总结）",
                        "contributions": [],
                        "score": 0,
                        "highlight": False,
                        "reason": "",
                    }
                )
    return all_results


def build_email_html(analyzed, date_str):
    """生成 HTML 邮件正文"""
    highlights = [p for p in analyzed if p.get("highlight")]
    others = [p for p in analyzed if not p.get("highlight")]
    highlights.sort(key=lambda x: x.get("score", 0), reverse=True)

    total = len(analyzed)
    hl_count = len(highlights)

    def paper_card(p):
        title = p.get("title", "")
        authors = p.get("authors", "")
        url = p.get("arxiv_url", "")
        summary = p.get("summary", "")
        contributions = p.get("contributions", [])
        score = p.get("score", 0)
        reason = p.get("reason", "")
        is_hl = p.get("highlight", False)

        badge = f'<span style="background:#ff4d4f;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;margin-right:8px;">🔥 推荐 {score}分</span>' if is_hl else ''
        reason_html = f'<p style="color:#ff4d4f;font-size:13px;margin:6px 0;"><b>推荐理由：</b>{reason}</p>' if is_hl and reason else ''

        contrib_html = ""
        if contributions:
            contrib_items = "".join([f"<li>{c}</li>" for c in contributions])
            contrib_html = f'<ul style="margin:6px 0;padding-left:18px;font-size:13px;color:#555;">{contrib_items}</ul>'

        return f'''
        <div style="border:1px solid #e8e8e8;border-radius:8px;padding:14px 16px;margin-bottom:14px;background:#fafafa;">
          <div style="margin-bottom:6px;">{badge}<a href="{url}" style="font-size:15px;color:#1890ff;text-decoration:none;font-weight:600;">{title}</a></div>
          <div style="font-size:12px;color:#888;margin-bottom:8px;">{authors}</div>
          <p style="margin:6px 0;font-size:13px;color:#333;line-height:1.6;">{summary}</p>
          {reason_html}
          {contrib_html}
          <div style="margin-top:8px;"><a href="{url}" style="font-size:12px;color:#1890ff;">阅读原文 →</a></div>
        </div>
        '''

    hl_section = ""
    if highlights:
        cards = "".join([paper_card(p) for p in highlights])
        hl_section = f'''
        <h3 style="color:#ff4d4f;border-left:4px solid #ff4d4f;padding-left:10px;">🔥 推荐关注（{hl_count} 篇）</h3>
        {cards}
        '''

    other_section = ""
    if others:
        cards = "".join([paper_card(p) for p in others])
        other_section = f'''
        <h3 style="color:#333;border-left:4px solid #999;padding-left:10px;margin-top:24px;">📄 其他论文（{len(others)} 篇）</h3>
        {cards}
        '''

    html = f"""
    <html>
      <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,Ubuntu,Cantarell,'Open Sans','Helvetica Neue',sans-serif;color:#222;max-width:720px;margin:0 auto;padding:20px;">
        <h2 style="color:#1a1a1a;">Arxiv Daily | {date_str}</h2>
        <p style="font-size:14px;color:#555;">
          今日共 <b>{total}</b> 篇论文，其中 <b style="color:#ff4d4f;">{hl_count}</b> 篇与你关注的方向
          <span style="color:#888;">（{RESEARCH_AREAS}）</span>高度相关。
        </p>
        {hl_section}
        {other_section}
        <hr style="border:none;border-top:1px solid #eee;margin:30px 0;"/>
        <p style="font-size:12px;color:#aaa;text-align:center;">
          由 Arxiv Daily Agent 自动生成 · <a href="https://github.com" style="color:#aaa;">GitHub Actions</a>
        </p>
      </body>
    </html>
    """
    return html


def send_email(subject: str, html_body: str):
    """通过 QQ 邮箱 SMTP 发送邮件"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, [EMAIL_TO], msg.as_string())


def send_alert_email(subject: str, body: str):
    """发送纯文本告警邮件"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=30) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, [EMAIL_TO], msg.as_string())


def main():
    # 检查环境变量
    missing = []
    for key in ("MOONSHOT_API_KEY", "EMAIL_USER", "EMAIL_PASSWORD", "EMAIL_TO"):
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        print(f"Missing env vars: {missing}", file=sys.stderr)
        sys.exit(1)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. 抓取论文
    try:
        papers = fetch_papers()
    except Exception as e:
        print(f"Fetch papers failed: {e}", file=sys.stderr)
        send_alert_email(f"[Arxiv Daily] {today_str} 抓取失败", f"错误信息：{e}\n\n请检查 GitHub Actions 日志。")
        sys.exit(1)

    if not papers:
        send_alert_email(
            f"[Arxiv Daily] {today_str} | 今日暂无新论文",
            "过去 24 小时内 cs.AR OR cs.RO 类别没有新提交的论文。",
        )
        print("No papers found in 48h. Sent notice email.")
        return

    print(f"Fetched {len(papers)} papers.")

    # 2. Kimi 总结
    try:
        analyzed = analyze_papers(papers)
    except Exception as e:
        print(f"Analyze papers failed: {e}", file=sys.stderr)
        # 整体降级：只发标题列表
        fallback_html = f"""
        <html><body>
        <h2>Arxiv Daily | {today_str}</h2>
        <p style="color:red;">Kimi 总结服务暂时异常，今日仅提供论文列表：</p>
        <ul>
        """
        for p in papers:
            url = p.entry_id.replace("http://", "https://")
            title = p.title
            authors = ", ".join([a.name for a in p.authors[:3]])
            fallback_html += f'<li><a href="{url}">{title}</a> — {authors}</li>'
        fallback_html += "</ul></body></html>"
        send_email(f"[Arxiv Daily] {today_str} | {len(papers)} 篇论文", fallback_html)
        return

    # 3. 构建邮件
    html_body = build_email_html(analyzed, today_str)
    hl_count = len([p for p in analyzed if p.get("highlight")])
    subject = f"[Arxiv Daily] {today_str} | {len(analyzed)} 篇论文 · {hl_count} 篇高亮"

    # 4. 发送邮件
    try:
        send_email(subject, html_body)
        print(f"Email sent successfully: {subject}")
    except Exception as e:
        print(f"Send email failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
