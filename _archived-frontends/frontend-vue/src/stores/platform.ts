import { defineStore } from 'pinia';
import { platformApi, type JobSearchQuery } from '../api/client';
import {
  abilityMetrics,
  extractedEntities,
  extractedRelations,
  graphEdges,
  graphMetrics,
  graphNodes,
  hotSkillsMock,
  jobSearchMock,
  matchMock,
  platformModules,
  ragAnswerMock,
  resumeProfile,
  skillDemands,
  trendMock
} from '../data/mock';
import type {
  ExtractedEntity,
  ExtractedRelation,
  GraphEdge,
  GraphMetric,
  GraphNode,
  HotSkill,
  JobSearchResponse,
  JobTrendResponse,
  MatchResult,
  PlatformModule,
  RagAnswer
} from '../types/domain';

export type ViewKey =
  | 'dashboard'
  | 'collection'
  | 'storage'
  | 'nlp'
  | 'graph'
  | 'rag'
  | 'resume'
  | 'match'
  | 'analytics';

interface PlatformState {
  activeView: ViewKey;
  loading: boolean;
  modules: PlatformModule[];
  jobSearch: JobSearchResponse;
  hotSkills: HotSkill[];
  trend: JobTrendResponse;
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  graphMetrics: GraphMetric[];
  nlpEntities: ExtractedEntity[];
  nlpRelations: ExtractedRelation[];
  ragAnswer: RagAnswer;
  matchResult: MatchResult;
  lastQuery: JobSearchQuery;
}

export const usePlatformStore = defineStore('platform', {
  state: (): PlatformState => ({
    activeView: 'dashboard',
    loading: false,
    modules: platformModules,
    jobSearch: jobSearchMock,
    hotSkills: hotSkillsMock,
    trend: trendMock,
    graphNodes,
    graphEdges,
    graphMetrics,
    nlpEntities: extractedEntities,
    nlpRelations: extractedRelations,
    ragAnswer: ragAnswerMock,
    matchResult: matchMock,
    lastQuery: { page: 1, page_size: 10 }
  }),

  getters: {
    abilityScore: () => Math.round(abilityMetrics.reduce((sum, item) => sum + item.value, 0) / abilityMetrics.length),
    onlineModuleCount: (state) => state.modules.filter((module) => module.state === 'online').length,
    moduleStateText: (state) => {
      const warning = state.modules.filter((module) => module.state === 'warning').length;
      const mock = state.modules.filter((module) => module.state === 'mock').length;
      return `${state.modules.length} 个模块，${warning} 个待接入，${mock} 个演示态`;
    }
  },

  actions: {
    setView(view: ViewKey) {
      this.activeView = view;
    },

    async bootstrap() {
      this.loading = true;
      try {
        const [modules, jobs, skills, trend] = await Promise.all([
          platformApi.loadModules(),
          platformApi.searchJobs({ page: 1, page_size: 10 }),
          platformApi.loadSkillAnalysis(),
          platformApi.loadJobTrend()
        ]);
        this.modules = modules;
        this.jobSearch = jobs;
        this.hotSkills = skills;
        this.trend = trend;
      } finally {
        this.loading = false;
      }
    },

    async searchJobs(query: JobSearchQuery) {
      this.loading = true;
      this.lastQuery = query;
      try {
        this.jobSearch = await platformApi.searchJobs(query);
      } finally {
        this.loading = false;
      }
    },

    async refreshAnalytics() {
      this.loading = true;
      try {
        const [skills, trend] = await Promise.all([platformApi.loadSkillAnalysis(), platformApi.loadJobTrend()]);
        this.hotSkills = skills;
        this.trend = trend;
      } finally {
        this.loading = false;
      }
    },

    async analyzeText(text: string) {
      this.loading = true;
      try {
        const result = await platformApi.analyzeText(text);
        this.nlpEntities = result.entities;
        this.nlpRelations = result.relations;
      } finally {
        this.loading = false;
      }
    },

    async askRag(query: string) {
      this.loading = true;
      try {
        this.ragAnswer = await platformApi.askRag(query);
      } finally {
        this.loading = false;
      }
    },

    async runMatch(targetJobId: string, resumeText: string) {
      this.loading = true;
      try {
        this.matchResult = await platformApi.matchResume(targetJobId, resumeText);
      } finally {
        this.loading = false;
      }
    },

    simulateCollectionBoost() {
      this.modules = this.modules.map((module) =>
        module.key === 'crawler'
          ? { ...module, state: 'online', value: '13,420', latency: 'P95 1.8s' }
          : module
      );
    },

    parsedResume() {
      return resumeProfile;
    }
  }
});

export { abilityMetrics, resumeProfile, skillDemands };
