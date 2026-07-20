# 任务 126 — Git 变更盘点与原子提交拆分方案

**日期**: 2026-07-18
**分支**: `main`
**状态**: 仅审计，未修改、未暂存、未提交任何文件

---

## 一、统计概览

| 指标 | 数值 |
|------|------|
| 当前分支 | `main` |
| 已跟踪修改文件 | 19 |
| 未跟踪新增文件 | 44（不含目录内文件则为 ~41+） |
| 变更总行数 | +2672, -104 |
| 空白符问题 | 仅 Windows CRLF 提示，无实质性空白符错误 |
| 禁止提交文件 | 6（含 3 个遗留 pytest 临时目录） |
| 待人工确认文件 | 2 |

---

## 二、A-G 分类清单

### A. 正式业务代码

#### A1. 后端 API — Competition 与公司智能体

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/api/router.py` | M | 注册 competiton_core / competition_rag / company_agent 路由 |
| `app/core/config.py` | M | 新增 COMPANY_AGENT_* 5 个环境变量配置 |
| `app/api/routes/competition_core.py` | ?? | 岗位发现、角色版本、能力 Diff API |
| `app/api/routes/competition_rag.py` | ?? | RAG 证据生成、审计、健康检查 API |
| `app/api/routes/company_agent.py` | ?? | 公司智能体评分 API + health |
| `app/schemas/competition.py` | ?? | DiscoveryItem / PanoramaNode / ReviewRecord 等 Pydantic 模型 |
| `app/schemas/competition_rag.py` | ?? | EvidenceGenerateRequest / AuditRecord 等 |
| `app/schemas/company_agent.py` | ?? | CompanyAgentResult / HealthResponse 等 |
| `app/services/competition_core.py` | ?? | 岗位发现、版本演化、能力 Diff 核心逻辑 |
| `app/services/competition_rag.py` | ?? | 确定性离线 RAG 证据匹配、审计引擎 |
| `app/services/company_agent.py` | ?? | 多 Provider 公司智能体适配器（HTTP / disabled） |

#### A2. Java 分析服务

| 文件 | 状态 | 说明 |
|------|------|------|
| `backend/src/com/xh202621/App.java` | M | 前端 URL 从 `:8501` 更新为 `:3000` |
| `backend/src/com/xh202621/KnowledgeService.java` | M | 技术栈描述更新为 talentmatch-frontend/ React |

#### A3. TalentMatch 前端

| 文件 | 状态 | 说明 |
|------|------|------|
| `talentmatch-frontend/server.ts` | M | Express 代理路径净化：移除 `/api/platform/storage` 前缀 |
| `talentmatch-frontend/src/App.tsx` | M | 一级导航重构、人岗匹配画布、公司智能体集成、FAB 简历上传 |
| `talentmatch-frontend/src/PlatformPages.tsx` | M | 岗位管理页 Hub 布局、CapabilityPage、各子页面路由 |
| `talentmatch-frontend/src/index.css` | M | +2317 行：Competition 组件、RCG 图谱、证据页、公司智能体、响应式 |
| `talentmatch-frontend/src/types.ts` | M | +155 行：Competition / CompanyAgent TypeScript 类型定义 |
| `talentmatch-frontend/src/components/CompanyAgentPanel.tsx` | ?? | 公司智能体评分面板 |
| `talentmatch-frontend/src/components/CompetitionDiscovery.tsx` | ?? | 岗位发现卡片列表 + 详情 + 审核 |
| `talentmatch-frontend/src/components/CompetitionErrorBoundary.tsx` | ?? | Competition 错误边界 + 返回首页 |
| `talentmatch-frontend/src/components/CompetitionEvidence.tsx` | ?? | RAG 证据生成、声明验证、审计 |
| `talentmatch-frontend/src/components/CompetitionRoleEvolution.tsx` | ?? | 角色能力版本演化 + Diff 对比 |
| `talentmatch-frontend/src/components/RoleCapabilityGraph.tsx` | ?? | 岗位能力图谱（SVG 力导向布局 + 筛选 + 键盘可访问） |
| `talentmatch-frontend/src/utils/companyAgent.ts` | ?? | 公司智能体前端状态机 + API 封装 |
| `talentmatch-frontend/src/utils/competitionValidators.ts` | ?? | Panorama 响应校验 + 类型 guard |

### B. 自动化测试

| 文件 | 状态 | 行数 | 覆盖目标 |
|------|------|------|----------|
| `tests/test_competition_core.py` | ?? | 587 | competition_core 发现/版本/Diff 逻辑 |
| `tests/test_competition_rag.py` | ?? | 574 | RAG 证据匹配、审计、Milvus 集成 |
| `tests/test_competition_integration.py` | ?? | 493 | Competition 端到端集成 |
| `tests/test_competition_metrics.py` | ?? | 699 | 评估指标计算与口径验证 |
| `tests/test_company_agent.py` | ?? | 625 | 公司智能体 Provider、状态机、降级 |
| `tests/test_auth_routes.py` | ?? | 219 | 认证路由（JWT 签发/验证/黑名单） |
| `tests/test_search_routes.py` | ?? | 218 | 搜索路由 |
| `tests/test_security.py` | ?? | 220 | 安全头、CORS、依赖注入 |
| `tests/test_vectors_routes.py` | ?? | 232 | 向量路由 |
| `tests/test_milvus_talent.py` | ?? | 197 | Milvus 向量存储 |
| `tests/test_migrations.py` | ?? | 150 | 数据库迁移 |

> 所有测试均对应正式实现：`test_competition_*` → `app/services/competition_*`；
> `test_company_agent.py` → `app/services/company_agent.py`；
> 其余测试对应 `app/api/routes/` 下同名路由模块。

### C. 部署与验证

| 文件 | 状态 | 说明 |
|------|------|------|
| `deploy/docker-compose.competition.yml` | ?? | Competition 部署 Compose（含 Java/Python/Web） |
| `deploy/Dockerfile.python` | ?? | FastAPI 容器构建 |
| `deploy/Dockerfile.java` | ?? | Java 分析服务容器构建 |
| `deploy/Dockerfile.web` | ?? | 前端 Web 容器构建 |
| `deploy/.env.example` | ?? | 环境变量示例 ⚠ 含明文密码（见敏感信息检查） |
| `deploy/README.md` | ?? | 部署说明 |
| `scripts/verify-competition-deployment.ps1` | ?? | Windows 部署验证脚本 |
| `scripts/verify-competition-deployment.sh` | ?? | Linux/Mac 部署验证脚本 |
| `scripts/build_competition_annotation_set.py` | ?? | 标注集构建工具 |
| `scripts/evaluate_competition_metrics.py` | ?? | 评估指标计算工具 |

### D. 文档

| 文件 | 状态 | 说明 |
|------|------|------|
| `PROJECT_README.md` | M | 前端入口统一为 talentmatch-frontend/ |
| `SCRIPT_README.md` | M | 脚本说明更新 |
| `docs/architecture.md` | M | 架构更新为 React + TypeScript 前端 |
| `docs/legacy-readme.md` | M | 历史说明 |
| `docs/match-ai-api.md` | M | AI 匹配接口文档 |
| `docs/mvp-scope.md` | M | MVP 范围说明 |
| `docs/project-master-plan.md` | M | 项目总计划 |
| `docs/requirements-summary.md` | M | 需求摘要 |
| `docs/competition-evaluation-guide.md` | ?? | Competition 评估指南 |
| `docs/competition-ui-acceptance.md` | ?? | UI 验收记录 |
| `docs/delivery-verification.md` | ?? | 交付验证记录 |
| `docs/frontend-final-acceptance-2026-07-18.md` | ?? | 最终前端验收报告（任务 123-125） |
| `docs/project-completion-audit.md` | ?? | 项目完成审计 |
| `_archived-frontends/frontend-react/ARCHIVED.md` | M | 归档标记 |
| `_archived-frontends/frontend-vue/ARCHIVED.md` | M | 归档标记 |
| `competition-delivery/` * (11 文件) | ?? | 竞赛交付物：设计方案、架构、测试方案、演示脚本等 |

### E. 正式数据资产

| 文件 | 状态 | 大小 | 说明 |
|------|------|------|------|
| `data/competition/discoveries.json` | ?? | 8KB | 岗位发现种子数据 |
| `data/competition/evidence_sources.json` | ?? | 12KB | 证据源定义（258 行结构化 JSON） |
| `data/competition/panorama.json` | ?? | 8KB | 岗位能力图谱数据 |
| `data/competition/rag_audit.jsonl` | ?? | 4KB | 审计日志示例 |
| `data/competition/reviews.json` | ?? | 8KB | 审核记录示例 |
| `data/competition/roles.json` | ?? | 8KB | 角色数据 |
| `data/benchmarks/competition/annotation_manifest.json` | ?? | 4KB | 标注清单 |
| `data/benchmarks/competition/competition_evaluation_report.json` | ?? | 4KB | 评估报告 |
| `data/benchmarks/competition/jd_parsing_annotation_template.csv` | ?? | 376KB | JD 解析标注模板 |
| `data/benchmarks/competition/person_job_matching_annotation_template.csv` | ?? | 100KB | 人岗匹配标注模板 |
| `data/benchmarks/competition/resume_extraction_annotation_template.csv` | ?? | 4KB | 简历抽取标注模板 |
| `data/benchmarks/competition/README.md` | ?? | - | 标注数据说明 |

### F. 禁止提交

| 文件 | 原因 |
|------|------|
| `pytest-temp-529415458258443fb105b6f9f467f100/` | 遗留 pytest 临时目录，无权限删除 |
| `pytest-temp-727a7c02468843eda9c588e767e75e08/` | 同上 |
| `pytest-temp-d7d0f45667b145b0b348acfab900fd7a/` | 同上 |
| `data/competition/discoveries.json.bak` | JSON 备份文件，非正式数据 |
| `deploy/.env.example` (含明文密码项) | 含 `MYSQL_ROOT_PASSWORD=password`、`NEO4J_PASSWORD=password123`、`MINIO_SECRET_KEY=minioadmin`（见下方敏感信息检查） |
| `node_modules/` / `dist/` / `.pytest_cache/` | 构建产物与缓存（已在 .gitignore） |

### G. 待人工确认

| 文件 | 原因 |
|------|------|
| `competition-delivery/08-部署与运行说明.md` | 含 `password` / `token` 关键词（为文档说明用途，非泄露——但建议复核） |
| `data/benchmarks/competition/jd_parsing_annotation_template.csv` (376KB) | 最大数据文件，需确认是否为正式标注模板还是临时导出 |

---

## 三、依赖完整性检查

### 3.1 路由注册

```
app/api/router.py
  ├── include_router(competition_core.router)  ✅ 对应 app/api/routes/competition_core.py
  ├── include_router(competition_rag.router)    ✅ 对应 app/api/routes/competition_rag.py
  └── include_router(company_agent.router)      ✅ 对应 app/api/routes/company_agent.py
