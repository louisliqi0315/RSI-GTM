"""
Phase 2k — 双样本门臂（E）与回退臂（F），48 周 / 8 周 epoch
（新文件，不改动 gtm_sim.py / phase2d_* / phase2f_* / phase2g_* / phase2h_* /
phase2i_* / phase2j_* / 任何论文稿）

合成数据声明：全部机制均为合成假设，不是真实厂商数据，不宣称真实
转化率、收入、厂商表现或跨厂商泛化。

与 2j 同口径（仅预注册改动）：
- 同一门容忍（退订 +0.2、投诉 +0.1、信任上限 1.10 倍、wait_share < 0.95、
  真值 > 现任）、同一验证集规模（200 账户 / 8 周）、同一主指标
  （冻结评估器 pipeline_per_trust）、同一假采纳定义、同一伤害指标、
  同一静态 G（全程固定 {W0, S0, threshold 0.40, lambda 3.0}）。
- 对照臂 D0：复现 2j 臂 D（每 epoch 独立验证种子：第 e 次评估
  账户种子 seed+1000+e*10000、运行种子 seed+2000+e*10000；
  同一 epoch 内现任与全部候选共用该 epoch 的验证样本；
  旧二元候选集 4 变体；最优候选一票否决规则不变）。
- 臂 E：与 D0 的唯一差别是采纳确认——候选在当 epoch 新鲜验证样本上
  通过门后，还必须在第二个独立新鲜样本（账户种子
  seed+1000+e*10000+5000、运行种子 seed+2000+e*10000+5000，
  规模同为 200 账户 / 8 周）上再次通过同一门规则（第二样本上被选候选
  vs 第二样本上的现任），才采纳；否则整轮否决，不回退。
- 臂 F：与 D0 的唯一差别是门规则——最优候选未通过门时不整轮否决，
  而是按验证集管道/信任排序依次检查次优候选，采纳第一个通过门的
  候选；全部候选均未通过才整轮否决。
- 快照不消耗随机数：finalize_metrics 为纯计算，不触碰 rng，
  故逐段快照不改变账户轨迹；空比较种子上各臂与 STATIC 仍须
  逐种子完全相等。
"""
from __future__ import annotations

import random
from typing import Dict, List

from gtm_sim import (
    make_accounts, evolve_account, apply_action, finalize_metrics, new_metrics,
)
from phase2d_sim import policy_d, run_policy, _gate_pass, _legal
from phase2f_sim import _candidates_w_only, BASE_CFG

WEEKS_K = 48
EPOCH_K = 8


def _validation_seeds(arm: str, seed: int, epoch_idx: int):
    """返回 (账户种子, 运行种子)。D0/E/F 各 epoch 独立，与 2j 臂 D 相同。

    epoch_idx 为第几次评估（1..5）。账户种子 seed+1000+e*10000，
    运行种子 seed+2000+e*10000；与主运行种子（seed）均不冲突。
    """
    return seed + 1000 + epoch_idx * 10000, seed + 2000 + epoch_idx * 10000


def _confirmation_seeds(seed: int, epoch_idx: int):
    """E 臂第二样本种子：当 epoch 样本种子各 +5000。"""
    a, r = _validation_seeds("D0", seed, epoch_idx)
    return a + 5000, r + 5000


def _snapshot(metrics: Dict, accounts) -> Dict:
    fm = finalize_metrics(metrics, accounts)
    return {
        "pipeline_per_trust": fm["pipeline_per_trust"],
        "pipeline": fm["pipeline"],
        "trust_consumed": fm["trust_consumed"],
        "unsubscribe_rate_per_100_touches": fm["unsubscribe_rate_per_100_touches"],
        "complaint_rate_per_100_touches": fm["complaint_rate_per_100_touches"],
        "mean_reputation_change": fm["mean_reputation_change"],
        "wait_share": fm["wait_share"],
    }


