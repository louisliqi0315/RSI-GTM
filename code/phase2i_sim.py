"""
Phase 2i — 纯时间对照（A）与候选空间扩大（B），48 周 / 8 周 epoch
（新文件，不改动 gtm_sim.py / phase2d_* / phase2f_* / phase2g_* / phase2h_* /
任何论文稿）

合成数据声明：全部机制均为合成假设，不是真实厂商数据，不宣称真实
转化率、收入、厂商表现或跨厂商泛化。

与 2f/2g/2h 同口径（仅预注册改动）：
- 同一门容忍（退订 +0.2、投诉 +0.1、信任上限 1.10 倍、wait_share < 0.95、
  真值 > 现任）、同一验证集口径（200 账户 / 8 周 / 种子 seed+1000、seed+2000）、
  同一主指标（冻结评估器 pipeline_per_trust）、同一假采纳定义、同一伤害指标。
- A 臂：旧二元候选集（phase2f_sim._candidates_w_only）不变，主运行
  epoch 8 周、时程 48 周；与 2g 的唯一差别是时程 24→48 周。
- B 臂：epoch 同样 8 周、时程 48 周，与 A 的唯一差别是候选空间扩大
  （见 _candidates_expanded 与 policy_i 的 W2 定义）；门容忍与验证集不变。
- policy_i：对 W0/W1 逐行复现 phase2d_sim.policy_d；W2 为中间强度
  工作流（见模块说明），仅在三处与 W0/W1 不同。B 臂主运行与验证集
  均用 policy_i；A/STATIC 臂用原 policy_d / run_policy，不混用。
- 快照不消耗随机数：finalize_metrics 为纯计算，不触碰 rng，
  故逐段快照不改变账户轨迹；空比较种子上 A/B 与 STATIC 仍须逐种子完全相等。
"""
from __future__ import annotations

import random
from typing import Dict, List

from gtm_sim import (
    make_accounts, evolve_account, apply_action, finalize_metrics, new_metrics,
)
from phase2d_sim import policy_d, run_policy, _gate_pass, _legal, _over_budget, _state_features
from phase2f_sim import _candidates_w_only, BASE_CFG

WEEKS_I = 48
EPOCH_I = 8
WORKFLOWS = ["W0", "W1", "W2"]


def policy_i(acct, obs: float, cfg: Dict, rng: random.Random) -> str:
    """phase2i 策略。cfg.workflow in {W0, W1, W2}，state 恒 S0（本阶段）。

    W0：policy_d 的 W0 行为原样（无冷静、无轻触达优先、无伙伴优先）。
    W1：policy_d 的 W1 行为原样（冷静触发 ≥3、轻触达优先、伙伴优先）。
    W2（中间强度，新增）：
      (a) 轻触达优先保留：t1 意图 ≥0.65 且本周尚未触达 → TRIAL；
      (b) 冷静触发放宽：近 4 周触达 ≥4（而非 W1 的 ≥3）且未合格 → STOP_COOLING；
      (c) 伙伴使能优先取消：t2 行为与 W0 完全相同。
    其余分支（阈值、λ、价值-成本判断、WAIT、预算硬约束、S1 特征）
    与 policy_d 完全相同；S1 分支保留以便与 policy_d 逐行对齐，
    本阶段状态恒 S0 故不触发。
    """
    if _over_budget(acct):
        return "WAIT"
    workflow = cfg.get("workflow", "W0")
    state = cfg.get("state", "S0")
    threshold = cfg.get("threshold", 0.40)
    lam = cfg.get("lambda", 3.0)
    feats = _state_features(acct, obs)
    if state == "S1":
        eff = min(1.0, max(0.0, feats["smoothed"] + 0.3 * feats["trend"]))
    else:
        eff = obs
    touches_recent = sum(acct.touches_last4[-4:])
    # 冷静触发：W1 为 ≥3，W2 为 ≥4（更晚），W0 无冷静。
    if workflow == "W1" and touches_recent >= 3 and not acct.qualified:
        return "STOP_COOLING"
    if workflow == "W2" and touches_recent >= 4 and not acct.qualified:
        return "STOP_COOLING"
    if acct.track == "t1":
        if eff >= 0.65:
            # 轻触达优先：W1 与 W2 在本周尚未触达时给 TRIAL 而非 DEEP；W0 给 DEEP。
            if workflow in ("W1", "W2") and touches_recent == 0:
                action, value, cost = "TRIAL", 10.0 * eff, 1.5
            else:
                action, value, cost = "DEEP", 12.0 * eff, 3.0
        elif eff >= threshold:
            action, value, cost = "LIGHT", 6.0 * eff, 1.0
        elif eff >= 0.25:
            action, value, cost = "TRIAL", 10.0 * eff, 1.5
        else:
            return "WAIT"
    else:
        if eff >= threshold:
            # 伙伴优先：仅 W1 在伙伴效能 <0.8 时提前 PARTNER_ENABLE；W2 与 W0 相同。
            if workflow == "W1" and acct.partner_effectiveness < 0.8:
                return "PARTNER_ENABLE"
            action, value, cost = "PARTNER_TOUCH", 9.0 * eff, 1.5
        elif acct.partner_effectiveness < 0.8:
            return "PARTNER_ENABLE"
        else:
            return "WAIT"
    if value - lam * cost <= 0:
        return "WAIT"
    return action


