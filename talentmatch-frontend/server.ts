import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI, Type } from "@google/genai";
import dotenv from "dotenv";
import multer from "multer";
import mammoth from "mammoth";
import { PDFParse } from "pdf-parse";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import { mkdirSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";

dotenv.config({ path: ".env.local" });
dotenv.config();

const jobs = [
  { id: "backend", title: "高级后端工程师", description: "负责核心高并发服务架构设计与稳定性建设。", requirements: ["5年以上 Java/Go 开发经验", "熟悉分布式系统与云原生技术", "具备大型系统架构和性能优化经验"] },
  { id: "ai", title: "AI 算法工程师", description: "负责大语言模型、RAG 与智能应用研发。", requirements: ["熟悉 Python 与 PyTorch", "具有大模型微调或部署经验", "理解 RAG、Agent 与向量检索"] },
  { id: "frontend", title: "资深前端工程师", description: "负责企业级前端架构与数据可视化体验。", requirements: ["精通 React 与 TypeScript", "掌握前端工程化与性能优化", "具有复杂中后台项目经验"] },
  { id: "product", title: "高级产品经理", description: "负责 AI 招聘产品规划、需求分析与交付。", requirements: ["4年以上 B 端产品经验", "具备业务建模与数据分析能力", "熟悉 AI 产品落地流程"] },
];

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    const allowed = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword", "text/plain", "text/markdown"];
    cb(null, allowed.includes(file.mimetype) || /\.(pdf|docx?|txt|md)$/i.test(file.originalname));
  },
});

type Assessment = {
  id: string; createdAt: string; jobId: string; jobTitle: string; candidateName?: string;
  score: number; matchLevel: string; radar: Record<string, number>;
  experienceMatch: { relevance: number; alignment: number }; skillGaps: string[]; highlights: string[];
};
const assessmentSamples=():Assessment[]=>[
  {id:"sample-linchen",createdAt:new Date(Date.now()-35*60000).toISOString(),jobId:"backend",jobTitle:"高级后端工程师",candidateName:"林晨",score:91,matchLevel:"样本 · 卓越匹配",radar:{technical:94,experience:90,collaboration:84,education:78,softSkills:86},experienceMatch:{relevance:93,alignment:89},skillGaps:["Kubernetes","服务网格"],highlights:["Java、Go 与分布式系统经验覆盖核心岗位要求","具备复杂项目交付和性能优化经验"]},
  {id:"sample-zhouning",createdAt:new Date(Date.now()-75*60000).toISOString(),jobId:"ai",jobTitle:"AI 算法工程师",candidateName:"周宁",score:89,matchLevel:"样本 · 优秀匹配",radar:{technical:92,experience:83,collaboration:80,education:88,softSkills:82},experienceMatch:{relevance:91,alignment:86},skillGaps:["推理加速","模型评测体系"],highlights:["具备 LLM、RAG 与 PyTorch 项目经验","硕士学历与算法岗位研究要求匹配"]},
  {id:"sample-anonymous",createdAt:new Date(Date.now()-130*60000).toISOString(),jobId:"frontend",jobTitle:"资深前端工程师",candidateName:"匿名候选人",score:82,matchLevel:"样本 · 良好匹配",radar:{technical:86,experience:74,collaboration:86,education:76,softSkills:84},experienceMatch:{relevance:84,alignment:78},skillGaps:["大型前端架构","性能监控"],highlights:["React、TypeScript 和可视化技能匹配","团队协作证据较完整"]},
];
const history: Assessment[] = assessmentSamples();
const projectRoot = path.resolve(process.cwd(), "..");
const hrStatePath = path.join(projectRoot, "data", "hr_state.json");
const databasePath = path.join(process.cwd(),"data","talentmatch.sqlite");
mkdirSync(path.dirname(databasePath),{recursive:true});
const database=new DatabaseSync(databasePath);
database.exec("CREATE TABLE IF NOT EXISTS trend_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, fetched_at TEXT NOT NULL, payload_json TEXT NOT NULL)");
const latestTrend=database.prepare("SELECT payload_json, fetched_at FROM trend_snapshots WHERE job_id = ? ORDER BY id DESC LIMIT 1");
const saveTrend=database.prepare("INSERT INTO trend_snapshots (job_id, fetched_at, payload_json) VALUES (?, ?, ?)");
type HrState = { candidates:Array<Record<string,any>>; interviews:Array<Record<string,any>>; jobs:Array<Record<string,any>>; favorites:string[]; interviewTags?:Array<Record<string,any>>; notifications?:Array<Record<string,any>> };
// ── Write lock to prevent concurrent hr_state.json writes ──
let writeLock = Promise.resolve();
function lockedWrite(fn:()=>Promise<void>){writeLock=writeLock.then(fn,fn);return writeLock}
const initialHrState:HrState = {
  candidates:[
    {id:"candidate-linchen",name:"林晨",email:"linchen@example.com",phone:"138****1024",stage:"待评估",skills:["Java","Go","Redis","微服务"],experienceYears:6,education:"本科",projectScore:88,collaborationScore:84,createdAt:new Date().toISOString()},
    {id:"candidate-zhouning",name:"周宁",email:"zhouning@example.com",phone:"139****3078",stage:"待面试",skills:["Python","LLM","RAG","PyTorch","SQL"],experienceYears:4,education:"硕士",projectScore:92,collaborationScore:80,createdAt:new Date().toISOString()},
    {id:"candidate-anonymous",name:"匿名候选人",email:"",phone:"",stage:"待评估",skills:["React","TypeScript","可视化"],experienceYears:3,education:"本科",projectScore:76,collaborationScore:86,createdAt:new Date().toISOString()},
  ],
  interviews:[{id:"interview-1",candidateId:"candidate-zhouning",candidateName:"周宁",jobId:"ai",jobTitle:"AI 算法工程师",title:"周宁 · 技术一面",startsAt:new Date(Date.now()+86400000).toISOString(),endsAt:new Date(Date.now()+86400000+3600000).toISOString(),timezone:"Asia/Shanghai",format:"视频",customFormat:"",location:"",meetingUrl:"",interviewers:["技术面试官"],round:"技术一面",customRound:"",status:"scheduled",priority:"important",customPriority:"",tagIds:[],focusAreas:["系统设计","项目深度"],questions:[],internalNotes:"",candidateNotes:"",contactStatus:"not_contacted",reminderMinutes:30,isPinned:false,createdAt:new Date(Date.now()-86400000).toISOString(),updatedAt:new Date().toISOString()}],
  jobs:[],
  favorites:[],
  interviewTags:[
    {id:"tag-priority",name:"重点",color:"#f59e0b",createdAt:new Date().toISOString()},
    {id:"tag-tech",name:"技术面",color:"#3b82f6",createdAt:new Date().toISOString()},
    {id:"tag-hr",name:"HR面",color:"#10b981",createdAt:new Date().toISOString()},
    {id:"tag-review",name:"需复核",color:"#ef4444",createdAt:new Date().toISOString()},
    {id:"tag-urgent",name:"紧急",color:"#dc2626",createdAt:new Date().toISOString()},
  ],
  notifications:[],
};
async function readHrState():Promise<HrState>{try{const raw=JSON.parse(await fs.readFile(hrStatePath,"utf8"));const saved={...initialHrState,...raw,favorites:Array.isArray(raw.favorites)?raw.favorites:[],candidates:(raw.candidates||initialHrState.candidates).map((c:any)=>({...initialHrState.candidates.find(x=>x.id===c.id),...c})),interviewTags:raw.interviewTags||initialHrState.interviewTags||[],notifications:raw.notifications||initialHrState.notifications||[]};// Normalize interviews
saved.interviews=(saved.interviews||[]).map((iv:any)=>normalizeInterview(iv,saved.candidates));// Rebuild notifications
saved.notifications=buildNotifications(saved.interviews,saved.candidates,saved.notifications);return saved}catch{return initialHrState}}
async function writeHrState(state:HrState){await fs.mkdir(path.dirname(hrStatePath),{recursive:true});await fs.writeFile(hrStatePath,JSON.stringify(state,null,2),"utf8")}