```

### 3.2 Service/Route 引用链

| 路由模块 | 引用 schema | 引用 service |
|----------|------------|-------------|
| `company_agent.py` | ✅ `app.schemas.company_agent` | ✅ `app.services.company_agent` |
| `competition_core.py` | ✅ `app.schemas.competition` | ✅ `app.services.competition_core` |
| `competition_rag.py` | ✅ `app.schemas.competition_rag` | ✅ `app.services.competition_rag` |

无孤立路由、无缺失 import。

### 3.3 前端组件引用

| 组件 | 被引用位置 |
|------|-----------|
| `CompanyAgentPanel` | `App.tsx:8` ✅ |
| `CompetitionDiscovery` | `PlatformPages.tsx:4` ✅ |
| `CompetitionRoleEvolution` | `PlatformPages.tsx:5` ✅ |
| `RoleCapabilityGraph` | `PlatformPages.tsx:6` ✅ |
| `CompetitionEvidence` | `PlatformPages.tsx:7` ✅ |
| `CompetitionErrorBoundary` | `PlatformPages.tsx:8` ✅ |

Utils 引用：
- `competitionValidators.ts` → 被 4 个组件引用 ✅
- `companyAgent.ts` → 被 `CompanyAgentPanel.tsx` 引用 ✅

**无孤立组件。**

### 3.4 旧组件引用检查

- `CompetitionPanorama` — 源代码中 **零引用**（已确认删除的 CSS 即其残留）
- `CompetitionOverview` — 源代码中 **零引用**
- 上述两个 .tsx 文件在 `talentmatch-frontend/src/components/` 下已不存在 ✅

### 3.5 测试-实现对应

| 测试文件 | 对应实现 |
|----------|----------|
| `test_competition_core.py` | `app/services/competition_core.py` / `app/api/routes/competition_core.py` |
| `test_competition_rag.py` | `app/services/competition_rag.py` / `app/api/routes/competition_rag.py` |
| `test_competition_integration.py` | Competition 全栈集成 |
| `test_competition_metrics.py` | `scripts/evaluate_competition_metrics.py` |
| `test_company_agent.py` | `app/services/company_agent.py` / `app/api/routes/company_agent.py` |
| `test_auth_routes.py` | `app/api/routes/auth.py` |
| `test_search_routes.py` | `app/api/routes/search.py` |
| `test_security.py` | `app/core/security.py` / `app/core/middleware.py` |
| `test_vectors_routes.py` | `app/api/routes/vectors.py` |
| `test_milvus_talent.py` | `app/services/milvus_talent.py` |
| `test_migrations.py` | `app/db/migrations.py` |

全部对应，无孤儿测试。

---

## 四、敏感信息检查

### 4.1 命中文档类（说明性质，非泄露）

| 文件 | 行号 | 字段 |
|------|------|------|
| `deploy/.env.example` | 10 | `MYSQL_ROOT_PASSWORD=password` |
| `deploy/.env.example` | 16 | `NEO4J_PASSWORD=password123` |
| `deploy/.env.example` | 32 | `MINIO_SECRET_KEY=minioadmin` |
| `deploy/.env.example` | 33 | `MILVUS_TOKEN=` (空值) |
| `deploy/docker-compose.competition.yml` | — | 继承 docker-compose.yml 环境变量 |
| `competition-delivery/08-部署与运行说明.md` | — | 文档中提及部署参数（说明性质） |

### 4.2 命中源代码（非泄露 — 代码逻辑）

| 文件 | 说明 |
|------|------|
| `app/services/company_agent.py:117` | `self._api_key = settings.company_agent_api_key` — 从环境变量读取，`_redact_key()` 用于日志脱敏 |
| `app/services/company_agent.py:280` | `return {"Authorization": f"Bearer {self._api_key}"}` — 标准 Bearer Token 传递 |
| `app/services/competition_rag.py:46-47` | `PARTIAL_MATCH_CONFIDENCE` — 代码常量，非密钥 |
| `app/schemas/company_agent.py:146` | 注释 `"""Never exposes API keys or tokens."""` — 设计意图声明 |

**结论**: 源代码中无硬编码密钥。`.env.example` 含明文开发密码，标准做法（建议提交时在 `.env.example` 中保留 `changeme` 占位符或明确标记为开发环境）。

---

## 五、大文件检查

| 文件 | 大小 | 建议 |
|------|------|------|
| `data/benchmarks/competition/jd_parsing_annotation_template.csv` | 376KB | 可提交 — <5MB 阈值，标注模板 |
| `data/benchmarks/competition/person_job_matching_annotation_template.csv` | 100KB | 可提交 |
| `data/competition/evidence_sources.json` | 12KB | 可提交 |
| 其余所有新文件 | <15KB | 可提交 |

**无超过 5MB 的文件。**

---

## 六、推荐的原子提交顺序

### 提交 1：Competition 与公司智能体后端能力

**建议消息**:
```
feat(api): add competition intelligence and company agent services
```

**精确文件清单**:
```
app/api/router.py
app/core/config.py
app/api/routes/competition_core.py
app/api/routes/competition_rag.py
app/api/routes/company_agent.py
app/schemas/competition.py
app/schemas/competition_rag.py
app/schemas/company_agent.py
app/services/competition_core.py
app/services/competition_rag.py
app/services/company_agent.py
```

**功能边界**: Competition 岗位发现、角色版本演化、能力 Diff、RAG 证据审计、公司智能体评分 API

**依赖**: 无外部提交依赖（自包含：路由→schema→service 完整）

**提交前验证**:
```powershell
cd E:\202676
python -m pytest tests/test_competition_core.py tests/test_competition_rag.py tests/test_company_agent.py -v
```

**提交后验证**: 同上 + 检查 FastAPI OpenAPI 文档含新路由

**未跟踪文件**: 是（除 router.py/config.py 为修改外，其余 9 个为新增）

**风险**: 无

---

### 提交 2：Java 分析服务前端引用更新

**建议消息**:
```
chore(java): update frontend URL and stack description to talentmatch-frontend/
```

**精确文件清单**:
```
backend/src/com/xh202621/App.java
backend/src/com/xh202621/KnowledgeService.java
```

**功能边界**: 仅更新前端 URL（8501→3000）和技术栈描述文字

**依赖**: 无

**提交前验证**: Java 编译通过

**提交后验证**: `GET http://127.0.0.1:8081/api/health` 返回正确的 `frontend` 字段

