# AgentPulse

**Agent Benchmark SOTA 实时追踪工具**

专注追踪软件工程 Agent、环境交互 Agent、工具调用 Agent 等方向的最新 SOTA 分数、模型和历史变化。

> 所有数据均来自公开来源，详见各 benchmark 官方网站。

---

## 与同类项目的区别

| 项目 | 类型 | 问题 |
|------|------|------|
| [ai-agent-benchmark-compendium](https://github.com/philschmid/ai-agent-benchmark-compendium) | benchmark 目录 | 静态列表，不追踪 SOTA 分数和更新时间 |
| Papers with Code | 全品类追踪 | Agent 维度分类粗，更新延迟大 |
| **本项目** | **SOTA 追踪器** | 关注"现在谁最好、好多少、什么时候变化的" |

本项目专注回答三个问题：**现在谁最好？好多少？什么时候超过的？**

---

## Benchmark 覆盖维度

| 维度 | Benchmark |
|------|-----------|
| 软件工程 Agent | SWE-bench Verified |
| 环境交互 Agent | Terminal-Bench 2.0、WebArena、OSWorld |
| 工具调用 Agent | Toolathlon、τ-bench |
| 通用 Agent | GAIA |

---

## 数据结构

核心数据文件：[`data/benchmarks.yaml`](data/benchmarks.yaml)

每个 benchmark 记录：
- 简介和评测方法
- 当前 SOTA 分数、模型、日期
- 官方来源链接
- 历史 SOTA 变化（`data/history/`）

---

## 自动更新

通过 GitHub Actions 每天定时检查以下来源：
- Papers with Code API
- 各 benchmark 官方 leaderboard

发现更新后自动创建 PR，人工审核后合并。不追求全自动，追求**有人维护的准确**。

---

## 贡献

欢迎提交新的 benchmark 数据或 SOTA 更新，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 在线页面

[AgentPulse GitHub Pages](https://happymayzhang.github.io/agentpulse/)（即将上线）
