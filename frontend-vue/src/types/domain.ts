export type ModuleState = 'online' | 'warning' | 'offline' | 'mock';

export interface PlatformModule {
  key: string;
  name: string;
  stack: string;
  state: ModuleState;
  metric: string;
  value: string;
  latency?: string;
  description: string;
}

export interface AbilityMetric {
  name: string;
  value: number;
  benchmark: number;
}

export interface SkillDemand {
  skill: string;
  demand: number;
  owned: number;
  gap: number;
  category: string;
}

export interface JobRecord {
  id: string | number;
  title: string;
  company_name?: string;
  company?: string;
  city?: string;
  industry?: string;
  education?: string;
  experience?: string;
  salary_min?: number;
  salary_max?: number;
  salary?: string;
  skills: string[];
  published_at?: string;
  source?: string;
  matchRate?: number;
}

export interface AggregationBucket {
  key: string;
  count: number;
}

export interface JobSearchResponse {
  total: number;
  page: number;
  page_size: number;
  items: JobRecord[];
  aggregations: Record<string, AggregationBucket[]>;
  source?: 'api' | 'mock';
}

export interface HotSkill {
  skill: string;
  count: number;
  related_job_count: number;
}

export interface TrendBucket {
  key: string;
  count: number;
}

export interface JobTrendResponse {
  by_date: TrendBucket[];
  by_city: TrendBucket[];
  by_industry: TrendBucket[];
  source?: 'api' | 'mock';
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'user' | 'skill-owned' | 'skill-gap' | 'skill-learning' | 'job' | 'company' | 'data' | 'model';
  score?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
}

export interface ExtractedEntity {
  text: string;
  type: '技能' | '岗位' | '公司' | '学历' | '经验' | '地点';
  confidence: number;
}

export interface ExtractedRelation {
  source: string;
  relation: string;
  target: string;
  confidence: number;
}

export interface RagChunk {
  id: string;
  title: string;
  score: number;
  source: string;
  content: string;
}

export interface RagAnswer {
  query: string;
  answer: string;
  chunks: RagChunk[];
}

export interface ResumeProfile {
  name: string;
  title: string;
  education: string;
  years: string;
  intent: string;
  skills: string[];
  projects: string[];
}

export interface MatchResult {
  targetJobId: string;
  targetJobName: string;
  matchScore: number;
  matchedSkills: string[];
  missingSkills: string[];
  learningPath: string[];
  aiAnalysis?: string;
  source?: 'api' | 'mock';
}

export interface GraphMetric {
  name: string;
  value: number;
  detail: string;
}