def run_policy_i(accounts, cfg: Dict, weeks: int, seed: int) -> Dict:
    """用 policy_i 在给定账户上跑 weeks 周，返回真值指标（冻结评估器）。
    逐行对齐 phase2d_sim.run_policy，仅策略函数由 policy_d 换为 policy_i。"""
    rng = random.Random(seed)
    metrics = new_metrics()
    for _ in range(weeks):
        for acct in accounts:
            evolve_account(acct, rng)
            obs = acct.observed_intent(rng)
            action = _legal(acct, policy_i(acct, obs, cfg, rng))
            apply_action(acct, action, rng, metrics)
    return finalize_metrics(metrics, accounts)


def _candidates_expanded(cfg: Dict) -> List[Dict]:
    """B 臂候选集：2 个非现任工作流 × 3 种阈值/λ组合，共 6 个。状态恒 S0。"""
    cur = cfg.get("workflow", "W0")
    others = [w for w in WORKFLOWS if w != cur]
    thr = cfg.get("threshold", 0.40)
    lam = cfg.get("lambda", 3.0)
    tunes = [
        (thr, lam),
        (min(0.8, thr + 0.05), lam),
        (max(0.15, thr - 0.05), max(1.0, lam - 1.0)),
    ]
    return [
        {"workflow": w, "state": "S0", "threshold": t, "lambda": l}
        for w in others for (t, l) in tunes
    ]


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


def run_arm_i(arm: str, seed: int, n_accounts: int, weeks: int = WEEKS_I,
              epoch: int = EPOCH_I) -> Dict:
    """跑一 2i 臂。arm in {STATIC, A, B}。主运行循环逐行对齐 phase2h_sim.run_arm_h，
    仅 epoch 为 8 周；A 用原 policy_d/验证集，B 用 policy_i/验证集。"""
    assert arm in ("STATIC", "A", "B")
    cfg: Dict = dict(BASE_CFG)
    rng = random.Random(seed)
    accounts = make_accounts(n_accounts, seed)
    metrics = new_metrics()
    veto_log: List[Dict] = []
    fake_adoptions = 0
    adoptions = 0
    progressive_adoptions = 0
    prev_workflow_before_last_adoption = None  # 上一次采纳所离开的工作流
    epochs_evaluated = 0
    adoption_weeks: List[int] = []
    adoption_workflows: List[str] = []
    snapshots: List[Dict] = []
    for start in range(0, weeks, epoch):
        epoch_weeks = min(epoch, weeks - start)
        for _ in range(epoch_weeks):
            for acct in accounts:
                evolve_account(acct, rng)
                obs = acct.observed_intent(rng)
                if arm == "B":
                    action = _legal(acct, policy_i(acct, obs, cfg, rng))
                else:
                    action = _legal(acct, policy_d(acct, obs, cfg, rng))
                apply_action(acct, action, rng, metrics)
        snap = _snapshot(metrics, accounts)
        snap["week"] = start + epoch_weeks
        snapshots.append(snap)
        if start + epoch_weeks >= weeks:
            break
        if arm == "STATIC":
            continue  # 静态 G：从不评估候选，从不递归
        # ---- 递归候选评估（验证集口径与 2f/2g/2h 完全相同）----
        if arm == "B":
            incumbent_val = run_policy_i(make_accounts(200, seed + 1000), cfg, 8, seed + 2000)
            cands = _candidates_expanded(cfg)
            cand_true = [run_policy_i(make_accounts(200, seed + 1000), c, 8, seed + 2000)
                         for c in cands]
        else:
            incumbent_val = run_policy(make_accounts(200, seed + 1000), cfg, 8, seed + 2000)
            cands = _candidates_w_only(cfg)
            cand_true = [run_policy(make_accounts(200, seed + 1000), c, 8, seed + 2000)
                         for c in cands]
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
            old_wf = cfg.get("workflow", "W0")
            new_wf = cands[chosen]["workflow"]
            # 递进采纳仅对第 2 次及以后的采纳定义：首次采纳无“上一次
            # 采纳所离开的工作流”可比，故不计入递进采纳。
            if prev_workflow_before_last_adoption is not None \
                    and new_wf != prev_workflow_before_last_adoption:
                progressive_adoptions += 1
            prev_workflow_before_last_adoption = old_wf
            adoptions += 1
            adoption_weeks.append(start + epoch_weeks)
            adoption_workflows.append(new_wf)
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
        "snapshots": snapshots,
        "final_config": cfg,
        "empty_comparison": bool(adoptions == 0 and cfg == dict(BASE_CFG)),
    })
    return result
