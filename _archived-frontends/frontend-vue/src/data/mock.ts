import type {
  AbilityMetric,
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
  RagAnswer,
  ResumeProfile,
  SkillDemand
} from '../types/domain';

export const platformModules: PlatformModule[] = [
  {
    key: 'crawler',
    name: '数据采集',
    stack: 'Scrapy + Playwright',
    state: 'mock',
    metric: '今日入库',
    value: '12,860',
    latency: 'P95 2.1s',
    description: '静态站点走 Scrapy，动态渲染岗位页走 Playwright，代理池与节流策略已预留。'
  },
  {
    key: 'storage',
    name: '数据存储',
    stack: 'MySQL + Elasticsearch',
    state: 'warning',
    metric: '岗位索引',
    value: '100k+',
    latency: 'ES 38ms',
    description: 'MySQL 保存强一致业务数据，ES 支持全文检索、聚合与岗位趋势。'
  },
  {
    key: 'nlp',
    name: 'NLP处理',
    stack: 'HanLP / LAC + 讯飞星火API',
    state: 'mock',
    metric: '实体召回',
    value: '91.6%',
    latency: 'LLM 860ms',
    description: '基础分词与 NER 本地处理，复杂语义、关系抽取走星火大模型。'
  },
  {
    key: 'kg',
    name: '知识图谱',
    stack: 'Neo4j + py2neo',
    state: 'online',
    metric: '图谱节点',
    value: '18,420',
    latency: 'Cypher 72ms',
    description: '岗位、技能、企业、简历形成图结构，支持路径推理与能力缺口发现。'
  },
  {
    key: 'rag',
    name: 'RAG框架',
    stack: 'LangChain + ChromaDB',
    state: 'mock',
    metric: '向量片段',
    value: '46,500',
    latency: 'Recall 0.82',
    description: '检索岗位JD、学习资源和简历证据，增强匹配解释和学习路线生成。'
  },
  {
    key: 'analysis',
    name: '数据分析',
    stack: 'Pandas + NetworkX',
    state: 'online',
    metric: '缺口岗位',
    value: '238',
    latency: 'Batch 4min',
    description: 'Pandas 做清洗统计，NetworkX 做中心性、社区发现和岗位关联分析。'
  }
];

export const abilityMetrics: AbilityMetric[] = [
  { name: '数据建模', value: 86, benchmark: 78 },
  { name: '工程实现', value: 79, benchmark: 74 },
  { name: '业务理解', value: 88, benchmark: 80 },
  { name: 'AI增强分析', value: 72, benchmark: 84 },
  { name: '可视化表达', value: 82, benchmark: 77 },
  { name: '系统设计', value: 75, benchmark: 79 }
];

export const skillDemands: SkillDemand[] = [
  { skill: 'Python', demand: 94, owned: 88, gap: 6, category: '编程' },
  { skill: 'SQL', demand: 92, owned: 90, gap: 2, category: '数据' },
  { skill: 'Elasticsearch', demand: 86, owned: 63, gap: 23, category: '检索' },
  { skill: 'Neo4j', demand: 82, owned: 58, gap: 24, category: '图谱' },
  { skill: 'RAG', demand: 91, owned: 52, gap: 39, category: 'AI' },
  { skill: 'HanLP', demand: 76, owned: 64, gap: 12, category: 'NLP' },
  { skill: 'FastAPI', demand: 84, owned: 80, gap: 4, category: '后端' },
  { skill: 'Pandas', demand: 89, owned: 86, gap: 3, category: '分析' }
];