// ── Interview normalizer: convert legacy fields to new structure ────────────
const STATUS_MAP:Record<string,string>={"待进行":"scheduled","待安排":"pending","已安排":"scheduled","进行中":"in_progress","已完成":"completed","已取消":"cancelled"};
function normalizeInterview(raw:Record<string,any>,candidates:Array<Record<string,any>>):Record<string,any>{
  const candidate=candidates.find(c=>c.id===raw.candidateId)||{name:raw.candidateName||"匿名候选人"};
  const now=new Date().toISOString();
  // merge legacy scheduledAt / single interviewer / tags / notes
  const startsAt=raw.startsAt||raw.scheduledAt||now;
  const endsAt=raw.endsAt||(raw.startsAt?new Date(new Date(raw.startsAt).getTime()+3600000).toISOString():new Date(Date.now()+3600000).toISOString());
  const interviewers=Array.isArray(raw.interviewers)&&raw.interviewers.length?raw.interviewers:(raw.interviewer?[raw.interviewer]:["待分配"]);
  const tagIds=Array.isArray(raw.tagIds)?raw.tagIds:Array.isArray(raw.tags)?[]:[];
  return {
    id:raw.id||crypto.randomUUID(),
    candidateId:raw.candidateId||"",
    candidateName:candidate.name||raw.candidateName||"匿名候选人",
    jobId:raw.jobId||"",
    jobTitle:raw.jobTitle||"待定岗位",
    title:raw.title||`${candidate.name||raw.candidateName||"候选人"} · ${raw.round||raw.jobTitle||"面试"}`,
    startsAt, endsAt,
    timezone:raw.timezone||"Asia/Shanghai",
    format:raw.format||"视频",
    customFormat:raw.customFormat||"",
    location:raw.location||"",
    meetingUrl:raw.meetingUrl||"",
    interviewers,
    round:raw.round||"初试",
    customRound:raw.customRound||"",
    status:STATUS_MAP[raw.status]||raw.status||"scheduled",
    priority:raw.priority||"普通",
    customPriority:raw.customPriority||"",
    tagIds,
    focusAreas:Array.isArray(raw.focusAreas)?raw.focusAreas:[],
    questions:Array.isArray(raw.questions)?raw.questions:[],
    internalNotes:raw.internalNotes||raw.notes||"",
    candidateNotes:raw.candidateNotes||"",
    contactStatus:raw.contactStatus||"not_contacted",
    reminderMinutes:typeof raw.reminderMinutes==="number"?raw.reminderMinutes:30,
    isPinned:Boolean(raw.isPinned),
    createdAt:raw.createdAt||now,
    updatedAt:raw.updatedAt||now,
  };
}

// ── Generate notifications from interviews ──────────────────────────────────
function buildNotifications(interviews:Array<Record<string,any>>,candidates:Array<Record<string,any>>,existing:Array<Record<string,any>>):Array<Record<string,any>>{
  const now=Date.now();
  const upcoming=interviews.filter(iv=>{
    const s=STATUS_MAP[iv.status]||iv.status;
    return s==="scheduled"||s==="in_progress";
  });
  return upcoming.map(iv=>{
    const startsAt=new Date(iv.startsAt||iv.scheduledAt||0).getTime();
    const diff=startsAt-now;
    const isSoon=diff>0&&diff<3600000; // within 1 hour
    const existingNote=existing.find(n=>n.target?.interviewId===iv.id);
    return {
      id:existingNote?.id||`notif-${iv.id}`,
      type:"interview" as const,
      title:isSoon?`即将开始：${iv.candidateName} ${iv.round||""}`.trim():`面试安排：${iv.candidateName}`,
      detail:`${iv.jobTitle||""} · ${new Date(iv.startsAt||iv.scheduledAt).toLocaleString("zh-CN",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false})}`,
      time:iv.updatedAt||iv.createdAt||new Date().toISOString(),
      readAt:existingNote?.readAt||null,
      target:{page:"interviews",interviewId:iv.id,candidateId:iv.candidateId},
    };
  });
}

async function localEvolution(jobId:string){const [trendText,jobText]=await Promise.all([fs.readFile(path.join(projectRoot,"data","evolution.csv"),"utf8"),fs.readFile(path.join(projectRoot,"data","jobs.csv"),"utf8")]);const trendRows=trendText.trim().split(/\r?\n/).slice(1).map(line=>{const [id,period,skill,demand]=line.split(",");return {jobId:id,period,skill,demand:Number(demand),sourceCount:1}});const jobRows=jobText.trim().split(/\r?\n/).slice(1).map(line=>{const [id,name]=line.split(",");return {roleId:id,role:name,recordCount:trendRows.filter(row=>row.jobId===id).length}});const selected=trendRows.filter(row=>row.jobId===jobId);const fallback=selected.length?selected:trendRows.filter(row=>row.jobId===jobRows[0]?.roleId);const activeId=selected.length?jobId:jobRows[0]?.roleId;return {title:jobRows.find(row=>row.roleId===activeId)?.role||"岗位技能需求趋势",jobId:activeId,roleOptions:jobRows,series:fallback,seriesCount:fallback.length,source:"data/evolution.csv"}}
async function captureTalentVector(candidate:Record<string,any>){try{const response=await fetch(`${process.env.STORAGE_API_URL||"http://127.0.0.1:8080"}/api/talent-vectors/upsert`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(candidate),signal:AbortSignal.timeout(1800)});return response.ok?{status:"stored"}:{status:"unavailable",httpStatus:response.status}}catch{return {status:"unavailable"}}}

let crawlerState = { status:"idle", startedAt:"", finishedAt:"", message:"尚未执行采集", pid:0 };
let runtimeAi = { provider:process.env.AI_PROVIDER||"google", model:process.env.GEMINI_MODEL||"gemini-2.5-flash", baseUrl:process.env.AI_BASE_URL||"", apiKey:process.env.GEMINI_API_KEY||"" };

const clamp = (value: unknown, fallback = 80) => Math.max(0, Math.min(100, Number(value) || fallback));
const normalize = (value: any, job: typeof jobs[number]): Assessment => ({
  id: crypto.randomUUID(), createdAt: new Date().toISOString(), jobId: job.id, jobTitle: job.title,
  candidateName: typeof value.candidateName === "string" ? value.candidateName : undefined,
  score: clamp(value.score), matchLevel: String(value.matchLevel || "良好匹配"),
  radar: {
    technical: clamp(value.radar?.technical), experience: clamp(value.radar?.experience),
    collaboration: clamp(value.radar?.collaboration), education: clamp(value.radar?.education), softSkills: clamp(value.radar?.softSkills),
  },
  experienceMatch: { relevance: clamp(value.experienceMatch?.relevance), alignment: clamp(value.experienceMatch?.alignment) },
  skillGaps: Array.isArray(value.skillGaps) ? value.skillGaps.slice(0, 5).map(String) : [],
  highlights: Array.isArray(value.highlights) ? value.highlights.slice(0, 5).map(String) : [],
});

