import {
  extractedEntities,
  extractedRelations,
  hotSkillsMock,
  jobSearchMock,
  matchMock,
  platformModules,
  ragAnswerMock,
  trendMock
} from '../data/mock';
import type {
  ExtractedEntity,
  ExtractedRelation,
  HotSkill,
  JobRecord,
  JobSearchResponse,
  JobTrendResponse,
  MatchResult,
  PlatformModule,
  RagAnswer
} from '../types/domain';

export interface JobSearchQuery {
  keyword?: string;
  city?: string;
  industry?: string;
  education?: string;
  experience?: string;
  salary_min?: number;
  salary_max?: number;
  skills?: string[];
  page?: number;
  page_size?: number;
}

interface JavaJob {
  id: string;
  name: string;
  type?: string;
  description?: string;
  skills?: string[];
}

interface JavaMatchResponse {
  targetJobId?: string;
  targetJobName?: string;
  score?: number;
  matchedSkills?: string[];
  missingSkills?: string[];
  suggestions?: string[];
  aiAnalysis?: string;
}

const timeoutMs = 4500;

async function requestJson<T>(path: string, init?: RequestInit): Promise<T | null> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers
      }
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  } finally {
    window.clearTimeout(timer);
  }
}

function buildQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) {
      value.filter(Boolean).forEach((item) => search.append(key, String(item)));
      return;
    }
    search.append(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}

function mapJavaJobs(rows: JavaJob[]): JobRecord[] {
  return rows.map((row, index) => ({
    id: row.id,
    title: row.name,
    company_name: '本地知识库',
    city: ['上海', '北京', '深圳', '杭州'][index % 4],
    industry: row.type || '智能招聘',
    education: '本科',
    experience: index % 2 === 0 ? '3-5年' : '1-3年',
    salary_min: 20 + index * 2,
    salary_max: 32 + index * 3,
    skills: row.skills || [],
    source: 'Java API',
    matchRate: Math.max(64, 92 - index * 4)
  }));
}

function jobSearchFromJava(rows: JobRecord[], page = 1, pageSize = 10): JobSearchResponse {
  const skills = new Map<string, number>();
  const cities = new Map<string, number>();
  const industries = new Map<string, number>();
  rows.forEach((job) => {
    job.skills.forEach((skill) => skills.set(skill, (skills.get(skill) || 0) + 1));
    if (job.city) cities.set(job.city, (cities.get(job.city) || 0) + 1);
    if (job.industry) industries.set(job.industry, (industries.get(job.industry) || 0) + 1);
  });
  const bucket = (map: Map<string, number>) =>
    Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([key, count]) => ({ key, count }));
  return {
    total: rows.length,
    page,
    page_size: pageSize,
    items: rows.slice((page - 1) * pageSize, page * pageSize),
    aggregations: {
      skills: bucket(skills),
      cities: bucket(cities),
      industries: bucket(industries),
      educations: [
        { key: '本科', count: rows.length },
        { key: '硕士', count: Math.max(1, Math.round(rows.length * 0.18)) }
      ],
      experiences: [
        { key: '1-3年', count: Math.max(1, Math.round(rows.length * 0.42)) },
        { key: '3-5年', count: Math.max(1, Math.round(rows.length * 0.48)) }
      ]
    },
    source: 'api'
  };
}

async function fetchJavaJobs(): Promise<JobRecord[]> {
  const data = await requestJson<{ jobs?: JavaJob[] }>('/java-api/jobs');
  return data?.jobs ? mapJavaJobs(data.jobs) : [];
}

export const platformApi = {
  async loadModules(): Promise<PlatformModule[]> {
    const [javaHealth, storageHealth] = await Promise.all([
      requestJson<{ status: string }>('/java-api/health'),
      requestJson<{ status: string }>('/storage-api/health')
    ]);
    return platformModules.map((module) => {
      if (module.key === 'storage') {
        return { ...module, state: storageHealth ? 'online' : module.state };
      }
      if (module.key === 'kg' || module.key === 'analysis') {
        return { ...module, state: javaHealth ? 'online' : module.state };
      }
      return module;
    });
  },

  async searchJobs(query: JobSearchQuery): Promise<JobSearchResponse> {
    const storage = await requestJson<JobSearchResponse>(
      `/storage-api/search/jobs${buildQuery({
        keyword: query.keyword,
        city: query.city,
        industry: query.industry,
        education: query.education,
        experience: query.experience,
        salary_min: query.salary_min,
        salary_max: query.salary_max,
        skills: query.skills,
        page: query.page || 1,
        page_size: query.page_size || 10
      })}`
    );
    if (storage) return { ...storage, source: 'api' };

    const javaJobs = await fetchJavaJobs();
    if (javaJobs.length) {
      return jobSearchFromJava(javaJobs, query.page || 1, query.page_size || 10);
    }

    const keyword = query.keyword?.toLowerCase();
    const items = jobSearchMock.items.filter((job) => {
      const text = `${job.title}${job.company_name}${job.city}${job.industry}${job.skills.join('')}`.toLowerCase();
      const keywordOk = !keyword || text.includes(keyword);
      const cityOk = !query.city || job.city === query.city;
      const industryOk = !query.industry || job.industry === query.industry;
      return keywordOk && cityOk && industryOk;
    });
    return { ...jobSearchMock, items, total: items.length, source: 'mock' };
  },

  async loadSkillAnalysis(): Promise<HotSkill[]> {
    const data = await requestJson<{ hot_skills: HotSkill[] }>('/storage-api/analysis/skills?size=20');
    return data?.hot_skills?.length ? data.hot_skills : hotSkillsMock;
  },

  async loadJobTrend(): Promise<JobTrendResponse> {
    const data = await requestJson<JobTrendResponse>('/storage-api/analysis/jobs/trend');
    return data ? { ...data, source: 'api' } : trendMock;
  },

  async matchResume(targetJobId: string, resumeText: string): Promise<MatchResult> {
    const data = await requestJson<JavaMatchResponse>('/java-api/match', {
      method: 'POST',
      body: JSON.stringify({ targetJobId, resumeText })
    });
    if (data) {
      return {
        targetJobId: data.targetJobId || targetJobId,
        targetJobName: data.targetJobName || targetJobId,
        matchScore: data.score ?? 0,
        matchedSkills: data.matchedSkills || [],
        missingSkills: data.missingSkills || [],
        learningPath: data.suggestions || [],
        aiAnalysis: data.aiAnalysis,
        source: 'api'
      };
    }
    return { ...matchMock, targetJobId };
  },

  async analyzeText(text: string): Promise<{ entities: ExtractedEntity[]; relations: ExtractedRelation[] }> {
    const trimmed = text.trim();
    if (!trimmed) {
      return { entities: extractedEntities, relations: extractedRelations };
    }
    const entities = extractedEntities.filter((entity) => trimmed.includes(entity.text));
    return {
      entities: entities.length ? entities : extractedEntities,
      relations: extractedRelations
    };
  },

  async askRag(query: string): Promise<RagAnswer> {
    return {
      ...ragAnswerMock,
      query: query.trim() || ragAnswerMock.query
    };
  }
};
