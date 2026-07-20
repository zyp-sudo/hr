# 系统架构设计

> 本文档是架构细化说明。项目方向、建设原则、功能总览和里程碑以 `docs/project-master-plan.md` 为准。
> 当前可验收能力和明确降级项以 `docs/mvp-scope.md` 为准；下表中标为目标的技术不代表已经落地。

## 技术约束与目标技术栈

当前版本优先保证本地可运行、接口清晰、业务闭环完整。正式前端为 `talentmatch-frontend/`
（React 19 + TypeScript + Vite + Express 网关，端口 `3000`）；
运行时采用 FastAPI 公开 API、Java 分析服务、MySQL、Elasticsearch 和 Neo4j。CSV/JSON
是采集与快照同步介质。其余技术是后续路线：

| 模块 | 目标技术 | 作用 |
| --- | --- | --- |
| 数据采集 | Scrapy + Playwright | Scrapy 处理静态页面，Playwright 处理 JS 动态渲染页面，配合代理池、限速、重试和反爬策略 |
| 数据存储 | MySQL + Elasticsearch | MySQL 存储结构化岗位、技能、来源、质量评分；Elasticsearch 支持 JD 全文检索和聚合分析 |
| NLP 处理 | HanLP / LAC + DeepSeek API | HanLP/LAC 做中文分词、词性和 NER 基础处理；DeepSeek 做复杂语义理解、实体消歧和关系抽取 |
| 知识图谱 | Neo4j + py2neo | Neo4j 存储岗位、技能、能力维度和时序关系；py2neo 提供 Python 写入和查询接口 |
| 图谱可视化 | AntV G6 / ECharts Graph | G6 支持力导向布局、节点聚类和交互探索；ECharts Graph 用于轻量展示 |
| RAG 框架 | LangChain + ChromaDB + DeepSeek API | LangChain 编排 DeepSeek 调用链，ChromaDB 做向量存储，实现检索增强生成 |
| 后端框架 | FastAPI / Flask | FastAPI 提供高性能 API 和 OpenAPI 文档；Flask 可作为轻量替代 |
| 前端 | React 19 + TypeScript + Vite | 当前唯一正式交付前端（`talentmatch-frontend/`）；旧 Python Web（`_archived-frontends/frontend/app.py`）、`_archived-frontends/frontend-react/` 和 `_archived-frontends/frontend-vue/` 已归档 |
| 数据分析 | Pandas + NetworkX | Pandas 做清洗统计，NetworkX 做中心性、社区发现、路径分析等图算法 |
| 简历解析 | PaddleOCR / Tesseract + PDF/Word 本地解析 + 自定义 NER | 本地 OCR 处理图片和扫描版 PDF，PDF/Word 本地解析处理文本型简历，自定义 NER 抽取结构化字段 |

阶段定位：

- 当前原型：React + TypeScript 前端（`talentmatch-frontend/`）+ FastAPI + Java HTTP Server，已完成多源采集、ETL、质量评分、自动知识图谱和历史时序趋势。
- 运行时：ETL/KG 快照增量同步到 MySQL、Elasticsearch、Neo4j；公开 API 查询三类数据库。

## 分层架构

```text
┌─────────────────────────────────────────────────────┐
│  talentmatch-frontend (React + TypeScript + Express, :3000)  │
│  仪表盘 · 图谱可视化 · 匹配诊断 · 演化趋势          │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP JSON
          ┌───────────┴───────────┐
          v                       v
┌─────────────────┐     ┌─────────────────────┐
│  FastAPI (:8080) │     │  Java 分析 (:8081)   │
│  公开数据/API    │     │  内部分析服务        │
│  · 岗位查询      │     │  · 图谱构建          │
│  · 匹配评估      │     │  · 演化分析          │
│  · 数据质量      │     │  · ETL/KG 汇总       │
│  · 搜索聚合      │     │  · 数据采样          │
└────────┬────────┘     └──────────┬──────────┘
         │                         │
         └───────────┬─────────────┘
                     v
┌─────────────────────────────────────────────────────┐
│  数据层                                             │
│  · MySQL (:3307)         结构化业务数据              │
│  · Elasticsearch (:9200)  全文检索与聚合             │
│  · Neo4j (:7474/:7687)   岗位能力图谱                │
│  · Milvus (:19530)        人才向量检索               │
└─────────────────────────────────────────────────────┘
```

## 生产版数据流

