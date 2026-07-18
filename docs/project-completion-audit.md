# 项目数据规模、质量指标与算法指标口径审计报告

> **生成日期**: 2026-07-17
> **审计范围**: E:\202676 仓库内所有数据文件、manifest、benchmark、文档
> **原则**: 不修改业务代码、现有数据和测试；只创建本报告

---

## 1. 数据文件实际记录数

### 1.1 采集层 CSV

| 文件 | 行数 (wc -l) | 数据行 (去表头) | 文件大小 | 备注 |
| --- | --- | --- | --- | --- |
| `data/collected_jobs.csv` | 546 | **545** | 809 KB | 含 BOM 表头；与 china_jobs.csv 完全相同 |
| `data/china_jobs.csv` | 546 | **545** | 809 KB | 与 collected_jobs.csv 字节级一致 |
| `data/foreign_jobs.csv` | 1 | **0** | 161 B | 仅表头，无海外数据 |
| `data/jobs.csv` | 5 | **4** | 584 B | 早期 MVP 手工演示数据 |
| `data/collected_job_skills.csv` | 856 | **855** | 1,071 KB | 对应 545 条岗位的技能命中 |
| `data/collected_sources.csv` | 2 | **1** | 222 B | 仅 1 条来源记录 |
| `data/resume_samples.csv` | 4 | **3** | 433 B | 3 条简历样本 |

### 1.2 ETL 统一层

| 文件 | 行数 | 数据行 | 文件大小 | 生成时间 |
| --- | --- | --- | --- | --- |
| `data/etl/unified_jobs.csv` | 55,268 | **55,267** | 72.8 MB | 2026-07-17 11:11 |
| `data/etl/unified_job_skills.csv` | 69,616 | **69,615** | 42.4 MB | 2026-07-17 11:11 |
| `data/etl/data_quality_report.csv` | 7 | **6** | 1 KB | 按来源聚合 |
| `data/etl/job_candidate_scores.csv` | 50,001 | **50,000** | 17.9 MB | 候选人-岗位评分 |

### 1.3 仓库导出层

| 文件 | 行数 | 含义 | 文件大小 | 生成时间 |
| --- | --- | --- | --- | --- |
| `data/warehouse/elasticsearch_jobs.ndjson` | **110,220** | 55,110 条 index action + 55,110 条 document (ES bulk 格式) | 70.2 MB | 2026-07-15 |
| `data/warehouse/chroma_documents.jsonl` | **55,110** | 每条岗位 1 个 Chroma 文档 | 54.5 MB | 2026-07-15 |

### 1.4 知识图谱层

| 文件 | 行数 | 数据行 | 文件大小 | 生成时间 |
| --- | --- | --- | --- | --- |
| `data/kg/nodes.csv` | 908 | **907** | 176 KB | 2026-07-15 |
| `data/kg/edges.csv` | 1,807 | **1,806** | 377 KB | 2026-07-15 |
| `data/kg/role_aliases.csv` | — | **34,094** | 2.2 MB | 岗位别名消歧 |
| `data/kg/skill_trends.csv` | — | **2,932** | 235 KB | 技能月度趋势 |

### 1.5 原始采集数据

| 路径 | 文件数 | 备注 |
| --- | --- | --- |
| `data/raw/china_jobs/tencent/` | 大量 | 腾讯岗位详情 JSON（6,950 个 raw JSON 总计） |
| `data/raw/china_jobs/meituan/` | 有 | 美团岗位 |
| `data/raw/china_jobs/huawei/` | 有 | 华为岗位 |
| `data/raw/china_jobs/baidu/` | 有 | 百度岗位 |
| `data/raw/china_jobs/jobonline/` | 有 | 公共就业服务 |
| `data/raw/china_jobs/ncss/` | 有 | 国家大学生就业服务 |

---

## 2. 文档中关键数字的含义溯源

### 2.1 "545"（实际 545 条）

