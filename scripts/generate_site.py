"""
generate_site.py — 从 benchmarks.yaml 生成 docs/index.html 静态页面
用法：python scripts/generate_site.py
"""

import json
import re
import yaml
from pathlib import Path
from datetime import date

ROOT         = Path(__file__).parent.parent
YAML_PATH    = ROOT / "data" / "benchmarks.yaml"
OUTPUT_PATH  = ROOT / "docs" / "index.html"
HISTORY_DIR  = ROOT / "data" / "history"


def load_data():
    with open(YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def name_to_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_history(name: str) -> list[dict]:
    path = HISTORY_DIR / f"{name_to_slug(name)}.yaml"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def score_to_float(score_str):
    """把 '94.6%' 转为 94.6，空字符串返回 None"""
    if not score_str:
        return None
    return float(score_str.rstrip("%"))


def score_color(score_str):
    """根据分数返回颜色 class"""
    v = score_to_float(score_str)
    if v is None:
        return "score-unknown"
    if v >= 90:
        return "score-high"
    if v >= 60:
        return "score-mid"
    return "score-low"


def render_history_rows(history: list[dict]) -> str:
    """渲染历史记录子行（历史从旧到新，最新一条是当前 SOTA）"""
    if not history:
        return ""
    rows = ""
    for i, entry in enumerate(history):
        is_current = (i == len(history) - 1)
        score = entry.get("score", "—")
        model = entry.get("model", "—") or "—"
        bm_date = entry.get("date", "—") or "—"
        recorded = entry.get("recorded_at", "") or ""
        label = '<span style="color:var(--green);font-size:11px">● 当前</span>' if is_current else ""
        rows += f"""
          <tr>
            <td style="color:var(--muted);font-size:12px;padding-left:8px">{recorded}</td>
            <td><span class="score {score_color(score)}" style="font-size:12px">{score}</span> {label}</td>
            <td style="font-size:12px">{model}</td>
            <td style="color:var(--muted);font-size:12px">{bm_date}</td>
          </tr>"""
    return rows


def render_benchmark_row(bm):
    name = bm.get("name", "")
    desc = bm.get("description", "")
    methodology = bm.get("methodology", "")
    score = bm.get("sota_score", "") or ""
    model = bm.get("sota_model", "") or ""
    bm_date = bm.get("sota_date", "") or ""
    source = bm.get("source_url", "") or ""
    leaderboard = bm.get("official_leaderboard", "") or ""

    history = load_history(name)

    is_self_reported = bm.get("is_self_reported", True)
    score_cls = score_color(score)
    credibility = '<span class="badge-self-reported" title="厂商自报数据，未经第三方独立验证">⚠ 自报</span>' if is_self_reported else '<span class="badge-verified" title="经第三方独立验证">✓ 验证</span>'
    score_html = f'<span class="score {score_cls}">{score if score else "—"}</span> {credibility if score else ""}'

    links = []
    if source:
        links.append(f'<a href="{source}" target="_blank" rel="noopener">论文</a>')
    if leaderboard:
        links.append(f'<a href="{leaderboard}" target="_blank" rel="noopener">Leaderboard</a>')

    slug = name_to_slug(name)
    if len(history) > 1:
        links.append(f'<a class="history-toggle" data-target="hist-{slug}" href="#">历史({len(history)})</a>')
        links.append(f'<a class="chart-btn" data-slug="{slug}" data-name="{name}" href="#">📈</a>')

    links_html = " · ".join(links) if links else "—"
    model_html = model if model else "—"
    date_html = bm_date if bm_date else "—"
    tooltip = f'title="{methodology}"' if methodology else ""

    history_row = ""
    if len(history) > 1:
        hist_rows = render_history_rows(history)
        history_row = f"""
      <tr id="hist-{slug}" class="history-row" style="display:none">
        <td colspan="6" style="padding:0 14px 10px 28px">
          <table style="width:100%;border-collapse:collapse">
            <thead>
              <tr>
                <th style="font-size:11px;color:var(--muted);padding:4px 8px;text-align:left">记录时间</th>
                <th style="font-size:11px;color:var(--muted);padding:4px 8px;text-align:left">分数</th>
                <th style="font-size:11px;color:var(--muted);padding:4px 8px;text-align:left">模型</th>
                <th style="font-size:11px;color:var(--muted);padding:4px 8px;text-align:left">来源日期</th>
              </tr>
            </thead>
            <tbody>{hist_rows}</tbody>
          </table>
        </td>
      </tr>"""

    return f"""
      <tr>
        <td class="bm-name" {tooltip}>{name}</td>
        <td class="bm-desc">{desc}</td>
        <td class="bm-score">{score_html}</td>
        <td class="bm-model">{model_html}</td>
        <td class="bm-date">{date_html}</td>
        <td class="bm-links">{links_html}</td>
      </tr>{history_row}"""


def render_category_section(cat):
    cat_name = cat["name"]
    cat_desc = cat.get("description", "")
    benchmarks = cat.get("benchmarks", [])
    cat_id = cat_name.replace("/", "-").replace(" ", "-")

    rows = "".join(render_benchmark_row(bm) for bm in benchmarks)

    return f"""
    <section class="category" id="cat-{cat_id}" data-category="{cat_name}">
      <div class="category-header">
        <h2>{cat_name}</h2>
        <p class="category-desc">{cat_desc}</p>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Benchmark</th>
              <th>简介</th>
              <th>当前 SOTA</th>
              <th>SOTA 模型</th>
              <th>更新日期</th>
              <th>链接</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
      </div>
    </section>"""


def build_filter_buttons(categories):
    buttons = ['<button class="filter-btn active" data-filter="all">全部</button>']
    for cat in categories:
        name = cat["name"]
        buttons.append(f'<button class="filter-btn" data-filter="{name}">{name}</button>')
    return "\n".join(buttons)


def build_all_benchmarks_json(categories):
    """把所有 benchmark 扁平化为 JSON，供前端模型搜索用"""
    all_bms = []
    for cat in categories:
        for bm in cat.get("benchmarks", []):
            all_bms.append({
                "category": cat["name"],
                "name": bm.get("name", ""),
                "sota_score": bm.get("sota_score", "") or "",
                "sota_model": bm.get("sota_model", "") or "",
                "sota_date": bm.get("sota_date", "") or "",
                "source_url": bm.get("source_url", "") or "",
                "official_leaderboard": bm.get("official_leaderboard", "") or "",
            })
    return json.dumps(all_bms, ensure_ascii=False)


def build_history_json(categories):
    """构建 {slug: {name, points:[{date,score,model}]}} 供 Chart.js 使用"""
    result = {}
    for cat in categories:
        for bm in cat.get("benchmarks", []):
            name = bm.get("name", "")
            slug = name_to_slug(name)
            history = load_history(name)
            if len(history) < 2:
                continue
            points = []
            for entry in history:
                score_str = entry.get("score", "")
                try:
                    score = float(str(score_str).rstrip("%"))
                except (ValueError, AttributeError):
                    continue
                points.append({
                    "date":  entry.get("date", "") or "",
                    "score": score,
                    "model": entry.get("model", "") or "",
                })
            if len(points) >= 2:
                result[slug] = {"name": name, "points": points}
    return json.dumps(result, ensure_ascii=False)


def generate_html(data):
    categories = data.get("categories", [])
    today = date.today().strftime("%Y-%m-%d")
    filter_buttons = build_filter_buttons(categories)
    sections = "".join(render_category_section(cat) for cat in categories)
    bm_json = build_all_benchmarks_json(categories)
    history_json = build_history_json(categories)
    total = sum(len(c.get("benchmarks", [])) for c in categories)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AgentPulse</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg: #0f1117;
      --surface: #1a1d27;
      --border: #2a2d3e;
      --text: #e2e8f0;
      --muted: #8892a4;
      --accent: #6366f1;
      --accent-light: #818cf8;
      --green: #22c55e;
      --yellow: #eab308;
      --red: #ef4444;
      --radius: 8px;
    }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.6;
    }}

    /* ── Header ── */
    header {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 24px 40px;
    }}
    .header-inner {{
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      align-items: flex-end;
      gap: 16px;
      flex-wrap: wrap;
    }}
    header h1 {{
      font-size: 22px;
      font-weight: 700;
      color: var(--accent-light);
      letter-spacing: -0.5px;
    }}
    header h1 span {{ color: var(--text); }}
    .header-meta {{
      color: var(--muted);
      font-size: 13px;
      margin-left: auto;
    }}
    .header-meta strong {{ color: var(--text); }}

    /* ── Tagline ── */
    .tagline {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 12px 40px 0;
      color: var(--muted);
      font-size: 13px;
    }}

    /* ── Filter bar ── */
    .filter-bar {{
      position: sticky;
      top: 0;
      z-index: 10;
      background: var(--bg);
      border-bottom: 1px solid var(--border);
      padding: 12px 40px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .filter-btn {{
      background: var(--surface);
      color: var(--muted);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 4px 14px;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .filter-btn:hover {{ border-color: var(--accent); color: var(--accent-light); }}
    .filter-btn.active {{
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 600;
    }}

    /* ── Model search ── */
    .model-search {{
      max-width: 1200px;
      margin: 24px auto 0;
      padding: 0 40px;
    }}
    .model-search h3 {{
      font-size: 14px;
      color: var(--muted);
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .search-row {{
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
    }}
    .search-row input {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      color: var(--text);
      padding: 8px 14px;
      font-size: 14px;
      width: 300px;
      outline: none;
      transition: border-color 0.15s;
    }}
    .search-row input:focus {{ border-color: var(--accent); }}
    .search-row button {{
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: var(--radius);
      padding: 8px 18px;
      font-size: 14px;
      cursor: pointer;
    }}
    #model-results {{ display: none; }}
    #model-results table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 4px;
    }}
    #model-results th, #model-results td {{
      padding: 8px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }}
    #model-results th {{ color: var(--muted); font-weight: 500; }}

    /* ── Main ── */
    main {{
      max-width: 1200px;
      margin: 24px auto;
      padding: 0 40px 60px;
    }}

    /* ── Category section ── */
    .category {{
      margin-bottom: 40px;
    }}
    .category.hidden {{ display: none; }}
    .category-header {{
      margin-bottom: 12px;
    }}
    .category-header h2 {{
      font-size: 16px;
      font-weight: 700;
      color: var(--accent-light);
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    .category-header h2::before {{
      content: "";
      display: inline-block;
      width: 3px;
      height: 16px;
      background: var(--accent);
      border-radius: 2px;
    }}
    .category-desc {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 4px;
    }}

    /* ── Table ── */
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: var(--radius);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    thead tr {{
      background: var(--surface);
    }}
    th {{
      padding: 10px 14px;
      text-align: left;
      font-size: 12px;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }}
    tbody tr {{
      transition: background 0.1s;
    }}
    tbody tr:hover {{ background: var(--surface); }}
    tbody tr + tr td {{ border-top: 1px solid var(--border); }}
    td {{
      padding: 10px 14px;
      vertical-align: top;
    }}
    .bm-name {{
      font-weight: 600;
      white-space: nowrap;
      color: var(--text);
      cursor: default;
    }}
    .bm-desc {{
      color: var(--muted);
      font-size: 13px;
      max-width: 320px;
      line-height: 1.4;
    }}
    .bm-score {{ white-space: nowrap; }}
    .bm-model {{ white-space: nowrap; font-size: 13px; }}
    .bm-date {{ white-space: nowrap; color: var(--muted); font-size: 13px; }}
    .bm-links a {{
      color: var(--accent-light);
      text-decoration: none;
      font-size: 13px;
    }}
    .bm-links a:hover {{ text-decoration: underline; }}

    /* ── Score badges ── */
    .score {{
      display: inline-block;
      padding: 2px 10px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 13px;
    }}
    .score-high  {{ background: rgba(34,197,94,0.15);  color: var(--green); }}
    .score-mid   {{ background: rgba(234,179,8,0.15);  color: var(--yellow); }}
    .score-low   {{ background: rgba(239,68,68,0.15);  color: var(--red); }}
    .score-unknown {{ background: var(--surface); color: var(--muted); }}

    /* ── Credibility badges ── */
    .badge-self-reported {{
      font-size: 11px;
      color: #f59e0b;
      background: rgba(245,158,11,0.1);
      border: 1px solid rgba(245,158,11,0.3);
      border-radius: 4px;
      padding: 1px 5px;
      vertical-align: middle;
      cursor: help;
    }}
    .badge-verified {{
      font-size: 11px;
      color: var(--green);
      background: rgba(34,197,94,0.1);
      border: 1px solid rgba(34,197,94,0.3);
      border-radius: 4px;
      padding: 1px 5px;
      vertical-align: middle;
    }}

    /* ── History rows ── */
    .history-row td {{ background: rgba(99,102,241,0.04); }}
    a.history-toggle {{
      color: var(--muted);
      font-size: 12px;
      text-decoration: none;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1px 8px;
    }}
    a.history-toggle:hover {{ color: var(--accent-light); border-color: var(--accent); }}

    /* ── Footer ── */
    footer {{
      text-align: center;
      color: var(--muted);
      font-size: 12px;
      padding: 24px;
      border-top: 1px solid var(--border);
    }}
    footer a {{ color: var(--accent-light); text-decoration: none; }}

    /* ── SOTA 趋势图 Modal ── */
    .modal-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.7);
      z-index: 100;
      align-items: center;
      justify-content: center;
    }}
    .modal-overlay.open {{ display: flex; }}
    .modal-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 24px;
      width: min(620px, 92vw);
      position: relative;
    }}
    .modal-close {{
      position: absolute;
      top: 10px;
      right: 14px;
      background: none;
      border: none;
      color: var(--muted);
      font-size: 22px;
      cursor: pointer;
      line-height: 1;
    }}
    .modal-close:hover {{ color: var(--text); }}
    .modal-title {{
      font-size: 15px;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 16px;
    }}
    a.chart-btn {{
      color: var(--muted);
      font-size: 13px;
      text-decoration: none;
    }}
    a.chart-btn:hover {{ color: var(--accent-light); }}

    /* ── 中文模型专栏 ── */
    .cn-section {{
      max-width: 1200px;
      margin: 16px auto 0;
      padding: 0 40px;
    }}
    .cn-toggle {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 10px 16px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text);
      font-size: 14px;
      font-weight: 500;
      width: 100%;
      text-align: left;
      transition: border-color 0.15s;
    }}
    .cn-toggle:hover {{ border-color: var(--accent); }}
    .cn-toggle .arrow {{ margin-left: auto; transition: transform 0.2s; font-style: normal; }}
    .cn-toggle.open .arrow {{ transform: rotate(90deg); }}
    .cn-body {{ display: none; padding: 14px 0 0; }}
    .cn-body.open {{ display: block; }}
    .cn-body > p {{ color: var(--muted); font-size: 13px; margin-bottom: 12px; }}
    .cn-stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }}
    .cn-stat {{
      background: rgba(99,102,241,0.08);
      border: 1px solid rgba(99,102,241,0.2);
      border-radius: var(--radius);
      padding: 6px 14px;
      font-size: 13px;
    }}
    .cn-stat strong {{ color: var(--accent-light); }}

    /* ── 移动端适配 ── */
    @media (max-width: 768px) {{
      header {{ padding: 16px; }}
      .tagline, .model-search, .cn-section {{ padding-left: 16px; padding-right: 16px; }}
      .filter-bar {{ padding: 10px 16px; gap: 6px; }}
      main {{ padding: 0 16px 40px; }}
      .header-meta {{ display: none; }}
      .filter-btn {{ font-size: 12px; padding: 3px 10px; }}
      .bm-desc, .bm-date {{ display: none; }}
      .search-row {{ flex-wrap: wrap; }}
      .search-row input {{ width: 100%; }}
      .search-row button {{ width: 100%; }}
      .cn-stats {{ gap: 8px; }}
    }}
  </style>
