# GTM-PolicyBench — English Companion Package for the arXiv Preprint

**Accompanying paper:** *Towards RSI-GTM: Trust-Constrained, Verification-Gated Recursive Self-Improvement for Go-to-Market*

**Author:** Qi Li — Independent Researcher

**What this package is:** This is an English companion package built for the arXiv preprint line. It is a NEW package, created alongside — not on top of — the original frozen package at `~/workspace/gtm-research/benchmark-package/` (69 files). The original package is untouched: no file in it was modified, added, or removed, and its manifest checksums still verify. The full paper draft in this package is a copy of `~/workspace/gtm-research/paper-draft-arxiv-submission.md` (see `docs/paper-draft-arxiv-submission.md`).

**What this package is not:** It is not a replacement for the frozen package, and it is not a new experiment. No new experiment was run for this package, no new load-bearing claim or number was added, and no public release link, repository address, or author information beyond what the user supplied was invented. The code and data release link in the paper draft (line 1155 of the draft) is https://github.com/louisliqi0315/RSI-GTM.

## 1. The benchmark

GTM-PolicyBench is a benchmark design proposed in the paper, with three parts:

1. **Simulator** (`code/`, Python standard library only): sequential go-to-market (GTM) policy simulation under a trust-budget constraint. Policies run on accounts and produce metrics such as Pipeline-per-Trust.
2. **Trajectory-level offline evaluation design:** offline evaluation (fitted Q evaluation / off-policy evaluation) applied to simulated trajectories, together with its falsification record. The honest conclusions retained here are: trajectory-level fitted Q evaluation is only a ranking heuristic and its magnitudes are unreliable; naive bandit off-policy evaluation is unusable; sequential doubly robust evaluation was falsified and must not be cited.
3. **Cluster randomised-trial (RCT) protocol design:** a trial protocol design with account clusters as the randomisation unit (Chapter 6 of the paper). It has not been executed at a real vendor.

**The status must be stated exactly as follows, and must not be inflated:**

> This package is a benchmark design plus one simulator implementation, not yet a public benchmark.
> It has no third-party adoption, no public leaderboard, and no real vendor data.
> It must not be described as an already public benchmark, as already adopted by third parties, or as having validated a real strategy.

## 2. Data statement

**All data in this package are synthetic.** Accounts, intent, trust consumption, and reputation changes in the simulator are coded assumptions — not real vendor logs, not real conversion rates, and not real revenue.

This package claims no real vendor effect. Figures in the China vendor GTM map that come from media reporting or from reprinted financials are labelled as such in the paper and must not be treated as audited financial facts.

## 3. Directory structure

```
benchmark-package-en/
├── README.md                       This file (English)
├── MANIFEST.md                     File list: line counts, sha256 checksums, source paths
├── code/                           Simulator and run entry points (26 .py files, byte-identical copies of the original package)
├── data/                           Result JSON files (14 .json files, byte-identical copies of the original package)
└── docs/
    ├── paper-draft-arxiv-submission.md   Copy of the arXiv submission-format draft (English; author, affiliation, email, and ORCID filled; code release link: https://github.com/louisliqi0315/RSI-GTM)
    ├── stage-summary-en.md               One-page English summary of stages 2a–2k (designs and conclusion limits; the stage reports govern)
    ├── reports-zh/                  Stage reports in Chinese, byte-identical copies of the original package (13 files; not translated in full)
    ├── preregistrations-zh/         Preregistrations in Chinese, byte-identical copies of the original package (6 files: 2e, 2g–2k)
    ├── zh-originals/                Other original Chinese-language files from the original package (phase2a README, public-signal panel and schema, example output, 2b T1 real-attempt record)
    └── reproduction-smoke-seeds30-pass.log   Smoke-reproduction log for this package (see Section 6)
```

**A note on code comments:** The `code/` copies are byte-identical to the original package, including any Chinese-language comments inside the code. Those comments were deliberately NOT translated, because editing the code would break checksum consistency with the original package and with reproducibility. This README states that fact explicitly so that no reader mistakes an untranslated comment for an oversight.

