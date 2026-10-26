"""
Phase 2d — 决定性实验仿真器（新文件，不改动 gtm_sim.py）

合成数据声明：全部机制均为合成假设，不是真实厂商数据，不宣称真实
转化率、收入或厂商表现。信任代理（声誉、退订、投诉）是设定机制，
不是实测品牌折损。

设计（对应 foundational-candidates-v1.md §4）：
- 递归改进必须超越阈值层：候选同时改变工作流拓扑与状态表示中的至少一层。
  工作流 W0 = 基线 G 的动作选择；W1 = 轻触达优先 + 三触达未合格后冷静的序列拓扑。
  状态表示 S0 = 快照观测意图；S1 = 事件流表示（观测意图 EMA + 趋势 + 疲劳调整）。
- 评估器：
  B：冻结评估器（与 gtm_sim.finalize_metrics 相同的真值指标）+ 验证门。
  C：无门，采纳按内部代理指标（回复数）最高，不检查伤害/预算。
  D：验证器可写篡改臂——内部报告被改写为真值与代理的混合（回复越多
     放大越多）、伤害被清零，采纳按篡改后分数最高；主运行的“宣称指标”
     同样被篡改，与真值分离。均匀放大不算篡改（不改变排序），故不采用。
  E：与 B 相同，但评估器改进走独立审批周期（见 phase2d_run.py）。
- 假采纳（fake adoption）定义（单位无关，可跨臂比较）：
  某 epoch 采纳的候选，其内部采纳分数高于现任内部分数，
  但独立冻结评估器给出的真值管道/信任不高于现任真值。
  B/E 的内部分数就是真值，故按定义假采纳应为 0（门要求真值 > 现任）；
  C/D 的内部分数是代理/篡改分数，故假采纳可能 > 0。
- 主运行宣称指标（用于分离度 gap = 宣称 - 真值）：
  B/E：宣称 = 真值；C：宣称 = 回复数 x 20 / 信任消耗（把每次回复都当管道
     的代理估计，合成假设，明确标注）；D：宣称 = 真值 x 1.5，伤害宣称为 0。
  该宣称定义在实验前写定，不事后调参。
- 吸收态实验（见 run 文件）：吸收机制是本实验编码的模型假设，
  通过只能证明“给定吸收态假设，动力学产生不对称/溢出模式”（模型一致性），
  不能证明真实世界不可逆。真实 T2/T3 仍需 GitHub 公开检验（未做）。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import gtm_sim
from gtm_sim import (
    Account, TRACK1_ACTIONS, TRACK2_ACTIONS, ACTIONS,
    apply_action, evolve_account, make_accounts,
    finalize_metrics, new_metrics,
)

WEEKS = 24
EPOCH = 8


def _over_budget(acct: Account) -> bool:
    return acct.trust_consumed >= gtm_sim.TRUST_BUDGET or acct.reputation < 0.45


def _state_features(acct: Account, obs: float) -> Dict:
    """更新并返回 S1 事件流特征，存在账户属性上（仿照 gtm_sim 人工规则的写法）。"""
    hist = getattr(acct, "_d_hist", None)
    if hist is None:
        hist = []
        acct._d_hist = hist  # type: ignore[attr-defined]
    hist.append(obs)
    if len(hist) > 4:
        hist.pop(0)
    smoothed = getattr(acct, "_d_smooth", obs)
    smoothed = 0.5 * smoothed + 0.5 * obs
    acct._d_smooth = smoothed  # type: ignore[attr-defined]
    trend = hist[-1] - hist[0] if len(hist) >= 2 else 0.0
    return {"smoothed": smoothed, "trend": trend, "fatigue": acct.fatigue_factor()}


def policy_d(acct: Account, obs: float, cfg: Dict, rng: random.Random) -> str:
    """cfg: workflow in {W0,W1}, state in {S0,S1}, threshold, lambda."""
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
    # W1 拓扑：三触达未合格后强制冷静一轮（序列结构本身是改进对象）
    if workflow == "W1" and touches_recent >= 3 and not acct.qualified:
        return "STOP_COOLING"
    if acct.track == "t1":
        if eff >= 0.65:
            if workflow == "W1" and touches_recent == 0:
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


def _legal(acct: Account, action: str) -> str:
    if acct.track == "t1" and action not in TRACK1_ACTIONS + ["STOP_COOLING"]:
        return "WAIT"
    if acct.track == "t2" and action not in TRACK2_ACTIONS:
        return "WAIT"
    return action


def run_policy(accounts: List[Account], cfg: Dict, weeks: int, seed: int) -> Dict:
    """用 policy_d 在给定账户上跑 weeks 周，返回真值指标（冻结评估器）。"""
    rng = random.Random(seed)
    metrics = new_metrics()
    for _ in range(weeks):
        for acct in accounts:
            evolve_account(acct, rng)
            obs = acct.observed_intent(rng)
            action = _legal(acct, policy_d(acct, obs, cfg, rng))
            apply_action(acct, action, rng, metrics)
    return finalize_metrics(metrics, accounts)


def _gate_pass(val: Dict, incumbent: Dict, harm_unsub_tol: float = 0.2,
               harm_comp_tol: float = 0.1, trust_cap: float = 1.10) -> bool:
    g1 = val["pipeline_per_trust"] > incumbent["pipeline_per_trust"]
    g3 = (val["unsubscribe_rate_per_100_touches"] <= incumbent["unsubscribe_rate_per_100_touches"] + harm_unsub_tol
          and val["complaint_rate_per_100_touches"] <= incumbent["complaint_rate_per_100_touches"] + harm_comp_tol
          and val["wait_share"] < 0.95)
    g5 = val["trust_consumed"] <= incumbent["trust_consumed"] * trust_cap
    return bool(g1 and g3 and g5)


def _candidates(cfg: Dict) -> List[Dict]:
    """每个候选都改变工作流或状态表示中的至少一层（不只是阈值）。"""
    wf = cfg.get("workflow", "W0")
    st = cfg.get("state", "S0")
    other_wf = "W1" if wf == "W0" else "W0"
    other_st = "S1" if st == "S0" else "S0"
    base_thr = cfg.get("threshold", 0.40)
    base_lam = cfg.get("lambda", 3.0)
    return [
        {"workflow": other_wf, "state": st, "threshold": base_thr, "lambda": base_lam},
        {"workflow": wf, "state": other_st, "threshold": base_thr, "lambda": base_lam},
        {"workflow": other_wf, "state": other_st, "threshold": min(0.8, base_thr + 0.05), "lambda": base_lam},
        {"workflow": other_wf, "state": st, "threshold": max(0.15, base_thr - 0.05), "lambda": max(1.0, base_lam - 1.0)},
    ]


def _proxy_pipeline_per_trust(val: Dict) -> float:
    """C 臂内部代理估计：每次回复都当作 20 单位管道（合成假设，见模块说明）。"""
    trust = max(1e-9, val["trust_consumed"])
    return val["replies"] * 20.0 / trust


def _tampered(val: Dict) -> Dict:
    """D 臂篡改后的报告：不是均匀放大（均匀放大不改变候选排序，算不上篡改）。
    篡改 = 把评估器改写为真值与代理的混合（80% 代理、20% 真值），
    回复越多的候选被放大得越多，排序因此偏离真值；伤害清零。
    主运行宣称指标用同一公式计算，见 run_arm。"""
    out = dict(val)
    proxy = _proxy_pipeline_per_trust(val)
    out["pipeline_per_trust"] = 0.2 * val["pipeline_per_trust"] + 0.8 * proxy
    out["pipeline"] = out["pipeline_per_trust"] * max(1e-9, val["trust_consumed"])
    out["unsubscribes"] = 0
    out["complaints"] = 0
    out["unsubscribe_rate_per_100_touches"] = 0.0
    out["complaint_rate_per_100_touches"] = 0.0
    out["replies"] = int(val["replies"] * 1.3)
    return out


def run_arm(arm: str, seed: int, n_accounts: int, weeks: int = WEEKS) -> Dict:
    """跑一臂主实验。arm in {B,C,D,E}。返回真值指标 + 宣称指标 + 否决日志。"""
    assert arm in ("B", "C", "D", "E")
    cfg: Dict = {"workflow": "W0", "state": "S0", "threshold": 0.40, "lambda": 3.0}
    rng = random.Random(seed)
    accounts = make_accounts(n_accounts, seed)
    metrics = new_metrics()
    veto_log: List[Dict] = []
    fake_adoptions = 0
    adoptions = 0
    epochs_evaluated = 0
    gate_changed = 0  # 仅 E：评估器改进被独立审批通过的次数
    harm_unsub_tol, harm_comp_tol, trust_cap = 0.2, 0.1, 1.10
    evaluator_version = 0
    for start in range(0, weeks, EPOCH):
        epoch_weeks = min(EPOCH, weeks - start)
        for _ in range(epoch_weeks):
            for acct in accounts:
                evolve_account(acct, rng)
                obs = acct.observed_intent(rng)
                action = _legal(acct, policy_d(acct, obs, cfg, rng))
                apply_action(acct, action, rng, metrics)
        if start + epoch_weeks >= weeks:
            break
        # ---- 递归候选评估（验证集：独立种子、独立账户）----
        incumbent_val = run_policy(make_accounts(200, seed + 1000), cfg, 8, seed + 2000)
        cands = _candidates(cfg)
        cand_true: List[Dict] = []
        cand_internal: List[float] = []
        for cand in cands:
            true_val = run_policy(make_accounts(200, seed + 1000), cand, 8, seed + 2000)
            cand_true.append(true_val)
            if arm == "D":
                cand_internal.append(_tampered(true_val)["pipeline_per_trust"])
            elif arm == "C":
                cand_internal.append(_proxy_pipeline_per_trust(true_val))
            else:
                cand_internal.append(true_val["pipeline_per_trust"])
        if arm == "B":
            incumbent_internal = incumbent_val["pipeline_per_trust"]
        elif arm == "C":
            incumbent_internal = _proxy_pipeline_per_trust(incumbent_val)
        elif arm == "D":
            incumbent_internal = _tampered(incumbent_val)["pipeline_per_trust"]
        else:
            incumbent_internal = incumbent_val["pipeline_per_trust"]
        epochs_evaluated += 1
        chosen = None
        if arm in ("B", "E"):
            # 有门：真值 > 现任且通过门才采纳
            best_idx = max(range(len(cands)), key=lambda i: cand_true[i]["pipeline_per_trust"])
            if _gate_pass(cand_true[best_idx], incumbent_val, harm_unsub_tol, harm_comp_tol, trust_cap):
                chosen = best_idx
            else:
                veto_log.append({"epoch": epochs_evaluated, "reason": "gate_failed",
                                 "best_true": cand_true[best_idx]["pipeline_per_trust"],
                                 "incumbent_true": incumbent_val["pipeline_per_trust"]})
        elif arm == "C":
            # 无门：按内部代理分数最高采纳（代理分数与真值管道不同）
            best_idx = max(range(len(cands)), key=lambda i: cand_internal[i])
            chosen = best_idx
        else:  # D
            best_idx = max(range(len(cands)), key=lambda i: cand_internal[i])
            chosen = best_idx
        if chosen is not None:
            adoptions += 1
            # 假采纳：内部高于现任，但真值不高于现任真值
            if cand_internal[chosen] > incumbent_internal and cand_true[chosen]["pipeline_per_trust"] <= incumbent_val["pipeline_per_trust"]:
                fake_adoptions += 1
            cfg = dict(cands[chosen])
        else:
            # 否决即回滚（参数不变），B/E 的 veto 已在上支记录；C/D 不否决
            pass
        if arm == "E":
            # 评估器改进独立审批：提议收紧门（伤害容忍 -0.05，信任上限 1.10->1.05）。
            # 审批测试（独立验证集、与策略改进分离）：G 必须仍优于回复贪心
            # 且被识别为伤害更高，否则提议被否决，评估器不变。
            val_g = run_policy(make_accounts(200, seed + 3000), {"workflow": "W0", "state": "S0", "threshold": 0.40, "lambda": 3.0}, 8, seed + 4000)
            # 回复贪心用 gtm_sim 原策略跑同样验证集
            rng2 = random.Random(seed + 4000)
            accts2 = make_accounts(200, seed + 3000)
            m2 = new_metrics()
            for _ in range(8):
                for acct in accts2:
                    evolve_account(acct, rng2)
                    obs = acct.observed_intent(rng2)
                    act = gtm_sim.policy_reply_greedy(acct, obs, {}, rng2)
                    act = _legal(acct, act)
                    apply_action(acct, act, rng2, m2)
            val_greedy = finalize_metrics(m2, accts2)
            if (val_g["pipeline_per_trust"] > val_greedy["pipeline_per_trust"]
                    and val_greedy["unsubscribe_rate_per_100_touches"] > val_g["unsubscribe_rate_per_100_touches"]):
                harm_unsub_tol = max(0.05, harm_unsub_tol - 0.05)
                trust_cap = 1.05
                evaluator_version += 1
                gate_changed += 1
            else:
                veto_log.append({"epoch": epochs_evaluated, "reason": "evaluator_improvement_rejected"})
    result = finalize_metrics(metrics, accounts)
    # 宣称指标
    if arm == "D":
        claimed = _tampered(result)["pipeline_per_trust"]
        claimed_unsub = 0.0
        claimed_comp = 0.0
    elif arm == "C":
        claimed = _proxy_pipeline_per_trust(result)
        claimed_unsub = result["unsubscribe_rate_per_100_touches"]
        claimed_comp = result["complaint_rate_per_100_touches"]
    else:
        claimed = result["pipeline_per_trust"]
        claimed_unsub = result["unsubscribe_rate_per_100_touches"]
        claimed_comp = result["complaint_rate_per_100_touches"]
    result.update({
        "arm": arm,
        "claimed_pipeline_per_trust": claimed,
        "separation_gap": claimed - result["pipeline_per_trust"],
        "claimed_unsubscribe_rate": claimed_unsub,
        "claimed_complaint_rate": claimed_comp,
        "vetoes": len(veto_log),
        "veto_log": veto_log,
        "fake_adoptions": fake_adoptions,
        "adoptions": adoptions,
        "epochs_evaluated": epochs_evaluated,
        "gate_changed": gate_changed,
        "evaluator_version": evaluator_version,
        "final_config": cfg,
        # 空比较：本臂的验证门/采纳在所有 epoch 中一次未变（参数与初始相同）
        "empty_comparison": bool(cfg == {"workflow": "W0", "state": "S0", "threshold": 0.40, "lambda": 3.0} and adoptions == 0),
    })
    return result


# ---------------------------------------------------------------- 吸收态实验

def run_absorbing(seed: int, n_accounts: int = 200) -> Dict:
    """
    模型一致性检验（不是真实世界证明）：
    - 基线期 8 周：所有队列用 G 策略跑，记录基线回应率。
    - 事件期：对照队列继续高价值动作（TRIAL/HUMAN）；吸收队列先触硬边界
      （声誉压至 0.10 且冻结——后续 WAIT/价值动作不再恢复声誉），再接受
      与对照完全相同的高价值动作 8 周；正向队列在基线期后接受高价值动作，
      用于度量同等幅度正向事件的增益（不对称比较）。
    - 溢出队列：自身未吸收，但与吸收账户同品牌（brand = id//20），
      品牌声誉惩罚使其声誉 -0.30（下限 0.10），再接受高价值动作。
    回应率 = 回复数/触达数（post 期）；合格率 = 合格数/账户数（post 期）。
    """
    rng = random.Random(seed)
    base_cfg = {"workflow": "W0", "state": "S0", "threshold": 0.40, "lambda": 3.0}

    def run_cohort(mode: str) -> Dict:
        accts = make_accounts(n_accounts, seed)
        # 基线期
        m_base = new_metrics()
        for _ in range(8):
            for acct in accts:
                evolve_account(acct, rng)
                obs = acct.observed_intent(rng)
                act = _legal(acct, policy_d(acct, obs, base_cfg, rng))
                apply_action(acct, act, rng, m_base)
        base_reply = m_base["replies"] / max(1, m_base["touches"])
        # 事件期：吸收队列冻结声誉
        absorbed = set()
        if mode in ("absorbed", "spillover"):
            # 吸收品牌：前 5 个品牌
            for acct in accts:
                if acct.id // 20 < 5:
                    if mode == "absorbed":
                        absorbed.add(acct.id)
                        acct.reputation = 0.10
                    else:
                        acct.reputation = max(0.10, acct.reputation - 0.30)
        m_post = new_metrics()
        qualified_before = sum(1 for a in accts if a.qualified)
        for _ in range(8):
            for acct in accts:
                evolve_account(acct, rng)
                # 吸收态冻结：WAIT 的声誉恢复与价值动作的恢复均不生效
                if acct.id in absorbed:
                    acct.reputation = 0.10
                obs = acct.observed_intent(rng)
                # post 期统一高价值动作：意图高则 HUMAN/DEEP，否则 TRIAL
                if acct.track == "t1":
                    act = "HUMAN" if obs >= 0.40 else "TRIAL"
                else:
                    act = "PARTNER_TOUCH" if obs >= 0.40 else "PARTNER_ENABLE"
                act = _legal(acct, act)
                apply_action(acct, act, rng, m_post)
                if acct.id in absorbed:
                    acct.reputation = 0.10
        post_reply = m_post["replies"] / max(1, m_post["touches"])
        post_qual = (sum(1 for a in accts if a.qualified) - qualified_before) / len(accts)
        return {"base_reply_rate": base_reply, "post_reply_rate": post_reply,
                "post_qualified_per_account": post_qual,
                "post_touches": m_post["touches"], "post_replies": m_post["replies"]}

    control = run_cohort("control")
    absorbed = run_cohort("absorbed")
    spillover = run_cohort("spillover")
    # 正向增益：对照 post 与基线的差（高价值动作本身带来的增益代理）
    positive_gain = control["post_reply_rate"] - control["base_reply_rate"]
    hard_drop = control["post_reply_rate"] - absorbed["post_reply_rate"]
    return {
        "control": control, "absorbed": absorbed, "spillover": spillover,
        "hard_drop_reply_rate": hard_drop,
        "positive_gain_reply_rate": positive_gain,
        "spillover_drop_reply_rate": control["post_reply_rate"] - spillover["post_reply_rate"],
        "absorbed_post_reply_ratio_to_control": absorbed["post_reply_rate"] / max(1e-9, control["post_reply_rate"]),
        "spillover_post_reply_ratio_to_control": spillover["post_reply_rate"] / max(1e-9, control["post_reply_rate"]),
    }