</head>
<body>

<header>
  <div class="header-inner">
    <h1>Agent<span>Pulse</span></h1>
    <div class="header-meta">
      追踪 <strong>{total}</strong> 个 Benchmark &nbsp;·&nbsp; 最后更新 <strong>{today}</strong>
    </div>
  </div>
</header>

<div class="tagline">
  专注 Agent 方向的 SOTA 实时追踪 &nbsp;—&nbsp;
  关注"<em>现在谁最好、好多少、什么时候变化的</em>"。
  所有数据均来自公开来源，详见各 benchmark 官方网站。
</div>

<div class="filter-bar">
  {filter_buttons}
</div>

<div class="cn-section">
  <button class="cn-toggle" onclick="toggleCnSection(this)">
    🇨🇳 中文模型专栏 <em class="arrow">▶</em>
  </button>
  <div class="cn-body" id="cn-body">
    <p>以下统计基于当前 SOTA 数据，筛选 DeepSeek / Qwen / Kimi / GLM / Yi / InternLM 等中文模型。</p>
    <div class="cn-stats" id="cn-stats"></div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Benchmark</th>
            <th>中文模型 SOTA</th>
            <th>分数</th>
            <th>日期</th>
          </tr>
        </thead>
        <tbody id="cn-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<div class="model-search">
  <h3>模型横向对比</h3>
  <div class="search-row">
    <input type="text" id="model-input" placeholder="输入模型名，如 Claude Sonnet 4.5" />
    <button onclick="searchModel()">查询</button>
  </div>
  <div id="model-results">
    <table>
      <thead><tr><th>维度</th><th>Benchmark</th><th>SOTA 分数</th><th>更新日期</th><th>链接</th></tr></thead>
      <tbody id="model-tbody"></tbody>
    </table>
  </div>