function fallbackAssessment(job: typeof jobs[number], resumeText: string) {
  // ── 从岗位要求拆解关键词 ──
  const keywords = job.requirements
    .flatMap(r => r.split(/[、/，,]/).map(k => k.trim()))
    .filter(k => k.length > 2);
  const hitKeywords = keywords.filter(k =>
    resumeText.toLowerCase().includes(k.toLowerCase()),
  );
  const signalRate = keywords.length ? hitKeywords.length / keywords.length : 0;

  // ── 文本长度贡献：每 200 字 +1，上限 5（鼓励提交真实内容）──
  const textBonus = Math.min(5, Math.floor(resumeText.length / 200));

  // ── 技能覆盖贡献：0–55 分（核心维度）──
  const skillCoverage = Math.round(signalRate * 55);

  // ── 基础分：只有命中证据时才给 ──
  const baseScore = signalRate > 0 ? 20 : 0;

  // ── 组合：0–100 分 ──
  const score = Math.min(95, baseScore + skillCoverage + textBonus);

  // ── 等级 ──
  const matchLevel =
    score >= 80 ? "优秀匹配"
    : score >= 60 ? "良好匹配"
    : score >= 30 ? "待观察"
    : "差距较大";

  // ── 雷达：按信号率缩放，无证据的软维度不高于 50 ──
  const radarBase = Math.max(0, Math.round(score * 0.7));
  const hasSignals = signalRate > 0;
  return {
    score,
    matchLevel,
    radar: {
      technical: Math.min(95, radarBase + (hasSignals ? 10 : 0)),
      experience: Math.min(95, radarBase + (hasSignals ? 8 : 0)),
      collaboration: 50,
      education: 50,
      softSkills: 50,
    },
    experienceMatch: {
      relevance: Math.round(signalRate * 80),
      alignment: Math.round(signalRate * 75),
    },
    skillGaps: hasSignals
      ? keywords.filter(k => !resumeText.toLowerCase().includes(k.toLowerCase())).slice(0, 5)
      : ["未提供有效技能证据，无法进行缺口分析"],
    highlights: hasSignals
      ? [
          `候选人简历命中 ${hitKeywords.length}/${keywords.length} 项岗位关键词`,
          ...hitKeywords.slice(0, 3).map(k => `具备「${k}」相关经验`),
        ]
      : ["简历中未检测到与岗位要求匹配的关键技能"],
  };
}

const graphJobProfiles = [
  { id:"job1", title:"高级后端工程师", minYears:5, groups:[["Java","Go"],["微服务","分布式架构"],["Redis","MySQL"],["性能优化","高并发"]] },
  { id:"job2", title:"云原生工程师", minYears:4, groups:[["Kubernetes","K8s"],["Docker","容器"],["Go"],["微服务","云原生"]] },
  { id:"job3", title:"技术架构师", minYears:7, groups:[["分布式架构","系统设计"],["微服务"],["Java","Go"],["技术管理","架构"]] },
];
function fallbackJobFit(candidate:Record<string,any>,profile:typeof graphJobProfiles[number]){
  const evidence=`${(candidate.skills||[]).join(" ")} ${candidate.profileText||""}`.toLowerCase();
  const matched=profile.groups.filter(group=>group.some(skill=>evidence.includes(skill.toLowerCase()))).map(group=>group.join("/"));
  const gaps=profile.groups.filter(group=>!group.some(skill=>evidence.includes(skill.toLowerCase()))).map(group=>group[0]);
  const score=Math.round(Math.min(98,matched.length/profile.groups.length*58+Math.min(1,Number(candidate.experienceYears||0)/profile.minYears)*22+Number(candidate.projectScore||0)*.12+Number(candidate.collaborationScore||0)*.08));
  const start=(candidate.skills||[])[0]||"现有专业能力";const target=gaps[0]||"岗位核心能力";const bridge=target.includes("Kubernetes")?"容器与 Docker":target.includes("分布式")?"微服务与系统设计":target.includes("技术管理")?"架构决策与项目推动":target.includes("性能")?"性能监控与压测":"岗位项目实践";
  return {score,matched,gaps,path:gaps.length?[start,bridge,target]:[start,"复杂项目实践",profile.title],summary:score>=85?`核心技能和经验与${profile.title}高度契合，可优先进入后续招聘环节。`:score>=65?`具备部分可迁移能力，补充${gaps.slice(0,2).join("、")||"岗位实践"}后适配度会明显提升。`:`当前能力证据与${profile.title}要求存在较大距离，建议先核实项目深度和关键技能。`};
}
async function generateJobFit(candidate:Record<string,any>,profile:typeof graphJobProfiles[number]){
  const fallback=fallbackJobFit(candidate,profile);if(!runtimeAi.apiKey)return fallback;
  const prompt=`请基于候选人证据生成岗位适配分析，只返回 JSON，字段为 summary、matched、gaps、path。不要在文本中提及AI或模型。\n候选人：${JSON.stringify(candidate)}\n岗位：${profile.title}\n岗位能力组：${JSON.stringify(profile.groups)}\n基础量化结果：${JSON.stringify(fallback)}`;
  try{
    let text="";
    if(runtimeAi.provider==="google"){const ai=new GoogleGenAI({apiKey:runtimeAi.apiKey});const response=await ai.models.generateContent({model:runtimeAi.model,contents:prompt,config:{responseMimeType:"application/json"}});text=response.text||"{}"}
    else{const base=(runtimeAi.baseUrl||({deepseek:"https://api.deepseek.com",openai:"https://api.openai.com"} as Record<string,string>)[runtimeAi.provider]||"").replace(/\/$/,"");const response=await fetch(`${base}/v1/chat/completions`,{method:"POST",headers:{Authorization:`Bearer ${runtimeAi.apiKey}`,"Content-Type":"application/json"},body:JSON.stringify({model:runtimeAi.model,messages:[{role:"system",content:"你是招聘岗位适配分析专家，只返回JSON，不提及AI。输出summary、matched、gaps、path。业务分数不可修改。"},{role:"user",content:prompt}],response_format:{type:"json_object"}})});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data:any=await response.json();text=data.choices?.[0]?.message?.content||"{}"}
    const result=JSON.parse(text);return {...fallback,summary:String(result.summary||fallback.summary),matched:Array.isArray(result.matched)?result.matched.slice(0,5).map(String):fallback.matched,gaps:Array.isArray(result.gaps)?result.gaps.slice(0,5).map(String):fallback.gaps,path:Array.isArray(result.path)?result.path.slice(0,5).map(String):fallback.path}
  }catch{return fallback}
}

