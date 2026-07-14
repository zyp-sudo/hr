# ETL 治理与数据质量评分

## 当前落地状态

本轮按中国公司招聘数据收敛，输出均带来源标记、采集时间戳和岗位发布时间：

- 采集来源：`Tencent Careers`
- 来源类型：`official_enterprise_api`
- 岗位记录：2271
- 技能证据：8637
- 候选人-岗位评分：4542
- 采集时间：见 `data/collection_report.json` 与 `data/raw/china_jobs/tencent/manifest.json`

阿里、网易当前仅注册为官方站点入口，首页抽链未获得稳定岗位详情，所以未混入统一表，避免污染质量。海外来源已默认禁用，后续 `all` 模式也不会自动爬取海外数据。

## 管道入口

采集中国公司岗位：

```powershell
$env:CHINA_JOB_SOURCES='china'
$env:CHINA_JOB_TARGET='2500'
$env:CRAWL_RESET='1'
$env:TENCENT_JOB_MAX='2300'
$env:ALLOW_FOREIGN_SOURCES='0'
python scripts\crawl_jobs_100k.py
```

海外来源防护：

- `scripts/crawl_jobs_100k.py` 默认 `CHINA_JOB_SOURCES=china`
- `CHINA_JOB_SOURCES=all` 默认仍只展开为中国公司来源
- Greenhouse、Lever、RemoteOK、Arbeitnow、Google、Apple 等海外来源会被跳过
- 只有显式设置 `ALLOW_FOREIGN_SOURCES=1` 才允许海外适配器运行

重跑 ETL：

```powershell
python scripts\etl_unify_jobs.py
```

解析本地简历样例或用户提供的简历文件：

```powershell
python scripts\parse_resume_local.py
```

## 输入与输出

输入：

- `data/collected_jobs.csv`
- `data/collected_job_skills.csv`
- `data/source_registry.csv`
- `data/resume_samples.csv`
- 可选：`data/application_outcomes.csv`

输出：

- `data/etl/unified_jobs.csv`
- `data/etl/unified_job_skills.csv`
- `data/etl/data_quality_report.csv`
- `data/etl/job_candidate_scores.csv`
- `data/etl/etl_manifest.json`

## 统一岗位 Schema

核心追溯字段：

- `record_id`
- `origin_record_id`
- `source_id`
- `source_type`
- `source_name`
- `source_url`
- `collected_at`
- `published_at`

岗位与组织字段：

- `country`
- `province`
- `city`
- `company`
- `department`
- `product`
- `category`
- `normalized_category`
- `role_id`
- `role_name`
- `job_title`
- `job_type`
- `work_years`

文本与抽取字段：

- `responsibility`
- `requirement`
- `raw_text`
- `normalized_skills`
- `skill_count`
- `skill_evidence`
- `capability_dimensions`
- `capability_scores`

应聘评估字段：

- `estimated_application_success_probability`
- `relative_ability_score`
- `scoring_basis`

质量字段：

- `quality_score`
- `quality_level`
- `quality_flags`
- `content_hash`

## 技能与能力维度

统一词表在 `scripts/job_taxonomy.py`：

- 技能抽取：`SKILL_ALIASES`
- 技能到子维度：`SKILL_DIMENSIONS`
- 子维度到能力组：`CAPABILITY_GROUPS`
- 岗位族识别：`ROLE_RULES`
- 岗位方向分类：`CATEGORY_RULES`

能力组示例：

- 工程基础能力
- 工程研发能力
- 数据能力
- 智能技术能力
- 基础设施能力
- 工程质量能力
- 安全能力
- 业务能力
- 体验能力
- 通用能力

## 应聘成功概率与相对能力分

`data/etl/job_candidate_scores.csv` 按“候选人-岗位”生成评分。当前没有真实投递结果时，使用 `data/resume_samples.csv` 中的本地示例简历生成可复现的规则评分。

如果提供 `data/application_outcomes.csv`，ETL 会读取：

- `application_id`
- `resume_id`
- `job_record_id`
- `outcome_label`

评分特征：

- 技能匹配率：45%
- 能力维度匹配率：20%
- 年限匹配：20%
- 学历匹配：10%
- 岗位数据质量：5%

相对能力分为 0-100。成功概率基于相对能力分做 sigmoid 映射；这不是最终招聘模型，只是可解释的基线估计，后续可用真实投递成败标签训练校准。

## 数据质量评分

每条岗位记录初始 100 分，按问题扣分：

- 缺岗位名：25
- 缺来源 URL：15
- 缺采集时间：15
- 缺发布时间：10
- 缺城市：5
- 缺公司：5
- 缺来源原始 ID：5
- 职责文本过短：12
- 要求文本过短：12
- 未抽取到技能：10
- 内容重复：20
- 未知来源：10

等级：

- A：`>=85`
- B：`70-84`
- C：`55-69`
- D：`<55`

质量报告按来源聚合，记录均分、等级分布和各类缺陷计数。
