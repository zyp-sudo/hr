# Competition Evaluation Guide

> 赛题独立评测框架与人工标注操作手册

## 概述

本目录 (`docs/competition-evaluation-guide.md`) 配套以下交付件：

| 交付件 | 路径 | 用途 |
|--------|------|------|
| 标注集构建脚本 | `scripts/build_competition_annotation_set.py` | 从真实ETL岗位中采样并生成标注模板 |
| 评测脚本 | `scripts/evaluate_competition_metrics.py` | 独立评测框架，计算Precision/Recall/F1/混淆矩阵 |
| 标注模板 | `data/benchmarks/competition/*.csv` | 人工标注CSV模板（当前为空） |
| 单元测试 | `tests/test_competition_metrics.py` | 29个测试用例覆盖全部三类评测 |
| 本指南 | `docs/competition-evaluation-guide.md` | 双人标注协议、分歧仲裁、指标口径 |

---

## 1. 三类评测任务

### 1.1 JD解析（Job Description Parsing）

**目标**：评估系统从岗位描述文本中提取结构化字段的准确度。

**评测字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `annotated_skills` | 集合（pipe-separated） | 规范化技能名称，参考 `scripts/job_taxonomy.py` 中的 `SKILL_ALIASES` |
| `annotated_responsibilities` | 集合（pipe-separated） | 核心职责短语 |
| `annotated_education` | 分类 | 最低学历要求：博士 / 硕士 / 本科 / 大专 / 不限 |
| `annotated_experience_years` | 数值 | 最低工作年限要求（整数） |

**指标**：

- **技能提取**：Precision、Recall、F1（micro-averaged，逐技能token比对）
- **学历准确率**：exact-match accuracy
- **经验年限准确率**：exact-match accuracy
- **职责短语重叠**：token-level Jaccard similarity（辅助指标）

**数据来源**：从 `data/etl/unified_jobs.csv` 中以固定随机种子（42）抽取至少100条 `data_engineering` 类别或ETL相关岗位。标注模板包含机标参考列（`machine_*`）供标注员参考，但标注员必须独立判断。

### 1.2 简历提取（Resume Extraction）

**目标**：评估系统从简历文本中提取结构化字段的准确度。

**评测字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `annotated_skills` | 集合 | 规范化技能名称 |
| `annotated_education` | 分类 | 最高学历 |
| `annotated_experience_years` | 数值 | 总工作年限 |
| `annotated_projects` | 集合 | 项目名称/描述 |
| `annotated_certifications` | 集合 | 证书名称 |

**指标**：

- 技能提取 Precision / Recall / F1
- 学历 exact-match accuracy
- 经验年限 exact-match accuracy
- 证书提取 Precision / Recall / F1
- 项目提取 Precision / Recall / F1

**注意**：简历文本必须真实脱敏，不得伪造。标注模板中的 `resume_text_placeholder` 列为空，由标注员填入脱敏后的简历文本。

### 1.3 人岗匹配（Person-Job Matching）

**目标**：评估系统对岗位与简历匹配程度的判断准确度。

**标签定义**：

| 标签 | 含义 |
|------|------|
| `match` | 简历满足岗位所有核心要求（技能、学历、经验均达标） |
| `partial_match` | 简历满足岗位部分核心要求（例如技能匹配但经验不足） |
| `no_match` | 简历不满足岗位核心要求 |

**指标**：

- **准确率（Accuracy）**：三分类总体准确率
- **Macro-F1**：三类F1的算术平均（处理类别不平衡）
- **混淆矩阵（Confusion Matrix）**：3×3矩阵展示每类的预测分布
- **每类指标**：Precision / Recall / Support

---

## 2. 双人标注协议

### 2.1 标注流程

```
┌──────────────┐    ┌──────────────┐
│  标注员 A     │    │  标注员 B     │
│  (独立标注)   │    │  (独立标注)   │
└──────┬───────┘    └──────┬───────┘
       │                   │
       └────────┬──────────┘
                ▼
        ┌──────────────┐
        │  一致性检查    │
        │  (Cohen's κ)  │
        └──────┬──────┘
               │
        ┌──────┴──────┐
        │   κ ≥ 0.6?   │
        └──────┬──────┘
          Yes  │  No
           ▼   │   ▼
    ┌─────────┐│┌──────────────┐
    │ 合并结果 │││  第三方仲裁   │
    └─────────┘││  (senior)    │
               │└──────┬───────┘
               │       ▼
               │┌──────────────┐
               ││ 重新标注争议  │
               ││ 条目直到 κ≥0.6│
               │└──────────────┘
```