function extractResumeFields(text: string) {
  // Name extraction — look for Chinese name patterns
  const namePatterns = [
    /(?:姓名|名字|候选人|应聘者|求职者)[：:]\s*([^\n]{2,8})/,
    /^([^\n]{2,4})\n/,
    /(?:姓名[：:]?\s*)([一-龥]{2,4})/,
  ];
  let name = "";
  for (const pattern of namePatterns) {
    const match = text.match(pattern);
    if (match && match[1] && /^[一-龥a-zA-Z]{2,8}$/.test(match[1].trim())) {
      name = match[1].trim();
      break;
    }
  }

  // Skills extraction
  const skillKeywords = [
    "Java","Python","Go","C++","Rust","C#","JavaScript","TypeScript","React","Vue","Angular",
    "Node.js","Spring","Django","Flask","FastAPI","Kubernetes","K8s","Docker","AWS","Azure",
    "GCP","MySQL","PostgreSQL","MongoDB","Redis","Kafka","RabbitMQ","Elasticsearch","微服务",
    "分布式","机器学习","深度学习","NLP","LLM","RAG","PyTorch","TensorFlow","数据分析",
    "产品设计","项目管理","UI设计","Figma","Sketch","Photoshop","SQL","Linux","Git",
    "CI/CD","Jenkins","Terraform","Ansible","Spark","Hadoop","Flink","Hive","Scala",
    "PHP","Ruby","Shell","HTML","CSS","Sass","Webpack","Vite","Next.js","Nuxt",
    "GraphQL","gRPC","Protobuf","Nginx","Tomcat","系统设计","架构设计","性能优化",
  ];
  const found = skillKeywords.filter(s => {
    const lower = text.toLowerCase();
    return lower.includes(s.toLowerCase());
  });
  const skills = found.length ? found.slice(0, 8) : [];

  // Years extraction
  let years = 0;
  const yearsPatterns = [
    /(\d+)\s*(?:年|工作经验|工作年限|相关经验)/,
    /(?:工作经验|工作年限|从业)[：:]*\s*(\d+)/,
    /(\d+)\s*年\s*(?:以上|左右)?\s*(?:工作|开发|项目|从业)/,
  ];
  for (const pattern of yearsPatterns) {
    const match = text.match(pattern);
    if (match) { years = parseInt(match[1]); break; }
  }

  // Education extraction
  let education = "本科";
  if (/博士|Ph\.?D|博士研究生/.test(text)) education = "博士";
  else if (/硕士|研究生|MBA|EMBA/.test(text)) education = "硕士";
  else if (/专科|大专/.test(text)) education = "专科";
  else if (/高中|中专|职高/.test(text)) education = "高中及以下";
  else if (/本科|学士|Bachelor/i.test(text)) education = "本科";

  // Experience summary extraction
  let experience = "";
  const expPatterns = [
    /(?:工作经历|项目经历|项目经验|工作经验|工作履历)[：:\s]*([\s\S]{0,400}?)(?:\n\s*(?:教育|技能|证书|语言|自我评价|个人信息|联系方式|$))/i,
    /(?:经历|经验)[：:\s]*([\s\S]{0,400}?)(?:\n\s*(?:教育|技能|证书|$))/i,
  ];
  for (const pattern of expPatterns) {
    const match = text.match(pattern);
    if (match && match[1].trim().length > 10) {
      experience = match[1].trim().slice(0, 400);
      break;
    }
  }
  // Fallback: use first substantial paragraph
  if (!experience) {
    const firstParagraph = text.split(/\n\s*\n/).find(p => p.trim().length > 40);
    if (firstParagraph) experience = firstParagraph.trim().slice(0, 400);
  }

  return { name, skills: skills.slice(0, 8), years: String(years), education, experience };
}

async function extractText(file: Express.Multer.File) {
  const ext = path.extname(file.originalname).toLowerCase();
  if (ext === ".txt" || ext === ".md" || file.mimetype.startsWith("text/")) return file.buffer.toString("utf8");
  if (ext === ".docx") return (await mammoth.extractRawText({ buffer: file.buffer })).value;
  if (ext === ".pdf") {
    const parser = new PDFParse({ data: file.buffer });
    try { return (await parser.getText()).text; } finally { await parser.destroy(); }
  }
  throw Object.assign(new Error("暂不支持旧版 DOC，请转换为 DOCX、PDF 或 TXT"), { status: 415 });
}

