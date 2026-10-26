"""
GTM-Sim v0 — 最小可运行合成仿真器（Phase 2a 原型骨架）

依赖：仅 Python 标准库（Python 3.10+）。不需要 pip install。

设计要点（对应 phase2-report.md §5.2）：
- 账户是合成的，不是真实厂商数据；潜变量意图、组织事件、用量爬坡/衰减、
  信任动力学全部由本文件内的显式机制生成，机制本身就是假设，不是测量。
- 信任负反馈环：高频 / 低质触达 -> 声誉与送达率下降 -> 后续触达效果下降。
  WAIT / 停止冷静会让疲劳衰减、声誉缓慢恢复，但不会把已消耗的信任预算清零。
- 信任预算按账户记账，不可跨账户挪用。G / G+ 在预算耗尽或声誉过低时强制 WAIT。
- 递归（G+）的单位是“被验证的改进”：候选参数只在通过验证门后才采纳，
  否则否决并回滚。评估器（evaluator）与候选策略分离：候选只能改策略参数，
  不能改评估函数、主指标或伤害指标的定义 —— 这是对 Gate G4 的最小实现。
- 本文件不含任何真实数据、不爬取、不购买、不推断个人数据。

动作空间（双轨）：
  Track 1（开发者 / API）: WAIT, LIGHT, DEEP, TRIAL, HUMAN
  Track 2（伙伴 / 生态）:   WAIT, PARTNER_TOUCH, PARTNER_ENABLE, STOP_COOLING
  其中 WAIT 与 STOP_COOLING 在两轨都可用；STOP_COOLING 是更强的冷静动作。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------- 动作定义

# 每个动作：信任成本、质量（越高烧信任越少、回复质量越高）、是否为直接触达
ACTIONS: Dict[str, Dict] = {
    "WAIT": {"trust_cost": 0.0, "quality": 0.0, "direct": False, "track": "both"},
    "LIGHT": {"trust_cost": 1.0, "quality": 0.7, "direct": True, "track": "t1"},
    "DEEP": {"trust_cost": 3.0, "quality": 1.0, "direct": True, "track": "t1"},
    "TRIAL": {"trust_cost": 1.5, "quality": 0.9, "direct": True, "track": "t1"},
    "HUMAN": {"trust_cost": 2.0, "quality": 1.2, "direct": True, "track": "t1"},
    "PARTNER_TOUCH": {"trust_cost": 1.5, "quality": 0.85, "direct": True, "track": "t2"},
    "PARTNER_ENABLE": {"trust_cost": 0.5, "quality": 0.0, "direct": False, "track": "t2"},
    "STOP_COOLING": {"trust_cost": 0.0, "quality": 0.0, "direct": False, "track": "both"},
}

TRACK1_ACTIONS = ["WAIT", "LIGHT", "DEEP", "TRIAL", "HUMAN"]
TRACK2_ACTIONS = ["WAIT", "PARTNER_TOUCH", "PARTNER_ENABLE", "STOP_COOLING"]

# 账户 segment 的管道基值（合成单位，不是货币、不是真实收入）
SEGMENT_VALUE = {"developer": 10.0, "enterprise": 50.0, "partner": 30.0}
# Track 2 的分成后净留存系数（合成假设：经伙伴结算后厂商净得一部分）
PARTNER_NET_FACTOR = 0.7
# Phase 2b 参数化（v0 字面值）：高质触达损伤 0.015，低质触达损伤 0.030，疲劳系数 0.30
REPUTATION_DAMAGE_HIGH = 0.015
REPUTATION_DAMAGE_LOW = 0.030
FATIGUE_COEF = 0.30


@dataclass
class Account:
    id: int
    track: str  # "t1" 或 "t2"
    segment: str
    intent: float  # 潜变量意图，0-1，不可直接观测的“真值”；策略只能看到带噪观测
    usage: float = 0.0  # 产品内用量（合成单位）
    reputation: float = 1.0  # 声誉代理，0-1
    trust_consumed: float = 0.0
    touches_last4: List[int] = field(default_factory=list)  # 近 4 周触达记录（1=触达）
    partner_effectiveness: float = 0.5  # 仅 Track 2：伙伴使能积累
    weeks_since_touch: int = 99
    qualified: bool = False

    def observed_intent(self, rng: random.Random) -> float:
        """策略看到的意图是带噪观测，不是真值。"""
        return min(1.0, max(0.0, self.intent + rng.gauss(0, 0.08)))

    def deliverability(self) -> float:
        return 0.5 + 0.5 * self.reputation

    def fatigue_factor(self) -> float:
        recent = sum(self.touches_last4[-4:])
        return 1.0 / (1.0 + FATIGUE_COEF * recent)


def make_accounts(n: int, seed: int) -> List[Account]:
    rng = random.Random(seed)
    accounts: List[Account] = []
    for i in range(n):
        track = "t2" if rng.random() < 0.40 else "t1"
        if track == "t2":
            segment = "partner"
        else:
            segment = "enterprise" if rng.random() < 0.30 else "developer"
        accounts.append(Account(
            id=i, track=track, segment=segment,
            intent=rng.uniform(0.05, 0.45),
        ))
    return accounts


def evolve_account(acct: Account, rng: random.Random) -> None:
    """每周潜变量演化：意图缓慢衰减 + 组织事件冲击 + 用量自然衰减。"""
    # 组织事件：融资 / 招人 / 换帅等（合成事件，概率固定、与真实厂商无关）
    event = rng.random() < 0.08
    if event:
        acct.intent = min(1.0, acct.intent + rng.uniform(0.15, 0.40))
    acct.intent = min(1.0, max(0.0, acct.intent * 0.97 + rng.gauss(0, 0.02)))
    # 用量：无新动作时缓慢衰减（流失的合成机制）
    acct.usage *= 0.98
    acct.touches_last4.append(0)
    acct.weeks_since_touch += 1


def apply_action(acct: Account, action: str, rng: random.Random,
                 metrics: Dict) -> None:
    """执行一周的动作，更新账户状态并累计指标。"""
    spec = ACTIONS[action]
    metrics["decisions"] += 1
    if action == "WAIT":
        metrics["wait_count"] += 1
        acct.reputation = min(1.0, acct.reputation + 0.01)
        return
    if action == "STOP_COOLING":
        metrics["wait_count"] += 1
        metrics["cooling_count"] += 1
        acct.reputation = min(1.0, acct.reputation + 0.02)
        acct.touches_last4[-1] = 0
        return
    if action == "PARTNER_ENABLE":
        acct.trust_consumed += spec["trust_cost"]
        metrics["trust_consumed"] += spec["trust_cost"]
        acct.partner_effectiveness = min(1.0, acct.partner_effectiveness + 0.10)
        acct.touches_last4[-1] = 0
        return

    # 直接触达
    metrics["touches"] += 1
    acct.touches_last4[-1] = 1
    acct.weeks_since_touch = 0
    acct.trust_consumed += spec["trust_cost"]
    metrics["trust_consumed"] += spec["trust_cost"]
    # 信任动力学：低质触达烧声誉更多；声誉下降会通过送达率反噬后续效果
    damage = spec["trust_cost"] * (REPUTATION_DAMAGE_HIGH if spec["quality"] >= 1.0 else REPUTATION_DAMAGE_LOW)
    acct.reputation = max(0.05, acct.reputation - damage)

    # 回复概率：意图 × 送达率 × 疲劳 × 动作质量 × 伙伴效能（仅 Track 2）
    base = 0.35 if acct.track == "t1" else 0.30
    quality_factor = min(1.2, spec["quality"]) if spec["quality"] > 0 else 0.0
    partner_factor = acct.partner_effectiveness if action == "PARTNER_TOUCH" else 1.0
    p_reply = base * acct.intent * acct.deliverability() * acct.fatigue_factor() * quality_factor * partner_factor
    # 人工触达在低意图时效率很低（浪费高管时间，合成机制）
    if action == "HUMAN" and acct.intent < 0.35:
        p_reply *= 0.4
    replied = rng.random() < min(0.85, p_reply)
    if not replied:
        # 未回复也产生小概率伤害（被标记、退订）
        if rng.random() < 0.008:
            metrics["unsubscribes"] += 1
        if rng.random() < 0.003:
            metrics["complaints"] += 1
        return

    metrics["replies"] += 1
    # 合格管道：回复 + 意图足够高 + 尚未合格（避免同一账户重复计管道）
    if acct.intent >= 0.45 and not acct.qualified:
        p_qual = 0.45 * acct.intent + (0.15 if action in ("DEEP", "HUMAN", "TRIAL") else 0.0)
        if rng.random() < p_qual:
            acct.qualified = True
            value = SEGMENT_VALUE[acct.segment]
            if action == "PARTNER_TOUCH":
                value *= PARTNER_NET_FACTOR  # 分成后净值
            if action == "TRIAL":
                value *= 0.85  # 试用激励让利（合成假设）
            metrics["pipeline"] += value
            metrics["qualified_count"] += 1
            # 用量爬坡：合格后用量上升，后续周自然衰减（见 evolve）
            acct.usage += value * 0.5
            metrics["retained_usage"] += acct.usage
    # 伤害：高频触达下的退订 / 投诉（频率越高、声誉越低，概率越高）
    recent = sum(acct.touches_last4[-4:])
    p_unsub = 0.004 + 0.004 * max(0, recent - 2) + 0.01 * (1 - acct.reputation)
    p_complaint = 0.0015 + 0.002 * max(0, recent - 2) + 0.005 * (1 - acct.reputation)
    if rng.random() < p_unsub:
        metrics["unsubscribes"] += 1
    if rng.random() < p_complaint:
        metrics["complaints"] += 1


# ---------------------------------------------------------------- 策略

# 策略签名：(acct, observed_intent, params, rng) -> action
PolicyFn = Callable[[Account, float, Dict, random.Random], str]

TRUST_BUDGET = 30.0  # 每账户信任预算（合成单位），G / G+ 的硬约束


def _over_budget(acct: Account) -> bool:
    return acct.trust_consumed >= TRUST_BUDGET or acct.reputation < 0.45


def policy_reply_greedy(acct: Account, obs: float, params: Dict, rng: random.Random) -> str:
    """基线 1：每轮选预测回复率最高的动作，忽略信任预算。"""
    if acct.track == "t2":
        return "PARTNER_TOUCH"
    if obs >= 0.55:
        return "DEEP"
    if obs >= 0.30:
        return "LIGHT"
    return "LIGHT"  # 即使意图低也发 —— 这正是贪心的问题


def policy_human_rules(acct: Account, obs: float, params: Dict, rng: random.Random) -> str:
    """基线 2：人工规则 —— 固定序列：3 次触达后转人工，冷静 4 周后重新开始。
    （v0 修正：此前版本转人工后永久冷静，低估了人工规则的产量；现为可循环序列。）"""
    total_touches = getattr(acct, "_rule_touches", 0)
    if total_touches >= 4 and acct.weeks_since_touch >= 4:
        total_touches = 0
        acct._rule_touches = 0  # type: ignore[attr-defined]
    if total_touches < 3:
        acct._rule_touches = total_touches + 1  # type: ignore[attr-defined]
        return "LIGHT" if acct.track == "t1" else "PARTNER_TOUCH"
    if total_touches == 3:
        acct._rule_touches = 4  # type: ignore[attr-defined]
        return "HUMAN" if acct.track == "t1" else "PARTNER_TOUCH"
    return "STOP_COOLING"


def policy_wait_heavy(acct: Account, obs: float, params: Dict, rng: random.Random) -> str:
    """基线 3：过度克制 —— 90% 概率 WAIT，与意图无关。
    注意：v0 刻意不把它定义为“只在意图极高时触达”，因为那种“聪明等待”
    本身就是 G 的一部分；把它写成基线会让 Pipeline-per-Trust 被“几乎不做”
    刷高（见 README 的比率可博弈说明）。本基线测的是“无差别克制”。"""
    if rng.random() < 0.90:
        return "WAIT"
    return "LIGHT" if acct.track == "t1" else "PARTNER_TOUCH"


def policy_g(acct: Account, obs: float, params: Dict, rng: random.Random) -> str:
    """基线 4：G —— 信任约束序贯策略，无递归。参数固定。"""
    if _over_budget(acct):
        return "WAIT"
    lam = params.get("lambda", 3.0)  # 信任影子价格（v0 修正：此前 0.6 从不生效，λ 必须与期望管道同量级才起约束作用）
    threshold = params.get("threshold", 0.40)
    # 信任影子定价：期望管道 - λ × 信任成本 <= 0 则 WAIT（不触达的价值显式化）
    if acct.track == "t1":
        if obs >= 0.65:
            action, value, cost = "DEEP", 12.0 * obs, 3.0
        elif obs >= threshold:
            action, value, cost = "LIGHT", 6.0 * obs, 1.0
        elif obs >= 0.25:
            action, value, cost = "TRIAL", 10.0 * obs, 1.5
        else:
            return "WAIT"
    else:
        if obs >= threshold:
            action, value, cost = "PARTNER_TOUCH", 9.0 * obs, 1.5
        elif acct.partner_effectiveness < 0.8:
            return "PARTNER_ENABLE"
        else:
            return "WAIT"
    if value - lam * cost <= 0:
        return "WAIT"
    return action


def policy_g_static(acct: Account, obs: float, params: Dict, rng: random.Random) -> str:
    """供验证用的 G 静态版：与 policy_g 相同，但不带递归状态。"""
    return policy_g(acct, obs, params, rng)


# ---------------------------------------------------------------- 仿真主循环


def new_metrics() -> Dict:
    return {
        "decisions": 0, "touches": 0, "replies": 0, "qualified_count": 0,
        "pipeline": 0.0, "trust_consumed": 0.0, "unsubscribes": 0, "complaints": 0,
        "wait_count": 0, "cooling_count": 0, "retained_usage": 0.0,
        "vetoes": 0, "rollbacks": 0,
    }


def finalize_metrics(metrics: Dict, accounts: List[Account]) -> Dict:
    touches = max(1, metrics["touches"])
    trust = max(1e-9, metrics["trust_consumed"])
    reputation_change = sum(a.reputation for a in accounts) / len(accounts) - 1.0
    return {
        **metrics,
        "reply_rate": metrics["replies"] / touches,
        "pipeline_per_trust": metrics["pipeline"] / trust,
        "unsubscribe_rate_per_100_touches": 100.0 * metrics["unsubscribes"] / touches,
        "complaint_rate_per_100_touches": 100.0 * metrics["complaints"] / touches,
        "mean_reputation_change": reputation_change,
        "wait_share": metrics["wait_count"] / max(1, metrics["decisions"]),
        "qualified_per_100_accounts": 100.0 * metrics["qualified_count"] / len(accounts),
        # 比率可博弈标记：WAIT 占比 >0.95 的策略，其 Pipeline-per-Trust
        # 可能只是“几乎不做”刷出来的，必须同时看绝对管道量，不得单独取胜。
        "inaction_flag": "DEGENERATE_INACTION" if metrics["wait_count"] / max(1, metrics["decisions"]) > 0.95 else "ok",
    }


def simulate(accounts: List[Account], policy: PolicyFn, params: Dict,
             weeks: int, seed: int) -> Dict:
    """单次仿真（无递归）：返回聚合指标。"""
    rng = random.Random(seed)
    metrics = new_metrics()
    for _week in range(weeks):
        for acct in accounts:
            evolve_account(acct, rng)
            obs = acct.observed_intent(rng)
            action = policy(acct, obs, params, rng)
            # 动作合法性检查：Track 1 账户不能用 Track 2 专属动作，反之亦然
            if acct.track == "t1" and action not in TRACK1_ACTIONS + ["STOP_COOLING"]:
                action = "WAIT"
            if acct.track == "t2" and action not in TRACK2_ACTIONS:
                action = "WAIT"
            apply_action(acct, action, rng, metrics)
    return finalize_metrics(metrics, accounts)


# ---------------------------------------------------------------- 递归（G+）

# 候选参数扰动：只改策略参数（阈值、λ），不改评估器与指标定义（Gate G4）
CANDIDATE_DELTAS = [
    {"threshold": -0.05, "lambda": 0.0},
    {"threshold": +0.05, "lambda": 0.0},
    {"threshold": 0.0, "lambda": -1.0},
    {"threshold": 0.0, "lambda": +1.0},
]


def _apply_delta(params: Dict, delta: Dict) -> Dict:
    out = dict(params)
    out["threshold"] = min(0.8, max(0.15, out.get("threshold", 0.40) + delta["threshold"]))
    out["lambda"] = min(5.0, max(1.0, out.get("lambda", 3.0) + delta["lambda"]))
    return out


def _gate_pass(validation: Dict, incumbent: Dict) -> bool:
    """验证门（G+ 的最小实现）：G1 + G3 + G5，缺一不可。G2 在本原型中由
    验证集的独立种子近似（验证账户与主运行账户种子不同），G4 由代码结构保证
    （评估函数 finalize_metrics 在任何候选下都不变）。"""
    g1 = validation["pipeline_per_trust"] > incumbent["pipeline_per_trust"]
    g3 = (
        validation["unsubscribe_rate_per_100_touches"] <= incumbent["unsubscribe_rate_per_100_touches"] + 0.2
        and validation["complaint_rate_per_100_touches"] <= incumbent["complaint_rate_per_100_touches"] + 0.1
        and validation["wait_share"] < 0.95  # 防“永远等待”退化
    )
    g5 = validation["trust_consumed"] <= incumbent["trust_consumed"] * 1.10
    return bool(g1 and g3 and g5)


def simulate_gplus(seed: int, n_accounts: int, weeks: int, gated: bool,
                   base_params: Optional[Dict] = None) -> Dict:
    """G+：按 epoch 递归。每 epoch 结束时生成候选，在独立验证集上评估；
    gated=True 时只有通过验证门才采纳，否则否决 + 回滚；
    gated=False 时（消融）按验证集回复总数最高采纳，不经过门 —— 模拟无门递归
    以“回复量”这个可营销代理目标代替 Pipeline-per-Trust，学到“发更多”的捷径。
    注意：若按回复率（分母为触达数）选，无门反而会选更挑剔的策略，那不是
    本消融要测的失败模式；消融测的是“目标错位”，不是“阈值高低”。"""
    params = dict(base_params or {"threshold": 0.40, "lambda": 3.0})
    rng = random.Random(seed)
    accounts = make_accounts(n_accounts, seed)
    metrics = new_metrics()
    epoch = 8
    for start in range(0, weeks, epoch):
        epoch_weeks = min(epoch, weeks - start)
        for _week in range(epoch_weeks):
            for acct in accounts:
                evolve_account(acct, rng)
                obs = acct.observed_intent(rng)
                action = policy_g(acct, obs, params, rng)
                if acct.track == "t1" and action not in TRACK1_ACTIONS + ["STOP_COOLING"]:
                    action = "WAIT"
                if acct.track == "t2" and action not in TRACK2_ACTIONS:
                    action = "WAIT"
                apply_action(acct, action, rng, metrics)
        if start + epoch_weeks >= weeks:
            break
        # ---- 递归候选评估（验证集：独立种子、独立账户，避免自证）----
        incumbent_val = simulate(make_accounts(80, seed + 1000), policy_g_static,
                                 params, 8, seed + 2000)
        best_candidate, best_val = None, None
        best_reply_candidate, best_reply_val = None, None
        for delta in CANDIDATE_DELTAS:
            cand = _apply_delta(params, delta)
            val = simulate(make_accounts(80, seed + 1000), policy_g_static,
                           cand, 8, seed + 2000)
            if best_val is None or val["pipeline_per_trust"] > best_val["pipeline_per_trust"]:
                best_candidate, best_val = cand, val
            # 无门目标：验证集回复总数（不是回复率，见 simulate_gplus 说明）
            if best_reply_val is None or val["replies"] > best_reply_val["replies"]:
                best_reply_candidate, best_reply_val = cand, val
        if gated:
            if best_val is not None and _gate_pass(best_val, incumbent_val):
                params = best_candidate  # type: ignore[assignment]
            else:
                metrics["vetoes"] += 1
                metrics["rollbacks"] += 1  # 否决即回滚到现任参数（参数不变）
        else:
            # 无门：按回复率采纳，不检查伤害与预算 —— 消融对照
            if best_reply_candidate is not None:
                params = best_reply_candidate
    result = finalize_metrics(metrics, accounts)
    result["final_params"] = params
    return result


BASELINES: Dict[str, str] = {
    "reply_greedy": "回复率贪心（忽略信任预算）",
    "human_rules": "人工规则（固定序列 3 次触达后转人工）",
    "wait_heavy": "WAIT-heavy（过度克制）",
    "G": "G：信任约束序贯策略，无递归",
    "G+_gated": "G+ 有门递归（Gate 全开）",
    "G+_ungated": "G+ 无门递归（消融：按回复率采纳，不过门）",
}


def run_all(seed: int = 42, n_accounts: int = 200, weeks: int = 24) -> Dict:
    """六个基线并跑一次对照。返回每个基线的完整指标（含强制伤害指标）。"""
    results: Dict[str, Dict] = {}
    results["reply_greedy"] = simulate(make_accounts(n_accounts, seed),
                                       policy_reply_greedy, {}, weeks, seed + 1)
    results["human_rules"] = simulate(make_accounts(n_accounts, seed),
                                      policy_human_rules, {}, weeks, seed + 2)
    results["wait_heavy"] = simulate(make_accounts(n_accounts, seed),
                                     policy_wait_heavy, {}, weeks, seed + 3)
    results["G"] = simulate(make_accounts(n_accounts, seed), policy_g,
                            {"threshold": 0.40, "lambda": 3.0}, weeks, seed + 4)
    results["G+_gated"] = simulate_gplus(seed, n_accounts, weeks, gated=True)
    results["G+_ungated"] = simulate_gplus(seed, n_accounts, weeks, gated=False)
    return results