### 2.2 标注规范

1. **独立性**：两位标注员必须独立完成标注，不得交流讨论直到一致性检查完成。
2. **标注员标识**：每人在 `annotator_id` 列填入唯一标识（如 `reviewer_a`、`reviewer_b`）。
3. **标注日期**：在 `annotation_date` 列填入标注日期（ISO格式：`YYYY-MM-DD`）。
4. **技能标注**：参考 `scripts/job_taxonomy.py` 中的 `SKILL_ALIASES` 规范化技能名称。未覆盖的技能在 `annotation_notes` 中注明。
5. **不确定条目**：标注员无法确定的条目，在 `annotation_notes` 中标记 `UNCERTAIN`，由仲裁员决定。

### 2.3 分歧仲裁

- **仲裁触发条件**：Cohen's kappa < 0.6 或任一字段的一致率 < 80%。
- **仲裁员资质**：需具备3年以上技术招聘或NLP标注经验。
- **仲裁流程**：
  1. 第三方审阅所有不一致条目。
  2. 判定最终标签，在 `annotation_notes` 中记录仲裁理由。
  3. 更新模板，合并为最终标注版本（文件名加 `_adjudicated` 后缀）。
- **最终标注**：仲裁后的标注作为评测的ground truth。

### 2.4 IAA 度量

**Cohen's Kappa** 计算公式：

```
κ = (p_o - p_e) / (1 - p_e)
```

其中：
- `p_o` = 观察到的一致率
- `p_e` = 期望的随机一致率

**解释**：

| κ 范围 | 一致程度 |
|---------|----------|
| < 0.0 | 低于随机 |
| 0.0 – 0.2 | 轻微 |
| 0.21 – 0.4 | 一般 |
| 0.41 – 0.6 | 中等 |
| 0.61 – 0.8 | 实质性 |
| 0.81 – 1.0 | 几乎完美 |

本项目要求 **κ ≥ 0.6**（实质性一致及以上）。

---

## 3. 指标口径

### 3.1 技能提取 Precision / Recall / F1

采用 **micro-averaged** 方式，将所有测试样本的技能token对汇总后统一计算：

```
TP = Σ|predicted_skills_i ∩ annotated_skills_i|   （所有样本的正确匹配数之和）
FP = Σ|predicted_skills_i - annotated_skills_i|   （所有样本的误报数之和）
FN = Σ|annotated_skills_i - predicted_skills_i|   （所有样本的漏报数之和）

Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 × P × R / (P + R)
```

### 3.2 字段准确率（Education / Experience）

采用 **exact-match accuracy**：

```
Accuracy = count(predicted == annotated) / total_samples
```

### 3.3 人岗匹配 Macro-F1

对三个类别分别计算F1后取算术平均：

```
F1_match = 2 × P_match × R_match / (P_match + R_match)
F1_partial = ...
F1_no_match = ...

Macro-F1 = (F1_match + F1_partial + F1_no_match) / 3
```

这保证了每个类别权重相同，不受类别样本数不均衡的影响。

### 3.4 混淆矩阵

3×3矩阵，行=真实标签，列=预测标签：

```
              预测
          match  partial  no_match
真实 match   TP     E_mp     E_mn
     partial E_pm   TP       E_pn
     no_matchE_nm   E_np     TP
```

---

## 4. 可复现性保证

### 4.1 固定随机种子

```python
SEED = 42
random.seed(SEED)
```

所有采样、排列、ID生成均基于此种子。运行 `python -m scripts.build_competition_annotation_set` 多次产生完全相同的输出。

### 4.2 评测独立性

- **机标参考列**（`machine_skills`、`machine_education`、`machine_work_years`）仅供标注员参考，不是ground truth。
- **评测脚本**调用的是 `scripts/job_taxonomy.py` 中的已有规则系统，该系统编写于本评测框架之前，与标注模板独立。
- **严禁**用规则生成答案再验证同一规则——这违反了评测独立性的基本原则。

### 4.3 pending_annotation 机制

当以下任一条件不满足时，评测框架报告 `pending_annotation` 而非计算指标：

1. 所有记录的标注列非空
2. 至少有2位标注员独立完成标注

