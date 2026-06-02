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

### [ ] GAIA 自动追踪
llm-stats 未收录，备选方案：
- HuggingFace Datasets API（GAIA leaderboard 背后可能挂 HF dataset）
- 库：`huggingface_hub`
- 探索入口：`https://huggingface.co/spaces/gaia-benchmark/leaderboard`

### [ ] WebArena 自动追踪
llm-stats 未收录，备选方案：
- 检查官方 GitHub repo（`web-arena-x/webarena`）是否有 `results.json`
- 探索入口：`https://github.com/web-arena-x/webarena`

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

### [ ] SOTA 趋势图
- 读取 `data/history/` 数据，每个 benchmark 显示折线图
- 可用 Chart.js（纯前端，无需后端）

### [ ] 中文模型专栏
竞品几乎都缺这个视角，是差异化机会。

- 在页面加"中文模型"筛选按钮
- 显示 DeepSeek / Qwen / Kimi / GLM 系列在各 benchmark 上的横向对比
- 数据从 llm-stats API 按 `organization` 字段过滤

### [ ] 移动端适配
当前页面在手机上表格会横向溢出，需要响应式调整。

---

## 已知限制（不计划修复）

| 限制 | 原因 |
|------|------|
| WebArena / GAIA 暂时手动 | 没有可靠的机器可读数据源，探索中 |
| 自报数据无法验证 | llm-stats 本身也依赖厂商提交，标注出来即可 |
| 历史数据从现在才开始积累 | 没有可靠的历史数据来源，只能从现在往后记 |

---

## 手动检查清单（每次更新时参考）

- [ ] WebArena：`https://benchlm.ai/benchmarks/webArena`
- [ ] GAIA：`https://huggingface.co/spaces/gaia-benchmark/leaderboard`
