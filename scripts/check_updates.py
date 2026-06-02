"""
check_updates.py — AgentPulse SOTA 更新检查脚本

数据来源：
  llm-stats.com REST API（覆盖 5/7 benchmark）
  WebArena / GAIA：llm-stats 未收录，标记为需人工检查

用法：
  python scripts/check_updates.py              # 只检查，打印报告
  python scripts/check_updates.py --apply      # 检查 + 自动写入 YAML
  python scripts/check_updates.py --ci         # CI 模式：有更新时退出码 1，供 GitHub Actions 创建 PR

环境变量：
  LLM_STATS_API_KEY   llm-stats.com API key（本地放 .env，CI 放 GitHub Secret）
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date as _date
from pathlib import Path

import requests
import yaml

# ── 加载 .env（本地开发用）──────────────────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

ROOT         = Path(__file__).parent.parent
YAML_PATH    = ROOT / "data" / "benchmarks.yaml"
SUMMARY_PATH = ROOT / "data" / "_pending_updates.json"
HISTORY_DIR  = ROOT / "data" / "history"


def name_to_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def append_history(name: str, score: str, model: str, bm_date: str) -> None:
    """把旧 SOTA 追加到历史记录文件（在覆盖更新之前调用）"""
    if not score:
        return
    slug = name_to_slug(name)
    path = HISTORY_DIR / f"{slug}.yaml"
    entry = {
        "score":       score,
        "model":       model or "",
        "date":        bm_date or "",
        "recorded_at": _date.today().isoformat(),
    }
    history = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            history = yaml.safe_load(f) or []
    # 避免重复追加相同记录
    if history and history[-1].get("score") == score and history[-1].get("model") == model:
        return
    history.append(entry)
    HISTORY_DIR.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(history, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

API_BASE = "https://api.llm-stats.com"

# ── benchmark 名称 → llm-stats benchmark ID ──────────────────────────────────
LLM_STATS_ID_MAP = {
    "SWE-bench Verified": "swe-bench-verified",
    "Terminal-Bench 2.0": "terminal-bench-2",
    "OSWorld":            "osworld",
    "Toolathlon":         "toolathlon",
    "τ-bench":            "tau-bench",
}

# llm-stats 未收录，需人工检查
MANUAL_CHECK = {
    "WebArena": "https://benchlm.ai/benchmarks/webArena",
    "GAIA":     "https://huggingface.co/spaces/gaia-benchmark/leaderboard",
}


def get_api_key() -> str:
    key = os.environ.get("LLM_STATS_API_KEY", "")
    if not key:
        print("错误：未找到 LLM_STATS_API_KEY，请在 .env 或环境变量中设置")
        sys.exit(1)
    return key


def fetch_top_score(benchmark_id: str, api_key: str) -> dict | None:
    """从 llm-stats API 拉取指定 benchmark 的最高分条目"""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        r = requests.get(
            f"{API_BASE}/stats/v1/scores",
            headers=headers,
            params={"benchmark": benchmark_id, "limit": 1},
            timeout=10,
        )
        r.raise_for_status()
        scores = r.json().get("scores", [])
        if not scores:
            return None
        top = scores[0]
        return {
            "sota_score": f"{top['score'] * 100:.1f}%",
            "sota_model": top.get("model_name", ""),
            "sota_date":  top.get("scored_at", "")[:7],
            "source":     f"llm-stats.com / {benchmark_id}",
        }
    except Exception as e:
        print(f"  [API 错误] {benchmark_id}: {e}")
        return None


def score_to_float(s: str) -> float | None:
    if not s:
        return None
    try:
        return float(s.rstrip("%"))
    except ValueError:
        return None


def is_higher(new_score: str, old_score: str) -> bool:
    n = score_to_float(new_score)
    o = score_to_float(old_score)
    if n is None:
        return False
    if o is None:
        return True
    return n > o


def check_all(data: dict, api_key: str) -> tuple[list[dict], list[str]]:
    updates       = []
    manual_needed = []

    for cat in data.get("categories", []):
        for bm in cat.get("benchmarks", []):
            name      = bm["name"]
            old_score = bm.get("sota_score", "") or ""

            if name in MANUAL_CHECK:
                manual_needed.append(name)
                continue

            bm_id = LLM_STATS_ID_MAP.get(name)
            if bm_id is None:
                print(f"  [跳过] {name}：未配置数据源")
                continue

            print(f"  检查 {name} (当前 SOTA: {old_score or '—'})")
            fetched = fetch_top_score(bm_id, api_key)
            time.sleep(0.3)

            if fetched and is_higher(fetched["sota_score"], old_score):
                updates.append({
                    "category":  cat["name"],
                    "name":      name,
                    "old_score": old_score or "—",
                    "new_score": fetched["sota_score"],
                    "new_model": fetched["sota_model"],
                    "new_date":  fetched["sota_date"],
                    "source":    fetched["source"],
                })

    return updates, manual_needed


def apply_updates(data: dict, updates: list[dict]) -> dict:
    index = {bm["name"]: bm
             for cat in data.get("categories", [])
             for bm in cat.get("benchmarks", [])}
    for u in updates:
        bm = index.get(u["name"])
        if bm is None:
            continue
        # 先把旧 SOTA 存入历史记录
        append_history(
            u["name"],
            bm.get("sota_score", "") or "",
            bm.get("sota_model", "") or "",
            bm.get("sota_date", "") or "",
        )
        bm["sota_score"] = u["new_score"]
        if u["new_model"]:
            bm["sota_model"] = u["new_model"]
        if u["new_date"]:
            bm["sota_date"] = u["new_date"]
    return data


def print_report(updates: list[dict], manual_needed: list[str]):
    if updates:
        print(f"\n发现 {len(updates)} 处更新：")
        print("-" * 65)
        for u in updates:
            model_str = f" ({u['new_model']})" if u["new_model"] else ""
            print(f"  [{u['category']}] {u['name']}")
            print(f"    {u['old_score']}  →  {u['new_score']}{model_str}")
            print(f"    来源: {u['source']}")
        print("-" * 65)
    else:
        print("\n自动检查：未发现更新。")

    if manual_needed:
        print(f"\n以下 {len(manual_needed)} 个 benchmark 需人工检查（llm-stats 未收录）：")
        for name in manual_needed:
            print(f"  {name:20} → {MANUAL_CHECK[name]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply",        action="store_true", help="自动写入 YAML")
    parser.add_argument("--ci",           action="store_true", help="CI 模式")
    parser.add_argument("--init-history", action="store_true", help="从当前 YAML 初始化历史记录文件")
    args = parser.parse_args()

    api_key = get_api_key() if not args.init_history else ""

    print(f"加载数据：{YAML_PATH}")
    with open(YAML_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if args.init_history:
        count = 0
        for cat in data.get("categories", []):
            for bm in cat.get("benchmarks", []):
                append_history(
                    bm["name"],
                    bm.get("sota_score", "") or "",
                    bm.get("sota_model", "") or "",
                    bm.get("sota_date", "") or "",
                )
                count += 1
        print(f"历史记录初始化完成：{count} 个 benchmark → {HISTORY_DIR}")
        sys.exit(0)

    print("\n开始检查更新...\n")
    updates, manual_needed = check_all(data, api_key)
    print_report(updates, manual_needed)

    if not updates:
        sys.exit(0)

    if args.apply or args.ci:
        apply_updates(data, updates)
        with open(YAML_PATH, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        print(f"\nYAML 已更新：{YAML_PATH}")

    if args.ci:
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(updates, f, ensure_ascii=False, indent=2)
        print(f"摘要已写入：{SUMMARY_PATH}")
        sys.exit(1)


if __name__ == "__main__":
    main()
