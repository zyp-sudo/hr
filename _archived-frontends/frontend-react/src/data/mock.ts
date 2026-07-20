import type { AbilityScore, HeatmapPoint, JobMatch, LearningStage, SkillRank, TalentGap, TrendPoint } from '../types/domain';

export const abilityScore = 82;

export const abilityRadar: AbilityScore[] = [
  { label: '数据建模', value: 86, benchmark: 78 },
  { label: '工程实现', value: 76, benchmark: 72 },
  { label: '业务理解', value: 88, benchmark: 80 },
  { label: 'AI工具', value: 72, benchmark: 84 },
  { label: '沟通协同', value: 91, benchmark: 76 },
  { label: '系统设计', value: 68, benchmark: 74 }
];

export const skillRanks: SkillRank[] = [
  { name: 'SQL', score: 94, status: 'owned', demand: 92 },
  { name: 'Python', score: 88, status: 'owned', demand: 89 },
  { name: 'Tableau', score: 84, status: 'owned', demand: 72 },
  { name: '机器学习', score: 70, status: 'learning', demand: 86 },
  { name: 'RAG', score: 52, status: 'gap', demand: 91 },
  { name: 'A/B实验', score: 64, status: 'learning', demand: 76 }
];

export const jobMatches: JobMatch[] = [
  {
    id: 'job-1',
    title: '高级数据分析师',
    company: '星河智能',
    matchRate: 91,
    salary: '25-35K',
    city: '上海',
    matchedSkills: ['SQL', 'Python', 'Tableau', '业务分析'],
    missingSkills: ['因果推断', 'RAG'],
    learningPath: ['补齐因果推断案例', '完成RAG指标分析项目', '沉淀一份业务诊断报告']
  },
  {
    id: 'job-2',
    title: 'AI产品数据分析',
    company: '澜舟科技',
    matchRate: 84,
    salary: '22-32K',
    city: '北京',
    matchedSkills: ['SQL', 'A/B实验', '用户增长'],
    missingSkills: ['LLM评测', 'Prompt分析'],
    learningPath: ['学习LLM评测指标', '做一个Prompt效果对比看板', '补充AI产品案例']
  },
  {
    id: 'job-3',
    title: '商业智能BI工程师',
    company: '云策数据',
    matchRate: 78,
    salary: '20-28K',
    city: '深圳',
    matchedSkills: ['SQL', '数据仓库', 'Tableau'],
    missingSkills: ['指标体系治理', 'Airflow'],
    learningPath: ['搭建指标字典', '完成调度链路项目', '优化可视化组件规范']
  }
];

export const growthTrend: TrendPoint[] = [
  { month: '1月', score: 62, marketDemand: 70 },
  { month: '2月', score: 66, marketDemand: 72 },
  { month: '3月', score: 71, marketDemand: 75 },
  { month: '4月', score: 76, marketDemand: 79 },
  { month: '5月', score: 79, marketDemand: 82 },
  { month: '6月', score: 82, marketDemand: 85 }
];

export const learningStages: LearningStage[] = [
  {
    stage: 'Stage 01',
    title: '分析基础强化',
    skills: ['SQL窗口函数', 'Python数据处理', '统计假设检验'],
    duration: '2周',
    outcome: '能独立完成指标拆解和数据清洗'
  },
  {
    stage: 'Stage 02',
    title: '业务实验能力',
    skills: ['A/B实验', '因果推断', '用户分层'],
    duration: '3周',
    outcome: '能设计实验并评估策略收益'
  },
  {
    stage: 'Stage 03',
    title: 'AI分析增强',
    skills: ['RAG', 'LLM评测', 'Prompt分析'],
    duration: '4周',
    outcome: '能分析AI产品效果并形成优化建议'
  },
  {
    stage: 'Stage 04',
    title: '高阶岗位作品集',
    skills: ['行业诊断报告', '可视化叙事', '面试案例复盘'],
    duration: '2周',
    outcome: '形成可投递的岗位匹配证据'
  }
];

export const heatmapData: HeatmapPoint[] = [
  { industry: '互联网', skill: 'SQL', value: 94 },
  { industry: '互联网', skill: 'RAG', value: 83 },
  { industry: '互联网', skill: 'A/B实验', value: 91 },
  { industry: '金融', skill: 'SQL', value: 88 },
  { industry: '金融', skill: '风控建模', value: 95 },
  { industry: '金融', skill: 'Python', value: 82 },
  { industry: '制造', skill: '数据仓库', value: 76 },
  { industry: '制造', skill: '预测模型', value: 79 },
  { industry: '医疗', skill: '机器学习', value: 84 },
  { industry: '医疗', skill: '隐私计算', value: 72 }
];

export const talentGaps: TalentGap[] = [
  { role: 'AI数据分析师', demand: 128, supply: 76, gap: 52 },
  { role: 'BI工程师', demand: 96, supply: 82, gap: 14 },
  { role: '增长分析师', demand: 104, supply: 68, gap: 36 },
  { role: '风控建模分析', demand: 88, supply: 54, gap: 34 }
];