```text
Scrapy / Playwright
  -> 原始页面与接口缓存
  -> Pandas 清洗与 ETL
  -> HanLP / LAC / DeepSeek API 抽取实体和关系
  -> MySQL 结构化入库
  -> Elasticsearch 全文索引
  -> Neo4j 图谱写入
  -> ChromaDB 向量索引
  -> FastAPI 查询服务
  -> React + TypeScript / AntV G6 / ECharts 展示
```

## 当前已落地产物

当前代码仍保持轻量原型可运行，同时已经为目标架构生成可迁移产物：

- `scripts/build_full_pipeline.py`：一键执行 ETL、图谱构建、仓库导出、DeepSeek 抽取和本地简历解析。
- `scripts/export_architecture_artifacts.py`：生成 MySQL DDL/LOAD SQL、Elasticsearch NDJSON、ChromaDB JSONL、Neo4j Cypher。
- `scripts/deepseek_extract.py`：使用 DeepSeek API 抽取岗位实体、技能、能力维度和关系；没有 Key 时生成 dry-run 结果。
- `scripts/parse_resume_local.py`：纯本地解析 `.docx`、文本型 `.pdf`、图片简历和样本文本，不上传简历内容。
- `GET /api/architecture-summary`：汇总各架构层的状态、记录数和产物路径。
- `/?page=architecture`：Web 端展示架构落地状态。

## 核心领域对象

- JobRole：岗位。
- Skill：技能点。
- Capability：能力维度。
- GraphNode：图谱节点。
- GraphEdge：图谱边。
- EvolutionPoint：技能需求时间点。
- MatchResult：人岗匹配结果。
- DataSource：原始数据来源。

## API 第一版

- `GET /api/health`：健康检查。
- `GET /api/jobs`：岗位列表。
- `GET /api/graph`：岗位能力图谱。
- `GET /api/evolution?jobId=...`：岗位能力动态演化。
- `GET /api/data-quality`：数据源质量评估。
- `GET /api/etl-summary`：ETL 统一 Schema、质量报告和样例。
- `GET /api/kg-summary`：自动知识图谱、消歧、趋势和版本统计。
- `GET /api/architecture-summary`：架构落地模块、导入产物和流水线状态。
- `POST /api/match`：根据简历文本和目标岗位输出匹配诊断。
- `POST /api/discover`：返回新兴岗位发现样例。
- `GET /api/samples`：返回当前 CSV 数据样本，便于验证数据来源。

## 当前数据层

CSV 作为采集与 ETL 的可审计交换层；运行时岗位查询使用 MySQL，图谱查询使用 Neo4j。数据库不可用时核心接口返回 503，不做隐式 CSV 回退。

- 岗位和技能来自 `jobs.csv`、`job_skills.csv`。
- 技能同义词来自 `skill_aliases.csv`，用于匹配时标准化。
- 动态演化来自 `evolution.csv`。
- 数据质量来自 `data_sources.csv`。
- 简历样本来自 `resume_samples.csv`。
- 新岗位发现样本来自 `discoveries.csv`。

## 后续替换路线

1. 数据采集升级：
   - 将当前 `urllib` 适配器拆分为 Scrapy spiders。
   - 对 JS 动态招聘页接入 Playwright。
   - 增加代理池、限速、失败重试、robots/站点策略记录和 checkpoint。

2. 数据层落地：
   - MySQL 存储结构化实体。
   - Neo4j 存储图谱关系和时间属性。
   - Elasticsearch 存储 JD 原文和报告。
   - ChromaDB 存储岗位、技能和简历向量。

3. NLP 与图谱升级：
   - HanLP/LAC 完成中文分词、NER 和基础实体候选。
   - DeepSeek API 完成复杂关系抽取、岗位实体消歧和能力层级推理。
   - Neo4j + py2neo 承接 `data/kg/*.csv` 里的节点、边、版本和趋势。
   - NetworkX 进行中心性、社区发现、相似岗位聚类和路径推理。

4. 服务与前端升级：
   - 后端迁移到 FastAPI 或 Flask，保留当前 API 语义。
   - 前端已迁移到 React + TypeScript（`talentmatch-frontend/`）。
   - 图谱页面改用 AntV G6 或 ECharts Graph。

5. RAG 与简历解析：
   - PaddleOCR/Tesseract 本地处理图片和扫描版 PDF 简历。
   - PDF/Word 本地解析优先抽取文本型简历内容。
   - 自定义 NER 抽取技能、项目、年限、教育、证书。
   - LangChain + ChromaDB + DeepSeek API 支持岗位解释、学习路径和问答。
   - 生成结论必须带 `sourceIds`，无来源进入人工审核。