**未跟踪文件**: 否（修改已有文件）

**风险**: 无

---

### 提交 3：TalentMatch 前端集成与图谱体验

**建议消息**:
```
feat(talentmatch): integrate competition workflows and capability graphs
```

**精确文件清单**:
```
talentmatch-frontend/server.ts
talentmatch-frontend/src/App.tsx
talentmatch-frontend/src/PlatformPages.tsx
talentmatch-frontend/src/index.css
talentmatch-frontend/src/types.ts
talentmatch-frontend/src/components/CompanyAgentPanel.tsx
talentmatch-frontend/src/components/CompetitionDiscovery.tsx
talentmatch-frontend/src/components/CompetitionErrorBoundary.tsx
talentmatch-frontend/src/components/CompetitionEvidence.tsx
talentmatch-frontend/src/components/CompetitionRoleEvolution.tsx
talentmatch-frontend/src/components/RoleCapabilityGraph.tsx
talentmatch-frontend/src/utils/companyAgent.ts
talentmatch-frontend/src/utils/competitionValidators.ts
```

**功能边界**: 岗位管理 Hub、岗位发现审核、能力演化对比、岗位能力图谱、RAG 证据审计、公司智能体面板、人岗匹配画布、FAB 简历上传

**依赖**: 提交 1（后端 API）——前端 API 调用依赖后端路由已注册

