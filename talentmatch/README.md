# TalentMatch Web

本目录包含项目的正式 React/TypeScript 前端和 Express 网关。

请优先阅读仓库根目录的 [`README.md`](../README.md)，其中包含完整的 Docker、Python、Java、Node.js 安装与启动过程。

单独启动前端网关：

```bash
npm ci
npm run dev
```

默认地址为 <http://localhost:3000>。前端默认连接：

- Python API：`http://127.0.0.1:8080`
- Java API：`http://127.0.0.1:8081`

可复制 `.env.example` 为 `.env.local` 配置可选 AI 服务。没有 API Key 时仍可使用本地规则评估。
