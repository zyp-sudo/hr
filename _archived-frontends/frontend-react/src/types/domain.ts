export type SkillStatus = 'owned' | 'gap' | 'learning' | 'required';

export interface AbilityScore {
  label: string;
  value: number;
  benchmark: number;
}

export interface SkillRank {
  name: string;
  score: number;
  status: SkillStatus;
  demand: number;
}

export interface JobMatch {
  id: string;
  title: string;
  company: string;
  matchRate: number;
  salary: string;
  city: string;
  matchedSkills: string[];
  missingSkills: string[];
  learningPath: string[];
}

export interface TrendPoint {
  month: string;
  score: number;
  marketDemand: number;
}

export interface GraphNodeData {
  label: string;
  category: SkillStatus | 'user';
  score?: number;
}

export interface LearningStage {
  stage: string;
  title: string;
  skills: string[];
  duration: string;
  outcome: string;
}

export interface HeatmapPoint {
  industry: string;
  skill: string;
  value: number;
}

export interface TalentGap {
  role: string;
  demand: number;
  supply: number;
  gap: number;
}
