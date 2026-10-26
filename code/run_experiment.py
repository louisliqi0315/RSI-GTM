#!/usr/bin/env python3
"""运行 GTM-Sim v0 六基线对照。

用法：
  python3 run_experiment.py [--seed 42] [--accounts 200] [--weeks 24]
                            [--out example_output.json]

输出：JSON（完整指标）+ 终端 Markdown 表格。
注意：输出中只报主指标视为无效 —— 本脚本始终同时输出伤害指标
（退订率、投诉率、声誉变化、WAIT 占比、否决/回滚次数）。
全部结果均为合成数据，不得解读为真实转化率或收入。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gtm_sim import BASELINES, run_all  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="GTM-Sim v0 六基线对照")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--accounts", type=int, default=200)
    parser.add_argument("--weeks", type=int, default=24)
    parser.add_argument("--out", type=str, default="example_output.json")
    args = parser.parse_args()

    results = run_all(seed=args.seed, n_accounts=args.accounts, weeks=args.weeks)
    payload = {
        "disclaimer": "SYNTHETIC ONLY — 全部为合成数据，不是真实厂商数据，"
                      "不得解读为真实转化率、收入或任何厂商的表现。",
        "config": {"seed": args.seed, "accounts": args.accounts, "weeks": args.weeks},
        "baselines": BASELINES,
        "results": results,
    }
    out_path = Path(__file__).resolve().parent / args.out
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # 终端表格：主指标 + 强制伤害指标并列
    print("| 基线 | Pipeline-per-Trust | 回复率 | 退订/100触达 | 投诉/100触达 | 声誉变化 | WAIT占比 | 否决/回滚 |")
    print("|---|---|---|---|---|---|---|---|")
    for name, r in results.items():
        print(f"| {name} | {r['pipeline_per_trust']:.3f} | {r['reply_rate']:.3f} | "
              f"{r['unsubscribe_rate_per_100_touches']:.2f} | "
              f"{r['complaint_rate_per_100_touches']:.2f} | "
              f"{r['mean_reputation_change']:.3f} | {r['wait_share']:.2f} | "
              f"{r['vetoes']}/{r['rollbacks']} |")
    print(f"\n完整 JSON 已写入：{out_path}")
    print("注意：G+_gated 的 final_params 见 JSON；G+_ungated 否决/回滚恒为 0，"
          "因为它不过验证门 —— 这本身就是消融对照的记录。")


if __name__ == "__main__":
    main()
