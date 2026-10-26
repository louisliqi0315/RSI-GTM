"""Phase 2b 缺口 3：10 种子 + 参数敏感性。

- 10 种子固定为 0..9（与任务书一致；此前 multi_seed_report.md 用 12 种子，
  本文件不覆盖它，仅作交叉对照）。
- 每种子 200 账户、24 周，与 v0 完全同配置。
- 输出：均值、标准差、95% CI（均值 ±1.96*SD/sqrt(n)，n=10 时为近似，
  同时报告中位数与逐种子胜负计数，后者比均值更诚实）、成对胜负。
- 敏感性扫描（用 gtm_sim_phase2b 参数化副本，v0 原文件不动）：
  声誉损伤倍数 0.5x / 1x / 2x；信任预算 15 / 30 / 60；伙伴净留存系数 0.5 / 0.7 / 0.9。
  每组用种子 0..2 跑（控制运行时间），报告 gated>ungated 与 gated>G 的胜负计数
  是否随参数翻转。注意：这是机制敏感性，不是真实世界敏感性。

用法：
  python3 phase2b_multiseed.py --out phase2b_multiseed_results.json
全部结果均为合成数据。
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

import gtm_sim_phase2b as sim
from phase2b_ranking import floor_sensitivity_aggregated, pareto_frontier, ranked

BASELINES = ["reply_greedy", "human_rules", "wait_heavy", "G", "G+_gated", "G+_ungated"]
SEEDS = list(range(10))


def summarize(per_seed):
    out = {}
    for name in BASELINES:
        vals = [per_seed[s][name]["pipeline_per_trust"] for s in SEEDS if s in per_seed]
        pipes = [per_seed[s][name]["pipeline"] for s in SEEDS if s in per_seed]
        reps = [per_seed[s][name]["mean_reputation_change"] for s in SEEDS if s in per_seed]
        n = len(vals)
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals) if n > 1 else 0.0
        out[name] = {
            "mean_pipeline_per_trust": round(mean, 4),
            "sd": round(sd, 4),
            "ci95_halfwidth": round(1.96 * sd / math.sqrt(n), 4) if n > 1 else 0.0,
            "median": round(statistics.median(vals), 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "mean_pipeline": round(statistics.mean(pipes), 1),
            "mean_reputation_change": round(statistics.mean(reps), 4),
            "per_seed": {str(s): round(per_seed[s][name]["pipeline_per_trust"], 4) for s in sorted(per_seed)},
        }
    # 成对胜负（逐种子）
    pairs = {}
    for a, b in [("G+_gated", "G+_ungated"), ("G+_gated", "G"), ("G", "G+_ungated"),
                 ("G+_gated", "reply_greedy")]:
        wins = sum(1 for s in per_seed if per_seed[s][a]["pipeline_per_trust"] > per_seed[s][b]["pipeline_per_trust"])
        pairs[f"{a}>{b}"] = f"{wins}/{len(per_seed)}"
    out["_pairs"] = pairs
    out["_floor_sensitivity"] = floor_sensitivity_aggregated(per_seed)
    # 种子 42 的帕累托（与 v0 对照用，不计入 10 种子统计）
    return out


def sensitivity_scan():
    results = {}
    # 基准组（1x, 30, 0.7）用种子 0..2
    def run_group(label, damage_mult, budget, partner_factor):
        sim.REPUTATION_DAMAGE_HIGH = 0.015 * damage_mult
        sim.REPUTATION_DAMAGE_LOW = 0.030 * damage_mult
        sim.TRUST_BUDGET = budget
        sim.PARTNER_NET_FACTOR = partner_factor
        per = {}
        for s in [0, 1, 2]:
            per[s] = sim.run_all(seed=s, n_accounts=200, weeks=24)
        gated_ungated = sum(1 for s in per if per[s]["G+_gated"]["pipeline_per_trust"] > per[s]["G+_ungated"]["pipeline_per_trust"])
        gated_g = sum(1 for s in per if per[s]["G+_gated"]["pipeline_per_trust"] > per[s]["G"]["pipeline_per_trust"])
        results[label] = {
            "gated>ungated": f"{gated_ungated}/3",
            "gated>G": f"{gated_g}/3",
            "mean_gated": round(statistics.mean([per[s]["G+_gated"]["pipeline_per_trust"] for s in per]), 4),
            "mean_G": round(statistics.mean([per[s]["G"]["pipeline_per_trust"] for s in per]), 4),
            "mean_ungated": round(statistics.mean([per[s]["G+_ungated"]["pipeline_per_trust"] for s in per]), 4),
        }

    run_group("baseline_damage1x_budget30_partner0.7", 1.0, 30.0, 0.7)
    run_group("damage0.5x", 0.5, 30.0, 0.7)
    run_group("damage2x", 2.0, 30.0, 0.7)
    run_group("budget15", 1.0, 15.0, 0.7)
    run_group("budget60", 1.0, 60.0, 0.7)
    run_group("partner0.5", 1.0, 30.0, 0.5)
    run_group("partner0.9", 1.0, 30.0, 0.9)
    # 恢复 v0 默认
    sim.REPUTATION_DAMAGE_HIGH, sim.REPUTATION_DAMAGE_LOW = 0.015, 0.030
    sim.TRUST_BUDGET, sim.PARTNER_NET_FACTOR = 30.0, 0.7
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="phase2b_multiseed_results.json")
    args = ap.parse_args()
    per_seed = {s: sim.run_all(seed=s, n_accounts=200, weeks=24) for s in SEEDS}
    summary = summarize(per_seed)
    summary["_sensitivity"] = sensitivity_scan()
    # 种子 42 帕累托与门槛（对照 v0，不计入统计）
    r42 = sim.run_all(seed=42, n_accounts=200, weeks=24)
    summary["_seed42_pareto"] = [(n, round(p, 1), round(e, 4)) for n, p, e in pareto_frontier(r42)]
    summary["_seed42_ranked_floor200"] = [(n, round(e, 4), round(p, 1)) for n, e, p in ranked(r42, 200)]
    payload = {"disclaimer": "SYNTHETIC ONLY — 全部合成数据，不是真实厂商数据。",
               "seeds": SEEDS, "summary": summary,
               "per_seed_pipeline_per_trust": {str(s): {n: round(per_seed[s][n]["pipeline_per_trust"], 4) for n in BASELINES} for s in SEEDS}}
    Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