**来源**: `data/collected_jobs.csv` 当前磁盘上的数据行数。

**代表什么**: **最新一次采集运行**（2026-07-17 11:11，target=1000）写入磁盘的增量记录。`collection_report.json` 记载 `new_records_this_run: 546`（与 545 差 1，可能含 BOM 计数差异）。

**不是**: 累计采集总量。累计总量在 `data/etl/unified_jobs.csv` 中为 55,267 条。

### 2.2 "55,110"

**来源**: `pipeline_manifest.json`（2026-07-15）、`architecture_manifest.json`（2026-07-15）、`kg_manifest.json`（2026-07-15）三者一致记载。

**代表什么**: **2026-07-15 管道运行时的岗位快照**——仓库导出（ES/Chroma/MySQL/Neo4j）和 KG 的基准记录数。这是 cleanroom 验证的 55,110 不变量（见 `docs/p1-remediation.md`）。

**不是**: 最新的 ETL 统一记录数（最新为 55,267，增量 +157）。

### 2.3 "55,267"

**来源**: `data/etl/etl_manifest.json`（2026-07-17）和 `data/collection_report.json`（2026-07-17）。

**代表什么**: **截至 2026-07-17 的最新 ETL 统一岗位记录数**。比 7/15 快照多 157 条。

### 2.4 "1,000+"

**来源**: `docs/project-master-plan.md` L66 "最终扩展到 1000+ JD"，`collection_report.json` 中 `target: 1000`。

**代表什么**: **单次采集运行的岗位目标数**。最近一次运行目标 1000 条，实际获取 546 条（545 条中国 + 0 条海外），`target_met: true`（因 gap=0 即无未覆盖来源时即视为达标，而非达到 1000）。

### 2.5 "100k"（十万）

**来源**: 采集主入口脚本命名 `scripts/crawl_jobs_100k.py`。

**代表什么**: **工程命名的 aspirational 上限**，不是已实现的数据规模。`collection_report.json` 明确声明 "The pipeline never duplicates postings just to hit 100k." 当前实际 ETL 记录为 55,267，约为十万目标的 55%。

### 2.6 "110,220"

**来源**: `data/warehouse/elasticsearch_jobs.ndjson` 行数。

**代表什么**: **Elasticsearch Bulk API 格式的行数**，每 2 行对应 1 条岗位（1 行 index action + 1 行 document JSON）。实际文档数 = 110,220 / 2 = 55,110。

---

## 3. 口径区分

### 3.1 当前采集快照（Delta）

- **文件**: `data/collected_jobs.csv`（545 行）、`data/china_jobs.csv`（545 行）
- **性质**: 单次采集运行写入的**增量记录**，不是全量累计
- **证据**: 文件大小仅 809 KB，不可能容纳 55,267 条记录

### 3.2 ETL 后记录（累积全量）

- **文件**: `data/etl/unified_jobs.csv`（55,267 行）
- **性质**: 所有采集运行合并后的**统一全量岗位表**，经标准化、去重、质量评分
- **时间戳**: 2026-07-17 11:11
- **字段**: 包含规范化分类、技能标准化、能力维度、质量分等 30+ 列

### 3.3 仓库导出记录（上一快照）

- **文件**: `data/warehouse/elasticsearch_jobs.ndjson`（55,110 文档）、`data/warehouse/chroma_documents.jsonl`（55,110 文档）
- **性质**: 基于 2026-07-15 管道的**导出产物**，供 MySQL/ES/Neo4j/ChromaDB 导入
- **时效性**: 落后 ETL 最新记录 157 条（55,267 - 55,110 = 157）
- **说明**: 仓库导出不是每次采集自动触发，需独立运行 `build_full_pipeline.py` 或 `export_architecture_artifacts.py`

### 3.4 数据库运行态记录

