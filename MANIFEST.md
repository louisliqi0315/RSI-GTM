# GTM-PolicyBench — English Companion Package — MANIFEST

Companion to the arXiv preprint *Towards RSI-GTM: Trust-Constrained, Verification-Gated Recursive Self-Improvement for Go-to-Market* (Qi Li, Independent Researcher).

This is a NEW companion package. The original frozen package at `~/workspace/gtm-research/benchmark-package/` (69 files) is untouched; its checksums were re-verified after this package was built (see the verification note at the end). No new experiment was run for this package, no new load-bearing claim or number was added, and no public release link or repository address was invented.

Status, stated honestly: this package is a benchmark design plus one simulator implementation, not yet a public benchmark. It has no third-party adoption, no public leaderboard, and no real vendor data. All data are synthetic.

How to read this table: `lines` is the `wc -l` line count; `sha256` is the SHA-256 of the file in this package. For copied files, the checksum matches the source file byte for byte. Code comments in Chinese were deliberately NOT translated, so that code checksums stay identical to the original package. `MANIFEST.md` itself is excluded from its own table (its checksum can be computed by any reader). Build artefacts such as `code/__pycache__/` are not part of this package and were removed after the smoke run.

The code and data release link in `docs/paper-draft-arxiv-submission.md` (line 1155 of the draft) is https://github.com/louisliqi0315/RSI-GTM. No placeholder remains open in this package.

