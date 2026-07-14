import { Card, Progress, Tag, Timeline } from 'antd';
import { useEffect, useState } from 'react';
import { talentApi } from '../api/client';
import type { JobMatch } from '../types/domain';

export default function JobMatching() {
  const [jobMatches, setJobMatches] = useState<JobMatch[]>([]);

  useEffect(() => {
    talentApi.getJobMatches().then(setJobMatches);
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="m-0 text-2xl font-semibold text-white">岗位匹配</h1>
        <p className="mt-2 text-slate-400">展示岗位名称、匹配度、技能符合情况、缺失技能和推荐学习路线。</p>
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        {jobMatches.map((job) => (
          <Card key={job.id} className="glass-panel !rounded-xl" title={<span className="text-white">{job.title}</span>}>
            <div className="mb-5 flex items-center justify-between">
              <div className="text-sm text-slate-400">{job.company} · {job.city}</div>
              <Tag color={job.matchRate >= 85 ? 'green' : 'blue'}>{job.salary}</Tag>
            </div>
            <Progress type="dashboard" percent={job.matchRate} strokeColor="#22d3ee" trailColor="#1d2b44" />
            <div className="mt-5">
              <div className="mb-2 text-sm text-slate-400">技能符合情况</div>
              {job.matchedSkills.map((skill) => <Tag key={skill} color="green">{skill}</Tag>)}
            </div>
            <div className="mt-4">
              <div className="mb-2 text-sm text-slate-400">缺失技能</div>
              {job.missingSkills.map((skill) => <Tag key={skill} color="red">{skill}</Tag>)}
            </div>
            <div className="mt-5">
              <div className="mb-3 text-sm text-slate-400">推荐学习路线</div>
              <Timeline items={job.learningPath.map((item) => ({ children: <span className="text-slate-200">{item}</span> }))} />
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
