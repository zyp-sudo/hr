# XH-202621 岗位能力图谱项目 README

> 正式交付前端统一为 `frontend/app.py`。`frontend-react/` 和 `frontend-vue/` 已归档为
> 视觉原型。RAG、扫描件 OCR 和未来趋势预测当前明确为 MVP 后续能力，见
> `docs/mvp-scope.md`，不得按已完成能力计入验收。

## 项目定位

本项目面向“多源异构数据驱动岗位和能力图谱构建与动态演化分析研究”赛题，目标是构建一个可运行、可演示、可继续扩展的数据驱动系统。

当前运行技术栈：

- 前端：Python
- 后端：FastAPI 公开 API + Java 分析服务
- 业务数据层：MySQL 8.x
- 检索与聚合：Elasticsearch 8.13.x
- 知识图谱：Neo4j 5.x
- CSV / JSON：采集、ETL 与数据库导入交换文件
- 数据来源：中国真实岗位公开数据

目标生产技术栈：

- 数据采集：Scrapy + Playwright
- 数据存储：MySQL + Elasticsearch（当前运行时）
- NLP 处理：HanLP / LAC + DeepSeek API
- 知识图谱：Neo4j + py2neo
- 图谱可视化：AntV G6 / ECharts Graph
- RAG：LangChain + ChromaDB + DeepSeek API
- 后端框架：FastAPI / Flask
- 正式前端：Python Web（React/Vue 原型已归档）
- 数据分析：Pandas + NetworkX
- 简历解析：PaddleOCR / Tesseract + PDF/Word 本地解析 + 自定义 NER

## 核心能力

- 多源岗位数据采集
- 边爬取边整理的 10w+ 目标采集管道
- ETL 统一 Schema
- 每条数据保留来源和时间戳
- 数据质量评分
- 岗位-技能-能力图谱
- 岗位能力动态演化分析
- 人岗匹配诊断
- 前端可视化演示

## 项目结构

```text
backend/                  Java 后端 HTTP API
frontend/                 Python 前端页面
scripts/                  数据采集、ETL、启动脚本
data/                     CSV、JSON、ETL、图谱、仓库导入和 AI 产物
docs/                     设计文档、架构文档、ETL 治理说明
README.md                 项目快速启动 README
PROJECT_README.md         项目总 README
SCRIPT_README.md          采集、ETL、图谱和架构脚本 README
```

## 启动项目

一键启动（编译后端 + 启动后端 + 启动前端）：

**Git Bash / Linux / Mac：**

```bash
bash start.sh
```

**Windows PowerShell：**

```powershell
powershell -File start.ps1
```

脚本会自动停止旧进程、编译 Java 后端、启动后端(8080)、等待后端就绪、再启动前端(8501)。按 `Ctrl+C` 一键停止所有服务。

默认地址：

```text
前端: http://localhost:8501
后端: http://localhost:8080
```

架构落地页可直接打开：

```text
http://localhost:8501/?page=architecture
http://localhost:8501/?page=results
```

如需单独停止服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-dev.ps1
```

## 主要页面

- `/?page=dashboard`：项目总览
- `/?page=results`：统一结果
- `/?page=architecture`：架构落地状态
- `/?page=graph`：岗位能力图谱
- `/?page=match`：人岗匹配
- `/?page=evolution`：动态演化
- `/?page=quality`：数据质量
- `/?page=etl`：ETL 治理与统一 Schema
- `/?page=samples`：样本数据
- `/?page=real_jobs`：真实岗位数据

## 主要 API

- `GET /api/health`
- `GET /api/jobs`
- `GET /api/graph`
- `GET /api/evolution?jobId=...`
- `GET /api/data-quality`
- `GET /api/etl-summary`
- `GET /api/kg-summary`
- `GET /api/architecture-summary`
- `GET /api/samples`
- `GET /api/real-jobs`
- `POST /api/match`
- `POST /api/discover`

## 数据说明

核心数据目录：

- `data/collected_jobs.csv`：真实采集岗位总表，包含中国和海外来源
- `data/collected_job_skills.csv`：真实采集岗位技能抽取结果
- `data/collected_sources.csv`：真实采集来源统计
- `data/china_jobs.csv`：中国岗位分表
- `data/foreign_jobs.csv`：海外岗位分表
- `data/source_registry.csv`：数据源注册表
- `data/etl/unified_jobs.csv`：统一 Schema 后的岗位数据
- `data/etl/unified_job_skills.csv`：统一后的岗位技能证据
- `data/etl/data_quality_report.csv`：数据质量报告
- `data/kg/nodes.csv`：自动构建的岗位、技能、能力维度节点
- `data/kg/edges.csv`：岗位-技能-能力维度关系边
- `data/kg/role_aliases.csv`：岗位实体消歧证据
- `data/kg/skill_trends.csv`：技能需求时序趋势
- `data/kg/graph_versions.csv`：时序图谱版本快照
- `data/warehouse/mysql_schema.sql`：MySQL 表结构
- `data/warehouse/mysql_load.sql`：MySQL CSV 导入脚本
- `data/warehouse/elasticsearch_jobs.ndjson`：Elasticsearch 批量索引数据
- `data/warehouse/chroma_documents.jsonl`：ChromaDB / RAG 文档
- `data/warehouse/neo4j_import.cypher`：Neo4j 图谱导入脚本
- `data/ai/deepseek_extractions.jsonl`：DeepSeek 岗位实体和关系抽取结果
- `data/resumes/parsed_resumes.jsonl`：纯本地简历解析结果

## 一键架构流水线

按当前架构重新生成 ETL、知识图谱、生产化导入产物、DeepSeek 抽取产物和本地简历解析产物：

```powershell
python scripts\build_full_pipeline.py
```

没有配置 `DEEPSEEK_API_KEY` 时，DeepSeek 抽取脚本会生成 dry-run 结果，保证项目离线可运行。

## 10w+ 边爬边整理脚本

脚本说明单独放在：

```text
SCRIPT_README.md
```

该 README 包含 10w+ 采集、ETL、图谱构建、架构产物导出、DeepSeek 抽取和纯本地简历解析说明。

## 404 排查

- `http://localhost:8080` 是后端 API 索引，不是前端页面。
- 前端页面打开 `http://localhost:8501`、`http://localhost:8501/architecture` 或 `http://localhost:8501/results`。
- 后端接口使用 `/api/...`，例如 `http://localhost:8080/api/health`。
- 如仍看到旧 404，先运行 `scripts\stop-dev.ps1` 再重新启动前后端。

## 设计文档

- `docs/project-master-plan.md`：项目方向、原理和功能总览
- `docs/architecture.md`：系统架构设计
- `docs/etl-governance.md`：ETL 治理和数据质量评分设计
- `docs/requirements-summary.md`：需求摘要

## 当前状态

项目已具备基础闭环：

```text
真实岗位数据 -> ETL 统一 Schema -> 质量评分 -> 图谱 / 演化 / 匹配 / 前端展示
```

后续重点是继续接入更多真实数据源，提高数据规模、来源覆盖和岗位类别覆盖。
