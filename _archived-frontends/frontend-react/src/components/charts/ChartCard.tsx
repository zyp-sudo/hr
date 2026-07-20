import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';

interface ChartCardProps {
  title: string;
  option: EChartsOption;
  height?: number;
}

export default function ChartCard({ title, option, height = 300 }: ChartCardProps) {
  return (
    <div className="glass-panel rounded-xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="m-0 text-base font-semibold text-white">{title}</h2>
        <span className="text-xs text-cyan-200/70">ECharts</span>
      </div>
      <ReactECharts option={option} style={{ height }} />
    </div>
  );
}
