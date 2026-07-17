export interface JobProfile { id: string; title: string; description: string; requirements: string[] }
export interface AssessmentResult {
  id?: string; createdAt?: string; candidateName?: string; jobId?: string; jobTitle?: string;
  score: number; matchLevel: string;
  radar: { technical: number; experience: number; collaboration: number; education: number; softSkills: number };
  experienceMatch: { relevance: number; alignment: number };
  skillGaps: string[]; highlights: string[];
}

/** UI-facing assessment shape used by the draggable candidate cards. */
export interface AssessmentViewModel {
  score: number;
  level: string;
  industry: number;
  title: number;
  gaps: string[];
  strengths: string[];
  radar: number[];
}