| Package path | Source path | Lines | sha256 |
|---|---|---:|---|
| `README.md` | `newly written in this package (no external source file)` | 141 | `80840c683e1a0511cb9c1b0429da044fd57dc406d3d6d582353c7c3ccccc9db6` |
| `code/gtm_sim.py` | `benchmark-package/code/gtm_sim.py` | 426 | `699e450c2e4673fee4e6c189b1bf6f641f300e10d7615153403ab4b119eaf219` |
| `code/gtm_sim_phase2b.py` | `benchmark-package/code/gtm_sim_phase2b.py` | 430 | `f54d04c281354d977eb6c6165469542a3e8317097ebd4519bea4879c522fd3eb` |
| `code/phase2b_multiseed.py` | `benchmark-package/code/phase2b_multiseed.py` | 117 | `e16a0bef32cfc6892eeaef79ae905472499d7ca1c2569dae195acbaa196c53b4` |
| `code/phase2b_ope.py` | `benchmark-package/code/phase2b_ope.py` | 403 | `21b5664a4ed834d970a4f26061fbd38c1154cea4d8e4c755ef0e82ea060e252d` |
| `code/phase2b_ope_run.py` | `benchmark-package/code/phase2b_ope_run.py` | 132 | `35697d58a14402dd622e5ffc1b0449f49c767675d8950a9996685d726a43ca29` |
| `code/phase2b_ranking.py` | `benchmark-package/code/phase2b_ranking.py` | 82 | `9d38b25f10de1f9be6045c707d52e9a5101a5bdd10f711d12f3f34ea25d834be` |
| `code/phase2b_t1.py` | `benchmark-package/code/phase2b_t1.py` | 138 | `e1c6ae2bb331060894530ca100cb5ca2e2819da3f30ffae601a403b83d3d75d4` |
| `code/phase2c_multiseed.py` | `benchmark-package/code/phase2c_multiseed.py` | 174 | `3a86587420cb6a71081323982e4df1a28035d240d1fe5d7edf87c179f143f3d2` |
| `code/phase2c_seqope.py` | `benchmark-package/code/phase2c_seqope.py` | 467 | `9c2a02869517dc1047b5aaf3ca27e288db3ba1fd37662d2624623a8c6673a366` |
| `code/phase2c_seqope_run.py` | `benchmark-package/code/phase2c_seqope_run.py` | 167 | `7272850879e4ee59d76dd25072220a5d97df30aa944e9044361891429259e028` |
| `code/phase2c_sim.py` | `benchmark-package/code/phase2c_sim.py` | 432 | `0b29d03e14f58a56b548d6224194ecf5aa3a9fffaf7459c0c02ff7ed33b5e6f8` |
| `code/phase2d_run.py` | `benchmark-package/code/phase2d_run.py` | 85 | `094bff3a11316c8b7beb69505ff8d5909bc876e0b26eefc007adb4e402b1dc39` |
| `code/phase2d_sim.py` | `benchmark-package/code/phase2d_sim.py` | 391 | `11fb9ef7f8c01c028d54ae563f8901e8b78763f6ef37f57b54a67db3c9a5f057` |
| `code/phase2f_run.py` | `benchmark-package/code/phase2f_run.py` | 96 | `9c2e476189890383520972c42c70bdae89765f15b922b79af9fd258ccd245208` |
| `code/phase2f_sim.py` | `benchmark-package/code/phase2f_sim.py` | 158 | `8ed249051c1dad977f448946c163f9314b30d3bf3187adf5e9c00265e356d9a7` |
| `code/phase2g_run.py` | `benchmark-package/code/phase2g_run.py` | 137 | `4eee0f6a22272b0170503a7cd5ff8bdd24a04198bf310e13f96a579bae0ae473` |
| `code/phase2g_sim.py` | `benchmark-package/code/phase2g_sim.py` | 20 | `80fa87a0df13493db0fa5ecb78792b5f10651678e4af6090f04311d61aa8dd60` |
| `code/phase2h_run.py` | `benchmark-package/code/phase2h_run.py` | 156 | `3b53f4eb71b1e469d7644447abfcbeaa1ede0fa386cc2ccf8f835c2f1ef87fbc` |
| `code/phase2h_sim.py` | `benchmark-package/code/phase2h_sim.py` | 119 | `72efb485b240c627c6e4d752cb9b40967b2eb29a6cd692e6f36447a619e09863` |
| `code/phase2i_run.py` | `benchmark-package/code/phase2i_run.py` | 164 | `cfc6fa1733e87c58088a1254164bd92c8c3691d768431575115554df92885421` |
| `code/phase2i_sim.py` | `benchmark-package/code/phase2i_sim.py` | 233 | `61623b61fadeab236a469040dfb49e6cfc346aa636bc497a3b76b28565e0e232` |
| `code/phase2j_run.py` | `benchmark-package/code/phase2j_run.py` | 179 | `2d2cb12a9d91b33721b29b22e377a2a945cfbd68c44cecd0074484c051be2e92` |
| `code/phase2j_sim.py` | `benchmark-package/code/phase2j_sim.py` | 189 | `516311515bfc4c37aa4aaab644ff9e748b79020af1de29263f4d3558c74b8b3d` |
| `code/phase2k_run.py` | `benchmark-package/code/phase2k_run.py` | 225 | `bc85b2b5181e15c4d216dd314330cfa8bc23e0baea599074191be824a75941c0` |
| `code/phase2k_sim.py` | `benchmark-package/code/phase2k_sim.py` | 198 | `516a263b48804e0b705fea13f24c9e40a42afc3880894efb1e0b2536b2b9e70b` |
| `code/run_experiment.py` | `benchmark-package/code/run_experiment.py` | 57 | `d68e2551a5d866203eb188db9395271a74baf6a96ff657e255f681891c9a45e7` |
| `data/example_output.json` | `benchmark-package/data/example_output.json` | 163 | `c8730f391751a67aef52976bb68828641063cbaf99eea57ed551c772c67d5d02` |
| `data/phase2b_multiseed_results.json` | `benchmark-package/data/phase2b_multiseed_results.json` | 429 | `5c46e0f31eeacf232e07eee939bd716659f78e7d6575f2186473492e38aafc1f` |
| `data/phase2b_ope_results.json` | `benchmark-package/data/phase2b_ope_results.json` | 521 | `2e9af67a3fa81fe89306b0eef16285c92d3e7a8d51dcf03d66d74beb0299e6d0` |
| `data/phase2b_t1_synthetic.json` | `benchmark-package/data/phase2b_t1_synthetic.json` | 37 | `d8992ee7762e593f76a9b9f41596c3cb1e4b4c00799cd71310777559aa327424` |
| `data/phase2c_multiseed_results.json` | `benchmark-package/data/phase2c_multiseed_results.json` | 1098 | `ab5544f37ba54147e0a025e53c311aeff679fa5623576dc62ab9033a6b41750d` |
| `data/phase2c_seqope_results.json` | `benchmark-package/data/phase2c_seqope_results.json` | 503 | `3f29f175465834c905b656b90c837246b817a4cd278d5a6f281a1edbd3d245aa` |
| `data/phase2d_results.json` | `benchmark-package/data/phase2d_results.json` | 1255 | `be8ce77ebffa6079cab6c4cc4764e6a45179ce31915cc35cc9f545df5d7db5e4` |
| `data/phase2f_results.json` | `benchmark-package/data/phase2f_results.json` | 2317 | `5055ea36ef5b013560524ffabd637b3bbf720f5f41879903da6b18131ee2dc4a` |
| `data/phase2g_results.json` | `benchmark-package/data/phase2g_results.json` | 1673 | `eef49a18a1299b1a9dde3883b01cc127b87b346d0efb985f22c03b03458ed793` |
| `data/phase2h_results.json` | `benchmark-package/data/phase2h_results.json` | 9627 | `c5305118d5b479b30e6cfa999dda02834f6ec6e24b27825aed51b3be3aa5e4e3` |
| `data/phase2i_results.json` | `benchmark-package/data/phase2i_results.json` | 9179 | `26827551fe7ddb74661cb1471abc0205f56db00d2cb0eca762f550a725b29c21` |
| `data/phase2j_results.json` | `benchmark-package/data/phase2j_results.json` | 15460 | `08143358458721bff9e2a1f16c2fb34646db014b85091725932dfc4f8f270b40` |
| `data/phase2k_results.json` | `benchmark-package/data/phase2k_results.json` | 19727 | `43dccfe479275ac202c9cbfc5d17dd9ee4f32d76a3357f9a12c2fda14d13c399` |
| `data/public_signal_panel.schema.json` | `benchmark-package/data/public_signal_panel.schema.json` | 0 | `987035a0bd187bd222b5ee4ba4d3ee8398b2efb84a9e1cdb56dfc9ab92efdf8e` |
| `docs/paper-draft-arxiv-submission.md` | `~/workspace/gtm-research/paper-draft-arxiv-submission.md` | 1155 | `b5d6131eb09a814b753c6935593c4478b0c1427141eb71fe0e13aebb470bd96a` |
| `docs/reproduction-smoke-seeds30-pass.log` | `newly written in this package (no external source file)` | 129 | `8f07383bda062aa98b96f62bf5b04e078bbe0e3dfa07a4ddb2220569cc993660` |
| `docs/stage-summary-en.md` | `newly written in this package (no external source file)` | 34 | `d2b33a14a8eb1e52d3d2092ca450a39af98fe1e6074b2f9457d04bb111dd132a` |
| `docs/preregistrations-zh/phase2e_prereg.md` | `benchmark-package/docs/preregistrations/phase2e_prereg.md` | 80 | `a98e884efeed5cebea6b81638a339010b2fb3a6ebea132ded8e8edd140a15b3d` |
| `docs/preregistrations-zh/phase2g_prereg.md` | `benchmark-package/docs/preregistrations/phase2g_prereg.md` | 17 | `24b84eed2428d8fa00fa5a449285f1df0269ef901fab205c0b228e897d735f40` |
| `docs/preregistrations-zh/phase2h_prereg.md` | `benchmark-package/docs/preregistrations/phase2h_prereg.md` | 36 | `5b5b8f001d2e0caedbfc789500575b6d23a4d89574cb12e7040c655f2126b1a5` |
| `docs/preregistrations-zh/phase2i_prereg.md` | `benchmark-package/docs/preregistrations/phase2i_prereg.md` | 121 | `5c3965251ade9c9ff2c5363ee96a82261e5fb553148927136fb571e366695bb0` |
| `docs/preregistrations-zh/phase2j_prereg.md` | `benchmark-package/docs/preregistrations/phase2j_prereg.md` | 142 | `b8f48c7af8c0258d487497bbb2332ab9cb9e294cbbbeebfeced2537a2d3b3174` |
| `docs/preregistrations-zh/phase2k_prereg.md` | `benchmark-package/docs/preregistrations/phase2k_prereg.md` | 108 | `cd2dc553947502ff18adc39c8f1ee951cb4efebbc726384435eb77090b08e33c` |
| `docs/reports-zh/multi_seed_report.md` | `benchmark-package/docs/reports/multi_seed_report.md` | 71 | `b77194695d6e9a6723ee36e4978fe4143b118e6b37263f90fdcf4e662b18a792` |
| `docs/reports-zh/phase2b_multi_seed_report.md` | `benchmark-package/docs/reports/phase2b_multi_seed_report.md` | 95 | `2696bcaff46505635fc6744a22fdade8b07c9bbf154b23f34f8dc4b247192359` |
| `docs/reports-zh/phase2b_ope_report.md` | `benchmark-package/docs/reports/phase2b_ope_report.md` | 137 | `d9f3d1d9bebc68090db27c59eb4d016f71afa5e891c85f36d7fd54c042ecb7de` |
| `docs/reports-zh/phase2b_report.md` | `benchmark-package/docs/reports/phase2b_report.md` | 102 | `fea122498f7f2642cba6894a3d2b8291a84324ae75a8199019262a46fa3e9f7e` |
| `docs/reports-zh/phase2c_report.md` | `benchmark-package/docs/reports/phase2c_report.md` | 258 | `0d3c869b31000dc743dbff7d300aeb446ac8c1910660ec9d66437a33ddfea587` |
| `docs/reports-zh/phase2d_report.md` | `benchmark-package/docs/reports/phase2d_report.md` | 215 | `9d4a59665d79a58c63c5818409c868d7a5504ae8de6f386ae04aa95d1131a2c4` |
| `docs/reports-zh/phase2e_report.md` | `benchmark-package/docs/reports/phase2e_report.md` | 381 | `4a0a49c3d786b32a23f370c7de2ea0757855c3a56d36882dba3dc294e6eab14d` |
| `docs/reports-zh/phase2f_report.md` | `benchmark-package/docs/reports/phase2f_report.md` | 230 | `71dc376c5b67abc10562b39efe831affc31b1ae7000cd2765e8d3eb5acb9918f` |
| `docs/reports-zh/phase2g_report.md` | `benchmark-package/docs/reports/phase2g_report.md` | 179 | `2b494e53ff1736600f05c88feb0a4f8b0feabb3abff50211824a9aa7719d07f5` |
| `docs/reports-zh/phase2h_report.md` | `benchmark-package/docs/reports/phase2h_report.md` | 271 | `8bb721350660fb70b06b922be53410f481dd308896c1d1eee754fc68b1e763b6` |
| `docs/reports-zh/phase2i_report.md` | `benchmark-package/docs/reports/phase2i_report.md` | 217 | `370e7ba2147cd68243d50e4634ca23bf90eb88ea8618548e737697dcebe2ee43` |
| `docs/reports-zh/phase2j_report.md` | `benchmark-package/docs/reports/phase2j_report.md` | 283 | `3737c6d0addb41f16c5b9f987558de688cf4cd3c05f465ba7e2dd73ba52fbafc` |
| `docs/reports-zh/phase2k_report.md` | `benchmark-package/docs/reports/phase2k_report.md` | 287 | `ff17f59b97f9dfe691c3de909839744997c6033ac20e444f29a3c9ccb0641468` |
| `docs/zh-originals/example_output.md` | `benchmark-package/docs/example_output.md` | 39 | `94c95879715daaa438927371a035caed65d96186e5bdabbd2643c297aa5b355a` |
| `docs/zh-originals/phase2a-README-original.md` | `benchmark-package/docs/phase2a-README-original.md` | 83 | `2698ab741332b88c3458cc4c485e249e56bef422ff8fb6fec59deedcdb6898ca` |
| `docs/zh-originals/phase2b_t1_real_attempt.md` | `benchmark-package/docs/phase2b_t1_real_attempt.md` | 85 | `67a253585c983569e887ed7b9e2af9cabead3cf93d7961edeadb5637c8e46a9a` |
| `docs/zh-originals/public_signal_panel.md` | `benchmark-package/docs/public_signal_panel.md` | 105 | `9fcd0fd4c00b05eaa5be35c2c71f226b6cc25a895c88264005acadc19817fa5a` |
| `docs/zh-originals/public_signal_panel.schema.json` | `benchmark-package/docs/public_signal_panel.schema.json` | 0 | `987035a0bd187bd222b5ee4ba4d3ee8398b2efb84a9e1cdb56dfc9ab92efdf8e` |

Total files listed: 68 (plus this MANIFEST.md).
