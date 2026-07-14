import { Card, Steps, Tag, Timeline } from 'antd';
import { learningStages } from '../data/mock';

export default function GrowthPath() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="m-0 text-2xl font-semibold text-white">成长路径</h1>
        <p className="mt-2 text-slate-400">技能学习树、依赖关系和学习阶段规划。</p>
      </div>
      <Card className="glass-panel !rounded-xl">
        <Steps
          current={1}
          items={learningStages.map((stage) => ({
            title: stage.stage,
            description: stage.title
          }))}
        />
      </Card>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Card className="glass-panel !rounded-xl" title={<span className="text-white">技能学习树</span>}>
          <Timeline
            items={learningStages.map((stage) => ({
              children: (
                <div>
                  <div className="font-semibold text-white">{stage.title}</div>
                  <div className="mt-1 text-sm text-slate-400">{stage.duration} · {stage.outcome}</div>
                  <div className="mt-2">{stage.skills.map((skill) => <Tag color="blue" key={skill}>{skill}</Tag>)}</div>
                </div>
              )
            }))}
          />
        </Card>
        <Card className="glass-panel !rounded-xl" title={<span className="text-white">技能依赖关系</span>}>
          <div className="space-y-3">
            {learningStages.slice(1).map((stage, index) => (
              <div key={stage.stage} className="rounded-lg border border-line bg-panel2 p-4">
                <div className="text-sm text-slate-400">{learningStages[index].title}</div>
                <div className="my-2 text-cyan-200">↓ 依赖</div>
                <div className="font-semibold text-white">{stage.title}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