**Verification method:** Every copied file was compared with its original by `sha256sum`. All `code/` and `data/` copies, all Chinese report and preregistration copies, all `zh-originals/` copies, and the paper-draft copy match their sources byte for byte. The full per-file list is in `MANIFEST.md`.

## 4. Stage designs and conclusion limits (summary; the reports govern)

Primary metric: Pipeline-per-Trust. Paired differences below are against the static policy unless stated otherwise. **Rows for different designs must not be averaged, mixed, or used to overwrite one another.** The full one-page table is in `docs/stage-summary-en.md`; the stage reports in `docs/reports-zh/` govern in case of any discrepancy.

| Stage | Design | Conclusion limit |
|---|---|---|
| 2a | Seed 42 / 200 accounts / 24 weeks, preliminary simulation | Gated 0.310, G 0.208, ungated 0.154, reply-rate greedy 0.108 with reputation change −0.853; preliminary synthetic results only |
| 2b | 10 multi-seeds; public panel T1 real collection attempt | Gated mean 0.319, G 0.309, gated > G in only 6/10; gated > ungated in 9/10 with lower harm; public panel T1 is a negative result (17 fields, at least 7 without weekly public sources; panel rows deliberately not generated) |
| 2c | 1000 accounts / 10 seeds / 24 weeks | Gated − G +0.0001, 95% CI [−0.031, +0.031], win/loss 4/10 — indistinguishable in efficiency; gated − ungated +0.0994, CI [0.066, 0.132], 10/10 with lower harm; the gate's established value is vetoing bad recursion, not improving efficiency |
| 2d | Four arms: gated frozen / ungated / evaluator-writable / evaluator-separation approval, 1000 accounts / 10 seeds / 24 weeks | B gated frozen 0.3028 (claimed 0.3028, gap 0, false adoptions 0); C ungated 0.2640 (claimed 0.9409, gap 0.6769, false adoptions 4); D evaluator-writable 0.2715 (claimed 0.8132, gap 0.5417, false adoptions 3); E evaluator-separation approval 0.3028, identical to B; B−C +0.0388 CI [0.019, 0.058] 10/10; B−D +0.0313 CI [0.018, 0.044] 10/10; the correct comparison is D vs B, not D vs C |
| 2e | Public test (no interviews, no vendor logs) | Trust-budget T2/T3 main difference-in-differences NOT executed (not a falsification: no BigQuery channel, and "first public blocklisting event" could not be operationalised directly; the preregistration must be rewritten); VRI ex ante prediction: directional support strengthened, still undecided, not passed |
| 2f | Stratified ablation: static G / workflow-only gated / state-only gated / joint gated, 1000 accounts / 10 seeds / 24 weeks | Static G 0.2868, workflow-only 0.2999, state-only 0.2861, joint B 0.3028; B − static G +0.0161 CI [−0.009, +0.041] containing zero — recursion gain unproven and contracted; workflow layer directionally consistent but lower bound −0.001, must not be reported as an established single-layer effect; state layer a clean zero; joint not better than either single layer |
| 2g | Workflow-only gated vs static G, 1000 accounts / 30 seeds / 24 weeks, 8-week epochs | **+0.0075, CI [+0.0010, +0.0141], 7/1/22**; within simulation, the workflow recursion gain holds (narrow margin, small effect), with three qualifiers: lower bound only about 13% of the mean, 22/30 differences exactly zero, two-sided sign test not significant, effect fallen back from 2f, empty-comparison rate 73.3%, harm not dominant across the board, primary metric only; must cite +0.0075, must not reuse 2f's +0.0131, must not average, and must not use the post-empty-comparison-exclusion +0.0282 (n = 8) as the main conclusion |
| 2h | Workflow-only gated vs static G, 1000 accounts / 30 seeds / 48 weeks, 4-week epochs | **+0.0056, CI [−0.0004, +0.0116], 6/2/22**; per preregistration: fragile, not an extension (interval contains zero and the mean is below 2g); empty-comparison rate 73.3%; all adoptions concentrated in week 4, then 10 rounds of zero adoptions and 322 vetoes, effective recursion depth 1; horizon and epoch were changed together, so this must not be read as "longer horizon necessarily kills the gain"; no pure-time control arm was set |
| 2i | Arm A pure-time control (old binary candidate set) and arm B expanded candidate space (added W2), 1000 accounts / 30 seeds / 48 weeks, 8-week epochs | Arm A **+0.0059, CI [+0.0001, +0.0116], 6/2/22**, empty-comparison rate 73.3%, all week-8 adoptions of W1, non-empty seeds identical to 2g/2h; arm B **+0.0033, CI [−0.0023, +0.0089], 7/3/20**, empty-comparison rate 66.7%, all week-8 adoptions (W1 in 4, W2 in 6), then 4 rounds of zero adoptions; B−A −0.0026 CI [−0.0085, +0.0033]; both arms have 0 seeds with ≥2 adoptions and total progressive adoptions 0; pure-time effect small (A vs 2g mean difference |0.0016| ≤ 0.003, and A at its week-24 checkpoint equals 2g's endpoint seed by seed); A (+0.0059) vs 2h (+0.0056) differ by only +0.0003, a knife-edge crossing of the zero line, not a substantive epoch effect — 2h's fragility must not be attributed mainly to denser epochs, and A must not be read as the 48-week gain having recovered; arm B was not a strict superset of arm A (missing the "thr unchanged, lam−1" variant), so the richness verdict was downgraded to "not shown effective under this candidate-set definition; the strict-superset test was not done; richness cannot be directly asserted to be irrelevant" |
| 2j | Control A0 (replication of 2i-A), arm C (strict superset, 8 candidates), arm D (independent validation seeds), 1000 accounts / 30 seeds / 48 weeks, 8-week epochs | A0 **+0.0059, CI [+0.0001, +0.0116], 6/2/22**, seed-by-seed identical to 2i-A; C **+0.0033, CI [−0.0023, +0.0089], 7/3/20**, seed-by-seed identical to 2i-B; completing the variants changed no endpoint result — richness can be fairly cleanly excluded as the bottleneck, and 2i's downgrade is thereby lifted; D **+0.0089, CI [+0.0023, +0.0155], 16/8/6**, empty-comparison rate 20.0%, adoptions 26/124 slots, per-round adoptions 7/4/5/6/4; D−A0 +0.0030 CI [−0.0053, +0.0113] containing zero; accurate reading of D: independent validation seeds broke depth 1 in the adoption-count sense (empty-comparison rate 73.3% → 20.0%, adoptions spread over 5 rounds), but produced no progressive recursion (total progressive adoptions 0, both multi-adoptions were reversions), and the increment over same-batch control A0 is unproven; gate-component evidence: best-candidate single-veto (seed 6 trust ratio 1.174 > 1.10, seed 29 complaint difference +0.391 > +0.1, where a passable W1 variant was dragged down by a whole-round veto); ratchet release and multiple chances to pass cannot be separated |
| 2k | Control D0 (replication of 2j-D), arm E (dual-sample gate), arm F (fallback), 1000 accounts / 30 seeds / 48 weeks, 8-week epochs | D0 **+0.0089, CI [+0.0023, +0.0155], 16/8/6**, seed-by-seed identical to 2j-D; E **+0.0010, CI [−0.0014, +0.0034], 6/3/21**, empty-comparison rate 70.0%, adoptions 9/141 slots; E−D0 −0.0079 CI [−0.0137, −0.0021] excluding zero; accurate reading of E: dual-sample confirmation almost erased D's entire gain; D's adoptions do not survive a second independent sample and come mainly from multiple chances to pass (with the gate-strictness qualifier: E is itself a stricter gate, so this must not be read as proof that ratchet release plays no role at all; confirmation blocked good and bad adoptions alike, net effect negative; the share of adoptions negative in the main run is still one-third in E); F **+0.0089, CI [+0.0024, +0.0155], 16/8/6**, F−D0 **+0.0000, CI [−0.0000, +0.0001], 1/0/29**, only 1 fallback adoption in 150 slots (seed 28, week 16, rank-1 W1); accurate reading of F: under the binary candidate set plus independent-validation-seed design, the fallback rule has almost no increment, but the test is unfair (the candidate set contains no W2; the original evidence situations for seeds 6 and 29 do not exist in this arm; seeds 6 and 29 in F were already rank-0 adoptions, so fallback was never triggered) and must not be read as "the fallback rule is generally ineffective"; the fallback branch is not closed; a fair fallback test must be a "fallback × strict superset × independent validation seeds" arm — that arm is future work after the freeze and is not claimed as done in this package |

**Unified wording for the workflow layer (from the paper):**

> A one-off small gain under the 24-week design, still a marginal effect of the same order at 48 weeks with the interval at the zero line's knife edge, with horizon and epoch not significantly changing it, and not shown to scale with time or rounds.
> Total progressive adoptions are 0 in all workflow tests.

**Conclusions that stand unchanged (2k set no arms for them, so 2k neither affects nor strengthens them):**

- Joint (workflow + state) recursion better than the static policy: unproven.
- Trust budget as a general primitive: unproven (only a GTM harm-audit / budget heuristic here).
- Adoption rule as a general principle or as a guarantee of no false improvement: unproven (necessary but not sufficient, plus independence grading).
- Evaluator separation as a necessary condition: unproven (downgraded to a recommendation).
- Gated > ungated / tampered: robust within simulation (2c, 2d), but that proves only that "the gate vetoes bad recursion", not an efficiency gain.

## 5. Citation status (arXiv line; must not be written as fully verified)

The accompanying submission-format draft contains **no internal citation markers**. Its citation status is a graded result, not a claim of full verification:

- **10 items verified against key sections of the originals** (not full page-by-page reading): AIDE², Blum–Hardt (2015), ImpossibleBench (preprint, under review), Darwin Gödel Machine, MaD-RSI, BenchJack, SWE-Bench Pro V2, SpecRSI, CollabFlow, and the harness-tampering audit.
- **The rest remain downgraded prose:** second-hand reprints, media-reported wording, undisclosed material, vendor self-report, survey-level statements, or partial verification — including MiniMax financials (Hong Kong Stock Exchange interim-report original verified for the MiniMax part only; the Zhipu part was not retrieved) and MLE-bench (partial: the validation-tool detail verified in the original §2.3; the private-label directory detail not found in the paper's main text).
- **Citation verification remains a status to be stated, not a completed claim.** No file in this package may be cited as evidence that "all citations have been verified".

Note on the original frozen package: its README described the frozen draft v9's state at freeze time (37 internal markers, 5 items verified against key sections). That description belongs to the v9 era. For the arXiv line in this package, the graded status above — produced by the later audit and by converting the remaining markers into downgraded prose — is the applicable one. The original package itself was not rewritten to match it.

## 6. Reproduction check (recorded as run)

Environment: Python 3.12.3, standard library only. Run from the copies in this package's `code/` directory (the original files were not run and not modified). Output was written to `/tmp`, not into the source directories.

### Passed: small-parameter full entry (30 seeds)

```bash
cd benchmark-package-en/code
python3 phase2k_run.py --accounts 50 --seeds 30 --weeks 16 --epoch 8 \
  --out /tmp/phase2k_smoke_repro_en.json
```

Result: **exit code 0, passed.** The script's built-in 50-account / 2-seed / 16-week smoke section passed; the full 30-seed section ran STATIC / D0 / E / F; `anchor_ok` was True for all three arms (D0, E, F); the output file `/tmp/phase2k_smoke_repro_en.json` was generated (that output lives in `/tmp` and is not included in this package). Means under these small parameters are only "it runs" evidence and must not be cited as formal experimental results (formal results are `data/phase2k_results.json` and the 2k report).

Full log: `docs/reproduction-smoke-seeds30-pass.log`.

### Known limitation 1: the `--seeds 2` call fails (not fixed; originals untouched)

```bash
cd benchmark-package-en/code
python3 phase2k_run.py --accounts 50 --seeds 2 --weeks 16 --epoch 8 \
  --out /tmp/phase2k_smoke_repro_en.json
```

Result: **exit code 1, not passed.** The built-in smoke section itself passes, but the following clean-test-case step fails with `ValueError: 6 is not in list` (near line 164 of `phase2k_run.py`, `seeds.index(s)`, where s is a hard-coded test seed, 6 or 29). Cause: the script requires the seed range to include 6 and 29, and `--seeds 2` (seeds 0, 1) does not satisfy that precondition. **That call must not be claimed as passing.** Fixing it would require editing the script and would break checksum consistency with the originals, so this package does not fix it; it records the failure honestly. (The failure log from the original package is retained in the original package; the failure is reproduced by the same precondition here.)

### Known limitation 2: D0 vs 2j-D reproduction-check path note (not a crash)

When run from `code/` alone, the script's D0 vs 2j-D reproduction check records an error for the missing `phase2j_results.json` in the same directory (`error: [Errno 2] No such file or directory: 'phase2j_results.json'`). That check is fault-tolerant (try/except) and does not interrupt the run — this package's own smoke log shows exactly that line at the end, with exit code 0. The data file lives in this package's `data/` directory; to make that check pass, `data/phase2j_results.json` would need to be placed in the run directory. This package does not edit the script for that purpose.

### Reproduction not done

- No formal-parameter (1000 accounts / 30 seeds / 48 weeks) full experiment was rerun: that would repeat existing results and is not part of packaging; formal results are the JSON files in `data/` and the stage reports.
- Not all 26 scripts were individually smoke-tested: the reproduction check uses the 2k entry point as representative (2k depends on `gtm_sim.py`, `phase2d_sim.py`, and `phase2f_sim.py`, covering the core simulation chain); the runnability of the remaining scripts is not individually claimed here.

## 7. Use and reuse rules

1. When citing an effect size, label the design as in Section 4 (horizon + epoch + candidate set + validation-seed rule + gate rule). Do not average, mix, or let one arm cover another.
2. When citing a conclusion, carry the qualifiers: synthetic data, unproven items, and the citation status above. None of them may be dropped.
3. This package must not be used to claim: real vendor effects, an already public benchmark, third-party adoption, fully verified citations, a trust budget as a general primitive, an adoption rule as a general guarantee, evaluator separation as a necessary condition, a proven workflow recursion gain, recursion strengthening with rounds, independent validation seeds having restored recursion, or a generally ineffective fallback rule. In the paper, those phrases appear only in prohibition sentences.
4. When reusing code, verify copies against the checksums in `MANIFEST.md`. Any modification should start a new version; it must not be passed off as this package.

## 8. Three things that still cannot be claimed (kept verbatim from the paper's conclusion)

1. Gated recursion cannot be claimed to have improved efficiency or conversion at real vendors or on real logs.
2. Fitted Q evaluation, or any offline evaluation method, cannot be claimed to have validated a real strategy.
3. Public signals cannot be claimed to predict developer ramp rates, and media-reported figures in the China map cannot be claimed as financial facts.

(Four further items of equal importance, see the end of Section 4: joint recursion better than static is unproven; the trust budget is not a general primitive; the adoption rule is not a general principle or guarantee; evaluator separation is not a necessary condition. The workflow-only single layer is the sole exception, and only with its horizon, epoch, candidate-set, validation-seed-rule, and gate-rule qualifiers.)