def run_arm_k(arm: str, seed: int, n_accounts: int, weeks: int = WEEKS_K,
              epoch: int = EPOCH_K) -> Dict:
    """跑一 2k 臂。arm in {STATIC, D0, E, F}。主运行循环逐行对齐 phase2j_sim.run_arm_j。"""
    assert arm in ("STATIC", "D0", "E", "F")
    cfg: Dict = dict(BASE_CFG)
    rng = random.Random(seed)
    accounts = make_accounts(n_accounts, seed)
    metrics = new_metrics()
    veto_log: List[Dict] = []
    fake_adoptions = 0
    adoptions = 0
    progressive_adoptions = 0
    prev_workflow_before_last_adoption = None
    epochs_evaluated = 0
    adoption_weeks: List[int] = []
    adoption_workflows: List[str] = []
    adoption_details: List[Dict] = []
    snapshots: List[Dict] = []
    validation_seed_log: List[Dict] = []
    for start in range(0, weeks, epoch):
        epoch_weeks = min(epoch, weeks - start)
        for _ in range(epoch_weeks):
            for acct in accounts:
                evolve_account(acct, rng)
                obs = acct.observed_intent(rng)
                action = _legal(acct, policy_d(acct, obs, cfg, rng))
                apply_action(acct, action, rng, metrics)
        snap = _snapshot(metrics, accounts)
        snap["week"] = start + epoch_weeks
        snapshots.append(snap)
        if start + epoch_weeks >= weeks:
            break
        if arm == "STATIC":
            continue
        # ---- 递归候选评估（验证集规模 200 / 8 周，种子规则见 _validation_seeds）----
        epochs_evaluated += 1
        acct_seed, run_seed = _validation_seeds(arm, seed, epochs_evaluated)
        log_entry = {"epoch": epochs_evaluated, "week": start + epoch_weeks,
                     "account_seed": acct_seed, "run_seed": run_seed}
        incumbent_val = run_policy(make_accounts(200, acct_seed), cfg, 8, run_seed)
        cands = _candidates_w_only(cfg)
        cand_true = [run_policy(make_accounts(200, acct_seed), c, 8, run_seed)
                     for c in cands]
        ranked = sorted(range(len(cands)),
                        key=lambda i: cand_true[i]["pipeline_per_trust"], reverse=True)
        chosen = None
        chosen_rank = None
        if arm == "F":
            # 回退：按验证集排序依次检查，采纳第一个通过门的候选。
            for rank, idx in enumerate(ranked):
                if _gate_pass(cand_true[idx], incumbent_val, 0.2, 0.1, 1.10):
                    chosen, chosen_rank = idx, rank
                    break
            if chosen is None:
                veto_log.append({"epoch": epochs_evaluated, "week": start + epoch_weeks,
                                 "reason": "all_candidates_failed",
                                 "best_true": cand_true[ranked[0]]["pipeline_per_trust"],
                                 "incumbent_true": incumbent_val["pipeline_per_trust"]})
        else:
            best_idx = ranked[0]
            if _gate_pass(cand_true[best_idx], incumbent_val, 0.2, 0.1, 1.10):
                if arm == "E":
                    acct2, run2 = _confirmation_seeds(seed, epochs_evaluated)
                    log_entry["confirmation_account_seed"] = acct2
                    log_entry["confirmation_run_seed"] = run2
                    incumbent_val2 = run_policy(make_accounts(200, acct2), cfg, 8, run2)
                    cand_val2 = run_policy(make_accounts(200, acct2),
                                           cands[best_idx], 8, run2)
                    if _gate_pass(cand_val2, incumbent_val2, 0.2, 0.1, 1.10):
                        chosen, chosen_rank = best_idx, 0
                    else:
                        veto_log.append({"epoch": epochs_evaluated, "week": start + epoch_weeks,
                                         "reason": "confirmation_failed",
                                         "best_true": cand_true[best_idx]["pipeline_per_trust"],
                                         "incumbent_true": incumbent_val["pipeline_per_trust"],
                                         "confirmation_true": cand_val2["pipeline_per_trust"],
                                         "confirmation_incumbent_true": incumbent_val2["pipeline_per_trust"]})
                else:
                    chosen, chosen_rank = best_idx, 0
            else:
                veto_log.append({"epoch": epochs_evaluated, "week": start + epoch_weeks,
                                 "reason": "gate_failed",
                                 "best_true": cand_true[best_idx]["pipeline_per_trust"],
                                 "incumbent_true": incumbent_val["pipeline_per_trust"]})
        validation_seed_log.append(log_entry)
        if chosen is not None:
            old_wf = cfg.get("workflow", "W0")
            new_wf = cands[chosen]["workflow"]
            if prev_workflow_before_last_adoption is not None \
                    and new_wf != prev_workflow_before_last_adoption:
                progressive_adoptions += 1
            prev_workflow_before_last_adoption = old_wf
            adoptions += 1
            adoption_weeks.append(start + epoch_weeks)
            adoption_workflows.append(new_wf)
            adoption_details.append({"epoch": epochs_evaluated, "week": start + epoch_weeks,
                                     "workflow": new_wf, "rank": chosen_rank,
                                     "fallback_used": bool(chosen_rank and chosen_rank > 0),
                                     "threshold": cands[chosen]["threshold"],
                                     "lambda": cands[chosen]["lambda"]})
            if cand_true[chosen]["pipeline_per_trust"] > incumbent_val["pipeline_per_trust"] \
                    and cand_true[chosen]["pipeline_per_trust"] <= incumbent_val["pipeline_per_trust"]:
                fake_adoptions += 1
            cfg = dict(cands[chosen])
    result = finalize_metrics(metrics, accounts)
    result.update({
        "arm": arm,
        "claimed_pipeline_per_trust": result["pipeline_per_trust"],
        "separation_gap": 0.0,
        "claimed_unsubscribe_rate": result["unsubscribe_rate_per_100_touches"],
        "claimed_complaint_rate": result["complaint_rate_per_100_touches"],
        "vetoes": len(veto_log),
        "veto_log": veto_log,
        "fake_adoptions": fake_adoptions,
        "adoptions": adoptions,
        "progressive_adoptions": progressive_adoptions,
        "epochs_evaluated": epochs_evaluated,
        "adoption_weeks": adoption_weeks,
        "adoption_workflows": adoption_workflows,
        "adoption_details": adoption_details,
        "snapshots": snapshots,
        "validation_seed_log": validation_seed_log,
        "final_config": cfg,
        "empty_comparison": bool(adoptions == 0 and cfg == dict(BASE_CFG)),
    })
    return result
