# 公开信号面板 Schema（Phase 2a · 周频 · segment / cohort 级）

> 红线：本面板只用公开、可复现的来源字段；只做 segment / cohort 级聚合。
> 不含任何个人标识、不追踪个人、不爬取、不购买个人数据、不推断个人隐私。
> 面板里没有转化率 —— 公开信号只能做“采用热度 / 爬坡 / 衰减”的代理预测，
> 绝不能把代理热度宣称为某家厂商的转化率或收入。

配套机器可读 schema：`public_signal_panel.schema.json`（同一目录）。
本文件是人类可读版 + T1–T3 评估骨架；示例行是**合成示例，不是真实数据**。

## 1. 一行 = 一个 segment 在一周的聚合

| 字段 | 类型 | 说明 / 来源性质 |
|---|---|---|
| `panel_id` | string | 面板版本，如 `gtm-panel-v0` |
| `week_start` | string（YYYY-MM-DD，周一） | 周频，全部字段按此周对齐 |
| `segment` | enum | `developer_api` / `enterprise` / `partner_channel` / `consumer_paid` |
| `cohort` | string | 如 `model_family` 的公开名称 + 版本代际（不含个人、公司名单） |
| `model_release_count` | int ≥ 0 | 该周公开模型 / 版本发布数（官方公告聚合） |
| `license_type` | enum | `open_weights` / `open_weights_with_custom_terms` / `proprietary_api` / `mixed` |
| `list_price_snapshot` | object | 官网定价页快照的区间（谷时 / 峰时、缓存命中与否分开记，禁止跨口径比较） |
| `cloud_listings` | int ≥ 0 | 该周在公开云市场 listing 的平台数（Bedrock / Foundry / Azure 等，仅计数） |
| `third_party_hosts` | int ≥ 0 | 公开第三方托管商数（仅计数，不含客户名单） |
| `host_price_spread` | float ≥ 0 | 同模型在托管商间的公开价差（最高/最低比，价差大 = 市场不成熟的摩擦信号） |
| `openrouter_share_direction` | enum | `up` / `flat` / `down`（周 token 份额方向，**不是收入**；见 F1） |
| `hf_downloads_band` | enum | `low` / `mid` / `high`（Hugging Face 公开下载量分档，不用精确个人级数据） |
| `public_integrations` | int ≥ 0 | 公开集成清单中的集成数（Dify / n8n / Langflow 等公开目录，仅计数） |
| `docs_examples_update_count` | int ≥ 0 | 该周文档 / 示例 / 迁移工具的公开更新次数（爬坡使能的代理） |
| `org_event_count` | int ≥ 0 | 公开组织事件数（融资、IPO 进程、出口登记、行业方案发布；仅事件计数与时间戳） |
| `public_job_postings` | int ≥ 0 | 公开岗位标题与地点聚合计数（**不统计个人、不记录求职者**） |
| `controversy_event` | bool | 该周是否有公开争议事件（蒸馏指控、出口管制等，仅时间戳） |
| `notes` | string | 口径说明（如“本行 token 份额受托管商结构变化影响，见 F3”） |

**明确不进面板的字段**：个人姓名、邮箱、电话、个人社交账号、个人行为轨迹、
任何厂商内部的注册 / 付费 / 用量数据、任何购买的名单。

## 2. 示例行（合成示例，不是真实数据）

```json
{
  "panel_id": "gtm-panel-v0",
  "week_start": "2026-10-19",
  "segment": "developer_api",
  "cohort": "EXAMPLE-MODEL-FAMILY",
  "model_release_count": 0,
  "license_type": "open_weights_with_custom_terms",
  "list_price_snapshot": {"off_peak_per_million": 0.14, "peak_per_million": 0.28, "cache_note": "cache-miss basis"},
  "cloud_listings": 3,
  "third_party_hosts": 6,
  "host_price_spread": 2.4,
  "openrouter_share_direction": "flat",
  "hf_downloads_band": "high",
  "public_integrations": 12,
  "docs_examples_update_count": 2,
  "org_event_count": 1,
  "public_job_postings": 3,
  "controversy_event": false,
  "notes": "SYNTHETIC EXAMPLE ROW"
}
```

