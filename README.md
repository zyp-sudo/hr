# TalentMatch 人岗匹配智能评估系统

TalentMatch 是一个面向招聘场景的人岗匹配与人才分析项目，包含岗位管理、候选人评估、人才图谱、重点人才跟踪、招聘趋势分析和向量检索能力。

当前正式入口是 `talentmatch/` 中的 React + TypeScript 前端。完整服务包括：

- TalentMatch Web：React 19、TypeScript、Vite、Express，端口 `3000`
- Python API：FastAPI，端口 `8080`
- Java 分析服务：JDK 21，端口 `8081`
- MySQL：业务数据，宿主机端口 `3307`
- Elasticsearch：搜索与聚合，端口 `9200`
- Neo4j：人才与能力图谱，HTTP `7474`、Bolt `7687`
- Milvus：人才向量库，端口 `19530`、管理端口 `9091`

## 1. 服务地址

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| TalentMatch 前端 | <http://localhost:3000> | 正式 Web 界面 |
| 前端健康检查 | <http://localhost:3000/api/health> | Express 网关状态 |
| Python API | <http://localhost:8080> | API 入口 |
| Swagger | <http://localhost:8080/docs> | Python API 文档 |
| Python 健康检查 | <http://localhost:8080/api/health> | 数据服务状态 |
| Java API | <http://localhost:8081> | 内部分析服务 |
| Neo4j Browser | <http://localhost:7474> | 图数据库管理界面 |
| Elasticsearch | <http://localhost:9200> | 搜索服务 |
| Milvus WebUI | <http://localhost:9091/webui/> | 向量数据库状态 |

## 2. 下载项目

使用 HTTPS：

```bash
git clone https://github.com/zyp-sudo/hr.git
cd hr
```

或使用已配置 GitHub 公钥的 SSH：

```bash
git clone git@github.com:zyp-sudo/hr.git
cd hr
```

后续获取更新：

```bash
git pull --ff-only origin main
```

如果本地已经修改文件，请先提交或使用 `git stash`，不要直接覆盖同伴的工作。

## 3. 环境要求

| 工具 | 推荐版本 | 最低要求 | 本项目测试版本 |
| --- | --- | --- | --- |
| Git | 2.40+ | 2.30+ | 2.49.0 |
| Python | 3.12 | 3.11 | 3.12.10 |
| Node.js | 22 LTS 或 24 | 22.13+ | 24.18.0 |
| npm | 10+ | 10+ | 11.16.0 |
| JDK / javac | 21 LTS | 21 | 21.0.11 |
| Docker Engine | 24+ | 24+ | 29.4.3 |
| Docker Compose | v2+ | v2+ | v5.1.3 |
| PowerShell | 5.1 或 7+ | 5.1 | Windows 自带版本可用 |

建议至少准备 8 GB 内存和 15 GB 可用磁盘；推荐 12–16 GB 内存。

确认工具安装成功：

```powershell
git --version
python --version
node --version
npm.cmd --version
javac -version
docker --version
docker compose version
```

> Windows PowerShell 如果禁止执行 `npm.ps1`，请使用 `npm.cmd`。本文的 Windows 命令已按此方式编写。

## 4. 容器与版本

`docker-compose.yml` 负责数据库和基础设施；前端、Python API、Java API 默认运行在宿主机上。

| Compose 服务 | Docker 镜像 | 宿主机端口 | 默认本地账号 |
| --- | --- | --- | --- |
| `mysql` | `mysql:8.4` | `3307` | `root / password` |
| `neo4j` | `neo4j:5.26-community` | `7474`, `7687` | `neo4j / password123` |
| `elasticsearch` | `elasticsearch:8.13.4` | `9200` | 未启用鉴权 |
| `milvus-etcd` | `quay.io/coreos/etcd:v3.5.18` | 不对外暴露 | 内部服务 |
| `milvus-minio` | `minio/minio:RELEASE.2024-12-18T13-15-44Z` | 不对外暴露 | `minioadmin / minioadmin` |
| `milvus` | `milvusdb/milvus:v2.6.19` | `19530`, `9091` | 未启用鉴权 |

