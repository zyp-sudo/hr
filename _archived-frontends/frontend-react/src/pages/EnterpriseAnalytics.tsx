import { Card, Progress, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import ChartCard from '../components/charts/ChartCard';
import { growthTrend, heatmapData, talentGaps } from '../data/mock';
import type { TalentGap } from '../types/domain';

export default function EnterpriseAnalytics() {
  const industries = [...new Set(heatmapData.map((item) => item.industry))];
  const skills = [...new Set(heatmapData.map((item) => item.skill))];
  const heatmapOption: EChartsOption = {
    tooltip: {},
    grid: { top: 24, right: 24, bottom: 60, left: 70 },
    xAxis: { type: 'category', data: skills, axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'category', data: industries, axisLabel: { color: '#94a3b8' } },
    visualMap: { min: 60, max: 100, calculable: true, orient: 'horizontal', bottom: 0, textStyle: { color: '#94a3b8' } },
    series: [{
      type: 'heatmap',
      data: heatmapData.map((item) => [skills.indexOf(item.skill), industries.indexOf(item.industry), item.value])
    }]
  };

  const trendOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    grid: { top: 32, right: 24, bottom: 28, left: 36 },
    xAxis: { type: 'category', data: growthTrend.map((item) => item.month), axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1d2b44' } } },
    series: [{ name: '行业趋势', type: 'bar', data: growthTrend.map((item) => item.marketDemand), color: '#3b82f6' }]
  };

  const columns: ColumnsType<TalentGap> = [
    { title: '岗位', dataIndex: 'role' },
    { title: '需求', dataIndex: 'demand' },
    { title: '供给', dataIndex: 'supply' },
    {
      title: '缺口',
      dataIndex: 'gap',
      render: (value: number) => <Progress percent={Math.min(100, value)} showInfo={false} strokeColor="#ef4444" />
    }
  ];

  return (
    <div className="space-y-5">
      <div>
        <h1 className="m-0 text-2xl font-semibold text-white">企业人才分析</h1>
        <p className="mt-2 text-slate-400">技能需求热力图、人才缺口分析和行业趋势。</p>
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <ChartCard title="技能需求热力图" option={heatmapOption} height={380} />
        <ChartCard title="行业趋势" option={trendOption} height={380} />
      </div>
      <Card className="glass-panel !rounded-xl" title={<span className="text-white">人才缺口分析</span>}>
        <Table rowKey="role" columns={columns} dataSource={talentGaps} pagination={false} />
      </Card>
    </div>
  );
}