- **载体**: Docker 中的 MySQL 8.4、Elasticsearch 8.13.4、Neo4j 5.26
- **记录数**: cleanroom 验证为 55,110 条岗位（基于 7/15 快照）
- **同步方式**: `bootstrap_storage.py --sync` 增量同步，SHA-256 变化检测
- **状态文件**: `data/sync/storage_state.json`、`data/sync/elasticsearch_state.json`

### 3.5 历史累计记录

- **体现**: ETL 统一表 55,267 条；source_counts 显示 JobOnline 50,000 条来自公共就业服务平台
- **来源分布**（据 collection_report.json）:
  | 来源 | 记录数 |
  | --- | --- |
  | JobOnline 公共就业服务 | 50,000 |
  | 美团招聘 | 2,394 |
  | 腾讯招聘 | 2,375 |
  | 华为招聘 | 378 |
  | 国家大学生就业服务 | 100 |
  | 百度招聘 | 20 |

---

## 4. ⚠️ 口径冲突与数据一致性问题

### 4.1 collected_jobs.csv 与 ETL 统一表口径不同（待验证，不直接判定为缺陷）

| 维度 | collection_report.json 记载 | 磁盘实测 | 口径解释 |
| --- | --- | --- | --- |
| 记录数 | `actual_records: 55267` | 545 行数据 | 前者为 ETL merge 后的累计总量；后者为本次运行写入磁盘的快照行数 |
| write_mode | `merge` | 文件仅含本轮增量 | merge 语义落在 ETL 层（`unified_jobs.csv`）；采集层 CSV 可能仅保留当轮 delta |

**当前事实**:
- `data/collected_jobs.csv` 磁盘上为 545 条（**本轮采集快照**）
- `data/etl/unified_jobs.csv` 磁盘上为 55,267 条（**多轮 merge 后的 ETL 累计全量**）
- `collection_report.json` 中的 `actual_records: 55267` 与 ETL 统一表一致，说明 manifest 记录的是 merge 后的累计值
- 二者差异（545 vs 55,267）源自**口径不同**，而非数据损坏：545 是当轮快照，55,267 是历史累计

**暂不判定的原因**:
- 未验证采集脚本的 merge 路径是否将全量快照写入其他输出文件（如 `data/etl/` 下的中间产物）
- 未验证以 `--reset` 模式从 `collected_jobs.csv` 重跑 ETL 时是否能从 raw JSON 恢复历史全量
- 未验证增量同步链路（`bootstrap_storage.py --sync`）是否依赖 `collected_jobs.csv` 还是仅依赖 `unified_jobs.csv`
- 在以上验证完成前，将二者口径差异判定为"程序缺陷"依据不足

**建议**: 在文档或 `collection_report.json` 的 note 字段中明确 `collected_jobs.csv` 的语义是"当前/最近一轮采集快照"还是"累计全量"，消除歧义。

### 4.2 仓库导出快照待刷新

| 数据层 | 记录数 | 时间戳 | 状态 |
| --- | --- | --- | --- |
| ETL unified_jobs.csv | 55,267 | 2026-07-17 11:11 | 最新 |
| Warehouse (ES/Chroma) | 55,110 | 2026-07-15 20:53 | ⚠️ 待刷新 |
| KG (nodes/edges) | 907/1,806 | 2026-07-15 20:53 | ⚠️ 待刷新 |
| **差异** | **+157** | **落后约 14 小时** | — |

仓库导出产物（`elasticsearch_jobs.ndjson`、`chroma_documents.jsonl`、`nodes.csv`、`edges.csv`）基于 2026-07-15 管道运行生成。自那之后 ETL 统一表又积累 157 条新记录。这不是错误——仓库导出不是每次采集自动触发，需独立运行 `build_full_pipeline.py`。当前状态标记为"待刷新"。数据库运行态（若已拉起 Docker 并执行 `--sync`）的实际记录数以 `data/sync/storage_state.json` 为准。

### 4.3 ES ndjson 行数 = 2× 文档数