这些账号仅用于本地开发，不要直接用于公网服务器。

常用容器命令：

```bash
docker compose up -d       # 启动全部基础设施
docker compose ps          # 查看状态和健康检查
docker compose logs -f     # 持续查看日志
docker compose down        # 停止容器，保留数据卷
docker compose down -v     # 停止并删除数据卷，会清空本地数据库
```

## 5. 第一次安装依赖

### 5.1 Python

Windows PowerShell：

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux/macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

需要运行测试时安装开发依赖：

```bash
python -m pip install -r requirements-dev.txt
```

### 5.2 前端

`package-lock.json` 已提交，团队成员应使用 `npm ci` 获得一致版本。

Windows PowerShell：

```powershell
Set-Location talentmatch
npm.cmd ci
Set-Location ..
```

Linux/macOS：

```bash
cd talentmatch
npm ci
cd ..
```

## 6. 启动方式 A：使用 `start.ps1`（Windows 推荐）

确保 Docker Desktop 已启动，在项目根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

脚本会自动：

1. 启动 MySQL、Neo4j、Elasticsearch、Milvus、etcd 和 MinIO。
2. 等待数据库健康检查通过。
3. 将仓库数据增量同步到 MySQL、Neo4j 和 Elasticsearch。
4. 编译并启动 Java 服务 `8081`。
5. 启动 Python API `8080`。
6. 前端依赖不存在时使用 `npm ci` 安装。
7. 启动 TalentMatch 前端 `3000`。

启动成功后打开 <http://localhost:3000>。

按 `Ctrl+C` 会停止脚本管理的前端、Python 和 Java 进程。数据库容器默认继续运行；停止数据库使用：

```powershell
docker compose down
```

数据库已经初始化、只想重启应用层：

```powershell
$env:SKIP_STORAGE_INIT = "true"
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

启动后自动执行接口冒烟检查：

```powershell
$env:XH_STARTUP_SMOKE_TEST = "true"
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

## 7. 启动方式 B：不使用 `start.ps1`

适合分别观察各服务日志，或使用 Linux/macOS。以下命令均从项目根目录开始。

Linux/macOS 如果已经完成第 5 节的依赖安装，也可以直接运行等价的一键脚本：

```bash
bash start.sh
```

需要手动分别启动时，继续执行下面的步骤。

### 7.1 启动基础设施

```bash
docker compose up -d mysql neo4j elasticsearch milvus-etcd milvus-minio milvus
docker compose ps
```

等待 `mysql`、`neo4j`、`elasticsearch`、`milvus` 显示为 `healthy`。

### 7.2 初始化和同步数据

先激活 Python 虚拟环境，再执行：

```bash
python scripts/bootstrap_storage.py --sync
python scripts/sync_mysql_to_es.py --auto
```

### 7.3 启动 Java 分析服务