这确保不会在标注未完成时误报虚假的高分结果。

---

## 5. 运行方法

### 5.1 生成标注模板

```bash
python -m scripts.build_competition_annotation_set
```

输出目录：`data/benchmarks/competition/`

- `jd_parsing_annotation_template.csv` — JD解析标注模板（200条）
- `resume_extraction_annotation_template.csv` — 简历提取标注模板（30条）
- `person_job_matching_annotation_template.csv` — 人岗匹配标注模板（600对）
- `annotation_manifest.json` — 清单与协议
- `README.md` — 目录说明

### 5.2 标注阶段

1. 将CSV模板分发给两位标注员。
2. 标注员填写 `annotator_id`、`annotation_date` 和标注值列。
3. 汇总后检查IAA，必要时仲裁。
4. 将最终标注文件放回 `data/benchmarks/competition/`。

### 5.3 运行评测

```bash
python -m scripts.evaluate_competition_metrics [--output report.json]
```

输出JSON报告包含：
- `status` — `pending_annotation` | `partial_annotation` | `evaluated`
- `annotation_status` — 每个数据集的标注状态
- `jd_parsing` — JD解析指标
- `resume_extraction` — 简历提取指标
- `person_job_matching` — 人岗匹配指标

### 5.4 运行测试

```bash
python -m pytest tests/test_competition_metrics.py -v
```

29个测试用例，覆盖：
- 标注集构建（8个测试）
- 评测器行为（2个测试）
- 指标计算辅助函数（8个测试）
- 标注状态检测（3个测试）
- 模拟标注集成测试（4个测试）
- 模板数量报告（1个测试）
- 其他（3个测试）

---

## 6. 与现有Benchmark的关系

本评测框架与现有benchmark互补，非替代：

| 维度 | 现有Benchmark | 赛题评测框架 |
|------|-------------|-------------|
| **目的** | 回归测试、快速反馈 | 独立精度评估 |
| **标注方式** | 模板生成 / 单人标注 | 双人独立标注+仲裁 |
| **规模** | 165条模板 + 24条holdout + 4查询 | 200 JD + 30简历 + 600配对 |
| **JD字段** | 仅技能 | 技能+职责+学历+经验 |
| **简历字段** | 技能+学历+年限 | 技能+学历+年限+项目+证书 |
| **匹配粒度** | 二分类(≥60分) | 三分类+混淆矩阵 |
| **标注状态** | single-reviewer | double-reviewer + IAA |
| **指标覆盖** | P/R/F1 + Acc | P/R/F1 + Acc + Macro-F1 + 混淆矩阵 |

---

## 7. 当前状态

**所有标注模板的标注列均为空——状态为 `pending_annotation`。**

- JD Parsing: 0/200 records annotated
- Resume Extraction: 0/30 records annotated  
- Person-Job Matching: 0/600 pairs annotated

在完成双人标注之前，运行评测脚本将输出 `pending_annotation` 状态，不会计算任何指标。

---

## 8. 附录

### A. 技能标注规范

标注员在填写 `annotated_skills` 时，应映射到以下规范化技能名称：

```
Java, Python, Go, C++, JavaScript, React, Vue, Android, iOS, Unity,
SQL, Redis, Kafka, Docker, Kubernetes, Linux, Microservices, DevOps,
Big Data, Data Warehouse, Machine Learning, Deep Learning, NLP, LLM,
RAG, Vector Search, Prompt Engineering, Testing, Security, Product,
Marketing, Design, Excel
```

完整映射参见 `scripts/job_taxonomy.py` 中的 `SKILL_ALIASES` 字典。

### B. 学历标注规范

| 标注值 | 含义 |
|--------|------|
| 博士 | 博士研究生及以上 |
| 硕士 | 硕士研究生及以上 |
| 本科 | 大学本科及以上 |
| 大专 | 大专/专科学历 |
| 高中 | 高中/中专学历 |
| 不限 | 无学历要求 |

当岗位描述中出现"XX优先"时，标注的是最低要求而非优先条件。例如"硕士及以上，博士优先"应标注为"硕士"。

### C. 职责标注规范

标注员从 `responsibility` 原文中提取3-5个关键职责短语，使用pipe分隔：

```
微服务架构设计|数据库性能优化|系统高可用保障
```

短语应简洁、可独立理解，不包含完整的句子上下文。
