# AgentPulse Roadmap

当前状态：MVP 已上线，7 个 benchmark，5 个自动追踪，2 个手动，历史记录已启动。

---

## P0 — 核心差异点补全（尽快做）

### [x] 历史记录功能
项目定位的核心差异是"什么时候超过的"，但 `data/history/` 目前是空的。

- `check_updates.py --apply` 写入新 SOTA 时，同时把旧记录追加到 `data/history/<benchmark-id>.yaml`
- 格式示例：
  ```yaml
  - score: "50.0%"
    model: "Claude Sonnet 4.5"
    date: "2026-01"
    superseded_by: "GPT-5.5"
    superseded_date: "2026-06"
  ```
- `generate_site.py` 读取历史记录，每个 benchmark 卡片下方显示变化时间线

### [x] 数据可信度标注
llm-stats API 返回 `is_self_reported` 和 `verified` 字段，目前丢弃了。

- YAML 里加 `is_self_reported` 字段
- 页面上自报数据加"⚠ 自报"标注，第三方验证的加"✓"
- 提升数据可信度，这是与竞品的重要区别

---

## P1 — 自动化补全

### [x] GAIA 自动追踪
数据源：`gaia-benchmark/results_public` parquet（HuggingFace Datasets Server）
- 单次 HTTP 请求下载 ~110KB parquet，pyarrow 解析，找最高 score 行
- 已加入 `CUSTOM_FETCHERS`，无需 llm-stats API key

### [x] WebArena 自动追踪
数据源：官方 Google Sheets leaderboard CSV 导出（无需 API key）
- 官方 GitHub README 链接的 Sheets：`1M801lEpBbKSNwP-vDBkC_pF7LdyGU1f_ufZb_NWNBZQ`
- 解析 "Success Rate (%)" 列，日期格式 MM/YYYY → YYYY-MM

### [x] 新 benchmark 发现脚本
目前新 benchmark 出现完全靠人工感知。

- 每周跑一次 `scripts/discover_new.py`
- 调用 llm-stats `/stats/v1/updates?days=7`，过滤 `category` 包含 `agent`/`code`/`tool` 的新条目
- 有新条目时自动在 GitHub 开 issue，提醒人工评估是否纳入

### [x] PR body 改进
当前自动创建的 PR 内容信息量不足。

- 在 PR body 里自动生成新旧分数对比表
- 格式：`| Benchmark | 旧 SOTA | 新 SOTA | 模型 | 来源 |`

---

## P2 — 页面增强

### [x] SOTA 趋势图
- 读取 `data/history/` 数据，build_history_json() 打包到页面
- Chart.js CDN，点击 📈 按钮弹出折线图 modal

### [x] 中文模型专栏
- 页面顶部可展开专栏，JS 关键词过滤（DeepSeek/Qwen/Kimi/GLM/Yi/InternLM）
- 显示中文模型领先的 benchmark 数量和详情表格

### [x] 移动端适配
- `@media (max-width: 768px)` 响应式 CSS
- 隐藏描述/日期列，搜索框全宽，导航栏 padding 缩减

---

## 已知限制（不计划修复）

| 限制 | 原因 |
|------|------|
| WebArena / GAIA 已自动 | WebArena: Google Sheets CSV；GAIA: HF parquet |
| 自报数据无法验证 | llm-stats 本身也依赖厂商提交，标注出来即可 |
| 历史数据从现在才开始积累 | 没有可靠的历史数据来源，只能从现在往后记 |

---

## 手动检查清单（每次更新时参考）

- [x] WebArena：自动追踪（Google Sheets CSV）
- [x] GAIA：自动追踪（parquet）
