# 多源岗位采集与 ETL 脚本

主入口：

```powershell
python scripts\crawl_jobs_100k.py
```

## 数据源分组

当前脚本按地区分组采集：

- `china`：Tencent Careers、Alibaba Careers、NetEase Careers
- `foreign`：Google Careers、Apple Jobs、Greenhouse ATS、Lever ATS、Remote OK、Arbeitnow
- `imports`：`data/imports/*.csv` 本地合法导入数据

默认运行：

```powershell
$env:CHINA_JOB_TARGET='100000'
$env:CHINA_JOB_SOURCES='china,foreign,imports'
python scripts\crawl_jobs_100k.py
```

只跑中国源：

```powershell
$env:CHINA_JOB_SOURCES='china,imports'
python scripts\crawl_jobs_100k.py
```

只跑海外源：

```powershell
$env:CHINA_JOB_SOURCES='foreign,imports'
python scripts\crawl_jobs_100k.py
```

## 重要参数

```powershell
$env:CHINA_JOB_TARGET='100000'
$env:CHINA_JOB_SOURCES='china,foreign,imports'
$env:CHINA_JOB_BALANCED='1'
$env:CHINA_JOB_PER_SOURCE_LIMIT='0'
$env:CRAWL_RESET='0'
$env:TENCENT_JOB_MAX='100000'
$env:TENCENT_JOB_WORKERS='32'
$env:ARBEITNOW_MAX_PAGES='2000'
```

开关：

```powershell
$env:ENABLE_OFFICIAL_HTML='1'
$env:ENABLE_GREENHOUSE='1'
$env:ENABLE_LEVER='1'
$env:ENABLE_REMOTEOK='1'
$env:ENABLE_ARBEITNOW='1'
$env:ENABLE_TENCENT='1'
$env:ENABLE_IMPORTS='1'
```

## 配置文件

中国/海外官网入口：

```text
data/company_targets.csv
```

格式：

```csv
region,adapter,source,company,country,url,enabled,note
china,official_html,Alibaba Careers,Alibaba,China,https://talent.alibaba.com/,1,Alibaba official careers page
foreign,official_html,Google Careers,Google,United States,https://www.google.com/about/careers/applications/jobs/results/,1,Google official careers page
```

Greenhouse / Lever 公司 token：

```text
data/source_targets.csv
```

格式：

```csv
sourceType,token,enabled,note
greenhouse,stripe,1,Greenhouse board token
lever,postman,1,Lever company token
```

本地导入数据：

```text
data/imports/*.csv
```

支持常见字段别名：`title`、`job_title`、`company`、`company_name`、`description`、`responsibility`、`requirement`、`requirements`、`skills`、`source_url`、`url`、`published_at` 等。

## 输出文件

总表：

```text
data/collected_jobs.csv
data/collected_job_skills.csv
data/collected_sources.csv
data/collection_report.json
```

分区表：

```text
data/china_jobs.csv
data/foreign_jobs.csv
```

ETL 统一 Schema：

```text
data/etl/unified_jobs.csv
data/etl/unified_job_skills.csv
data/etl/data_quality_report.csv
data/etl/etl_manifest.json
```

默认写入模式是合并：

- 每轮先读取已有 `data/collected_jobs.csv`
- 再合并本轮新抓数据
- 然后按去重规则写回总表和分区表
- 不会因为新一轮抓取量少就清空旧数据

每轮报告 `data/collection_report.json` 会写入：

- `write_mode`：`merge` 表示合并，`reset` 表示清空重跑
- `existing_records_before_run`：本轮开始前已有多少条
- `new_records_this_run`：本轮抓到并初步去重后的新数据量
- `actual_records`：合并去重后的总数据量
- `region_counts`：中国和海外分区数量

如果确实要清空重跑，显式设置：

```powershell
$env:CRAWL_RESET='1'
python scripts\crawl_jobs_100k.py
```

## 去重与质量评分

采集后会按两层规则去重：

- `source + postId`
- `title + company + city + responsibility 前 300 字`

ETL 阶段还会计算 `content_hash`，重复内容会标记：

```text
quality_flags=duplicate_content
```

质量评分包含：缺标题、缺来源 URL、缺采集时间、缺发布时间、缺城市、缺公司、职责/要求过短、未命中技能、内容重复、未知来源等。

## 循环运行

桌面脚本：

```text
C:\Users\周羿澎\Desktop\run-crawl-loop.ps1
```