export const jobSearchMock: JobSearchResponse = {
  total: 1286,
  page: 1,
  page_size: 10,
  source: 'mock',
  items: [
    {
      id: 'job-ai-001',
      title: 'AI数据分析师',
      company_name: '星河智能科技',
      city: '上海',
      industry: '人工智能',
      education: '本科',
      experience: '3-5年',
      salary_min: 25,
      salary_max: 38,
      skills: ['Python', 'SQL', 'RAG', 'ECharts', '业务分析'],
      published_at: '2026-07-07',
      source: 'BOSS直聘',
      matchRate: 91
    },
    {
      id: 'job-kg-002',
      title: '知识图谱工程师',
      company_name: '云策数据',
      city: '北京',
      industry: '企业服务',
      education: '本科',
      experience: '3-5年',
      salary_min: 28,
      salary_max: 42,
      skills: ['Neo4j', 'py2neo', 'NLP', '实体识别', '图算法'],
      published_at: '2026-07-06',
      source: '猎聘',
      matchRate: 84
    },
    {
      id: 'job-es-003',
      title: '搜索推荐后端工程师',
      company_name: '澜舟科技',
      city: '深圳',
      industry: '互联网',
      education: '本科',
      experience: '5-10年',
      salary_min: 32,
      salary_max: 50,
      skills: ['Elasticsearch', 'FastAPI', 'MySQL', '推荐系统', '向量检索'],
      published_at: '2026-07-06',
      source: '企业官网',
      matchRate: 79
    },
    {
      id: 'job-rag-004',
      title: 'RAG应用架构师',
      company_name: '明辰AI平台',
      city: '杭州',
      industry: '大模型应用',
      education: '硕士',
      experience: '5-10年',
      salary_min: 40,
      salary_max: 65,
      skills: ['LangChain', 'ChromaDB', 'Prompt工程', 'Python', '服务编排'],
      published_at: '2026-07-05',
      source: '拉勾',
      matchRate: 73
    }
  ],
  aggregations: {
    cities: [
      { key: '上海', count: 318 },
      { key: '北京', count: 276 },
      { key: '深圳', count: 242 },
      { key: '杭州', count: 198 }
    ],
    industries: [
      { key: '人工智能', count: 356 },
      { key: '企业服务', count: 214 },
      { key: '互联网', count: 268 },
      { key: '金融科技', count: 188 }
    ],
    skills: [
      { key: 'Python', count: 812 },
      { key: 'SQL', count: 754 },
      { key: 'Elasticsearch', count: 426 },
      { key: 'Neo4j', count: 318 },
      { key: 'RAG', count: 292 }
    ],
    educations: [
      { key: '本科', count: 912 },
      { key: '硕士', count: 248 },
      { key: '大专', count: 126 }
    ],
    experiences: [
      { key: '1-3年', count: 338 },
      { key: '3-5年', count: 506 },
      { key: '5-10年', count: 342 }
    ],
    salary_ranges: [
      { key: '20-30K', count: 402 },
      { key: '30-50K', count: 518 },
      { key: '50K+', count: 126 }
    ]
  }
};

export const hotSkillsMock: HotSkill[] = [
  { skill: 'Python', count: 812, related_job_count: 768 },
  { skill: 'SQL', count: 754, related_job_count: 721 },
  { skill: 'Elasticsearch', count: 426, related_job_count: 398 },
  { skill: 'FastAPI', count: 384, related_job_count: 351 },
  { skill: 'Neo4j', count: 318, related_job_count: 292 },
  { skill: 'RAG', count: 292, related_job_count: 268 },
  { skill: 'HanLP', count: 186, related_job_count: 159 },
  { skill: 'Playwright', count: 174, related_job_count: 148 }
];

export const trendMock: JobTrendResponse = {
  source: 'mock',
  by_date: [
    { key: '07-01', count: 138 },
    { key: '07-02', count: 164 },
    { key: '07-03', count: 172 },
    { key: '07-04', count: 151 },
    { key: '07-05', count: 186 },
    { key: '07-06', count: 214 },
    { key: '07-07', count: 261 }
  ],
  by_city: [
    { key: '上海', count: 318 },
    { key: '北京', count: 276 },
    { key: '深圳', count: 242 },
    { key: '杭州', count: 198 },
    { key: '广州', count: 132 }
  ],
  by_industry: [
    { key: '人工智能', count: 356 },
    { key: '互联网', count: 268 },
    { key: '企业服务', count: 214 },
    { key: '金融科技', count: 188 },
    { key: '智能制造', count: 144 }
  ]
};

export const graphNodes: GraphNode[] = [
  { id: 'user', label: '候选人', type: 'user', score: 82 },
  { id: 'python', label: 'Python', type: 'skill-owned', score: 88 },
  { id: 'sql', label: 'SQL', type: 'skill-owned', score: 90 },
  { id: 'fastapi', label: 'FastAPI', type: 'skill-owned', score: 80 },
  { id: 'rag', label: 'RAG', type: 'skill-gap', score: 52 },
  { id: 'neo4j', label: 'Neo4j', type: 'skill-gap', score: 58 },
  { id: 'spark', label: '讯飞星火API', type: 'skill-learning', score: 61 },
  { id: 'playwright', label: 'Playwright', type: 'skill-learning', score: 66 },
  { id: 'job-ai', label: 'AI数据分析师', type: 'job', score: 91 },
  { id: 'job-kg', label: '知识图谱工程师', type: 'job', score: 84 },
  { id: 'company-a', label: '星河智能', type: 'company' },
  { id: 'company-b', label: '云策数据', type: 'company' },
  { id: 'mysql', label: 'MySQL业务库', type: 'data' },
  { id: 'es', label: 'ES搜索索引', type: 'data' },
  { id: 'spark-model', label: '语义抽取链', type: 'model' }
];