</div>

<main>
  {sections}
</main>

<div class="modal-overlay" id="chart-modal">
  <div class="modal-box">
    <button class="modal-close" onclick="closeChartModal()">×</button>
    <div class="modal-title" id="chart-title">SOTA 历史趋势</div>
    <canvas id="chart-canvas"></canvas>
  </div>
</div>

<footer>
  <a href="https://github.com/HappyMayzhang/agentpulse" target="_blank" rel="noopener">GitHub</a>
  &nbsp;·&nbsp; 数据来自各 benchmark 官方网站 &nbsp;·&nbsp; 发现错误？欢迎提 PR
</footer>

<script>
  const BENCHMARKS = {bm_json};
  const HISTORY    = {history_json};

  // ── Filter ──
  document.querySelectorAll(".filter-btn").forEach(btn => {{
    btn.addEventListener("click", () => {{
      document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const filter = btn.dataset.filter;
      document.querySelectorAll(".category").forEach(sec => {{
        if (filter === "all" || sec.dataset.category === filter) {{
          sec.classList.remove("hidden");
        }} else {{
          sec.classList.add("hidden");
        }}
      }});
    }});
  }});

  // ── Model search ──
  function searchModel() {{
    const query = document.getElementById("model-input").value.trim().toLowerCase();
    const tbody = document.getElementById("model-tbody");
    const resultsDiv = document.getElementById("model-results");
    tbody.innerHTML = "";
    if (!query) return;

    const matches = BENCHMARKS.filter(bm =>
      bm.sota_model && bm.sota_model.toLowerCase().includes(query)
    );

    if (matches.length === 0) {{
      tbody.innerHTML = '<tr><td colspan="5" style="color:var(--muted);text-align:center">未找到匹配的模型</td></tr>';
    }} else {{
      matches.forEach(bm => {{
        const links = [];
        if (bm.source_url) links.push(`<a href="${{bm.source_url}}" target="_blank">论文</a>`);
        if (bm.official_leaderboard) links.push(`<a href="${{bm.official_leaderboard}}" target="_blank">Leaderboard</a>`);
        const scoreVal = parseFloat(bm.sota_score);
        let cls = "score-unknown";
        if (!isNaN(scoreVal)) {{
          cls = scoreVal >= 90 ? "score-high" : scoreVal >= 60 ? "score-mid" : "score-low";
        }}
        tbody.innerHTML += `
          <tr>
            <td style="color:var(--muted)">${{bm.category}}</td>
            <td style="font-weight:600">${{bm.name}}</td>
            <td><span class="score ${{cls}}">${{bm.sota_score || "—"}}</span></td>
            <td style="color:var(--muted)">${{bm.sota_date || "—"}}</td>
            <td>${{links.join(" · ") || "—"}}</td>
          </tr>`;
      }});
    }}
    resultsDiv.style.display = "block";
  }}

  document.getElementById("model-input").addEventListener("keydown", e => {{
    if (e.key === "Enter") searchModel();
  }});

  // ── SOTA 趋势图 ──
  let _chart = null;

  function openChartModal(slug, name) {{
    const data = HISTORY[slug];
    if (!data) return;
    document.getElementById("chart-title").textContent = name + "  SOTA 历史趋势";
    document.getElementById("chart-modal").classList.add("open");
    if (_chart) {{ _chart.destroy(); _chart = null; }}
    const pts = data.points;
    _chart = new Chart(document.getElementById("chart-canvas"), {{
      type: "line",
      data: {{
        labels: pts.map(p => p.date),
        datasets: [{{
          label: "SOTA (%)",
          data: pts.map(p => p.score),
          borderColor: "#6366f1",
          backgroundColor: "rgba(99,102,241,0.12)",
          tension: 0.35,
          fill: true,
          pointRadius: 5,
          pointHoverRadius: 8,
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            callbacks: {{
              label: ctx => {{
                const p = pts[ctx.dataIndex];
                return p.score + "% — " + (p.model || "");
              }}
            }}
          }}
        }},
        scales: {{
          y: {{
            beginAtZero: false,
            ticks: {{ color: "#8892a4", callback: v => v + "%" }},
            grid: {{ color: "rgba(255,255,255,0.05)" }}
          }},
          x: {{
            ticks: {{ color: "#8892a4" }},
            grid: {{ color: "rgba(255,255,255,0.05)" }}
          }}
        }}
      }}
    }});
  }}

  function closeChartModal() {{
    document.getElementById("chart-modal").classList.remove("open");
    if (_chart) {{ _chart.destroy(); _chart = null; }}
  }}

  document.getElementById("chart-modal").addEventListener("click", e => {{
    if (e.target.id === "chart-modal") closeChartModal();
  }});

  document.addEventListener("click", e => {{
    const btn = e.target.closest(".chart-btn");
    if (!btn) return;
    e.preventDefault();
    openChartModal(btn.dataset.slug, btn.dataset.name);
  }});

  // ── 中文模型专栏 ──
  const CN_KW = ["deepseek", "qwen", "kimi", "glm-", "glm4", "yi-", "baichuan", "minimax", "ernie", "zhipu", "internlm"];

  function isChinese(m) {{
    const s = (m || "").toLowerCase();
    return CN_KW.some(k => s.includes(k));
  }}

  function toggleCnSection(btn) {{
    btn.classList.toggle("open");
    const body = document.getElementById("cn-body");
    body.classList.toggle("open");
    if (body.classList.contains("open") && !body.dataset.loaded) {{
      body.dataset.loaded = "1";
      const cnBms = BENCHMARKS.filter(b => isChinese(b.sota_model));
      document.getElementById("cn-stats").innerHTML =
        `<div class="cn-stat"><strong>${{cnBms.length}}</strong> / ${{BENCHMARKS.length}} 个 benchmark 由中文模型领先</div>`;
      const tbody = document.getElementById("cn-tbody");
      if (!cnBms.length) {{
        tbody.innerHTML = '<tr><td colspan="4" style="color:var(--muted);text-align:center">暂无中文模型领先</td></tr>';
      }} else {{
        tbody.innerHTML = cnBms.map(b => {{
          const v = parseFloat(b.sota_score);
          const cls = isNaN(v) ? "score-unknown" : v >= 90 ? "score-high" : v >= 60 ? "score-mid" : "score-low";
          return `<tr>
            <td style="font-weight:600">${{b.name}}</td>
            <td>${{b.sota_model}}</td>
            <td><span class="score ${{cls}}">${{b.sota_score || "—"}}</span></td>
            <td style="color:var(--muted)">${{b.sota_date || "—"}}</td>
          </tr>`;
        }}).join("");
      }}
    }}
  }}

  // ── History toggle ──
  document.addEventListener("click", e => {{
    const toggle = e.target.closest(".history-toggle");
    if (!toggle) return;
    e.preventDefault();
    const target = document.getElementById(toggle.dataset.target);
    if (!target) return;
    const hidden = target.style.display === "none";
    target.style.display = hidden ? "table-row" : "none";
    toggle.textContent = hidden
      ? toggle.textContent.replace("历史", "收起")
      : toggle.textContent.replace("收起", "历史");
  }});
</script>

</body>
</html>
"""


if __name__ == "__main__":
    data = load_data()
    html = generate_html(data)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    total = sum(len(c.get("benchmarks", [])) for c in data.get("categories", []))
    print(f"生成完成：{OUTPUT_PATH}（{total} 个 benchmark）")
