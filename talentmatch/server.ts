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
type HrState = { candidates:Array<Record<string,any>>; interviews:Array<Record<string,any>>; jobs:Array<Record<string,any>>; favorites:string[] };
const initialHrState:HrState = {
  candidates:[
    {id:"candidate-linchen",name:"林晨",email:"linchen@example.com",phone:"138****1024",stage:"待评估",skills:["Java","Go","Redis","微服务"],experienceYears:6,education:"本科",projectScore:88,collaborationScore:84,createdAt:new Date().toISOString()},
    {id:"candidate-zhouning",name:"周宁",email:"zhouning@example.com",phone:"139****3078",stage:"待面试",skills:["Python","LLM","RAG","PyTorch","SQL"],experienceYears:4,education:"硕士",projectScore:92,collaborationScore:80,createdAt:new Date().toISOString()},
    {id:"candidate-anonymous",name:"匿名候选人",email:"",phone:"",stage:"待评估",skills:["React","TypeScript","可视化"],experienceYears:3,education:"本科",projectScore:76,collaborationScore:86,createdAt:new Date().toISOString()},
  ],
  interviews:[{id:"interview-1",candidateId:"candidate-zhouning",candidateName:"周宁",jobTitle:"高级后端工程师",scheduledAt:new Date(Date.now()+86400000).toISOString(),interviewer:"技术面试官",status:"待进行"}],
  jobs:[],
  favorites:[],
};
async function readHrState():Promise<HrState>{try{const saved=JSON.parse(await fs.readFile(hrStatePath,"utf8"));return {...initialHrState,...saved,favorites:Array.isArray(saved.favorites)?saved.favorites:[],candidates:(saved.candidates||initialHrState.candidates).map((c:any)=>({...initialHrState.candidates.find(x=>x.id===c.id),...c}))}}catch{return initialHrState}}
async function writeHrState(state:HrState){await fs.mkdir(path.dirname(hrStatePath),{recursive:true});await fs.writeFile(hrStatePath,JSON.stringify(state,null,2),"utf8")}
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
      const target = `${baseUrl}${req.url}`;
      const upstream = await fetch(target, {
        method: req.method,
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: ["GET", "HEAD"].includes(req.method) ? undefined : JSON.stringify(req.body || {}),
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
  app.put("/api/hr/favorites/:candidateId",async(req,res,next)=>{try{const state=await readHrState();const candidate=state.candidates.find(item=>item.id===req.params.candidateId);if(!candidate)return res.status(404).json({error:"候选人不存在"});if(!state.favorites.includes(candidate.id))state.favorites.unshift(candidate.id);await writeHrState(state);res.json({favorite:true,candidateId:candidate.id})}catch(error){next(error)}});
  app.delete("/api/hr/favorites/:candidateId",async(req,res,next)=>{try{const state=await readHrState();state.favorites=state.favorites.filter(id=>id!==req.params.candidateId);await writeHrState(state);res.json({favorite:false,candidateId:req.params.candidateId})}catch(error){next(error)}});
  app.get("/api/notifications",async (_req,res)=>{const state=await readHrState();const interviews=state.interviews.filter(x=>x.status==="待进行").map(x=>({id:`interview-${x.id}`,type:"interview",title:`待安排面试：${x.candidateName||"匿名候选人"}`,detail:`${x.jobTitle||"待定岗位"} · ${x.interviewer||"待分配面试官"}`,time:x.scheduledAt||x.createdAt}));const resumes=state.candidates.map(x=>({id:`resume-${x.id}`,type:"resume",title:`收到新简历：${x.name||"匿名候选人"}`,detail:`${(x.skills||[]).slice(0,3).join("、")||"尚未提取技能"} · ${x.stage||"待评估"}`,time:x.createdAt}));res.json({items:[...interviews,...resumes].sort((a,b)=>String(b.time).localeCompare(String(a.time))).slice(0,12),unread:interviews.length+resumes.filter(x=>Date.now()-new Date(x.time).getTime()<7*86400000).length})});
  app.post("/api/hr/candidates", async (req,res,next)=>{try{const state=await readHrState();const item={id:crypto.randomUUID(),name:String(req.body.name||"匿名候选人").trim()||"匿名候选人",email:String(req.body.email||""),phone:String(req.body.phone||""),stage:String(req.body.stage||"待评估"),skills:Array.isArray(req.body.skills)?req.body.skills:String(req.body.skills||"").split(/[,，、]/).filter(Boolean),experienceYears:Number(req.body.experienceYears||0),education:String(req.body.education||"未填写"),projectScore:Number(req.body.projectScore||0),collaborationScore:Number(req.body.collaborationScore||0),profileText:String(req.body.profileText||req.body.resumeText||""),createdAt:new Date().toISOString()};state.candidates.unshift(item);await writeHrState(state);const vectorCapture=await captureTalentVector(item);res.status(201).json({...item,vectorCapture})}catch(e){next(e)}});
  app.get("/api/vector/health",async(_req,res)=>{try{const response=await fetch(`${process.env.STORAGE_API_URL||"http://127.0.0.1:8080"}/api/talent-vectors/health`,{signal:AbortSignal.timeout(1800)});res.status(response.status).send(await response.text())}catch{res.status(503).json({status:"unavailable",detail:"Milvus 向量服务未启动"})}});
  app.post("/api/hr/interviews", async (req,res,next)=>{try{const state=await readHrState();const item={id:crypto.randomUUID(),candidateId:String(req.body.candidateId||""),candidateName:String(req.body.candidateName||"匿名候选人"),jobTitle:String(req.body.jobTitle||"待定岗位"),scheduledAt:String(req.body.scheduledAt||new Date().toISOString()),interviewer:String(req.body.interviewer||"待分配"),status:"待进行",createdAt:new Date().toISOString()};state.interviews.unshift(item);const c=state.candidates.find(x=>x.id===item.candidateId);if(c)c.stage="待面试";await writeHrState(state);res.status(201).json(item)}catch(e){next(e)}});
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
