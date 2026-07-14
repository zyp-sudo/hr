# 人岗智能匹配与能力图谱系统：数据存储模块设计

## 第一部分：总体架构说明

MySQL 存储强一致、结构化核心业务数据：岗位、企业、技能、用户、简历、人岗匹配结果。Elasticsearch 存储面向检索与分析的宽文档：岗位搜索、技能聚合、企业搜索、简历搜索。

数据流：

```text
采集/解析/匹配服务 -> MySQL 事务写入
                  -> 同步服务读取 MySQL
                  -> 转换为 ES 文档
                  -> Elasticsearch 检索与聚合
```

同步方式：

- 当前：全量同步和基于 `updated_at` 的增量同步。
- 后续：可替换为定时任务、Canal/binlog、Kafka/RabbitMQ 消息同步。

## 第二部分：MySQL 表结构设计

### companies

企业表。

| 字段 | 类型 | 约束/索引 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | 企业ID |
| name | VARCHAR(255) | UNIQUE, INDEX | 企业名称 |
| industry | VARCHAR(100) | INDEX | 行业 |
| size | VARCHAR(50) |  | 企业规模 |
| region | VARCHAR(100) | INDEX | 地区 |
| description | TEXT |  | 企业简介 |
| recruiting_job_count | INT |  | 招聘岗位数量 |
| created_at / updated_at | DATETIME | updated_at INDEX | 同步水位 |

复合索引：`idx_companies_industry_region(industry, region)`。

### jobs

岗位表，按 10 万+ 数据设计。

| 字段 | 类型 | 约束/索引 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | 岗位ID |
| source_job_id | VARCHAR(120) | INDEX | 来源站点岗位ID |
| title | VARCHAR(255) | INDEX | 岗位名称 |
| company_id | BIGINT | FK, INDEX | 企业ID |
| company_name | VARCHAR(255) | INDEX | 冗余企业名称 |
| city/province/country | VARCHAR | INDEX | 工作地点 |
| salary_min/salary_max | INT | INDEX | 薪资区间，单位元/月 |
| salary_text | VARCHAR(100) |  | 原始薪资 |
| education | VARCHAR(80) | INDEX | 学历 |
| experience | VARCHAR(80) | INDEX | 经验 |
| description | TEXT |  | 岗位描述 |
| requirement | TEXT |  | 任职要求 |
| industry | VARCHAR(100) | INDEX | 行业 |
| job_type | VARCHAR(80) | INDEX | 岗位类型 |
| source/source_url | VARCHAR | INDEX(source) | 数据来源 |
| published_at | DATETIME | INDEX | 发布时间 |
| raw_payload | JSON |  | 原始数据 |
| created_at / updated_at | DATETIME | updated_at INDEX | 同步水位 |

复合索引：`city+industry`、`salary_min+salary_max`、`published_at`、`source+source_job_id`、`company_id+published_at`。

### skills

技能表。

| 字段 | 类型 | 约束/索引 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | 技能ID |
| name | VARCHAR(120) | UNIQUE, INDEX | 技能名称 |
| category | VARCHAR(100) | INDEX | 技能类别 |
| level | VARCHAR(50) | INDEX | 技能等级 |
| heat | FLOAT | INDEX | 技能热度 |
| related_job_count | INT |  | 相关岗位数量 |
| created_at / updated_at | DATETIME | updated_at INDEX | 同步水位 |

复合索引：`category+level`、`heat`。

### job_skills

岗位技能关联表。

| 字段 | 类型 | 约束/索引 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | 关联ID |
| job_id | BIGINT | FK, INDEX | 岗位ID |
| skill_id | BIGINT | FK, INDEX | 技能ID |
| required | BOOL | INDEX | 是否必需 |
| weight | INT |  | 匹配权重 |
| level | VARCHAR(50) | INDEX | 岗位要求等级 |

唯一约束：`uk_job_skill(job_id, skill_id)`。

### users / user_skills / resumes / match_results

- `users`：用户基本信息、教育摘要、项目摘要、求职意向。
- `user_skills`：用户技能标签、熟练度，唯一约束 `user_id+skill_id`。
- `resumes`：简历原文、教育背景、项目经历、技能标签、求职意向。
- `match_results`：用户和岗位的匹配度、满足技能、缺失技能、学习路径、解释详情。

## 第三部分：Elasticsearch Index Mapping

代码见 `app/services/es_mappings.py`。

索引：

- `job_index`：岗位搜索索引。`title/company_name/description/requirement/skill_text` 使用 IK 分词；`city/industry/education/experience/skills` 使用 keyword 聚合。
- `skill_index`：技能分析索引。支持技能热度、技能类别和相关岗位数量分析。
- `company_index`：企业搜索索引。企业名称和简介使用 IK 分词，行业/地区聚合。
- `resume_index`：简历搜索索引。简历原文、教育、项目文本使用 IK 分词，技能标签 keyword。

注意：生产 ES 8 环境需要安装 IK 插件，否则将 analyzer 改为标准分词器。

## 第四部分：SQLAlchemy Model 代码

代码位置：

- `app/models/company.py`
- `app/models/job.py`
- `app/models/skill.py`
- `app/models/user.py`
- `app/models/resume.py`
- `app/models/match_result.py`

所有模型继承 `TimestampMixin`，支持 Alembic 自动迁移。

## 第五部分：Elasticsearch 工具类代码

代码位置：`app/services/es_client.py`。

能力：

- 创建/删除索引
- 单条写入
- 批量写入
- 岗位全文检索
- 按技能搜索岗位
- 城市、行业、学历、经验、薪资聚合
- 技能热度聚合
- 岗位趋势分析

## 第六部分：MySQL 到 ES 同步服务代码

代码位置：`app/services/sync_service.py`。

设计：

- 每批默认 `800` 条，可通过 `SYNC_BATCH_SIZE` 配置。
- 使用 `selectinload` 降低 N+1 查询。
- 全量同步：`sync_all(recreate_indices=True/False)`。
- 增量同步：`sync_incremental(updated_since)`。
- 批量写入失败记录日志，局部失败不中断整个服务。

## 第七部分：FastAPI 搜索与分析接口代码

代码位置：

- `app/main.py`
- `app/api/routes/search.py`
- `app/api/routes/analysis.py`

接口：

- `GET /api/search/jobs`
- `GET /api/analysis/skills`
- `GET /api/analysis/jobs/trend`

## 第八部分：项目目录结构

```text
app/
├── main.py
├── core/
│   └── config.py
├── models/
│   ├── company.py
│   ├── job.py
│   ├── skill.py
│   ├── user.py
│   ├── resume.py
│   └── match_result.py
├── schemas/
│   └── search.py
├── api/
│   ├── deps.py
│   ├── router.py
│   └── routes/
│       ├── search.py
│       └── analysis.py
├── services/
│   ├── es_mappings.py
│   ├── es_client.py
│   └── sync_service.py
├── db/
│   ├── base.py
│   └── session.py
└── utils/
    └── time.py
```

## 第九部分：后续优化建议

1. 引入 Alembic 管理 MySQL schema 迁移。
2. 引入定时任务 APScheduler/Celery 定期执行增量同步。
3. 中长期改为 binlog/Kafka 同步，降低 MySQL 扫描压力。
4. MySQL 大表可按 `published_at` 或 `source` 分区，并对历史岗位做归档。
5. ES 岗位索引可按月份 rollover，配合 ILM 管理冷热数据。
6. 搜索结果可加入向量检索字段，形成 BM25 + Embedding 混合检索。
7. 匹配结果表可增加 `algorithm_version`，便于评估不同匹配算法。
