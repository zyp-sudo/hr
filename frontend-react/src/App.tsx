import { BarChartOutlined, BranchesOutlined, DashboardOutlined, LineChartOutlined, NodeIndexOutlined } from '@ant-design/icons';
import { Layout, Menu } from 'antd';
import { useState } from 'react';
import Dashboard from './pages/Dashboard';
import EnterpriseAnalytics from './pages/EnterpriseAnalytics';
import GrowthPath from './pages/GrowthPath';
import JobMatching from './pages/JobMatching';
import KnowledgeGraph from './pages/KnowledgeGraph';

const { Header, Sider, Content } = Layout;

const pages = {
  dashboard: <Dashboard />,
  graph: <KnowledgeGraph />,
  matching: <JobMatching />,
  growth: <GrowthPath />,
  enterprise: <EnterpriseAnalytics />
};

export default function App() {
  const [active, setActive] = useState<keyof typeof pages>('dashboard');

  return (
    <Layout className="min-h-screen bg-canvas subtle-grid">
      <Sider width={252} className="!bg-[#070d1a] border-r border-line">
        <div className="px-5 py-5">
          <div className="text-xs uppercase tracking-[0.26em] text-cyan-300/70">AI Talent OS</div>
          <div className="mt-2 text-lg font-semibold text-white">智能人才能力图谱</div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[active]}
          onClick={({ key }) => setActive(key as keyof typeof pages)}
          className="!bg-transparent !text-slate-300"
          items={[
            { key: 'dashboard', icon: <DashboardOutlined />, label: '首页 Dashboard' },
            { key: 'graph', icon: <BranchesOutlined />, label: '能力知识图谱' },
            { key: 'matching', icon: <BarChartOutlined />, label: '岗位匹配' },
            { key: 'growth', icon: <NodeIndexOutlined />, label: '成长路径' },
            { key: 'enterprise', icon: <LineChartOutlined />, label: '企业人才分析' }
          ]}
        />
      </Sider>
      <Layout className="!bg-transparent">
        <Header className="!h-16 !bg-[#07101f]/80 backdrop-blur border-b border-line px-8 flex items-center justify-between">
          <div>
            <div className="text-sm text-slate-400">Enterprise AI Data Platform</div>
            <div className="text-xl font-semibold text-white">智能人才能力图谱与岗位匹配系统</div>
          </div>
          <div className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-1 text-sm text-cyan-200">AI分析引擎在线</div>
        </Header>
        <Content className="p-6 xl:p-8">
          {pages[active]}
        </Content>
      </Layout>
    </Layout>
  );
}
