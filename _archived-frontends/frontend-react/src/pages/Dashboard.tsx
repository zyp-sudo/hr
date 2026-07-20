import { Card, List, Progress, Tag } from 'antd';
import type { EChartsOption } from 'echarts';
import { useEffect, useState } from 'react';
import { talentApi } from '../api/client';
import ChartCard from '../components/charts/ChartCard';
import MetricCard from '../components/MetricCard';

const chartText = { color: '#94a3b8' };
type DashboardData = Awaited<ReturnType<typeof talentApi.getDashboard>>;

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    talentApi.getDashboard().then(setData);
  }, []);

  if (!data) {
    return <div className="glass-panel rounded-xl p-6 text-slate-300">正在连接后端数据服务...</div>;
  }

  const { abilityRadar, abilityScore, growthTrend, jobMatches, skillRanks, backendConnected, graphNodeCount } = data;

  const radarOption: EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {},
    legend: { textStyle: chartText, bottom: 0 },
    radar: {
      indicator: abilityRadar.map((item) => ({ name: item.label, max: 100 })),
      splitLine: { lineStyle: { color: '#1d2b44' } },
      splitArea: { areaStyle: { color: ['rgba(59,130,246,0.04)', 'rgba(34,211,238,0.02)'] } },
      axisName: { color: '#cbd5e1' }
    },
    series: [
      {
        type: 'radar',
        data: [
          { name: '当前能力', value: abilityRadar.map((item) => item.value), areaStyle: { color: 'rgba(34,211,238,0.18)' } },
          { name: '岗位基准', value: abilityRadar.map((item) => item.benchmark), areaStyle: { color: 'rgba(139,92,246,0.12)' } }
        ]
      }
    ]
  };

  const trendOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { textStyle: chartText },
    grid: { top: 42, right: 24, bottom: 28, left: 36 },
    xAxis: { type: 'category', data: growthTrend.map((item) => item.month), axisLabel: chartText },
    yAxis: { type: 'value', axisLabel: chartText, splitLine: { lineStyle: { color: '#1d2b44' } } },
    series: [
      { name: '能力评分', type: 'line', smooth: true, data: growthTrend.map((item) => item.score), color: '#22d3ee' },
      { name: '市场需求', type: 'line', smooth: true, data: growthTrend.map((item) => item.marketDemand), color: '#8b5cf6' }
    ]
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        <MetricCard label="用户能力评分" value={abilityScore} suffix="/ 100" tone="blue" />
        <MetricCard label="高匹配岗位" value={jobMatches.length} tone="green" />
        <MetricCard label="图谱节点" value={graphNodeCount || skillRanks.length + jobMatches.length + 1} tone="purple" />
        <MetricCard label="后端连接" value={backendConnected ? '已连接' : 'Mock'} tone="amber" />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ChartCard title="AI能力雷达图" option={radarOption} height={360} />
        </div>
        <Card className="glass-panel !rounded-xl" title={<span className="text-white">技能排名</span>}>
          <List
            dataSource={skillRanks}
            renderItem={(item) => (
              <List.Item className="!border-line">
                <div className="w-full">
                  <div className="mb-2 flex justify-between text-sm">
                    <span className="text-slate-200">{item.name}</span>
                    <span className="text-cyan-200">{item.score}</span>
                  </div>
                  <Progress percent={item.score} showInfo={false} strokeColor="#22d3ee" trailColor="#1d2b44" />
                </div>
              </List.Item>
            )}
          />
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Card className="glass-panel !rounded-xl" title={<span className="text-white">推荐岗位</span>}>
          <div className="space-y-3">
            {jobMatches.map((job) => (
              <div key={job.id} className="rounded-lg border border-line bg-panel2 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="font-semibold text-white">{job.title}</div>
                    <div className="mt-1 text-sm text-slate-400">{job.company} · {job.city} · {job.salary}</div>
                  </div>
                  <Tag color="blue">{job.matchRate}%</Tag>
                </div>
              </div>
            ))}
          </div>
        </Card>
        <ChartCard title="能力成长趋势" option={trendOption} height={320} />
      </div>
    </div>
  );
}
