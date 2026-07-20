import { abilityRadar, abilityScore, growthTrend, heatmapData, jobMatches, learningStages, skillRanks, talentGaps } from '../data/mock';
import type { JobMatch, SkillRank } from '../types/domain';

interface BackendJob {
  id: string;
  name: string;
  type?: string;
  description?: string;
  skills?: string[];
}

interface BackendGraph {
  nodes?: unknown[];
  edges?: unknown[];
}

async function requestJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(path, { headers: { Accept: 'application/json' } });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function skillRanksFromJobs(jobs: BackendJob[]): SkillRank[] {
  const counts = new Map<string, number>();
  jobs.forEach((job) => {
    (job.skills || []).forEach((skill) => counts.set(skill, (counts.get(skill) || 0) + 1));
  });
  const max = Math.max(...counts.values(), 1);
  const rows = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .map(([name, count], index) => ({
      name,
      score: Math.max(48, Math.round((count / max) * 100)),
      demand: Math.max(50, Math.round((count / max) * 96)),
      status: index < 3 ? 'owned' : index < 6 ? 'learning' : 'gap'
    }) as SkillRank);
  return rows.length ? rows : skillRanks;
}

function jobMatchesFromJobs(jobs: BackendJob[]): JobMatch[] {
  const rows = jobs.slice(0, 9).map((job, index) => {
    const skills = job.skills || [];
    const matchRate = Math.max(62, 92 - index * 4);
    return {
      id: String(job.id),
      title: job.name,
      company: '真实岗位数据',
      matchRate,
      salary: '面议',
      city: '不限',
      matchedSkills: skills.slice(0, Math.max(1, Math.min(3, skills.length))),
      missingSkills: skills.slice(3, 6),
      learningPath: skills.slice(3, 6).length
        ? skills.slice(3, 6).map((skill) => `补齐 ${skill} 项目证据`)
        : ['补充项目指标', '完善业务场景描述', '沉淀可展示作品']
    };
  });
  return rows.length ? rows : jobMatches;
}

async function getBackendJobs() {
  const data = await requestJson<{ jobs?: BackendJob[] }>('/api/jobs');
  return data?.jobs || [];
}

export const talentApi = {
  async getDashboard() {
    const [jobs, graph] = await Promise.all([
      getBackendJobs(),
      requestJson<BackendGraph>('/api/graph')
    ]);
    const derivedSkillRanks = skillRanksFromJobs(jobs);
    const derivedJobMatches = jobMatchesFromJobs(jobs);
    return {
      abilityScore,
      abilityRadar,
      skillRanks: derivedSkillRanks,
      jobMatches: derivedJobMatches,
      growthTrend,
      graphNodeCount: graph?.nodes?.length ?? 0,
      backendConnected: jobs.length > 0
    };
  },
  async getGraph() {
    const jobs = await getBackendJobs();
    return {
      skillRanks: skillRanksFromJobs(jobs),
      jobMatches: jobMatchesFromJobs(jobs),
      backendConnected: jobs.length > 0
    };
  },
  async getJobMatches() {
    const jobs = await getBackendJobs();
    return jobMatchesFromJobs(jobs);
  },
  async getGrowthPath() {
    return learningStages;
  },
  async getEnterpriseAnalytics() {
    return { heatmapData, talentGaps, growthTrend };
  }
};