`elasticsearch_jobs.ndjson` 有 110,220 行，这是 Elasticsearch Bulk API 的标准格式（每文档 2 行：index action + document body）。行数 ≠ 文档数，对外引用时应用文档数 55,110，而非行数 110,220。

### 4.4 collected_jobs.csv 与 china_jobs.csv 完全相同

两个文件字节级一致（均为 809,310 bytes），`foreign_jobs.csv` 为空。海外数据采集已显式禁用（`ALLOW_FOREIGN_SOURCES=0`）。

---

## 5. 基准测试与算法指标审计

### 5.1 确定性回归基准（accuracy_report.json）

| 指标 | 数值 | 案例数 | 可信度 |
| --- | --- | --- | --- |
| JD 技能抽取 F1 | **1.0000** | 80 (20 词 × 4 模板) | 低 — 规则模板自测 |
| 岗位分类准确率 | **1.0000** | 45 (9 类 × 5 后缀) | 低 — 规则模板自测 |
| 简历字段准确率 | **1.0000** | 20 (5 样本 × 4 前缀) | 低 — 规则模板自测 |
| 匹配决策准确率 | **1.0000** | 20 (10 技能 × 2 结果) | 低 — 二值阈值判定 |

**总案例数**: 165
**全部指标**: 1.0（满分）
**性质**: 这是 `scripts/job_taxonomy.py` 中硬编码规则的**确定性回归测试**——用规则模板生成输入，再验证同一套规则的输出。满分 1.0 仅证明规则没有自相矛盾，**不能作为生产准确率对外宣传**。

### 5.2 人工标注 Holdout（accuracy_holdout_report.json）

| 指标 | 数值 | 案例数 | 可信度 |
| --- | --- | --- | --- |
| 技能抽取 Precision | **0.7647** | 12 条 skill 案例 | 中低 — 单标注者 |
| 技能抽取 Recall | **0.8667** | 12 条 skill 案例 | 中低 — 单标注者 |
| 技能抽取 F1 | **0.8125** | 12 条 skill 案例 | 中低 — 单标注者 |
| 岗位分类准确率 | **0.6667** | 12 条 category 案例 | 中低 — 单标注者 |

**总案例数**: 24（12 skill + 12 category）
**标注者**: 1 人，非双盲
**分层分类准确率**: AI 0.50 / 后端 0.50 / 数据 0.00 / 前端 0.00 / 其他各 1.00

**局限**:
- 样本量极小（24 条），统计误差很大
- 单标注者，无独立验证
- 非双盲设计，存在标注者偏差风险
- 岗位分类在小类（1 条样本）上的准确率不可靠（数据 0.0 和前端 0.0 各仅 1 条）
- 文档自述："Small diagnostic holdout; expand with two independent domain annotators before production claims"

### 5.3 检索基准（retrieval_report.json）

| 指标 | 数值 | Query 数 | 可信度 |
| --- | --- | --- | --- |
| Mean MRR@10 | **1.0000** | 4 | 低 — 仅 4 个 query |
| Mean nDCG@10 | **0.9315** | 4 | 低 — 仅 4 个 query |
| Mean Judged Coverage@10 | **1.0000** | 4 | — |

**Query 列表**: "大模型推理"、"Java 后台"、"产品经理"、"游戏引擎"
**标注方式**: Pooled top-10 候选集，单标注者，未评文档视为不相关

**局限**:
- 仅 4 个 query，覆盖极窄
- 单标注者，非双盲
- Judged coverage 100% 是因为只对 top-10 做标注（pooling），不是真实全库覆盖
- MRR=1.0 意味着每个 query 的第一个结果都是相关——4 个 query 均为精选案例
- 文档自述："expand pooling and use two reviewers for production claims"

### 5.4 字段覆盖率（field_coverage_report.json）

| 字段 | 非空记录 | 覆盖率 | 局限 |
| --- | --- | --- | --- |
| 学历 | 33,891 / 55,267 | **61.32%** | 仅提取显式学历词；"博士优先"等不计入 |
| 薪资 | 11,246 / 55,267 | **20.35%** | 仅标准人民币月薪/年薪；面议/外币/时薪留空 |

