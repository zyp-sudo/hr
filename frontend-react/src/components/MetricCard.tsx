interface MetricCardProps {
  label: string;
  value: string | number;
  suffix?: string;
  tone?: 'blue' | 'green' | 'purple' | 'amber';
}

const tones = {
  blue: 'from-blue-500/20 to-cyan-400/5 text-blue-200',
  green: 'from-emerald-500/20 to-cyan-400/5 text-emerald-200',
  purple: 'from-violet-500/20 to-cyan-400/5 text-violet-200',
  amber: 'from-amber-500/20 to-cyan-400/5 text-amber-200'
};

export default function MetricCard({ label, value, suffix, tone = 'blue' }: MetricCardProps) {
  return (
    <div className={`glass-panel rounded-xl bg-gradient-to-br ${tones[tone]} p-5`}>
      <div className="text-sm text-slate-400">{label}</div>
      <div className="mt-3 flex items-end gap-1">
        <span className="text-4xl font-semibold text-white">{value}</span>
        {suffix ? <span className="pb-1 text-sm text-slate-400">{suffix}</span> : null}
      </div>
    </div>
  );
}