## 3. T1–T3 评估骨架（全部是代理任务，不是转化率预测）

### T1 · 采用热度今测（nowcasting）
- **输入**：面板周频字段（供给侧 + 需求侧代理 + 组织信号）。
- **预测目标（代理标签）**：下 4 周 `openrouter_share_direction` 的方向（涨 / 平 / 跌）。
- **基线（必须打败）**：朴素持续性基线 —— 上周方向 = 下周方向。
- **指标**：方向准确率、校准度。
- **预注册成功标准**：时序模型方向准确率显著高于持续性基线，**且在模型发布周之外仍成立**（排除发布脉冲，见 F2）。
- **主要失效模式**：F1（token 通胀）、F2（发布脉冲）、F3（托管商结构变化）。

### T2 · 爬坡代理预测（预测“留下来”，不预测“注册”）
- **输入**：T1 信号 + 文档/示例/迁移工具更新频率 + 第三方托管商数量与价差收敛。
- **预测目标（代理标签）**：该 cohort 在 8 周后仍保持在公开集成清单与托管清单中（未被下架 / 边缘化）。
- **基线（必须打败）**：静态流行度基线 —— 当前排名预测未来排名。
- **指标**：AUC、排序相关性（Spearman）。
- **预注册成功标准**：时序模型在留存代理上的 AUC / 排序相关性显著高于静态基线。
- **主要失效模式**：F4（价格战混杂：降价带来的量涨与 GTM 带来的量涨无法仅凭公开数据分离）、F5（幸存者偏差）。

### T3 · 衰减预警（提前 2 周）
- **输入**：用量增速放缓、托管商下架、价格战、争议事件时间戳。
- **预测目标（代理标签）**：用量份额连续 4 周下滑，且预警需提前 2 周发出。
- **基线（必须打败）**：无预警基线（随机预警）。
- **指标**：提前 2 周的预警召回率 + 误报率上限。
- **预注册成功标准**：召回率高于随机，**且误报率有明确上限**（否则预警无用）。
- **主要失效模式**：F1、F3、F4。

## 4. 失效模式 F1–F5（实验后逐项打勾，缺一不可）

| # | 失效模式 | 含义 | 缓解 / 报告方式 |
|---|---|---|---|
| F1 | Token 通胀 | 推理 token 与 agent 循环放大 token 量，份额涨 ≠ 客户涨 | 份额只报方向，不报“客户增长”；同时报集成数与托管商数 |
| F2 | 发布脉冲 | 新模型发布周热度不可外推为留存 | 成功标准要求“发布周之外仍成立”；分开发布周 / 非发布周报告 |
| F3 | 托管商结构变化 | OpenRouter 新增 / 移除托管商会改变份额，与厂商 GTM 无关 | 备注托管商结构变化周；份额变化需与结构变化分开讨论 |
| F4 | 价格战混杂 | 降价带来的量涨与 GTM 带来的量涨无法仅凭公开数据分离 | 不做因果宣称；价格变动周单独标记，不归因 |
| F5 | 幸存者偏差 | 只看“还在清单里的模型”，低估被下架模型的失败率 | 保留下架 cohort 的历史行；留存率分母含已下架者 |

## 5. 本原型未做的事（诚实清单）

- 本文件只有 schema 与评估骨架，**没有采集真实面板数据**，也没有跑 T1–T3 的真实模型。
  采集真实面板时只能用公开来源，且必须遵守各来源的使用条款与 robots / API 限制；
  任何涉及个人的字段一律不进面板。
- 如果时序模型打不过持续性 / 静态基线，那就是有价值的负结果：
  说明公开信号对爬坡率的预测价值有限，G+ 的状态表示必须依赖产品内行为数据，
  而不是公开信号。负结果也要写进论文，不得只报正结果。