**注意**: 覆盖率 ≠ 抽取准确率。文档注明 "Coverage is source-data coverage, not extraction accuracy."

---

## 6. 无法从仓库确认的声明

以下声明出现在文档或 manifest 中，但无法从仓库文件直接验证：

| # | 声明 | 出处 | 无法确认原因 |
| --- | --- | --- | --- |
| 1 | `actual_records: 55267` 与 `collected_jobs.csv` 545 行口径一致 | collection_report.json | 两者口径不同（累计 merge vs 当轮快照），需验证 merge 路径和恢复逻辑后再下结论 |
| 2 | `write_mode: merge` 对 collected_jobs.csv 的实际语义 | collection_report.json | 未确认 merge 将全量快照写回 collected_jobs.csv 还是仅写入 ETL 中间产物 |
| 3 | "岗位分类准确率 >= 90%" | docs/requirements-summary.md | 要求 90%，但 holdout 实际 66.67% |
| 4 | "JD 解析准确率 >= 90%" | docs/requirements-summary.md | 确定性基准 100% 不可信；holdout 无此指标 |
| 5 | "简历提取准确率 >= 90%" | docs/requirements-summary.md | 仅有 5 条确定性样本；holdout 不测简历提取 |
| 6 | "单元测试覆盖率 >= 60%" | docs/requirements-summary.md | 仓库中未找到覆盖率报告文件 |
| 7 | `candidate_score_records: 50000` | etl_manifest.json | candidate_scores.csv 有 50,000 行但为规则生成（非真实投递） |
| 8 | Cleanroom 验证 55,110 不变量 | docs/p1-remediation.md | 需运行 Docker 环境才能复现 |
| 9 | RAG/ChromaDB 运行时可用 | docs/mvp-scope.md | 文档已标 "partial"，仅有数据待向量化 |
| 10 | DeepSeek 大模型抽取 | pipeline_manifest.json | 当前为 dry_run/rule_based，无 API Key |

---

## 7. 对外演示可宣传与不可宣传的指标

### ✅ 可以宣传（有可审计文件支撑）

| 指标 | 可宣传值 | 证据 | 注意事项 |
| --- | --- | --- | --- |
| ETL 统一岗位总量 | **55,267 条** | `data/etl/unified_jobs.csv` | 说明含 JobOnline 公共服务 50,000 条 |
| 知识图谱节点数 | **907 个** | `data/kg/nodes.csv` | 岗位+技能+能力维度节点 |
| 知识图谱边数 | **1,806 条** | `data/kg/edges.csv` | requires/belongs_to/bonus 关系 |
| 技能证据条数 | **69,615 条** | `data/etl/unified_job_skills.csv` | 从岗位 JD 中抽取的技能命中 |
| 岗位类别覆盖 | **10 类** | etl_manifest.json | AI/后端/数据/产品/云/测试/设计/其他/前端/安全 |
| 活跃采集来源 | **6 个** | collection_report.json | 腾讯/美团/华为/百度/NCSS/JobOnline |
| 原始采集文件 | **6,950+ 个** | `data/raw/` | 含岗位详情 JSON |
| 学历字段覆盖率 | **61.32%** | field_coverage_report.json | 基于显式学历词提取 |
| 薪资字段覆盖率 | **20.35%** | field_coverage_report.json | 标准人民币月薪/年薪 |
| 数据质量评分体系 | **扣分制 (100→)** | etl_manifest.json | 12 项扣分规则，A/B/C/D 四级 |
| 技能 F1 (holdout) | **0.8125** | accuracy_holdout_report.json | 24 条样本，标注"小样本诊断用" |
| 检索 nDCG@10 | **0.9315** | retrieval_report.json | 4 个 query，标注"回归基线" |
| 数据可溯源 | **每条带 source_id/timestamp/url** | unified_jobs.csv schema | 审计链完整 |

