# 正式 MVP 范围与能力边界

## 唯一正式前端

正式入口是 `frontend/app.py`，默认地址为 `http://localhost:8501`。根目录的
`start.ps1`、`start.sh` 和 `scripts/start-frontend.ps1` 只启动这一实现。

`frontend-react/` 与 `frontend-vue/` 是早期视觉原型，保留用于设计参考，不参与构建、
测试、部署或验收。二者的数据 Mock 不能作为正式功能证据。

## 当前真实能力

| 能力 | MVP 状态 | 运行时证据 |
| --- | --- | --- |
| MySQL 岗位查询 | 已实现 | `/api/jobs`、`/api/real-jobs` |
| Elasticsearch 检索和聚合 | 已实现 | `/api/search/jobs`、`/api/analysis/skills`、`/api/analysis/jobs/trend` |
| Neo4j 图谱 | 已实现 | `/api/graph`、`/api/kg-summary` |
| 历史动态演化 | 已实现 | `skill_trends`、`graph_versions`、`/api/evolution` |
| 规则型人岗匹配 | 已实现 | `/api/match`、MVP 准确率回归基准 |

## 明确降级、不得标记为已完成的能力

- **RAG**：当前只有 `chroma_documents.jsonl` 待向量化数据，没有运行时 ChromaDB、
  embedding、LangChain 检索链和带引用回答，因此状态是 `partial`。
- **OCR**：文本型 PDF/DOCX 可本地解析；扫描件和图片只有在操作者自行安装
  PaddleOCR 或 Tesseract 后才能处理，因此状态是 `partial`。
- **趋势预测**：当前展示真实历史月份聚合，没有训练或验证未来 3–6 个月预测模型，
  因此状态是 `partial`。
- **大模型抽取**：没有 API Key 时是确定性 `dry_run/rule_based`，不能宣称为真实
  DeepSeek 推理。

## 准确率口径

`python scripts/evaluate_accuracy.py` 执行 165 个确定性回归案例，报告写入
`data/benchmarks/accuracy_report.json`。该基准用于防止规则回归，不等同于独立标注的
生产准确率。正式 90% 结论仍需盲测集、人工双标和按岗位类别分层统计。

## 增量同步设计

1. `bootstrap_storage.py --sync` 对每个 ETL/KG 文件计算 SHA-256。
2. 未变化的表和图文件跳过；变化的 MySQL 快照表先替换再批量 upsert，变化的 Neo4j
   图快照重建，避免遗留已删除节点和边。
3. `sync_mysql_to_es.py --auto` 首次全量创建索引，后续从
   `data/sync/elasticsearch_state.json` 的 `max_collected_at` 水位增量索引。
4. 运行时状态文件位于 `data/sync/`，不进入 Git。
5. 聚合图谱是全局计算结果；当 ETL 快照变化时重新计算图谱属于有意设计，不能仅追加。