**提交前验证**:
```powershell
cd E:\202676\talentmatch-frontend
npm.cmd run lint
npm.cmd run build
```

**提交后验证**:
```powershell
cd E:\202676\talentmatch-frontend
npm.cmd run lint
npm.cmd run build
# 浏览器访问 http://localhost:3000 验收 6 个一级导航页面
```

**未跟踪文件**: 是（8 个新增组件/utils）

**风险**: 无

---

### 提交 4：自动化测试与评估工具

**建议消息**:
```
test: add competition, security and storage verification suites
```

**精确文件清单**:
```
tests/test_competition_core.py
tests/test_competition_rag.py
tests/test_competition_integration.py
tests/test_competition_metrics.py
tests/test_company_agent.py
tests/test_auth_routes.py
tests/test_search_routes.py
tests/test_security.py
tests/test_vectors_routes.py
tests/test_milvus_talent.py
tests/test_migrations.py
scripts/build_competition_annotation_set.py
scripts/evaluate_competition_metrics.py
```

**功能边界**: Competition 全量测试、认证/搜索/安全/向量基础设施测试、标注集构建与评估脚本

**依赖**: 提交 1（后端 API）、提交 3（前端类型定义被部分测试引用）

**提交前验证**:
```powershell
cd E:\202676
python -m pytest tests/test_competition_core.py tests/test_competition_rag.py tests/test_company_agent.py tests/test_auth_routes.py tests/test_search_routes.py tests/test_security.py tests/test_vectors_routes.py tests/test_milvus_talent.py tests/test_migrations.py -v
```

