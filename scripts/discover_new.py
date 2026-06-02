"""
discover_new.py — 每周扫描 llm-stats，发现新 Agent benchmark，自动开 GitHub issue

逻辑：
  1. 从 llm-stats 拉取全量 benchmark 列表
  2. 过滤 category 包含 agents / tool_calling 的条目
  3. 与 data/_known_benchmarks.json 对比，找出新增条目
  4. 如果有新条目：更新已知列表 + 开 GitHub issue 提醒人工评估

用法：
  python scripts/discover_new.py              # 只打印报告，不开 issue
  python scripts/discover_new.py --ci         # CI 模式：有新条目时开 GitHub issue

环境变量：
  LLM_STATS_API_KEY    llm-stats API key
  GITHUB_TOKEN         GitHub Actions 自动注入（开 issue 用）
  GITHUB_REPOSITORY    格式 owner/repo，GitHub Actions 自动注入
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

# ── 加载 .env ─────────────────────────────────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

ROOT            = Path(__file__).parent.parent
KNOWN_PATH      = ROOT / "data" / "_known_benchmarks.json"
API_BASE        = "https://api.llm-stats.com"
GITHUB_API_BASE = "https://api.github.com"

# 关注的 category 关键词
AGENT_CATEGORIES = {"agents", "tool_calling"}


def get_llm_stats_key() -> str:
    key = os.environ.get("LLM_STATS_API_KEY", "")
    if not key:
        print("错误：未找到 LLM_STATS_API_KEY")
        sys.exit(1)
    return key


def fetch_all_benchmarks(api_key: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(f"{API_BASE}/stats/v1/benchmarks", headers=headers, timeout=15)
    r.raise_for_status()
    return r.json().get("benchmarks", [])


def filter_agent_benchmarks(benchmarks: list[dict]) -> list[dict]:
    result = []
    for bm in benchmarks:
        cats = set(bm.get("categories", []))
        if cats & AGENT_CATEGORIES:
            result.append(bm)
    return result


def load_known() -> dict[str, dict]:
    """加载已知 benchmark 列表 {id: {name, categories}}"""
    if not KNOWN_PATH.exists():
        return {}
    with open(KNOWN_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_known(known: dict[str, dict]) -> None:
    with open(KNOWN_PATH, "w", encoding="utf-8") as f:
        json.dump(known, f, ensure_ascii=False, indent=2)


def create_github_issue(new_benchmarks: list[dict]) -> None:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo  = os.environ.get("GITHUB_REPOSITORY", "HappyMayzhang/agentpulse")
    if not token:
        print("  [跳过] 未找到 GITHUB_TOKEN，无法开 issue")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    rows = "\n".join(
        f"| `{bm['id']}` | {bm['name']} | {', '.join(bm.get('categories', []))} | [llm-stats]({bm.get('url', '')}) |"
        for bm in new_benchmarks
    )

    body = f"""llm-stats 本周新增了 **{len(new_benchmarks)}** 个 Agent 相关 benchmark，请人工评估是否纳入 AgentPulse 追踪。

## 新增列表

| ID | 名称 | 分类 | 链接 |
|----|------|------|------|
{rows}

## 纳入标准
- benchmark 有官方论文或组织背书
- 测试的是真实 Agent 能力（不只是函数补全）
- 有公开 leaderboard 或可复现的评测结果

## 操作
如果决定纳入，在 `data/benchmarks.yaml` 添加条目，并在 `scripts/check_updates.py` 的 `LLM_STATS_ID_MAP` 中注册 ID。
"""

    payload = {
        "title": f"[发现] {len(new_benchmarks)} 个新 Agent benchmark 待评估",
        "body":  body,
        "labels": ["new-benchmark"],
    }

    r = requests.post(
        f"{GITHUB_API_BASE}/repos/{repo}/issues",
        headers=headers,
        json=payload,
        timeout=10,
    )
    if r.status_code == 201:
        print(f"  GitHub issue 已创建：{r.json()['html_url']}")
    else:
        print(f"  [错误] 创建 issue 失败：{r.status_code} {r.text[:200]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true", help="CI 模式：有新条目时开 GitHub issue")
    args = parser.parse_args()

    api_key = get_llm_stats_key()

    print("拉取 llm-stats benchmark 列表...")
    all_bms      = fetch_all_benchmarks(api_key)
    agent_bms    = filter_agent_benchmarks(all_bms)
    print(f"  llm-stats 共 {len(all_bms)} 个 benchmark，其中 Agent 相关 {len(agent_bms)} 个")

    known        = load_known()
    new_bms      = [bm for bm in agent_bms if bm["id"] not in known]

    if not new_bms:
        print("\n未发现新 Agent benchmark。")
        # 首次运行时初始化已知列表
        if not known:
            updated = {bm["id"]: {"name": bm["name"], "categories": bm.get("categories", [])}
                       for bm in agent_bms}
            save_known(updated)
            print(f"已初始化已知列表：{len(updated)} 个 benchmark")
        sys.exit(0)

    print(f"\n发现 {len(new_bms)} 个新 Agent benchmark：")
    print("-" * 60)
    for bm in new_bms:
        cats = ", ".join(bm.get("categories", []))
        print(f"  {bm['id']:40} [{cats}]")
        print(f"  {bm['name']}")
        if bm.get("url"):
            print(f"  {bm['url']}")
        print()
    print("-" * 60)

    # 更新已知列表
    for bm in new_bms:
        known[bm["id"]] = {"name": bm["name"], "categories": bm.get("categories", [])}
    save_known(known)
    print(f"已知列表已更新：{len(known)} 个 benchmark")

    if args.ci:
        create_github_issue(new_bms)
        sys.exit(1)   # 告知 Actions 有新发现


if __name__ == "__main__":
    main()
