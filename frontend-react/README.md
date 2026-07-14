# 智能人才能力图谱与岗位匹配系统前端

技术栈：

- React + TypeScript
- TailwindCSS
- Ant Design
- ECharts
- React Flow (`@xyflow/react`)

## 页面结构

```text
src/
  App.tsx                         主布局、侧边导航、页面切换
  main.tsx                        React/AntD/Tailwind 入口
  api/client.ts                   数据接口层，当前读取 Mock
  data/mock.ts                    Mock 数据
  types/domain.ts                 领域类型定义
  components/
    MetricCard.tsx                指标卡片
    charts/ChartCard.tsx          ECharts 卡片封装
  pages/
    Dashboard.tsx                 首页 Dashboard
    KnowledgeGraph.tsx            React Flow 能力知识图谱
    JobMatching.tsx               岗位匹配
    GrowthPath.tsx                成长路径
    EnterpriseAnalytics.tsx       企业人才分析
```

## 启动

```powershell
cd frontend-react
npm install
npm run dev
```

默认端口：`http://localhost:5173`

## 数据接口

当前页面使用 `src/data/mock.ts`。接入真实后端时，优先替换 `src/api/client.ts`，页面组件无需改动。

接口草案见 `API_DESIGN.md`。

## 设计原则

- 深色主题，面向企业级 AI 数据平台
- 主要信息以指标卡、图表、图谱和表格表达
- 图谱节点颜色规范：
  - 绿色：已有技能
  - 红色：能力缺口
  - 蓝色：推荐学习
  - 紫色：岗位需求
