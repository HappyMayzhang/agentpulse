# 贡献指南

感谢你对 Agent Bench Tracker 的贡献！

## 贡献规则

1. **只接受官方来源的数据**，不接受二手或推测数据
2. **每次更新必须附上官方链接或截图证据**（在 PR 描述中说明）
3. **采用定期批量审核**（每月一次），非实时处理每一个 PR

## 如何提交新 benchmark

1. Fork 本仓库
2. 在 `data/benchmarks.yaml` 中按已有格式添加新条目
3. 在 PR 描述中注明：
   - benchmark 官方网站链接
   - 数据来源截图或链接
4. 提交 PR，等待审核合并

## YAML 格式模板

```yaml
- name: "Benchmark 名称"
  description: "一句话介绍 benchmark 的评测内容"
  methodology: "评测方法说明"
  sota_score: "xx.x%"
  sota_model: "模型名称"
  sota_date: "YYYY-MM-DD"
  source_url: "论文或官方介绍链接"
  official_leaderboard: "官方 leaderboard 链接"
```

## 如何更新 SOTA 记录

1. 更新 `data/benchmarks.yaml` 中对应条目的 `sota_*` 字段
2. 在 `data/history/<benchmark-name>.yaml` 中追加历史记录
3. PR 描述中说明数据来源

## 数据质量要求

- 分数必须来自官方 leaderboard 或 paper 原文
- 日期为结果公布日期（论文发布或 leaderboard 更新日期）
- 模型名称使用官方名称（含版本号）