export const graphEdges: GraphEdge[] = [
  { source: 'user', target: 'python', label: '已具备' },
  { source: 'user', target: 'sql', label: '已具备' },
  { source: 'user', target: 'fastapi', label: '已具备' },
  { source: 'user', target: 'rag', label: '待提升' },
  { source: 'user', target: 'neo4j', label: '待提升' },
  { source: 'user', target: 'spark', label: '学习中' },
  { source: 'user', target: 'playwright', label: '学习中' },
  { source: 'rag', target: 'job-ai', label: '岗位要求' },
  { source: 'python', target: 'job-ai', label: '核心技能' },
  { source: 'sql', target: 'job-ai', label: '核心技能' },
  { source: 'neo4j', target: 'job-kg', label: '岗位要求' },
  { source: 'spark', target: 'job-kg', label: '语义抽取' },
  { source: 'job-ai', target: 'company-a', label: '招聘方' },
  { source: 'job-kg', target: 'company-b', label: '招聘方' },
  { source: 'mysql', target: 'es', label: '同步' },
  { source: 'spark-model', target: 'neo4j', label: '关系写入' }
];

export const extractedEntities: ExtractedEntity[] = [
  { text: 'Python', type: '技能', confidence: 0.98 },
  { text: 'Elasticsearch', type: '技能', confidence: 0.95 },
  { text: '知识图谱工程师', type: '岗位', confidence: 0.93 },
  { text: '本科', type: '学历', confidence: 0.88 },
  { text: '上海', type: '地点', confidence: 0.91 }
];

export const extractedRelations: ExtractedRelation[] = [
  { source: '知识图谱工程师', relation: '要求技能', target: 'Neo4j', confidence: 0.94 },
  { source: '知识图谱工程师', relation: '要求技能', target: '实体识别', confidence: 0.91 },
  { source: 'AI数据分析师', relation: '补齐能力', target: 'RAG', confidence: 0.86 },
  { source: 'Elasticsearch', relation: '支撑能力', target: '全文检索', confidence: 0.93 }
];

export const ragAnswerMock: RagAnswer = {
  query: '我适合投 AI 数据分析师还是知识图谱工程师？',
  answer:
    '当前更适合优先投递 AI 数据分析师，匹配证据集中在 Python、SQL、指标分析和 FastAPI 服务化能力。知识图谱工程师可以作为 4-6 周后的进阶目标，建议补齐 Neo4j、Cypher、实体关系抽取和图算法项目证据。',
  chunks: [
    {
      id: 'chunk-1',
      title: '岗位JD：AI数据分析师',
      score: 0.91,
      source: 'Elasticsearch/job_index',
      content: '岗位强调 Python、SQL、业务指标、A/B 实验和 AI 工具增强分析能力。'
    },
    {
      id: 'chunk-2',
      title: '简历证据：数据平台项目',
      score: 0.86,
      source: 'ChromaDB/resume_chunks',
      content: '候选人完成过 FastAPI 数据服务、ECharts 看板和数据清洗链路。'
    },
    {
      id: 'chunk-3',
      title: '学习资源：Neo4j入门路线',
      score: 0.78,
      source: 'ChromaDB/learning_docs',
      content: '建议从 Cypher 查询、图数据建模、路径分析和社区发现开始。'
    }
  ]
};

export const resumeProfile: ResumeProfile = {
  name: '周同学',
  title: '数据分析 / AI应用方向',
  education: '本科 · 计算机科学',
  years: '3年项目经验',
  intent: 'AI数据分析师、知识图谱工程师、搜索推荐后端',
  skills: ['Python', 'SQL', 'FastAPI', 'ECharts', 'Pandas', 'Elasticsearch'],
  projects: ['岗位数据采集与清洗平台', '能力图谱可视化系统', '人岗匹配推荐原型']
};

export const matchMock: MatchResult = {
  targetJobId: 'job-ai-001',
  targetJobName: 'AI数据分析师',
  matchScore: 91,
  matchedSkills: ['Python', 'SQL', 'FastAPI', 'Pandas', '业务分析'],
  missingSkills: ['RAG评测', 'Prompt分析', '因果推断'],
  learningPath: [
    '第1周：完成 RAG 基础链路，使用 ChromaDB 构建岗位知识库。',
    '第2周：补一个 Prompt 效果评估看板，沉淀指标口径。',
    '第3周：用真实岗位数据做一次人岗匹配复盘报告。'
  ],
  aiAnalysis:
    '候选人的数据处理和工程实现基础较好，适合先投 AI 数据分析师。短板主要在大模型应用解释、RAG评测和高级实验方法，需要用项目证据补齐。',
  source: 'mock'
};

export const graphMetrics: GraphMetric[] = [
  { name: '技能中心性最高', value: 0.84, detail: 'Python 连接岗位、项目和学习路径最多' },
  { name: '最大能力缺口', value: 39, detail: 'RAG 与岗位需求差距最大' },
  { name: '岗位社区数量', value: 6, detail: 'AI分析、图谱工程、搜索推荐等社区明显' },
  { name: '学习路径覆盖率', value: 78, detail: '已为大部分缺口生成可执行路径' }
];
