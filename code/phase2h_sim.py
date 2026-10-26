"""
Phase 2h — 工作流-only 有门 vs 静态 G，48 周 / 4 周 epoch 可扩展性检验
（新文件，不改动 gtm_sim.py / phase2d_* / phase2f_* / phase2g_* / 任何论文稿）

合成数据声明：全部机制均为合成假设，不是真实厂商数据，不宣称真实
转化率、收入、厂商表现或跨厂商泛化。

与 2f/2g 同口径（仅两处预注册改动）：
- 同一仿真器：直接复用 phase2d_sim.policy_d / _gate_pass / _legal 与
  gtm_sim.make_accounts / evolve_account / observed_intent / apply_action /
  finalize_metrics，以及 phase2f_sim._candidates_w_only / BASE_CFG。
- 同一门容忍（退订 +0.2、投诉 +0.1、信任上限 1.10 倍、wait_share < 0.95、
  真值 > 现任）、同一验证集口径（200 账户 / 8 周 / 种子 seed+1000、seed+2000）、
  同一主指标（冻结评估器 pipeline_per_trust）、同一假采纳定义、同一伤害指标。
- 预注册改动 1：主运行时程 24 周 → 48 周。
- 预注册改动 2：主运行 epoch 8 周 → 4 周，故 48 周内共 11 次递归评估
  （第 4、8、…、44 周后）。验证集时程仍为 8 周，不随 epoch 缩短。
- 快照不消耗随机数：finalize_metrics 为纯计算，不触碰 rng，
  故逐段快照不改变账户轨迹；空比较种子上 W 与 STATIC 仍须逐种子完全相等。
"""
from __future__ import annotations

import random
from typing import Dict, List

from gtm_sim import (
    make_accounts, evolve_account, apply_action, finalize_metrics, new_metrics,
)
from phase2d_sim import policy_d, run_policy, _gate_pass, _legal
from phase2f_sim import _candidates_w_only, BASE_CFG

EPOCH_H = 4
WEEKS_H = 48


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


def run_arm_h(arm: str, seed: int, n_accounts: int, weeks: int = WEEKS_H,
              epoch: int = EPOCH_H) -> Dict:
    """跑一 2h 臂。arm in {STATIC, W}。主运行循环逐行对齐 phase2f_sim.run_arm_f，
    仅 epoch 由 8 周改为 4 周，并增加逐段快照与采纳轮次记录。"""
    assert arm in ("STATIC", "W")
    cfg: Dict = dict(BASE_CFG)
    rng = random.Random(seed)
    accounts = make_accounts(n_accounts, seed)
    metrics = new_metrics()
    veto_log: List[Dict] = []
    fake_adoptions = 0
    adoptions = 0
    epochs_evaluated = 0
    adoption_weeks: List[int] = []
    snapshots: List[Dict] = []
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
            continue  # 静态 G：从不评估候选，从不递归
        # ---- 递归候选评估（与 2f/2g 完全相同的验证集口径）----
        incumbent_val = run_policy(make_accounts(200, seed + 1000), cfg, 8, seed + 2000)
        cands = _candidates_w_only(cfg)
        cand_true: List[Dict] = []
        for cand in cands:
            cand_true.append(run_policy(make_accounts(200, seed + 1000), cand, 8, seed + 2000))
        epochs_evaluated += 1
        best_idx = max(range(len(cands)), key=lambda i: cand_true[i]["pipeline_per_trust"])
        if _gate_pass(cand_true[best_idx], incumbent_val, 0.2, 0.1, 1.10):
            chosen = best_idx
        else:
            veto_log.append({"epoch": epochs_evaluated, "week": start + epoch_weeks,
                             "reason": "gate_failed",
                             "best_true": cand_true[best_idx]["pipeline_per_trust"],
                             "incumbent_true": incumbent_val["pipeline_per_trust"]})
            chosen = None
        if chosen is not None:
            adoptions += 1
            adoption_weeks.append(start + epoch_weeks)
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
        "epochs_evaluated": epochs_evaluated,
        "adoption_weeks": adoption_weeks,
        "snapshots": snapshots,
        "final_config": cfg,
        "empty_comparison": bool(adoptions == 0 and cfg == dict(BASE_CFG)),
    })
    return result