新开终端。Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force backend\runtime-out | Out-Null
javac -encoding UTF-8 -d backend\runtime-out backend\src\com\xh202621\*.java
$env:BACKEND_PORT = "8081"
java -cp backend\runtime-out com.xh202621.App
```

Linux/macOS：

```bash
mkdir -p backend/runtime-out
javac -encoding UTF-8 -d backend/runtime-out backend/src/com/xh202621/*.java
BACKEND_PORT=8081 java -cp backend/runtime-out com.xh202621.App
```

### 7.4 启动 Python API

再新开终端，激活 `.venv` 后执行：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

检查 <http://localhost:8080/api/health>。

### 7.5 启动 TalentMatch 前端

再新开终端。Windows PowerShell：

```powershell
Set-Location talentmatch
$env:PORT = "3000"
npm.cmd run dev
```

Linux/macOS：

```bash
cd talentmatch
PORT=3000 npm run dev
```

打开 <http://localhost:3000>。

## 8. 可选环境配置与 AI 服务

没有 AI API Key 也可以运行，系统会使用本地规则完成基础评估。

Windows 用户可复制配置模板：

```powershell
Copy-Item scripts\local-env.example.ps1 scripts\local-env.ps1
Copy-Item talentmatch\.env.example talentmatch\.env.local
```

只在本地文件中填写自己的密钥。这两个真实配置文件已被 `.gitignore` 排除，禁止提交。

| 变量 | 默认值或用途 |
| --- | --- |
| `MYSQL_URL` | MySQL SQLAlchemy 连接地址 |
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | `neo4j` |
| `NEO4J_PASSWORD` | 本地默认 `password123` |
| `ES_HOST` | `http://localhost:9200` |
| `MILVUS_URI` | `http://localhost:19530` |
| `JAVA_BACKEND_URL` | Python API 访问 Java 服务，默认 `http://localhost:8081` |
| `JAVA_API_URL` | 前端网关访问 Java 服务，默认 `http://127.0.0.1:8081` |
| `STORAGE_API_URL` | 前端网关访问 Python API，默认 `http://127.0.0.1:8080` |
| `GEMINI_API_KEY` | 可选 Gemini 密钥 |
| `AI_PROVIDER` | `google`、`deepseek` 或 `openai` |
| `AI_BASE_URL` | OpenAI 兼容服务地址 |

不要把真实密码、Token、简历或候选人隐私数据提交到 Git。

## 9. 验证安装

```bash
# 后端测试
python -m pytest

# 存储计数验证（服务启动后）
python scripts/verify_storage_counts.py
```

Windows 前端检查：

```powershell
Set-Location talentmatch
npm.cmd run lint
npm.cmd run build
```

基础服务检查：

```powershell
Invoke-RestMethod http://localhost:8080/api/health
Invoke-RestMethod http://localhost:3000/api/health
docker compose ps
```

## 10. 常见问题

### Docker 服务一直不健康

```bash
docker compose ps
docker compose logs mysql neo4j elasticsearch milvus
```

确认端口 `3307`、`7474`、`7687`、`9200`、`19530`、`9091` 未被占用，并确认 Docker Desktop 有足够内存。

### `npm.ps1` 无法运行

改用 `npm.cmd ci` 和 `npm.cmd run dev`。

### 应用端口被占用

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-dev.ps1
```

### Python 无法连接 MySQL

```powershell
docker compose ps
$env:MYSQL_URL
python scripts\bootstrap_storage.py --sync
```

### 首次启动很慢

首次运行需要下载六个容器镜像、安装 npm 依赖并导入数据。后续会复用镜像、依赖和 Docker 数据卷。

## 11. 项目结构

```text
app/                    FastAPI 应用、API、数据访问与管理后台
backend/                Java 分析服务
talentmatch/            正式 React/TypeScript 前端与 Express 网关
scripts/                初始化、同步、采集、ETL、测试和启动脚本
data/                   示例数据、ETL 结果与数据库导入文件
tests/                  Python 自动化测试
docs/                   架构、数据治理和项目设计文档
docker-compose.yml      本地基础设施容器编排
requirements.txt        Python 运行依赖
requirements-dev.txt    Python 测试依赖
start.ps1               Windows 一键启动脚本
```

旧版入口说明已归档到 `docs/legacy-readme.md`。

## 12. 团队协作

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/your-feature
```

提交前至少执行：

```bash
python -m pytest
cd talentmatch
npm run lint
npm run build
```

不要提交：

- `.env`、`.env.local`、`scripts/local-env.ps1`
- API Key、数据库生产密码
- `node_modules/`、`.venv/`、`dist/`
- 本地 SQLite 数据库、日志和临时候选人数据
- 新生成的大体积爬虫原始响应

更多设计说明请查看 `docs/` 与 `PROJECT_README.md`。
