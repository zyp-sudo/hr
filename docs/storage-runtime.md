# MySQL、Elasticsearch 与 Neo4j 运行时接入

系统的公开 API 运行在 `http://localhost:8080`。核心数据不再由 API 读取 CSV：

- `GET /api/jobs`、`GET /api/real-jobs` 查询 MySQL `job_kg.job_postings`。
- `GET /api/graph` 执行 Neo4j Cypher，查询 `KgNode` 与 `KG_RELATION`。
- `GET /api/health` 分别报告 MySQL、Elasticsearch、Neo4j 的真实连接状态。
- `GET /api/search/jobs` 与 `/api/analysis/*` 查询 Elasticsearch `job_index`。
- 其余历史分析接口由公开 API 转发到 `8081` 的内部 Java 服务。

CSV 只保留为采集、ETL 和首次入库的交换文件，不是线上查询数据源。数据库不可用时，核心接口返回 HTTP 503，不会静默回退到 CSV。

## 初始化

```powershell
pip install -r requirements-storage.txt
powershell -ExecutionPolicy Bypass -File scripts/init-storage.ps1
```

该脚本启动 Docker 中的 MySQL 8.4、Elasticsearch 8.13.4、Neo4j 5.26，执行
`scripts/bootstrap_storage.py --sync`，再以水位方式同步 Elasticsearch。未变化的快照会跳过。
完全重建使用：

```powershell
python scripts/bootstrap_storage.py --reset
python scripts/sync_mysql_to_es.py --recreate-indices
```

启动完整系统：

```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```

## 环境变量

```text
MYSQL_URL=mysql+pymysql://root:password@localhost:3307/job_kg?charset=utf8mb4
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123
NEO4J_DATABASE=neo4j
GRAPH_NODE_LIMIT=160
JAVA_BACKEND_URL=http://localhost:8081
ES_HOST=http://localhost:9200
```

生产环境应覆盖默认密码。若使用已有数据库，可设置这些变量并以 `SKIP_STORAGE_INIT=true` 跳过本地 Docker 初始化。