**提交后验证**: 同上

**未跟踪文件**: 是（全部新增）

**风险**: `test_competition_integration.py` / `test_competition_metrics.py` 可能依赖 `data/competition/` 下的 JSON 种子数据——建议与提交 6 一起验证

---

### 提交 5：部署配置、交付文档与项目文档

**建议消息**:
```
docs(delivery): add deployment manifests, competition delivery docs and verification
```

**精确文件清单**:
```
PROJECT_README.md
SCRIPT_README.md
docs/architecture.md
docs/legacy-readme.md
docs/match-ai-api.md
docs/mvp-scope.md
docs/project-master-plan.md
docs/requirements-summary.md
docs/competition-evaluation-guide.md
docs/competition-ui-acceptance.md
docs/delivery-verification.md
docs/frontend-final-acceptance-2026-07-18.md
docs/project-completion-audit.md
_archived-frontends/frontend-react/ARCHIVED.md
_archived-frontends/frontend-vue/ARCHIVED.md
deploy/docker-compose.competition.yml
deploy/Dockerfile.python
deploy/Dockerfile.java
deploy/Dockerfile.web
deploy/README.md
scripts/verify-competition-deployment.ps1
scripts/verify-competition-deployment.sh
competition-delivery/01-作品设计实现方案.md
competition-delivery/02-系统架构与数据流程.md
competition-delivery/03-多源数据治理与质量控制.md
competition-delivery/04-幻觉防控与人工审核.md
competition-delivery/05-测试方案与指标口径.md
competition-delivery/06-新岗位输入输出案例.md
competition-delivery/07-Java岗位能力更新案例.md
competition-delivery/08-部署与运行说明.md
competition-delivery/09-PPT大纲.md
competition-delivery/10-十分钟演示视频脚本.md
competition-delivery/11-提交物检查清单.md
```

