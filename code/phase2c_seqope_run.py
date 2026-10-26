"""运行 Phase 2c 序贯 OPE 实验并输出 JSON（增量写入，中途失败不丢已完成部分）。

用法：python3 phase2c_seqope_run.py --out phase2c_seqope_results.json
全部合成数据。仅标准库。
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

import gtm_sim_phase2b as sim
from phase2b_ope import generate_sequential_log, rank_order, spearman
from phase2c_seqope import (POLICIES, cross_fitted_dr, cross_fitted_fqe,
                            fresh_run_warm, generate_sequential_log_warm,
                            trajectories_from_log, wilcoxon_gamma_bound)


def save(path, res):
    Path(path).write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def fqe_block(trajs, label):
    out = {}
    for p in POLICIES:
        cf = cross_fitted_fqe(trajs, p)
        out[p] = {k: round(v, 6) if isinstance(v, float) else v for k, v in cf.items()}
    out["_rank_ratio"] = rank_order({p: out[p]["ratio"] for p in POLICIES})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="phase2c_seqope_results.json")
    args = ap.parse_args()
    res = {"disclaimer": "SYNTHETIC ONLY — 全部合成数据，不是真实厂商数据。"}
    save(args.out, res)

    # --- 主实验：seed 501，200 账户，eps 0.3（与 Phase 2b OPE-2 同配置）---
    print("== main log seed501 ==", flush=True)
    log = generate_sequential_log(200, 24, seed=501, eps=0.3)
    trajs = trajectories_from_log(log)
    truth = sim.run_all(seed=501, n_accounts=200, weeks=24)
    truth_ratio = {p: truth[p]["pipeline"] / truth[p]["trust_consumed"] if truth[p]["trust_consumed"] > 0 else 0.0
                   for p in POLICIES + ["human_rules"]}
    truth_pipe = {p: truth[p]["pipeline"] / 200 for p in POLICIES + ["human_rules"]}
    res["main"] = {
        "config": {"seed": 501, "accounts": 200, "weeks": 24, "eps": 0.3},
        "truth_per_account_pipeline": {p: round(v, 4) for p, v in truth_pipe.items()},
        "truth_ratio": {p: round(v, 4) for p, v in truth_ratio.items()},
        "truth_rank_ratio": rank_order(truth_ratio),
        "fqe": fqe_block(trajs, "main"),
    }
    # FQE 排序与真值排序（仅 5 个可识别策略）
    fqe_ratios = {p: res["main"]["fqe"][p]["ratio"] for p in POLICIES}
    res["main"]["fqe_spearman_vs_truth"] = spearman(
        rank_order({p: truth_ratio[p] for p in POLICIES}),
        rank_order(fqe_ratios))
    res["main"]["fqe_rank"] = rank_order(fqe_ratios)
    save(args.out, res)

    # --- 序贯 DR（交叉拟合，含 ESS）---
    print("== sequential DR seed501 ==", flush=True)
    from phase2c_seqope import cross_fitted_dr as _cfdr  # noqa
    # cross_fitted_dr 内部重拟合 Q；为同时拿到 ESS，这里对全量拟合做一次 DR
    # （ESS 与自助 SE 需要单次拟合的轨迹贡献，交叉拟合的均值见 dr_cross）。
    from phase2c_seqope import fit_q_fqe, sequential_dr
    dr_out = {}
    for p in POLICIES:
        q_pipe = fit_q_fqe(trajs, p, "reward")
        q_trust = fit_q_fqe(trajs, p, "trust_cost")
        dr = sequential_dr(trajs, p, q_pipe, q_trust)
        dr_out[p] = {"DR_pipeline_per_account": round(dr["DR_pipeline_per_account"], 4),
                     "DR_se_bootstrap": round(dr["DR_se_bootstrap"], 4),
                     "ESS_week7": round(dr["ess_week7"], 1),
                     "ESS_week15": round(dr["ess_week15"], 1),
                     "ESS_week23": round(dr["ess_week23"], 1),
                     "n_trajectories": dr["n_trajectories"]}
    res["main"]["sequential_DR_fullfit"] = dr_out
    res["main"]["sequential_DR_rank"] = rank_order({p: dr_out[p]["DR_pipeline_per_account"] for p in POLICIES})
    res["main"]["sequential_DR_spearman_vs_truth"] = spearman(
        rank_order({p: truth_pipe[p] for p in POLICIES}),
        rank_order({p: dr_out[p]["DR_pipeline_per_account"] for p in POLICIES}))
    save(args.out, res)

    # --- 大样本日志：seed 502，1000 账户 ---
    print("== large log seed502 1000 accounts ==", flush=True)
    log2 = generate_sequential_log(1000, 24, seed=502, eps=0.3)
    trajs2 = trajectories_from_log(log2)
    truth2 = sim.run_all(seed=502, n_accounts=1000, weeks=24)
    tr2 = {p: truth2[p]["pipeline"] / truth2[p]["trust_consumed"] if truth2[p]["trust_consumed"] > 0 else 0.0
           for p in POLICIES}
    tp2 = {p: truth2[p]["pipeline"] / 1000 for p in POLICIES}
    res["large"] = {
        "config": {"seed": 502, "accounts": 1000, "weeks": 24, "eps": 0.3},
        "truth_per_account_pipeline": {p: round(v, 4) for p, v in tp2.items()},
        "truth_ratio": {p: round(v, 4) for p, v in tr2.items()},
        "truth_rank_ratio": rank_order(tr2),
        "fqe": fqe_block(trajs2, "large"),
    }
    res["large"]["fqe_spearman_vs_truth"] = spearman(
        rank_order(tr2), rank_order({p: res["large"]["fqe"][p]["ratio"] for p in POLICIES}))
    res["large"]["fqe_rank"] = rank_order({p: res["large"]["fqe"][p]["ratio"] for p in POLICIES})
    save(args.out, res)

    # --- 低探索日志：seed 503，200 账户，eps 0.1 ---
    print("== low-exploration log seed503 eps0.1 ==", flush=True)
    log3 = generate_sequential_log(200, 24, seed=503, eps=0.1)
    trajs3 = trajectories_from_log(log3)
    truth3 = sim.run_all(seed=503, n_accounts=200, weeks=24)
    tr3 = {p: truth3[p]["pipeline"] / truth3[p]["trust_consumed"] if truth3[p]["trust_consumed"] > 0 else 0.0
           for p in POLICIES}
    res["low_eps"] = {
        "config": {"seed": 503, "accounts": 200, "weeks": 24, "eps": 0.1},
        "truth_ratio": {p: round(v, 4) for p, v in tr3.items()},
        "truth_rank_ratio": rank_order(tr3),
        "fqe": fqe_block(trajs3, "low_eps"),
    }
    res["low_eps"]["fqe_spearman_vs_truth"] = spearman(
        rank_order(tr3), rank_order({p: res["low_eps"]["fqe"][p]["ratio"] for p in POLICIES}))
    res["low_eps"]["fqe_rank"] = rank_order({p: res["low_eps"]["fqe"][p]["ratio"] for p in POLICIES})
    save(args.out, res)

    # --- Warm 混杂网格（FQE vs 同人口真值）---
    print("== warm grid ==", flush=True)
    combos = [
        {"warm_prob": 0.3, "warm_boost": 1.8, "warm_override": 0.5, "label": "baseline_warm"},
        {"warm_prob": 0.5, "warm_boost": 1.8, "warm_override": 0.5, "label": "prob0.5"},
        {"warm_prob": 0.3, "warm_boost": 3.0, "warm_override": 0.5, "label": "boost3.0"},
        {"warm_prob": 0.3, "warm_boost": 1.8, "warm_override": 0.9, "label": "override0.9"},
        {"warm_prob": 0.5, "warm_boost": 3.0, "warm_override": 0.9, "label": "strong"},
        {"warm_prob": 0.3, "warm_boost": 1.0, "warm_override": 0.5, "label": "override_only_no_boost"},
    ]
    warm_res = {}
    for c in combos:
        lg = generate_sequential_log_warm(200, 24, seed=601, eps=0.3,
                                          warm_prob=c["warm_prob"], warm_boost=c["warm_boost"],
                                          warm_override=c["warm_override"])
        trj = trajectories_from_log(lg)
        fqe = fqe_block(trj, c["label"])
        truth_w = {}
        for p in POLICIES:
            fin = fresh_run_warm(p, 200, 24, seed=601, warm_prob=c["warm_prob"], warm_boost=c["warm_boost"])
            truth_w[p] = round(fin["per_account_pipeline"] / fin["per_account_trust"], 4) if fin["per_account_trust"] > 0 else 0.0
        warm_res[c["label"]] = {
            "params": {k: c[k] for k in ("warm_prob", "warm_boost", "warm_override")},
            "fqe_ratio": {p: fqe[p]["ratio"] for p in POLICIES},
            "fqe_rank": rank_order({p: fqe[p]["ratio"] for p in POLICIES}),
            "truth_ratio": truth_w,
            "truth_rank": rank_order(truth_w),
            "fqe_spearman_vs_truth": spearman(rank_order(truth_w),
                                              rank_order({p: fqe[p]["ratio"] for p in POLICIES})),
            "fqe_gated_minus_ungated": round(fqe["G+_gated"]["ratio"] - fqe["G+_ungated"]["ratio"], 4),
            "truth_gated_minus_ungated": round(truth_w["G+_gated"] - truth_w["G+_ungated"], 4),
            "fqe_gated_minus_G": round(fqe["G+_gated"]["ratio"] - fqe["G"]["ratio"], 4),
            "truth_gated_minus_G": round(truth_w["G+_gated"] - truth_w["G"], 4),
        }
        print("warm", c["label"], warm_res[c["label"]]["fqe_rank"], warm_res[c["label"]]["truth_rank"], flush=True)
    res["warm_grid"] = warm_res
    save(args.out, res)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
