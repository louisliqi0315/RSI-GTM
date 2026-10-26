"""Phase 2c 任务二：扩展多种子与机制扫描。

全部合成数据。仅标准库。使用 phase2c_sim（机制与 phase2b 完全相同，
默认参数下 seed=42 表与 v0 完全一致，已回归检查；仅把意图衰减与
组织事件概率抽为可扫描全局变量）。

内容：
1. 主扫描：种子 0-9，1000 账户，24 周，基线参数。报告均值、标准差、
   95% CI、逐种子值，以及成对差异的 t 置信区间、符号检验、Bootstrap
   区间、Wilcoxon Rosenbaum Gamma 界（复用 phase2c_seqope 的实现）。
2. 200 账户 10 种子成对统计：直接复用 phase2b_multiseed_results.json
   的逐种子值（不重跑、不覆盖），与 1000 账户结果对照。
3. 机制扫描（200 账户，种子 0-2，逐组恢复默认值）：疲劳系数、
   意图衰减、组织事件概率（Phase 2b 未扫描），以及损伤 2x 与预算 15
   的复现（检验“门在信任更脆弱时价值更大”这一条件性主张）。
4. 1000 账户损伤 2x 组（种子 0-2）：条件性主张在更大样本下是否成立。

用法：python3 phase2c_multiseed.py --out phase2c_multiseed_results.json
增量写入：主扫描完成后先保存，扫描组逐组追加。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path

import phase2c_sim as sim
from phase2c_seqope import wilcoxon_gamma_bound

BASELINES = ["reply_greedy", "human_rules", "wait_heavy", "G", "G+_gated", "G+_ungated"]
T_CRIT = {9: 2.262, 2: 4.303, 1: 12.706}


def paired_stats(diffs):
    n = len(diffs)
    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n else 0.0
    t = T_CRIT.get(n - 1, 2.0)
    wins = sum(1 for d in diffs if d > 0)
    # 单侧符号检验 p = P(X >= wins)，X ~ Bin(n, 0.5)
    p_sign = sum(math.comb(n, k) for k in range(wins, n + 1)) / (2 ** n) if n else 1.0
    # Bootstrap 均值差 CI（2000 次，固定种子）
    rng = random.Random(999)
    boots = []
    for _ in range(2000):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boots.append(statistics.mean(sample))
    boots.sort()
    lo = boots[int(0.025 * len(boots))]
    hi = boots[int(0.975 * len(boots)) - 1]
    gamma = wilcoxon_gamma_bound(diffs)
    return {
        "n": n, "mean_diff": round(mean, 4), "sd_diff": round(sd, 4),
        "ci95_t": [round(mean - t * se, 4), round(mean + t * se, 4)],
        "bootstrap_ci95": [round(lo, 4), round(hi, 4)],
        "wins": f"{wins}/{n}", "sign_test_p_one_sided": round(p_sign, 4),
        "wilcoxon_gamma": {"T_obs": gamma["T_obs"], "p_gamma1": round(gamma["p_gamma1"], 4),
                           "gamma_threshold": gamma["gamma_threshold"]},
        "per_seed_diff": [round(d, 4) for d in diffs],
    }


def summarize(per_seed, label):
    seeds = sorted(per_seed)
    out = {"seeds": seeds, "label": label, "policies": {}, "pairs": {}}
    for name in BASELINES:
        vals = [per_seed[s][name]["pipeline_per_trust"] for s in seeds]
        pipes = [per_seed[s][name]["pipeline"] for s in seeds]
        reps = [per_seed[s][name]["mean_reputation_change"] for s in seeds]
        n = len(vals)
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals) if n > 1 else 0.0
        out["policies"][name] = {
            "mean_pipeline_per_trust": round(mean, 4), "sd": round(sd, 4),
            "ci95_halfwidth": round(1.96 * sd / math.sqrt(n), 4) if n > 1 else 0.0,
            "median": round(statistics.median(vals), 4),
            "mean_pipeline": round(statistics.mean(pipes), 1),
            "mean_reputation_change": round(statistics.mean(reps), 4),
            "per_seed": {str(s): round(per_seed[s][name]["pipeline_per_trust"], 4) for s in seeds},
        }
    for a, b, key in [("G+_gated", "G+_ungated", "gated_minus_ungated"),
                      ("G+_gated", "G", "gated_minus_G")]:
        diffs = [per_seed[s][a]["pipeline_per_trust"] - per_seed[s][b]["pipeline_per_trust"] for s in seeds]
        out["pairs"][key] = paired_stats(diffs)
    return out


def restore_defaults():
    sim.FATIGUE_COEF = 0.30
    sim.INTENT_DECAY = 0.97
    sim.EVENT_PROB = 0.08
    sim.REPUTATION_DAMAGE_HIGH = 0.015
    sim.REPUTATION_DAMAGE_LOW = 0.030
    sim.TRUST_BUDGET = 30.0
    sim.PARTNER_NET_FACTOR = 0.7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="phase2c_multiseed_results.json")
    args = ap.parse_args()
    res = {"disclaimer": "SYNTHETIC ONLY — 全部合成数据，不是真实厂商数据。"}
    Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    # 1. 主扫描：1000 账户
    print("== main 1000 accounts seeds 0-9 ==", flush=True)
    restore_defaults()
    per_seed_1000 = {s: sim.run_all(seed=s, n_accounts=1000, weeks=24) for s in range(10)}
    res["main_1000"] = summarize(per_seed_1000, "1000 accounts, seeds 0-9, baseline params")
    Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res["main_1000"]["pairs"], indent=2, ensure_ascii=False), flush=True)

    # 2. 200 账户 10 种子成对统计（复用 Phase 2b 结果，不重跑）
    print("== reuse phase2b 200-account per-seed values ==", flush=True)
    old = json.loads(Path("phase2b_multiseed_results.json").read_text())
    per_seed_200 = {}
    for s_str, vals in old["per_seed_pipeline_per_trust"].items():
        per_seed_200[int(s_str)] = {name: {"pipeline_per_trust": v, "pipeline": 0.0,
                                            "mean_reputation_change": 0.0}
                                    for name, v in vals.items()}
    # 200 账户的 pairs 只需差分统计：用 summarize 的 pairs 部分（policies 的
    # pipeline/reputation 均值为占位 0，因原 JSON 未存逐种子管道量；差分统计
    # 仅依赖 pipeline_per_trust，正确）。
    res["reuse_200"] = summarize(per_seed_200, "200 accounts, seeds 0-9, from phase2b_multiseed_results.json (paired stats only)")
    Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. 机制扫描（200 账户，种子 0-2）
    print("== mechanism scans 200 accounts seeds 0-2 ==", flush=True)
    scans = []

    def run_group(label, **patches):
        restore_defaults()
        for k, v in patches.items():
            setattr(sim, k, v)
        per = {s: sim.run_all(seed=s, n_accounts=200, weeks=24) for s in [0, 1, 2]}
        summ = summarize(per, label)
        scans.append({"label": label, "patches": patches,
                      "mean_gated": summ["policies"]["G+_gated"]["mean_pipeline_per_trust"],
                      "mean_G": summ["policies"]["G"]["mean_pipeline_per_trust"],
                      "mean_ungated": summ["policies"]["G+_ungated"]["mean_pipeline_per_trust"],
                      "pairs": summ["pairs"]})
        print(label, scans[-1]["mean_gated"], scans[-1]["mean_G"], scans[-1]["mean_ungated"], flush=True)
        restore_defaults()

    run_group("baseline")
    run_group("fatigue0.15", FATIGUE_COEF=0.15)
    run_group("fatigue0.60", FATIGUE_COEF=0.60)
    run_group("intent_decay0.95", INTENT_DECAY=0.95)
    run_group("intent_decay0.99", INTENT_DECAY=0.99)
    run_group("event_prob0.04", EVENT_PROB=0.04)
    run_group("event_prob0.16", EVENT_PROB=0.16)
    run_group("damage2x", REPUTATION_DAMAGE_HIGH=0.030, REPUTATION_DAMAGE_LOW=0.060)
    run_group("budget15", TRUST_BUDGET=15.0)
    res["mechanism_scans_200"] = scans
    Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    # 4. 1000 账户损伤 2x 组
    print("== damage2x 1000 accounts seeds 0-2 ==", flush=True)
    restore_defaults()
    sim.REPUTATION_DAMAGE_HIGH = 0.030
    sim.REPUTATION_DAMAGE_LOW = 0.060
    per_d2 = {s: sim.run_all(seed=s, n_accounts=1000, weeks=24) for s in [0, 1, 2]}
    res["damage2x_1000"] = summarize(per_d2, "1000 accounts, seeds 0-2, damage 2x")
    restore_defaults()
    Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