**功能边界**: 项目文档、Competition 竞赛交付物、Docker 部署配置

**依赖**: 无代码依赖

**提交前验证**:
```powershell
rg -n "password|secret|token" deploy/.env.example  # 确认仅含开发默认值
cat deploy/docker-compose.competition.yml | python -c "import sys,json,yaml; yaml.safe_load(sys.stdin)"  # YAML 语法检查
```

**提交后验证**: 确认 Git 历史中文档正确渲染

**未跟踪文件**: 是（22 个新增）

**风险**:
- `deploy/.env.example` 含明文开发密码（`password`, `password123`, `minioadmin`）— 为标准 `.env.example` 做法，建议在文件中标注 "DEVELOPMENT ONLY"
- `competition-delivery/08-部署与运行说明.md` 提及部署参数 — 非泄露，属文档性质

---

### 提交 6：Competition 数据资产

**建议消息**:
```
data(competition): add competition seed data and benchmark annotation templates
```

**精确文件清单**:
```
data/competition/discoveries.json
data/competition/evidence_sources.json
data/competition/panorama.json
data/competition/rag_audit.jsonl
data/competition/reviews.json
data/competition/roles.json
data/benchmarks/competition/annotation_manifest.json
data/benchmarks/competition/competition_evaluation_report.json
data/benchmarks/competition/jd_parsing_annotation_template.csv
data/benchmarks/competition/person_job_matching_annotation_template.csv
data/benchmarks/competition/resume_extraction_annotation_template.csv
data/benchmarks/competition/README.md
```

