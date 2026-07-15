# XH-202621 岗位能力图谱系统

> **正式 MVP 入口：** `frontend/app.py`。React/Vue 目录已归档为视觉原型；真实 RAG、
> 扫描件 OCR 和未来趋势预测不在当前验收范围，完整边界见
> [docs/mvp-scope.md](docs/mvp-scope.md)。

> 当前运行时数据层为 MySQL + Elasticsearch + Neo4j。CSV 用于采集、ETL 和快照同步；配置与初始化方式见 [docs/storage-runtime.md](docs/storage-runtime.md)。

这是“多源异构数据驱动岗位和能力图谱构建与动态演化分析研究”项目的主入口说明。

## 快速启动

先启动后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-backend.ps1
```

再启动前端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-frontend.ps1
```

打开 Web 端：

```text
http://localhost:8501
http://localhost:8501/architecture
http://localhost:8501/results
```

后端 API 索引：

```text
http://localhost:8080
```

健康检查：

```text
http://localhost:8080/api/health
```

停止服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-dev.ps1
```

## 一键构建数据与图谱

按架构重新生成 ETL、知识图谱、仓库导入文件、DeepSeek 抽取结果和本地简历解析结果：

```powershell
python scripts\build_full_pipeline.py
```

当前没有配置 `DEEPSEEK_API_KEY` 时，DeepSeek 抽取会自动使用 dry-run 模式，保证离线可运行。

## 核心页面

- `http://localhost:8501`：项目总览
- `http://localhost:8501/results`：统一结果
- `http://localhost:8501/architecture`：架构落地状态
- `http://localhost:8501/graph`：岗位能力图谱
- `http://localhost:8501/match`：人岗匹配
- `http://localhost:8501/evolution`：动态演化
- `http://localhost:8501/etl`：ETL 治理
- `http://localhost:8501/real_jobs`：采集岗位

## 主要产物

- `data/collected_jobs.csv`：多源采集岗位总表
- `data/etl/unified_jobs.csv`：ETL 统一 Schema 岗位表
- `data/etl/data_quality_report.csv`：数据质量评分报告
- `data/kg/nodes.csv`：知识图谱节点
- `data/kg/edges.csv`：知识图谱关系
- `data/kg/role_aliases.csv`：岗位实体消歧证据
- `data/kg/skill_trends.csv`：技能需求趋势
- `data/warehouse/mysql_schema.sql`：MySQL 表结构
- `data/warehouse/elasticsearch_jobs.ndjson`：Elasticsearch 索引数据
- `data/warehouse/chroma_documents.jsonl`：RAG/ChromaDB 文档
- `data/warehouse/neo4j_import.cypher`：Neo4j 导入脚本
- `data/ai/deepseek_extractions.jsonl`：DeepSeek 抽取结果
- `data/resumes/parsed_resumes.jsonl`：纯本地简历解析结果

## 404 排查

- `http://localhost:8080` 是后端 API 索引，不是前端页面。
- 前端页面请打开 `http://localhost:8501`。
- 后端业务接口必须使用 `/api/...`，例如 `http://localhost:8080/api/architecture-summary`。
- 如果浏览器仍显示旧 404，先停止后重启：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-dev.ps1
powershell -ExecutionPolicy Bypass -File scripts\start-backend.ps1
powershell -ExecutionPolicy Bypass -File scripts\start-frontend.ps1
```

## 更多文档

- `PROJECT_README.md`：项目总说明
- `SCRIPT_README.md`：采集、ETL、图谱和架构脚本说明
- `docs/architecture.md`：系统架构设计
- `docs/project-master-plan.md`：项目总设计
- `docs/etl-governance.md`：ETL 治理和数据质量评分
- `docs/mvp-scope.md`：正式前端、能力边界、准确率口径和增量同步设计

## 质量门禁

```powershell
pip install -r requirements-dev.txt
pytest
python scripts/evaluate_accuracy.py
```

`pytest` 对核心匹配与评测模块执行覆盖率门禁，低于 60% 将失败。