运行：

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Desktop\run-crawl-loop.ps1"
```

逻辑：

- 每轮运行 `python scripts\crawl_jobs_100k.py`
- 结束后等待 5 分钟
- 再自动进入下一轮
- 日志写入 `E:\202676\logs\crawl-loop-时间.log`

## 关于 10w+

脚本不会复制重复岗位凑数。要真正达到 10w+，需要满足至少一种条件：

- 在 `data/source_targets.csv` 中追加大量 Greenhouse / Lever 公司 token
- 在 `data/company_targets.csv` 中追加更多中国/海外官网入口
- 在 `data/imports/` 中放入合法的大规模招聘 CSV

如果公开来源不足，脚本会在 `data/collection_report.json` 中记录 `gap`，不会伪造数据。

## 只重算 ETL

```powershell
python scripts\etl_unify_jobs.py
```

## 自动构建岗位-能力知识图谱

从 ETL 统一表构建图谱：

```powershell
python scripts\build_knowledge_graph.py
```

输入：

```text
data/etl/unified_jobs.csv
```

输出：

```text
data/kg/nodes.csv
data/kg/edges.csv
data/kg/role_aliases.csv
data/kg/skill_trends.csv
data/kg/graph_versions.csv
data/kg/kg_manifest.json
```

含义：

- `nodes.csv`：岗位、技能、能力维度节点
- `edges.csv`：岗位要求技能、技能归属能力维度、能力维度上下级关系
- `role_aliases.csv`：岗位名称消歧证据，例如 Java开发、Java工程师、后端开发合并到规范岗位
- `skill_trends.csv`：按月份统计某岗位-技能的需求频次
- `graph_versions.csv`：每个月的图谱版本快照统计

后端 `/api/graph` 会优先读取 `data/kg/nodes.csv` 和 `data/kg/edges.csv`。  
后端 `/api/evolution` 会优先读取 `data/kg/skill_trends.csv`。

## 一键架构流水线

按 `docs/architecture.md` 生成完整本地架构产物：

```powershell
python scripts\build_full_pipeline.py
```

该命令依次执行：

- `scripts\etl_unify_jobs.py`
- `scripts\build_knowledge_graph.py`
- `scripts\export_architecture_artifacts.py`
- `scripts\deepseek_extract.py`
- `scripts\parse_resume_local.py`

新增生产化导入产物：

```text
data/warehouse/mysql_schema.sql
data/warehouse/mysql_load.sql
data/warehouse/elasticsearch_jobs.ndjson
data/warehouse/chroma_documents.jsonl
data/warehouse/neo4j_import.cypher
data/warehouse/architecture_manifest.json
```

AI 与简历解析产物：

```text
data/ai/deepseek_extractions.jsonl
data/ai/deepseek_manifest.json
data/resumes/parsed_resumes.jsonl
data/resumes/resume_parse_manifest.json
data/pipeline_manifest.json
```

## Web 端统一结果

启动后端和前端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-backend.ps1
powershell -ExecutionPolicy Bypass -File scripts\start-frontend.ps1
```

打开：

```text
http://localhost:8501
http://localhost:8501/?page=results
http://localhost:8501/?page=architecture
http://localhost:8501/results
http://localhost:8501/architecture
```

这个页面统一展示：

- 采集岗位总量
- ETL 统一 Schema 记录数
- 技能证据数
- 图谱节点和关系数
- 岗位实体消歧证据
- 技能需求趋势
- 图谱版本快照
- 各来源质量评分
- MySQL、Elasticsearch、Neo4j、ChromaDB、DeepSeek、本地 OCR 各层产物状态

相关 API：

```text
GET /api/etl-summary
GET /api/kg-summary
GET /api/architecture-summary
GET /api/graph
GET /api/evolution
```

404 排查：

- `http://localhost:8080` 是后端 API 索引。
- 前端页面打开 `http://localhost:8501`。
- 后端业务接口必须带 `/api/...`。
- 如果端口被旧进程占用，先执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-dev.ps1
```

## DeepSeek API 配置

后续接入岗位实体抽取、关系抽取、岗位定义生成和 RAG 问答时，统一使用 DeepSeek API。

建议环境变量：

```powershell
$env:DEEPSEEK_API_KEY='你的 DeepSeek Key'
$env:DEEPSEEK_BASE_URL='https://api.deepseek.com'
$env:DEEPSEEK_MODEL='deepseek-chat'
```

当前采集、ETL、图谱 CSV 构建和架构产物导出脚本仍可离线运行，不依赖 DeepSeek Key。没有 Key 时 `scripts\deepseek_extract.py` 会写入 dry-run 抽取结果。

## 纯本地简历解析

解析样本简历：

```powershell
python scripts\parse_resume_local.py
```

解析指定文件：

```powershell
python scripts\parse_resume_local.py path\to\resume.docx
python scripts\parse_resume_local.py path\to\resume.pdf
python scripts\parse_resume_local.py path\to\resume.png
```

说明：

- `.docx` 使用本地 XML 解析。
- 文本型 `.pdf` 优先使用本地 `pypdf` 或 `pdftotext`。
- 图片和扫描件优先使用本地 PaddleOCR，其次使用本地 Tesseract。
- 简历内容不会发送到任何远程 API。