**功能边界**: Competition 功能种子数据、标注模板、评估报告

**依赖**: 提交 1（后端服务依赖 `data/competition/*.json` 作为数据源）

**提交前验证**: JSON 语法检查 + CSV 有效性

**提交后验证**: Competition API 返回数据与种子数据一致

**未跟踪文件**: 是（全部新增）

**风险**:
- `jd_parsing_annotation_template.csv` (376KB) 和 `person_job_matching_annotation_template.csv` (100KB) — 标注模板，需确认是否为正式版本而非临时导出
- `data/competition/discoveries.json.bak` — **不提交**，放入 `.gitignore` 或直接删除

---

## 七、禁止提交文件清单

```
pytest-temp-529415458258443fb105b6f9f467f100/
pytest-temp-727a7c02468843eda9c588e767e75e08/
pytest-temp-d7d0f45667b145b0b348acfab900fd7a/
data/competition/discoveries.json.bak
```
（以及：`__pycache__/`、`.pytest_cache/`、`node_modules/`、`dist/` — 已在 `.gitignore`）

## 八、待人工确认文件清单

| 文件 | 问题 |
|------|------|
| `data/competition/discoveries.json.bak` | 备份文件，建议删除后提交 → 放入提交 6 前需先删除 |
| `deploy/.env.example` | 含明文开发密码 — 标准做法但建议确认 |
| `data/benchmarks/competition/jd_parsing_annotation_template.csv` (376KB) | 标注模板，确认是否正式版本 |

## 九、提交汇总

| 序号 | 建议消息 | 文件数 | 依赖 |
|------|----------|--------|------|
| 1 | `feat(api): add competition intelligence and company agent services` | 11 | 无 |
| 2 | `chore(java): update frontend URL and stack description to talentmatch-frontend/` | 2 | 无（可独立回滚） |
| 3 | `feat(talentmatch): integrate competition workflows and capability graphs` | 13 | 提交 1 |
| 4 | `test: add competition, security and storage verification suites` | 13 | 提交 1, 3 |
| 5 | `docs(delivery): add deployment manifests, competition delivery docs and verification` | 32 | 无代码依赖 |
| 6 | `data(competition): add competition seed data and benchmark annotation templates` | 12 | 提交 1 |

**推荐执行顺序**: 1 → 2 → 3 → 4 → 5 → 6

或并行路径：先 1+2（独立），再 3，再 4+5+6（文档/测试/数据可并行）。

---

## 十、提交前全量验证脚本

在全部 6 个提交完成后执行：

```powershell
# 前端
cd E:\202676\talentmatch-frontend
npm.cmd run lint
npm.cmd run build

# 后端
cd E:\202676
python -m pytest --basetemp E:\202676\pytest-final-verify -ra

# 工作区整洁检查
git diff --check
rg -n "comp-panorama|comp-overview|comp-hub__tabs--five" talentmatch-frontend/src
```

---

## 十一、建议的下一条任务

**任务 127 — 选择性暂存与原子提交执行**

按本报告推荐的 6 个原子提交顺序，逐一 `git add` 精确文件列表，执行提交前验证，生成提交。需确认：

1. `data/competition/discoveries.json.bak` 已删除或不暂存
2. `deploy/.env.example` 已确认可提交
3. 3 个遗留 pytest-temp-* 目录已排除
4. 每次提交后运行对应验证命令
5. 不推送远程仓库

---

## 十二、最终声明

**任务 126 仅完成审计，未修改、未暂存、未提交任何文件。**

**是否可以进入任务 127 选择性暂存：是。**
