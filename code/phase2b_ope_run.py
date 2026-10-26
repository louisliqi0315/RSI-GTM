"""运行 Phase 2b OPE 单元测试并输出 JSON + 终端摘要。

实验：
- OPE-1a：n=2000, eps=0.3, 无混杂，六个静态目标（G_0.35/0.40/0.45 + 贪心/人工/等待）
- OPE-1b：样本量扫描 100 / 500 / 2000 / 10000（DR 为主）
- OPE-1c：探索率扫描 eps 0.05 / 0.3 / 0.7（n=2000，DR/IPS/SNIPS）
- OPE-1d：隐藏混杂（warm）+ oracle 对照（Q 含 warm）
- OPE-2：24 周序贯日志 naive DR vs fresh run 真值（六基线，确定性版）

用法：python3 phase2b_ope_run.py --out phase2b_ope_results.json
全部合成数据。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import gtm_sim_phase2b as sim
from phase2b_ope import (estimate, generate_one_step_log,
                         generate_sequential_log, ground_truth_one_step,
                         rank_order, spearman)

STATIC_TARGETS = ["reply_greedy", "human_rules", "wait_heavy", "G", "G_0.35", "G_0.45"]
SIX = ["reply_greedy", "human_rules", "wait_heavy", "G", "G+_gated", "G+_ungated"]


def eval_static(log, targets, use_warm=False):
    out = {}
    for t in targets:
        est = estimate(log, t, use_warm=use_warm)
        out[t] = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in est.items()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="phase2b_ope_results.json")
    args = ap.parse_args()
    res = {}

    # OPE-1a
    log = generate_one_step_log(2000, seed=101, eps=0.3, confounded=False)
    gt = ground_truth_one_step(20000, seed=102, targets=STATIC_TARGETS, confounded=False)
    est = eval_static(log, STATIC_TARGETS)
    res["OPE-1a"] = {"ground_truth": gt, "gt_rank": rank_order(gt),
                     "estimates": est,
                     "DR_rank": rank_order({t: est[t]["DR"] for t in STATIC_TARGETS}),
                     "DR_spearman_vs_gt": spearman(rank_order(gt), rank_order({t: est[t]["DR"] for t in STATIC_TARGETS})),
                     "SNIPS_rank": rank_order({t: est[t]["SNIPS"] for t in STATIC_TARGETS}),
                     "IPS_rank": rank_order({t: est[t]["IPS"] for t in STATIC_TARGETS})}

    # OPE-1b 样本量扫描（DR）
    sweep = {}
    for n in [100, 500, 2000, 10000]:
        lg = generate_one_step_log(n, seed=201, eps=0.3, confounded=False)
        e = eval_static(lg, STATIC_TARGETS)
        sweep[n] = {"DR_rank": rank_order({t: e[t]["DR"] for t in STATIC_TARGETS}),
                    "DR_spearman": spearman(rank_order(gt), rank_order({t: e[t]["DR"] for t in STATIC_TARGETS})),
                    "DR_values": {t: e[t]["DR"] for t in STATIC_TARGETS}}
    res["OPE-1b_sample_sweep"] = sweep

    # OPE-1c 探索率扫描
    eps_sweep = {}
    for eps in [0.05, 0.3, 0.7]:
        lg = generate_one_step_log(2000, seed=301, eps=eps, confounded=False)
        e = eval_static(lg, STATIC_TARGETS)
        eps_sweep[eps] = {est_name: rank_order({t: e[t][est_name] for t in STATIC_TARGETS})
                          for est_name in ["DR", "IPS", "SNIPS"]}
        eps_sweep[eps]["DR_spearman"] = spearman(rank_order(gt), rank_order({t: e[t]["DR"] for t in STATIC_TARGETS}))
        eps_sweep[eps]["IPS_spearman"] = spearman(rank_order(gt), rank_order({t: e[t]["IPS"] for t in STATIC_TARGETS}))
    res["OPE-1c_eps_sweep"] = eps_sweep

    # OPE-1d 隐藏混杂
    log_c = generate_one_step_log(2000, seed=401, eps=0.3, confounded=True)
    gt_c = ground_truth_one_step(20000, seed=402, targets=STATIC_TARGETS, confounded=True)
    est_c = eval_static(log_c, STATIC_TARGETS, use_warm=False)
    est_o = eval_static(log_c, STATIC_TARGETS, use_warm=True)
    # 混杂变体 A：估计器误用观测-only propensity（忽略 warm 改写）——这才是
    # 真实混杂会发生的偏误；用真实 propensity 时 DR 具有双重稳健性，不应翻转。
    log_hat = []
    for row in log_c:
        r2 = dict(row); r2["propensity"] = row["propensity_observed_only"]; log_hat.append(r2)
    est_hat = eval_static(log_hat, STATIC_TARGETS, use_warm=False)
    # 混杂变体 B：更强混杂（warm 50%、奖励 3 倍、改写 90%）
    log_s = generate_one_step_log(2000, seed=403, eps=0.3, confounded=True,
                                  warm_prob=0.5, warm_boost=3.0, warm_override=0.9)
    gt_s = ground_truth_one_step(20000, seed=404, targets=STATIC_TARGETS, confounded=True,
                                 warm_prob=0.5, warm_boost=3.0)
    est_s = eval_static(log_s, STATIC_TARGETS, use_warm=False)
    res["OPE-1d_confounded"] = {
        "ground_truth": gt_c, "gt_rank": rank_order(gt_c),
        "DR_rank_no_warm": rank_order({t: est_c[t]["DR"] for t in STATIC_TARGETS}),
        "DR_spearman_no_warm": spearman(rank_order(gt_c), rank_order({t: est_c[t]["DR"] for t in STATIC_TARGETS})),
        "DR_rank_oracle_warm": rank_order({t: est_o[t]["DR"] for t in STATIC_TARGETS}),
        "DR_spearman_oracle": spearman(rank_order(gt_c), rank_order({t: est_o[t]["DR"] for t in STATIC_TARGETS})),
        "estimates_no_warm": est_c, "estimates_oracle": est_o,
        "DR_rank_propensity_misspecified": rank_order({t: est_hat[t]["DR"] for t in STATIC_TARGETS}),
        "DR_spearman_propensity_misspecified": spearman(rank_order(gt_c), rank_order({t: est_hat[t]["DR"] for t in STATIC_TARGETS})),
        "strong_confounded_gt_rank": rank_order(gt_s),
        "strong_confounded_DR_rank": rank_order({t: est_s[t]["DR"] for t in STATIC_TARGETS}),
        "strong_confounded_DR_spearman": spearman(rank_order(gt_s), rank_order({t: est_s[t]["DR"] for t in STATIC_TARGETS})),
        "strong_confounded_DR_values": {t: est_s[t]["DR"] for t in STATIC_TARGETS},
        "strong_confounded_gt": gt_s,
    }

    # OPE-2 序贯 naive
    seq_log = generate_sequential_log(200, 24, seed=501, eps=0.3)
    est_seq = eval_static(seq_log, SIX)
    # human_rules 在序贯日志中无效：其内部计数器是目标策略自身的反事实历史，
    # 无法从 logging 轨迹恢复，故排名计算排除它，仅作示意保留（见报告）。
    # 真值：fresh run（确定性六基线，与 run_all 一致），换算为每账户总管道
    truth = sim.run_all(seed=999, n_accounts=1000, weeks=24)  # 大样本真值，降低真值噪声对排序对比的干扰
    gt_seq = {t: truth[t]["pipeline"] / 1000 for t in SIX}  # truth 为 1000 账户，分母必须对应
    res["OPE-2_sequential_naive"] = {
        "ground_truth_per_account_pipeline": gt_seq, "gt_rank": rank_order(gt_seq),
        "DR_rank_all6_incl_invalid_human": rank_order({t: est_seq[t]["DR"] for t in SIX}),
        "DR_rank_excl_human": rank_order({t: est_seq[t]["DR"] for t in SIX if t != "human_rules"}),
        "DR_spearman_excl_human": spearman(rank_order({t: gt_seq[t] for t in SIX if t != "human_rules"}),
                                            rank_order({t: est_seq[t]["DR"] for t in SIX if t != "human_rules"})),
        "estimates": est_seq,
        "note": "naive per-week DR treats weeks as independent bandit samples; "
                "state carryover (reputation, qualified, touches) is only partially "
                "captured by context buckets. See phase2b_ope_report.md for interpretation.",
    }

    Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False)[:12000])


if __name__ == "__main__":
    main()
