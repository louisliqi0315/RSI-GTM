# Phase 2b T1 真实面板采集尝试：未完成 / 负结果说明

> **本文件是“未完成”的诚实记录，不是面板数据。**
> 任务书要求：若公开采集不可靠或不足，宁可交付骨架 + 合成面板测试 +
> 明确的“未完成/负结果”说明，也绝不编造面板行。
> 因此本阶段**不交付任何真实面板行**，`phase2b_panel_rows.json` 故意不存在。

## 1. 尝试了什么（2026-10-25，公开搜索，文本检索，无登录、无爬取个人数据）

三次公开搜索，主题分别为：OpenRouter 上 Kimi K3 的 token 份额周频、
Hugging Face 上 Kimi K3 的下载量、Kimi K3 在云市场的 listing 情况。
结果均为**事件级、单点、口径不一**的信息，没有任何一个来源提供
schema 要求的周频、segment 级面板。

## 2. 找到的零散点（仅作“为什么拼不成行”的证据，不得拼成面板行）

- Together 团队自述：截至 2026-09-30，其平台上 DeepSeek V4.1 Flash 的
  OpenRouter token 份额为 40.8%、GLM 5.3 Flash 28.2%、Kimi K3 23.1%。
  **注意**：这是 Together 自述的“其平台服务份额”，不是 OpenRouter 全局份额，
  且只有一个日期点，无法构成周频方向序列。
  来源（搜索返回原文链接，逐字复制）：
  https://www.marktechpost.com/2026/10/05/meet-together-link-a-free-cli-that-runs-open-models-like-kimi-k3-and-glm-5-3-inside-claude-code-codex-and-opencode/
- 另一篇行业文章称：2026-10-12 至 10-18 当周，中国模型在 OpenRouter 上
  合计 164 万亿 token、全球前五均为中国模型。**注意**：这是“中国模型合计”，
  不是单个 cohort 的份额方向，且 token 量本身受推理 token 与 agent 循环放大
  （F1），不能直接当作采用热度。
  来源：https://dev.to/976905690/kimi-k31-pro-3-trillion-parameters-open-weights-one-fifth-the-price-moonshots-biggest-flex-2m8k
- Hugging Face 方面：第三方文章称 Kimi K3 权重在 Hugging Face 上
  “1.4 million downloads and counting”（截至 2026-08-09 前后），
  且权重共 96 个分片、约 1.56 TB。**注意**：这是累计下载量，不是周频下载量，
  无法换算为 schema 要求的 hf_downloads_band 周频分档而不编造口径。
  来源：https://locallyuncensored.com/blog/kimi-k3-explained.html
- 云市场方面：Kimi K3 于 2026-09-18 在 Amazon Bedrock 上线（AWS 公告经
  多家转载），并经 Fireworks 进入微软 Foundry。**注意**：这是两个事件日期，
  不是“每周云市场 listing 平台数”的周频计数；第三方托管商数、
  公开集成数、文档更新数、公开岗位聚合数在公开搜索中均无周频发布。
  来源：https://longbridge.com/en/news/299646361
  以及 https://www.silicon.co.uk/cloud/datacenter/aws-moonshot-kimi-631654

## 3. 为什么拼不成行（逐字段核对）

| schema 字段 | 公开来源现状 | 能否填 |
|---|---|---|
| week_start、segment、cohort | 可定义 | 可 |
| model_release_count（周频） | 只有发布事件日期，无周频官方汇总 | 需逐周人工核对官方公告，当前未做 |
| license_type | K3 为 open_weights_with_custom_terms（许可文本） | 可（单点） |
| list_price_snapshot | 官网定价页有快照，但不同平台、缓存口径价格差异大 | 单点可，跨周可比性需口径冻结 |
| cloud_listings、third_party_hosts | 只有“已上线 Bedrock / Foundry”等事件，无每周计数发布 | **不可** |
| host_price_spread | 第三方托管价格离散，但无每周同模型价差序列发布 | **不可** |
| openrouter_share_direction | 只有单点份额自述 / 合计 token 量，无单个 cohort 周频方向 | **不可** |
| hf_downloads_band | 只有累计下载量，无周频分档 | **不可** |
| public_integrations、docs_examples_update_count、org_event_count、public_job_postings | 无周频公开汇总 | **不可** |
| controversy_event | 有争议事件时间戳（可单点） | 单点可 |

结论：**schema 要求的 17 个字段中，至少 7 个在公开来源中无周频发布。**
强行填行必然是编造或口径混用。本阶段的正确交付是：T1 骨架 +
合成面板测试（见 §4），真实采集标记为“未完成”，并给出 schema 修订建议。

## 4. 已完成的部分（可复现）

- T1 评估骨架：`phase2b_t1.py`，持续性基线 + 多数类基线 + 手工必填字段校验。
- 合成面板测试（`phase2b_t1_synthetic.json`，52 周）：
  - 持续概率 0.8 时，持续性基线准确率 0.843（非发布周 0.886），
    多数类基线 0.471——持续性基线确实 beating 多数类基线，但数值
    接近设定值 0.8，说明代码正确，不是“发现了预测能力”。
  - 持续概率 1/3（随机三类）时，持续性基线 0.373，多数类 0.353——
    两者都接近随机，持续性基线在无持续性时并无魔力。
  - 结论：**基线代码通过了已知持续性的检验；真实面板的持续性未知，
    T1 的真实价值仍为“待验证”（U2），不得用合成测试宣称真实预测能力。**

## 5. Schema 修订建议（给下一轮）

1. 增加“部分行”类型：允许字段缺失但必须标注缺失原因与来源日期，
   否则 schema 本身会逼迫研究者编造。
2. 将 openrouter_share_direction 的定义收紧为“同一来源、同一口径、
   同一 cohort 的周环比方向”，并强制标注来源与口径变更周（F3）。
3. 真实采集的第一步不应是“填满 17 字段”，而是先做“事件时间轴”：
   仅记录发布、上市、定价变动、争议等事件日期，再判断事件时间轴
   是否足以支撑周频面板——当前证据表明不足。

## 6. 未做的事

- 未登录任何平台、未调用任何需密钥的 API、未爬取个人数据、
  未购买任何数据、未对外联络任何人。
- 未交付真实面板行；未宣称任何真实转化率、收入或厂商表现。