async function startServer() {
  const app = express();
  const port = Number(process.env.PORT || 3000);
  app.use(express.json({ limit: "2mb" }));

  app.get("/api/health", (_req, res) => res.json({ status: "ok", aiConfigured: Boolean(runtimeAi.apiKey), aiProvider:runtimeAi.provider, aiModel:runtimeAi.model, time: new Date().toISOString() }));
  const proxyPlatform = (baseUrl: string) => async (req: express.Request, res: express.Response) => {
    try {
      // Unwrap nested proxy format from the frontend:
      //   POST /api/platform/storage  { url, method, body }
      // becomes:
      //   POST $baseUrl/$url            body
      const body: any = req.body || {};
      const isWrapped = typeof body.url === "string" && body.method;
      const forwardPath: string = (isWrapped ? body.url : req.url).replace(/^\/api\/platform\/storage/, "");
      const forwardMethod: string = isWrapped ? body.method : req.method;
      const forwardBody: any = isWrapped ? body.body : body;

      const target = `${baseUrl}${forwardPath}`;
      const forwardHeaders: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "application/json",
      };
      // Forward auth token so FastAPI can validate JWT
      const auth = req.headers["authorization"];
      if (auth) forwardHeaders["Authorization"] = auth;
      const upstream = await fetch(target, {
        method: forwardMethod,
        headers: forwardHeaders,
        body: ["GET", "HEAD"].includes(forwardMethod) ? undefined : JSON.stringify(forwardBody || {}),
      });
      const contentType = upstream.headers.get("content-type") || "application/json; charset=utf-8";
      res.status(upstream.status).type(contentType).send(await upstream.text());
    } catch {
      res.status(503).json({ error: "平台数据服务暂未启动", upstream: baseUrl });
    }
  };
  app.use("/api/platform/java", proxyPlatform(process.env.JAVA_API_URL || "http://127.0.0.1:8081"));
  app.use("/api/platform/storage", proxyPlatform(process.env.STORAGE_API_URL || "http://127.0.0.1:8080"));
  app.get("/api/jobs", (_req, res) => res.json({ items: jobs }));
  app.get("/api/hr/state", async (_req,res)=>res.json(await readHrState()));
  app.get("/api/hr/favorites",async(_req,res)=>{const state=await readHrState();const items=state.favorites.map(id=>state.candidates.find(candidate=>candidate.id===id)).filter(Boolean).map(candidate=>({...candidate,latestAssessment:history.find(item=>(item.candidateName||"匿名候选人")===(candidate?.name||"匿名候选人"))||null}));res.json({items})});
  app.put("/api/hr/favorites/:candidateId",async(req,res,next)=>{try{const state=await readHrState();const candidate=state.candidates.find(item=>item.id===req.params.candidateId);if(!candidate)return res.status(404).json({error:"候选人不存在"});if(!state.favorites.includes(candidate.id))state.favorites.unshift(candidate.id);await lockedWrite(()=>writeHrState(state));res.json({favorite:true,candidateId:candidate.id})}catch(error){next(error)}});
  app.delete("/api/hr/favorites/:candidateId",async(req,res,next)=>{try{const state=await readHrState();state.favorites=state.favorites.filter(id=>id!==req.params.candidateId);await lockedWrite(()=>writeHrState(state));res.json({favorite:false,candidateId:req.params.candidateId})}catch(error){next(error)}});
  app.post("/api/hr/candidates", async (req,res,next)=>{try{const state=await readHrState();const item={id:crypto.randomUUID(),name:String(req.body.name||"匿名候选人").trim()||"匿名候选人",email:String(req.body.email||""),phone:String(req.body.phone||""),stage:String(req.body.stage||"待评估"),skills:Array.isArray(req.body.skills)?req.body.skills:String(req.body.skills||"").split(/[,，、]/).filter(Boolean),experienceYears:Number(req.body.experienceYears||0),education:String(req.body.education||"未填写"),projectScore:Number(req.body.projectScore||0),collaborationScore:Number(req.body.collaborationScore||0),profileText:String(req.body.profileText||req.body.resumeText||""),createdAt:new Date().toISOString()};state.candidates.unshift(item);await lockedWrite(()=>writeHrState(state));const vectorCapture=await captureTalentVector(item);res.status(201).json({...item,vectorCapture})}catch(e){next(e)}});
  app.get("/api/vector/health",async(_req,res)=>{try{const response=await fetch(`${process.env.STORAGE_API_URL||"http://127.0.0.1:8080"}/api/talent-vectors/health`,{signal:AbortSignal.timeout(1800)});res.status(response.status).send(await response.text())}catch{res.status(503).json({status:"unavailable",detail:"Milvus 向量服务未启动"})}});
  // ── Interviews CRUD ──────────────────────────────────────────────────────
  const VALID_STATUSES=["pending","scheduled","in_progress","completed","cancelled"];
  app.get("/api/hr/interviews",async(req,res,next)=>{try{
    const state=await readHrState();
    let list=state.interviews;
    const q=req.query as Record<string,string>;
    if(q.status&&VALID_STATUSES.includes(q.status)) list=list.filter(iv=>iv.status===q.status);
    if(q.candidateId) list=list.filter(iv=>iv.candidateId===q.candidateId);
    if(q.jobTitle) list=list.filter(iv=>String(iv.jobTitle||"").includes(q.jobTitle!));
    if(q.tag) list=list.filter(iv=>(iv.tagIds||[]).includes(q.tag));
    if(q.dateFrom) list=list.filter(iv=>new Date(iv.startsAt)>=new Date(q.dateFrom!));
    if(q.dateTo) list=list.filter(iv=>new Date(iv.startsAt)<=new Date(q.dateTo!));
    if(q.isPinned==="1") list=list.filter(iv=>Boolean(iv.isPinned));
    if(q.onlyFavorites==="1") list=list.filter(iv=>state.favorites.includes(iv.candidateId));
    if(q.search){const s=q.search.toLowerCase();list=list.filter(iv=>`${iv.candidateName}${iv.jobTitle}${(iv.interviewers||[]).join(" ")}${iv.title}`.toLowerCase().includes(s))}
    if(q.round) list=list.filter(iv=>iv.round===q.round);
    if(q.priority) list=list.filter(iv=>iv.priority===q.priority);
    // sort by startsAt descending (newest first)
    list=[...list].sort((a,b)=>new Date(String(b.startsAt||"")).getTime()-new Date(String(a.startsAt||"")).getTime());
    // pagination
    const page=Math.max(1,Number(q.page)||1);
    const pageSize=Math.min(100,Math.max(1,Number(q.pageSize)||200));
    const total=list.length;
    const items=list.slice((page-1)*pageSize,page*pageSize);
    res.json({items,total,page,pageSize});
  }catch(e){next(e)}});

  app.get("/api/hr/interviews/:id",async(req,res,next)=>{try{
    const state=await readHrState();
    const iv=state.interviews.find(x=>x.id===req.params.id);
    if(!iv) return res.status(404).json({error:"面试记录不存在"});
    res.json(iv);
  }catch(e){next(e)}});

  app.post("/api/hr/interviews",async(req,res,next)=>{try{
    const state=await readHrState();
    const body=req.body||{};
    // validate
    if(!body.candidateId) return res.status(400).json({error:"请选择候选人"});
    const candidate=state.candidates.find(c=>c.id===body.candidateId);
    if(!candidate) return res.status(400).json({error:"候选人不存在"});
    if(!body.startsAt) return res.status(400).json({error:"请设置面试开始时间"});
    if(!body.endsAt) return res.status(400).json({error:"请设置面试结束时间"});
    if(new Date(body.endsAt)<=new Date(body.startsAt)) return res.status(400).json({error:"结束时间必须晚于开始时间"});
    if(body.status&&!VALID_STATUSES.includes(body.status)) return res.status(400).json({error:`状态值无效，允许：${VALID_STATUSES.join(", ")}`});
    const now=new Date().toISOString();
    const item={
      id:crypto.randomUUID(),
      candidateId:body.candidateId,
      candidateName:candidate.name||"匿名候选人",
      jobId:body.jobId||"",
      jobTitle:body.jobTitle||"待定岗位",
      title:body.title||`${candidate.name||"匿名候选人"} · ${body.round||"面试"}`,
      startsAt:body.startsAt,
      endsAt:body.endsAt,
      timezone:body.timezone||"Asia/Shanghai",
      format:body.format||"视频",
      customFormat:body.customFormat||"",
      location:body.location||"",
      meetingUrl:body.meetingUrl||"",
      interviewers:Array.isArray(body.interviewers)?body.interviewers.filter(Boolean):(body.interviewer?[body.interviewer]:["待分配"]),
      round:body.round||"初试",
      customRound:body.customRound||"",
      status:body.status||"scheduled",
      priority:body.priority||"普通",
      customPriority:body.customPriority||"",
      tagIds:Array.isArray(body.tagIds)?body.tagIds:[],
      focusAreas:Array.isArray(body.focusAreas)?body.focusAreas.filter(Boolean):[],
      questions:Array.isArray(body.questions)?body.questions.filter(Boolean):[],
      internalNotes:body.internalNotes||"",
      candidateNotes:body.candidateNotes||"",
      contactStatus:body.contactStatus||"not_contacted",
      reminderMinutes:typeof body.reminderMinutes==="number"?body.reminderMinutes:30,
      isPinned:Boolean(body.isPinned),
      createdAt:now,
      updatedAt:now,
    };
    state.interviews.unshift(item);
    if(candidate) candidate.stage="待面试";
    state.notifications=buildNotifications(state.interviews,state.candidates,state.notifications||[]);
    await lockedWrite(()=>writeHrState(state));
    res.status(201).json(item);
  }catch(e){next(e)}});

  app.patch("/api/hr/interviews/:id",async(req,res,next)=>{try{
    const state=await readHrState();
    const iv=state.interviews.find(x=>x.id===req.params.id);
    if(!iv) return res.status(404).json({error:"面试记录不存在"});
    const body=req.body||{};
    // validate time if both provided
    if(body.startsAt||body.endsAt){
      const startsAt=body.startsAt||iv.startsAt;
      const endsAt=body.endsAt||iv.endsAt;
      if(new Date(endsAt)<=new Date(startsAt)) return res.status(400).json({error:"结束时间必须晚于开始时间"});
    }
    if(body.status&&!VALID_STATUSES.includes(body.status)) return res.status(400).json({error:`状态值无效`});
    // allowed update keys
    const allowed=["startsAt","endsAt","timezone","format","customFormat","location","meetingUrl","interviewers","round","customRound","status","priority","customPriority","tagIds","focusAreas","questions","internalNotes","candidateNotes","contactStatus","reminderMinutes","isPinned","title","jobTitle","jobId","candidateId"];
    for(const key of allowed){
      if(body[key]!==undefined){
        if(Array.isArray(body[key])) (iv as any)[key]=body[key].filter(Boolean);
        else (iv as any)[key]=body[key];
      }
    }
    // legacy compat keys
    if(body.interviewer&&!Array.isArray(body.interviewers)) iv.interviewers=[String(body.interviewer)];
    if(body.notes&&!body.internalNotes) iv.internalNotes=String(body.notes);
    if(body.tags&&!body.tagIds) iv.tagIds=body.tags.map(String).filter(Boolean);
    iv.updatedAt=new Date().toISOString();
    // update candidate stage
    const candidate=state.candidates.find(c=>c.id===iv.candidateId);
    if(candidate){
      const s=iv.status;
      if(s==="completed") candidate.stage="已面试";
      else if(s==="cancelled") candidate.stage="待评估";
      else if(s==="scheduled"||s==="in_progress") candidate.stage="待面试";
    }
    state.notifications=buildNotifications(state.interviews,state.candidates,state.notifications||[]);
    await lockedWrite(()=>writeHrState(state));
    res.json(iv);
  }catch(e){next(e)}});

  app.delete("/api/hr/interviews/:id",async(req,res,next)=>{try{
    const state=await readHrState();
    const idx=state.interviews.findIndex(x=>x.id===req.params.id);
    if(idx===-1) return res.status(404).json({error:"面试记录不存在"});
    state.interviews.splice(idx,1);
    state.notifications=buildNotifications(state.interviews,state.candidates,state.notifications||[]);
    await lockedWrite(()=>writeHrState(state));
    res.json({deleted:true,id:req.params.id});
  }catch(e){next(e)}});

  // ── Interview Tags CRUD ──────────────────────────────────────────────────
  app.get("/api/hr/interview-tags",async(_req,res,next)=>{try{
    const state=await readHrState();
    res.json({items:state.interviewTags||[]});
  }catch(e){next(e)}});

  app.post("/api/hr/interview-tags",async(req,res,next)=>{try{
    const state=await readHrState();
    const name=String(req.body.name||"").trim();
    if(!name) return res.status(400).json({error:"标签名称不能为空"});
    if((state.interviewTags||[]).some(t=>t.name===name)) return res.status(400).json({error:"标签名称已存在"});
    const tag={id:crypto.randomUUID(),name,color:req.body.color||"#6366f1",createdAt:new Date().toISOString()};
    state.interviewTags=(state.interviewTags||[]).concat([tag]);
    await lockedWrite(()=>writeHrState(state));
    res.status(201).json(tag);
  }catch(e){next(e)}});

  app.patch("/api/hr/interview-tags/:id",async(req,res,next)=>{try{
    const state=await readHrState();
    const tag=(state.interviewTags||[]).find(t=>t.id===req.params.id);
    if(!tag) return res.status(404).json({error:"标签不存在"});
    if(req.body.name!==undefined) tag.name=String(req.body.name).trim();
    if(req.body.color!==undefined) tag.color=String(req.body.color);
    await lockedWrite(()=>writeHrState(state));
    res.json(tag);
  }catch(e){next(e)}});

  app.delete("/api/hr/interview-tags/:id",async(req,res,next)=>{try{
    const state=await readHrState();
    const tagIdx=(state.interviewTags||[]).findIndex(t=>t.id===req.params.id);
    if(tagIdx===-1) return res.status(404).json({error:"标签不存在"});
    // remove tag from all interviews
    state.interviews.forEach(iv=>{if(iv.tagIds) iv.tagIds=iv.tagIds.filter((tid:string)=>tid!==req.params.id)});
    state.interviewTags!.splice(tagIdx,1);
    await lockedWrite(()=>writeHrState(state));
    res.json({deleted:true,id:req.params.id});
  }catch(e){next(e)}});

  // ── Candidate detail ─────────────────────────────────────────────────────
  app.get("/api/hr/candidates/:id",async(req,res,next)=>{try{
    const state=await readHrState();
    const c=state.candidates.find(x=>x.id===req.params.id);
    if(!c) return res.status(404).json({error:"候选人不存在"});
    res.json(c);
  }catch(e){next(e)}});

  app.patch("/api/hr/candidates/:id",async(req,res,next)=>{try{
    const state=await readHrState();
    const c=state.candidates.find(x=>x.id===req.params.id);
    if(!c) return res.status(404).json({error:"候选人不存在"});
    const allowed=["name","email","phone","stage","education","experienceYears","profileText"];
    for(const key of allowed){if(req.body[key]!==undefined) (c as any)[key]=req.body[key]}
    if(req.body.skills) c.skills=Array.isArray(req.body.skills)?req.body.skills:String(req.body.skills).split(/[,，、]/).filter(Boolean);
    await lockedWrite(()=>writeHrState(state));
    res.json(c);
  }catch(e){next(e)}});

  // ── Enhanced Notifications ──────────────────────────────────────────────
  app.get("/api/notifications",async(_req,res)=>{try{
    const state=await readHrState();
    const items=(state.notifications||[]).sort((a,b)=>String(b.time).localeCompare(String(a.time))).slice(0,20);
    const unread=items.filter(n=>!n.readAt).length;
    res.json({items,unread});
  }catch{res.json({items:[],unread:0})}});

  app.patch("/api/notifications/:id/read",async(req,res,next)=>{try{
    const state=await readHrState();
    const n=(state.notifications||[]).find(x=>x.id===req.params.id);
    if(!n) return res.status(404).json({error:"通知不存在"});
    n.readAt=new Date().toISOString();
    await lockedWrite(()=>writeHrState(state));
    res.json(n);
  }catch(e){next(e)}});

  app.post("/api/notifications/read-all",async(_req,res,next)=>{try{
    const state=await readHrState();
    const now=new Date().toISOString();
    (state.notifications||[]).forEach(n=>{if(!n.readAt) n.readAt=now});
    await lockedWrite(()=>writeHrState(state));
    res.json({marked:true});
  }catch(e){next(e)}});
  app.post("/api/hr/jobs", async (req,res,next)=>{try{const state=await readHrState();const item={...req.body,id:crypto.randomUUID(),createdAt:new Date().toISOString(),source:"HR手动创建"};state.jobs.unshift(item);await writeHrState(state);res.status(201).json(item)}catch(e){next(e)}});
  app.delete("/api/hr/jobs/:jobId", async (req,res,next)=>{try{const state=await readHrState();const before=state.jobs.length;state.jobs=state.jobs.filter((job:any)=>job.id!==req.params.jobId);if(state.jobs.length===before)return res.status(404).json({error:"岗位不存在或并非手动创建"});await writeHrState(state);res.json({deleted:true,jobId:req.params.jobId})}catch(e){next(e)}});

  app.get("/api/crawler/status", (_req,res)=>res.json(crawlerState));
  app.post("/api/crawler/refresh", (req,res)=>{
    if(crawlerState.status==="running")return res.status(409).json(crawlerState);
    const script=path.join(projectRoot,"scripts","refresh_jobs_runtime.py");
    const mode=req.body?.mode==="deep"?"deep":"quick";const allowed=["tencent","huawei","baidu","meituan"];const selected=(Array.isArray(req.body?.sources)?req.body.sources:[]).filter((x:any)=>allowed.includes(String(x)));const sources=mode==="deep"?"china,imports":(selected.length?selected:allowed).join(",");const target=mode==="deep"?Math.max(10000,Number(req.body?.target||100000)):Math.min(3000,Math.max(100,Number(req.body?.target||1000)));
    crawlerState={status:"running",startedAt:new Date().toISOString(),finishedAt:"",message:mode==="deep"?"后端深度岗位采集正在运行":`正在从 ${selected.length||allowed.length} 个公开招聘源快速采集`,pid:0};
    const child=spawn(process.env.PYTHON_COMMAND||"python",[script],{cwd:projectRoot,windowsHide:true,env:{...process.env,CRAWL_RESET:"0",CHINA_JOB_TARGET:String(target),CHINA_JOB_SOURCES:sources,CHINA_JOB_BALANCED:"1",ENABLE_TENCENT:"1",ENABLE_IMPORTS:mode==="deep"?"1":"0"},stdio:"ignore"});
    crawlerState.pid=child.pid||0;
    child.on("error",err=>{crawlerState={...crawlerState,status:"failed",finishedAt:new Date().toISOString(),message:`采集启动失败：${err.message}`}});
    child.on("exit",code=>{crawlerState={...crawlerState,status:code===0?"completed":"failed",finishedAt:new Date().toISOString(),message:code===0?"岗位采集、历史合并与搜索索引同步已完成":`采集任务退出，代码 ${code}`}});
    res.status(202).json(crawlerState);
  });

  app.get("/api/ai/settings",(_req,res)=>res.json({provider:runtimeAi.provider,model:runtimeAi.model,baseUrl:runtimeAi.baseUrl,apiKeyConfigured:Boolean(runtimeAi.apiKey),apiKeyMask:runtimeAi.apiKey?`${runtimeAi.apiKey.slice(0,4)}••••${runtimeAi.apiKey.slice(-4)}`:""}));
  app.post("/api/ai/settings",(req,res)=>{runtimeAi={provider:String(req.body.provider||"google"),model:String(req.body.model||"gemini-2.5-flash"),baseUrl:String(req.body.baseUrl||""),apiKey:String(req.body.apiKey||runtimeAi.apiKey||"")};res.json({provider:runtimeAi.provider,model:runtimeAi.model,baseUrl:runtimeAi.baseUrl,apiKeyConfigured:Boolean(runtimeAi.apiKey)})});
  app.get("/api/assessments", (_req, res) => res.json({ items: history.slice(0, 100) }));
  app.post("/api/assessments/samples",(_req,res)=>{const existing=new Set(history.map(x=>x.id));const added=assessmentSamples().filter(x=>!existing.has(x.id));history.unshift(...added);res.status(201).json({added:added.length,items:history.slice(0,100)})});
  app.get("/api/assessments/:id", (req, res) => { const item = history.find(x => x.id === req.params.id); item ? res.json(item) : res.status(404).json({ error: "评估记录不存在" }); });
  app.post("/api/graph/job-fit",async(req,res,next)=>{try{const state=await readHrState();const candidate=state.candidates.find(item=>item.id===String(req.body.candidateId||""));const profile=graphJobProfiles.find(item=>item.id===String(req.body.jobId||""));if(!candidate||!profile)return res.status(404).json({error:"候选人或岗位不存在"});res.json(await generateJobFit(candidate,profile))}catch(error){next(error)}});

  app.get("/api/trends",async(req,res,next)=>{
    const jobId=String(req.query.jobId||"java-backend-engineer");const refresh=req.query.refresh==="1";const cached=latestTrend.get(jobId) as {payload_json:string;fetched_at:string}|undefined;
    if(cached&&!refresh)return res.json({...JSON.parse(cached.payload_json),cachedAt:cached.fetched_at,cacheStatus:"cached"});
    try{const javaBase=process.env.JAVA_API_URL||"http://127.0.0.1:8081";const [trendResponse,insightResponse]=await Promise.all([fetch(`${javaBase}/api/evolution?jobId=${encodeURIComponent(jobId)}`),fetch(`${javaBase}/api/ai-insight?topic=evolution`).catch(()=>null)]);if(!trendResponse.ok)throw new Error(`趋势服务请求失败：HTTP ${trendResponse.status}`);const evolution=await trendResponse.json();const insight=insightResponse?.ok?await insightResponse.json():null;const fetchedAt=new Date().toISOString();const payload={evolution,insight};saveTrend.run(jobId,fetchedAt,JSON.stringify(payload));database.exec("DELETE FROM trend_snapshots WHERE id NOT IN (SELECT id FROM trend_snapshots ORDER BY id DESC LIMIT 100)");return res.json({...payload,cachedAt:fetchedAt,cacheStatus:"refreshed"})}
    catch(error){try{const evolution=await localEvolution(jobId);const fetchedAt=new Date().toISOString();const payload={evolution,insight:null};saveTrend.run(jobId,fetchedAt,JSON.stringify(payload));database.exec("DELETE FROM trend_snapshots WHERE id NOT IN (SELECT id FROM trend_snapshots ORDER BY id DESC LIMIT 100)");return res.json({...payload,cachedAt:fetchedAt,cacheStatus:"local-source"})}catch{if(cached)return res.json({...JSON.parse(cached.payload_json),cachedAt:cached.fetched_at,cacheStatus:"stale"});next(error)}}
  });

  app.post("/api/resumes/parse", upload.single("resume"), async (req, res, next) => {
    try {
      if (!req.file) return res.status(400).json({ error: "请选择简历文件" });
      const text = (await extractText(req.file)).replace(/\0/g, "").trim();
      if (!text) return res.status(422).json({ error: "未能从文件中提取到文字，请确认简历不是纯图片扫描件" });
      res.json({ fileName: req.file.originalname, text, characters: text.length });
    } catch (error) { next(error); }
  });

  app.post("/api/resumes/extract", async (req, res, next) => {
    try {
      const resumeText = String(req.body.resumeText || "").trim();
      if (resumeText.length < 20) return res.status(400).json({ error: "简历内容过短，请上传完整简历（至少20字）" });

      const fallback = extractResumeFields(resumeText);

      if (!runtimeAi.apiKey) {
        return res.json({ ...fallback, source: "regex" });
      }

      const prompt = `请从以下简历文本中提取结构化信息，只返回JSON。字段说明：
- name: 候选人姓名（中文姓名2-4字，英文姓名不超过20字符；确实找不到则为空字符串""）
- skills: 核心技能列表（字符串数组，如 ["Java","Python","产品设计","项目管理"]，最多8项）
- years: 工作年限数字（整数，找不到则为0）
- education: 最高学历，必须是以下之一："高中及以下"|"专科"|"本科"|"硕士"|"博士"（找不到则根据内容推断，实在无法判断则为"本科"）
- experience: 项目/工作经历摘要（用一段话概括最近或最核心的工作经历，200字以内；找不到则为空字符串）

简历文本：
${resumeText}`;

      let raw: any;
      if (runtimeAi.provider !== "google") {
        const base = (runtimeAi.baseUrl || ({ deepseek: "https://api.deepseek.com", openai: "https://api.openai.com" } as Record<string, string>)[runtimeAi.provider] || "").replace(/\/$/, "");
        const upstream = await fetch(`${base}/v1/chat/completions`, {
          method: "POST",
          headers: { Authorization: `Bearer ${runtimeAi.apiKey}`, "Content-Type": "application/json" },
          body: JSON.stringify({
            model: runtimeAi.model,
            messages: [
              { role: "system", content: "你是专业简历解析专家。只返回JSON，字段为name, skills, years, education, experience。skills必须是字符串数组。从简历文本中客观提取，不要编造信息。" },
              { role: "user", content: prompt }
            ],
            response_format: { type: "json_object" }
          })
        });
        if (!upstream.ok) {
          const errText = await upstream.text().catch(() => "");
          throw new Error(`AI 服务请求失败：HTTP ${upstream.status} ${errText.slice(0, 100)}`);
        }
        const aiData: any = await upstream.json();
        raw = JSON.parse(aiData.choices?.[0]?.message?.content || "{}");
      } else {
        const ai = new GoogleGenAI({ apiKey: runtimeAi.apiKey });
        const response = await ai.models.generateContent({
          model: runtimeAi.model,
          contents: prompt,
          config: {
            responseMimeType: "application/json",
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                name: { type: Type.STRING },
                skills: { type: Type.ARRAY, items: { type: Type.STRING } },
                years: { type: Type.NUMBER },
                education: { type: Type.STRING },
                experience: { type: Type.STRING },
              },
              required: ["name", "skills", "years", "education", "experience"]
            }
          }
        });
        raw = JSON.parse(response.text || "{}");
      }

      const allowedEdu = ["高中及以下", "专科", "本科", "硕士", "博士"];
      const result = {
        name: (String(raw.name || fallback.name || "").trim()).slice(0, 20) || "",
        skills: (Array.isArray(raw.skills) && raw.skills.length > 0
          ? raw.skills.map(String).slice(0, 8)
          : fallback.skills),
        years: (typeof raw.years === "number" && raw.years >= 0
          ? String(raw.years)
          : String(fallback.years || "0")),
        education: allowedEdu.includes(String(raw.education))
          ? String(raw.education)
          : fallback.education,
        experience: (String(raw.experience || fallback.experience || "").trim()).slice(0, 400),
        source: runtimeAi.apiKey ? "ai" : "regex",
      };

      res.json(result);
    } catch (error) { next(error); }
  });

  app.post("/api/evaluate", async (req, res, next) => {
    try {
      const resumeText = String(req.body.resumeText || "").trim();
      const typedTitle=String(req.body.jobTitle||"").trim();
      const job = jobs.find(item => item.id === req.body.jobId)||(typedTitle?{id:`custom-${typedTitle}`,title:typedTitle,description:"HR 自定义目标岗位",requirements:["结合候选人技能、经历、学历和项目证据进行综合判断","识别与自定义岗位名称相关的可迁移能力"]}:null);
      if (!job) return res.status(400).json({ error: "请选择或输入目标岗位" });
      if (resumeText.length < 30) return res.status(400).json({ error: "简历内容过短，请上传或输入完整简历" });
      let raw: any;
      if (!runtimeAi.apiKey) raw = fallbackAssessment(job, resumeText);
      else {
        if(runtimeAi.provider!=="google"){
          const base=(runtimeAi.baseUrl||({deepseek:"https://api.deepseek.com",openai:"https://api.openai.com"} as Record<string,string>)[runtimeAi.provider]||"").replace(/\/$/,"");
          const upstream=await fetch(`${base}/v1/chat/completions`,{method:"POST",headers:{Authorization:`Bearer ${runtimeAi.apiKey}`,"Content-Type":"application/json"},body:JSON.stringify({model:runtimeAi.model,messages:[{role:"system",content:"你是专业招聘评估专家。只返回JSON，字段为candidateName,score,matchLevel,radar,experienceMatch,skillGaps,highlights。"},{role:"user",content:`岗位：${job.title}\n要求：${job.requirements.join("；")}\n简历：${resumeText}`}],response_format:{type:"json_object"}})});
          if(!upstream.ok)throw new Error(`AI 服务请求失败：HTTP ${upstream.status}`);const aiData:any=await upstream.json();raw=JSON.parse(aiData.choices?.[0]?.message?.content||"{}");
        }else{
        const ai = new GoogleGenAI({ apiKey: runtimeAi.apiKey });
        const response = await ai.models.generateContent({
          model: runtimeAi.model,
          contents: `你是专业招聘评估专家。请根据目标岗位和简历进行客观的人岗匹配评估，所有文本必须使用简体中文。\n岗位：${job.title}\n岗位要求：${job.requirements.join("；")}\n简历：\n${resumeText}`,
          config: { responseMimeType: "application/json", responseSchema: {
            type: Type.OBJECT, properties: {
              candidateName: { type: Type.STRING }, score: { type: Type.INTEGER }, matchLevel: { type: Type.STRING },
              radar: { type: Type.OBJECT, properties: { technical:{type:Type.INTEGER}, experience:{type:Type.INTEGER}, collaboration:{type:Type.INTEGER}, education:{type:Type.INTEGER}, softSkills:{type:Type.INTEGER} }, required:["technical","experience","collaboration","education","softSkills"] },
              experienceMatch: { type: Type.OBJECT, properties: { relevance:{type:Type.INTEGER}, alignment:{type:Type.INTEGER} }, required:["relevance","alignment"] },
              skillGaps: { type: Type.ARRAY, items:{type:Type.STRING} }, highlights: { type: Type.ARRAY, items:{type:Type.STRING} },
            }, required:["score","matchLevel","radar","experienceMatch","skillGaps","highlights"]
          } }
        });
        raw = JSON.parse(response.text || "{}");}
      }
      raw.candidateName = String(req.body.candidateName || raw.candidateName || "匿名候选人").trim() || "匿名候选人";
      const assessment = normalize(raw, job);
      history.unshift(assessment); if (history.length > 100) history.length = 100;
      const state=await readHrState();const existing=state.candidates.find(x=>x.name===assessment.candidateName);const vectorCapture=await captureTalentVector({...existing,id:existing?.id||`assessment-${assessment.id}`,name:assessment.candidateName,skills:existing?.skills||[],profileText:resumeText,projectScore:assessment.radar.technical,collaborationScore:assessment.radar.collaboration,updatedAt:assessment.createdAt});
      res.json({...assessment,vectorCapture});
    } catch (error) { next(error); }
  });

  app.use((error: any, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
    console.error(error); const status = error.status || (error.code === "LIMIT_FILE_SIZE" ? 413 : 500);
    res.status(status).json({ error: status === 413 ? "文件不能超过 10MB" : error.message || "服务器处理失败" });
  });

  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({ server: { middlewareMode: true }, appType: "spa" }); app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist"); app.use(express.static(distPath)); app.get("*", (_req, res) => res.sendFile(path.join(distPath, "index.html")));
  }
  app.listen(port, "0.0.0.0", () => console.log(`TalentMatch: http://localhost:${port}`));
}

startServer().catch(console.error);
