# 正式 MVP 范围与能力边界

## 唯一正式前端

正式入口是 `talentmatch-frontend/`（React 19 + TypeScript + Vite + Express 网关），默认地址为
`http://localhost:3000`。完整启动说明见仓库根目录 [`README.md`](../README.md)。

`_archived-frontends/frontend/app.py`（Python Web）、`_archived-frontends/frontend-react/` 与 `_archived-frontends/frontend-vue/` 是历史/归档实现，
保留用于设计参考，不参与构建、测试、部署或验收。三者的数据 Mock 不能作为正式功能证据。

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
生产准确率。另有 24 条固定人工复核 holdout：技能 F1 为 0.8125、岗位分类准确率为
0.6667；4 个固定检索 query pool 的 MRR@10 为 1.0000、nDCG@10 为 0.9315。
两套人工基准目前都只有一名标注者，正式生产结论仍需扩大样本、双人独立标注和分层统计。

当前 55,110 条岗位中，保守规则可从原文明确提取学历 33,849 条（61.42%）和人民币
月/年薪区间 11,246 条（20.41%）。面议、外币、日时薪和没有周期的裸区间保持空值；
覆盖率不等同于字段抽取准确率。

## 增量同步设计

1. `bootstrap_storage.py --sync` 先用 SHA-256 判断哪些快照文件发生变化。
2. 变化的 MySQL 表载入临时快照表，按主键和 null-safe 行差异只 upsert 新增/变更行，
   并删除源快照中已不存在的主键；单表对账在一个事务中完成，不再整表 `DELETE`。
3. `sync_mysql_to_es.py --auto` 扫描 MySQL 主键/规范行哈希与 ES `sync_hash`，只索引新增或
   变更文档并传播删除；旧 `collected_at` 记录的更新也可检测。
4. 两类同步均使用互斥锁，状态 JSON 通过原子替换发布；连续第二轮应为零变更。
5. 运行时状态文件位于 `data/sync/`，不进入 Git。
6. Neo4j 是全局聚合快照；KG 输入变化时全量重算属于明确边界，不能仅追加。