### ⚠️ 需加限定词方可宣传

| 指标 | 可宣传值 | 必须加上的限定词 |
| --- | --- | --- |
| JD 技能抽取 F1 = 1.0 | 确定性回归基准 | "规则自测，非独立标注的生产准确率" |
| 岗位分类准确率 = 1.0 | 确定性回归基准 | "规则模板验证，holdout 实测 66.67%" |
| MRR@10 = 1.0 | 4 个精选 query | "仅 4 个 query 的回归基线，不具统计意义" |
| 人岗匹配准确率 = 1.0 | 确定性回归基准 | "二值阈值判定，非真实招聘效果校准" |

### ❌ 不可宣传

| 声明 | 不可宣传原因 |
| --- | --- |
| "十万级岗位数据" | 实际 55,267，55% 来自单一公共就业平台（JobOnline），企业官网不足 5,200 条 |
| "JD 解析准确率 ≥ 90%" | 要求中的目标值，holdout 分类准确率仅 66.67%，技能 F1 仅 81.25% |
| "简历提取准确率 ≥ 90%" | 无独立标注评测数据支撑 |
| "单元测试覆盖率 ≥ 60%" | 仓库中未找到覆盖率报告 |
| "RAG 检索增强生成已实现" | 文档自标 partial，仅有待向量化数据 |
| "大模型智能抽取" | 当前为 dry_run/rule_based，无 API Key |
| "海外岗位数据" | foreign_jobs.csv 为空，海外采集已禁用 |
| "双盲标注验证" | 所有标注均为单标注者，非双盲 |

---

## 8. 总评

### 8.1 数据规模现状

项目当前拥有 **55,267 条 ETL 统一岗位记录**（含 50,000 条公共就业平台数据 + ~5,200 条企业官网数据），**907 个知识图谱节点**、**1,806 条边**、**69,615 条技能证据**。数据规模满足 MVP 演示需求，但与脚本命名的"100k"目标有差距。JobOnline 公共服务占比过高（90.5%），企业官网数据代表性有限。

### 8.2 指标可信度

- **确定性基准**（165 案例，全 1.0）：不可对外作为准确率宣传，仅用于防止规则回归
- **人工 Holdout**（24 案例，技能 F1 0.81，分类 0.67）：较为诚实的诊断数据，但样本量过小、单标注者、非双盲。分类准确率 66.67% 显著低于比赛中"准确率 ≥ 90%"的要求
- **检索基准**（4 query，MRR 1.0，nDCG 0.93）：query 数过少，pooling 方式的 judged coverage=100% 是设计使然非真实覆盖

### 8.3 关键风险

1. **collected_jobs.csv 语义待明确**: 磁盘文件为 545 条当轮快照，ETL 统一表为 55,267 条累计全量。在 merge 路径、历史恢复和增量同步逻辑验证完成前，需明确该文件是"增量快照"还是"累计全量"，避免下游误读
2. **仓库导出过期**: ES/Chroma/MySQL 导入产物基于 7/15 快照，未随 ETL 更新
3. **JobOnline 数据质量未知**: 50,000 条公共就业服务数据占总量 90.5%，其来源可信度、去重质量和时效性未独立审计
4. **单点故障**: 所有标注和评测均为单人完成，无交叉验证

### 8.4 建议

1. 明确 `collected_jobs.csv` 的语义（增量快照还是累计全量），使其与 `collection_report.json` 和 ETL 统一表的表述一致
2. 重跑 `build_full_pipeline.py` 使仓库导出与 ETL 同步
3. 将 holdout 样本扩展到 ≥ 200 条，引入双人独立标注
4. 检索基准扩展到 ≥ 30 个 query，覆盖更多岗位类别
5. 生成并提交单元测试覆盖率报告
6. 若需达到"十万级"，需在保证质量的前提下扩展采集来源
