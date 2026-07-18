import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { Activity, AlertTriangle, ArrowLeft, ArrowUpRight, BriefcaseBusiness, CalendarDays, CheckCircle2, CircleDot, Clock3, FileText, GitCompareArrows, Heart, Info, Lock, Mail, MapPin, Phone, Plus, RefreshCw, Route, Search, ShieldAlert, Sparkles, Star, Trash2, TrendingUp, UserRound, X } from "lucide-react";
import CompetitionDiscovery from "./components/CompetitionDiscovery";
import CompetitionRoleEvolution from "./components/CompetitionRoleEvolution";
import RoleCapabilityGraph from "./components/RoleCapabilityGraph";
import CompetitionEvidence from "./components/CompetitionEvidence";
import CompetitionErrorBoundary from "./components/CompetitionErrorBoundary";

export type PageKey="overview"|"unified"|"graph"|"compare"|"evolution"|"jobs"|"favorites"|"about"|"capability"|"interviews";
type Json=Record<string,any>;
type JobRow={id:string;name:string;company?:string;city?:string;description?:string;summary?:string;requirement?:string;sourceUrl?:string;type?:string;skills?:string[];salary?:string;score?:number;updatedAt?:string;source?:string};
type AssessmentRow={id:string;candidateName?:string;jobTitle?:string;score:number;matchLevel:string;createdAt:string;skillGaps?:string[];highlights?:string[]};
type CandidateRow={id:string;name:string;email?:string;phone?:string;stage:string;createdAt:string;skills?:string[];experienceYears?:number;education?:string;projectScore?:number;collaborationScore?:number;profileText?:string};
type InterviewRow={id:string;candidateId:string;candidateName:string;jobTitle:string;scheduledAt:string;interviewer:string;location?:string;tags?:string[];notes?:string;status:string};

const meta:Record<PageKey,{eyebrow:string;title:string;desc:string}>={
  overview:{eyebrow:"HOME",title:"主页",desc:"集中查看在招岗位、候选人评估与近期招聘进展。"},
  jobs:{eyebrow:"JOB MANAGEMENT",title:"岗位管理",desc:"管理当前招聘岗位、核心要求和候选人匹配进度。"},
  graph:{eyebrow:"TALENT CAPABILITY GRAPH",title:"人才能力图谱",desc:"人岗匹配模块：拖动和点击能力节点，查看候选人的能力、缺口与岗位适配关系。"},
  compare:{eyebrow:"CANDIDATE COMPARISON",title:"候选人横向对比",desc:"从技能、经验、学历、项目与协作能力比较两位候选人的优势和短板。"},
  unified:{eyebrow:"ASSESSMENT RESULTS",title:"候选人评估结果",desc:"查看真实评估记录，辅助候选人筛选和面试决策。"},
  favorites:{eyebrow:"FAVORITE TALENTS",title:"特别关注",desc:"集中跟进重点候选人的档案、匹配结果与人才能力图谱。"},
  evolution:{eyebrow:"RECRUITMENT INSIGHTS",title:"招聘趋势洞察",desc:"按时间区间查看岗位热度及关键技能的演变。"},
  interviews:{eyebrow:"INTERVIEW MANAGEMENT",title:"面试管理",desc:"集中管理面试安排、候选人跟进、面试状态与标签，支持日历、列表和看板视图。"},
  about:{eyebrow:"ABOUT TALENTMATCH",title:"关于本项目",desc:"了解系统如何连接岗位采集、人才评估、能力图谱、向量检索与招聘趋势。"},
  capability:{eyebrow:"JOB CAPABILITY GRAPH",title:"岗位能力图谱",desc:"展示岗位—技能点—能力维度的全景关系图谱，支持技术栈、级别与版本筛选。"},
};
const fallbackJobs:JobRow[]=[
  {id:"backend",name:"高级后端工程师",company:"核心技术部",city:"上海",type:"社会招聘",salary:"30K-45K",skills:["Java","Go","分布式架构"],description:"负责高并发核心服务的架构设计、研发和稳定性建设。",score:92},
  {id:"ai",name:"AI 算法工程师",company:"人工智能中心",city:"深圳",type:"社会招聘",salary:"35K-55K",skills:["Python","LLM","RAG"],description:"负责大模型应用、智能评估算法和知识检索能力建设。",score:89},
  {id:"frontend",name:"资深前端工程师",company:"产品研发部",city:"北京",type:"社会招聘",salary:"28K-42K",skills:["React","TypeScript","可视化"],description:"负责企业级招聘产品前端架构与数据可视化体验。",score:86},
  {id:"product",name:"高级产品经理",company:"招聘产品部",city:"杭州",type:"社会招聘",salary:"25K-38K",skills:["产品规划","数据分析","AI产品"],description:"负责智能招聘产品规划、需求分析和跨团队交付。",score:83},
];
const timeText=(date=new Date())=>new Intl.DateTimeFormat("zh-CN",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(date).replace("/","-");

async function json(url:string,options?:RequestInit){const response=await fetch(url,options);const data=await response.json();if(!response.ok)throw new Error(data.error||data.detail||"数据加载失败");return data}
function normalizeJobs(data:any):JobRow[]{const rows=Array.isArray(data)?data:data?.jobs||data?.items||data?.data||[];return rows.map((x:any,i:number)=>{const salary=x.salary||x.salary_text||(x.salary_min||x.salary_max?[x.salary_min?`${x.salary_min}`:"",x.salary_max?`${x.salary_max}`:""].filter(Boolean).join("-"):"面议");return {id:String(x.id||x.postId||i),name:x.name||x.title||`招聘岗位 ${i+1}`,company:x.company||x.company_name||x.department||"招聘团队",city:x.city||"不限",type:x.type||x.industry||x.source||"社会招聘",salary,skills:x.skills||x.requirements||[],summary:x.summary||"",description:x.description||x.responsibility||x.summary||"暂无岗位说明",requirement:typeof x.requirement==="string"?x.requirement:"",sourceUrl:x.sourceUrl||x.source_url||"",updatedAt:x.updatedAt||x.published_at||x.collected_at,score:Number(x.score||x.matchRate||Math.max(70,92-i%8*3))}})}

/* ==========================================================================
   HOMEPAGE — Premium Executive Dashboard
   ========================================================================== */
function HomePage({onNavigate,isLoggedIn}:{onNavigate?:(page:PageKey|"matching")=>void;isLoggedIn:boolean}){
  const [remoteJobs,setRemoteJobs]=useState<JobRow[]>([]);const [localJobs,setLocalJobs]=useState<JobRow[]>([]);const [total,setTotal]=useState(0);const [candidates,setCandidates]=useState<CandidateRow[]>([]);const [interviews,setInterviews]=useState<InterviewRow[]>([]);const [assessments,setAssessments]=useState<AssessmentRow[]>([]);const [updated,setUpdated]=useState(timeText());const [adding,setAdding]=useState(false);const [selected,setSelected]=useState<JobRow|null>(null);
  /* ── Demo state (unauthenticated) ── */
  const [demoJobs,setDemoJobs]=useState<JobRow[]>([]);const [demoLoaded,setDemoLoaded]=useState(false);
  const load=async()=>{try{const [jobResult,hrResult,assessResult]=await Promise.allSettled([json("/api/platform/storage/api/search/jobs?page=1&page_size=6"),json("/api/hr/state"),json("/api/assessments")]);const hr=hrResult.status==="fulfilled"?hrResult.value:{candidates:[],interviews:[],jobs:[]};if(jobResult.status==="fulfilled"){setRemoteJobs(normalizeJobs(jobResult.value));setTotal(Number(jobResult.value.total||0))}setLocalJobs((hr.jobs||[]).map((x:any)=>({...x,name:x.name||x.title})));setCandidates(hr.candidates||[]);setInterviews(hr.interviews||[]);if(assessResult.status==="fulfilled")setAssessments(assessResult.value.items||[]);setUpdated(timeText())}catch{}};
  /* ── Demo data loader — public, no auth ── */
  const loadDemo=async()=>{try{const res=await fetch("/api/platform/storage",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:"/api/home/demo-jobs",method:"GET"})});const data=await res.json();setDemoJobs(normalizeJobs(data));setDemoLoaded(true)}catch{setDemoLoaded(true)}};
  useEffect(()=>{if(isLoggedIn){load()}else{loadDemo()}},[isLoggedIn]);
  const add=async(job:JobRow)=>{const saved=await json("/api/hr/jobs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(job)});setLocalJobs(x=>[{...saved,name:saved.name||saved.title},...x]);setAdding(false);setUpdated(timeText());setSelected({...saved,name:saved.name||saved.title})};
  const deleteLocalJob=async(jobId:string)=>{await json("/api/hr/jobs/"+jobId,{method:"DELETE"});setLocalJobs(x=>x.filter(j=>j.id!==jobId));setSelected(null);setUpdated(timeText())};
  const jobs=[...localJobs,...remoteJobs];const topJobs=isLoggedIn?jobs.slice(0,3):demoJobs.slice(0,6);
  const pendingInterviews=interviews.filter(x=>x.status==="待进行").length;
  const average=assessments.length?Math.round(assessments.reduce((sum,x)=>sum+x.score,0)/assessments.length):null;
  const totalJobs=total+localJobs.length;
  const gradients=["linear-gradient(135deg,#1a1040,#0d1a30)","linear-gradient(135deg,#0d1a30,#101a28)","linear-gradient(135deg,#1a1028,#0d1530)","linear-gradient(135deg,#0d1a30,#101a28)","linear-gradient(135deg,#1a1040,#101a28)","linear-gradient(135deg,#1a1028,#0d1a30)"];
  const badges=[{text:"高优先级",bg:"rgba(0,221,235,.12)",color:"#9bf2e9"},{text:"热招中",bg:"rgba(175,64,255,.12)",color:"#cabeff"},{text:"核心岗",bg:"rgba(127,213,205,.12)",color:"#9cd0d2"},{text:"急聘",bg:"rgba(255,175,64,.12)",color:"#ffaf40"},{text:"技术岗",bg:"rgba(64,200,255,.12)",color:"#40c8ff"},{text:"管理岗",bg:"rgba(255,128,200,.12)",color:"#ff80c8"}];
  /* ── UNAUTHENTICATED: Demo homepage ── */
  if(!isLoggedIn){
    return <div className="platform-main" style={{padding:0,margin:0,maxWidth:"100%"}}>
      {/* Hero — simplified */}
      <section className="home-hero" style={{minHeight:300,paddingBottom:48}}>
        <p className="home-hero__eyebrow">TalentMatch Preview</p>
        <h1 className="home-hero__title">{'人岗匹配智能评估系统'}</h1>
        <p className="home-hero__desc">{'登录后可查看完整岗位数据、启动人才评估、使用知识图谱与招聘趋势等全部功能。以下展示 10 条精选 Demo 数据。'}</p>
        <div className="home-hero__actions">
          <button className="home-hero__primary" onClick={()=>window.dispatchEvent(new CustomEvent("auth:open-login"))}><Lock/> {'登录查看全部数据'}</button>
          <span style={{fontSize:12,color:"rgba(196,199,200,.4)",marginLeft:12}}>{'共 10 条预览数据 · 来自 MySQL'}</span>
        </div>
      </section>
      <div style={{maxWidth:1280,margin:"0 auto",padding:"0 32px 32px"}}>
        {/* Stats — demo */}
        <div className="home-stats">
          <div className="home-stat"><p className="home-stat__label">{'Demo 岗位'} <BriefcaseBusiness/></p><h3 className="home-stat__value">{demoJobs.length}</h3><p className="home-stat__sub">{'MySQL 演示数据'}</p></div>
          <div className="home-stat"><p className="home-stat__label">{'覆盖城市'} <MapPin/></p><h3 className="home-stat__value mint">{new Set(demoJobs.map(j=>j.city)).size}</h3><p className="home-stat__sub">{'北京·上海·深圳·杭州·广州'}</p></div>
          <div className="home-stat"><p className="home-stat__label">{'技能标签'} <Sparkles/></p><h3 className="home-stat__value">{new Set(demoJobs.flatMap(j=>j.skills||[])).size}+</h3><p className="home-stat__sub">{'Java·Go·Python·React·K8s…'}</p></div>
          <div className="home-stat"><p className="home-stat__label">{'登录解锁'} <Lock/></p><h3 className="home-stat__value mint">100%</h3><p className="home-stat__sub">{'全部功能开放使用'}</p></div>
        </div>
        {/* Demo job cards — all 10 in two rows */}
        <section className="home-section">
          <div className="home-section__head">
            <div><p className="home-section__head-label">Demo Preview</p><h2 className="home-section__head-title">{'精选 Demo 岗位（10 条）'}</h2></div>
            <span style={{fontSize:12,color:"rgba(196,199,200,.35)"}}>{'数据来源: MySQL demo_homepage_jobs'}</span>
          </div>
          <div className="home-position-grid" style={{gridTemplateColumns:"repeat(auto-fill, minmax(340px, 1fr))"}}>
            {demoLoaded&&demoJobs.length===0?<div className="home-position-card" style={{gridColumn:"1/-1",padding:60,textAlign:"center",cursor:"default"}}><p style={{color:"rgba(196,199,200,.4)"}}>{'Demo 数据加载失败，请确认后端服务已启动'}</p></div>:
            demoJobs.map((job,i)=>{
              const badge=badges[i%badges.length];
              // Pick a deterministic gradient
              const g=gradients[i%gradients.length];
              return <button key={job.id} className="home-position-card" onClick={()=>setSelected(job)} style={{cursor:"default"}}>
                <div className="home-position-card__img" style={{background:g}}>
                  <div className="home-position-card__img-overlay"/>
                  <span className="home-position-card__img-badge" style={{background:badge.bg,color:badge.color}}>{badge.text}</span>
                </div>
                <div className="home-position-card__body">
                  <div className="home-position-card__score-row">
                    <h4 className="home-position-card__name">{job.name}</h4>
                    <span className="home-position-card__score">{job.score||85}{'分'}</span>
                  </div>
                  <p className="home-position-card__desc" style={{WebkitLineClamp:2,display:"-webkit-box",WebkitBoxOrient:"vertical",overflow:"hidden"}}>{job.description||job.summary}</p>
                  <div className="skill-tags" style={{marginBottom:14}}>{(job.skills||[]).slice(0,4).map((s:string)=><i key={s}>{s}</i>)}</div>
                  <div className="home-position-card__footer">
                    <span style={{fontSize:12,color:"rgba(196,199,200,.5)"}}><MapPin style={{width:14,height:14,marginRight:4,verticalAlign:"middle"}}/>{job.city||'不限'} · {job.company}</span>
                  </div>
                </div>
              </button>;
            })}
          </div>
        </section>
        {/* Login CTA */}
        <section className="home-section" style={{marginBottom:20}}>
          <div className="home-insights">
            <div className="home-quote-card">
              <div className="home-quote-card__icon"><Lock/></div>
              <p className="home-quote-card__text">{'登录后即可访问所有功能：岗位管理、人岗匹配（含人才能力图谱）、评估结果、招聘趋势等。'}</p>
              <button className="home-insight-card__action" style={{marginTop:16}} onClick={()=>window.dispatchEvent(new CustomEvent("auth:open-login"))}>{'立即登录'} <ArrowUpRight style={{width:14,height:14}}/></button>
            </div>
            <div className="home-insight-card">
              <div className="home-insight-card__head">
                <div className="home-insight-card__head-icon"><Activity/></div>
                <h3 className="home-insight-card__head-title">{'平台能力预览'}</h3>
              </div>
              <ul className="home-insight-card__list">
                <li className="home-insight-card__item"><div className="home-insight-card__dot"/><div className="home-insight-card__item-content"><h4>{'岗位管理'}</h4><p>{'管理招聘岗位、核心要求与候选人匹配进度。'}</p></div></li>
                <li className="home-insight-card__item"><div className="home-insight-card__dot"/><div className="home-insight-card__item-content"><h4>{'人岗匹配'}</h4><p>{'上传简历，AI 智能评估候选人与岗位的契合度。'}</p></div></li>
                <li className="home-insight-card__item"><div className="home-insight-card__dot"/><div className="home-insight-card__item-content"><h4>{'人才能力图谱'}</h4><p>{'人岗匹配功能：可视化候选人的能力、缺口与岗位适配关系。'}</p></div></li>
                <li className="home-insight-card__item"><div className="home-insight-card__dot"/><div className="home-insight-card__item-content"><h4>{'招聘趋势'}</h4><p>{'按时间查看岗位热度及关键技能的演变。'}</p></div></li>
              </ul>
            </div>
          </div>
        </section>
      </div>
      {selected&&<JobDialog job={selected} close={()=>setSelected(null)} isReadonly/>}
    </div>;
  }

  /* ── AUTHENTICATED: Full dashboard ── */
  return <div className="platform-main" style={{padding:0,margin:0,maxWidth:"100%"}}>
    {/* Hero Section */}
    <section className="home-hero">
      <p className="home-hero__eyebrow">Executive Dashboard</p>
      <h1 className="home-hero__title">{'人岗匹配智能评估系统'}</h1>
      <p className="home-hero__desc">{'精准管理组织人力资本，实时监控招聘流程与精英候选人匹配评分。集中查看在招岗位、候选人评估与近期招聘进展，驱动数据化招聘决策。'}</p>
      <div className="home-hero__actions">
        <button className="home-hero__primary" onClick={()=>setAdding(true)}><Plus/> {'发布新岗位'}</button>
        <button className="home-hero__secondary" onClick={()=>onNavigate?.("evolution")}><TrendingUp/> {'查看招聘趋势'}</button>
      </div>
    </section>
    <div style={{maxWidth:1280,margin:"0 auto",padding:"0 32px 32px"}}>
      {/* Stats Grid */}
      <div className="home-stats">
        <button className="home-stat" onClick={()=>onNavigate?.("jobs")}>
          <p className="home-stat__label">{'在招岗位'} <BriefcaseBusiness/></p>
          <h3 className="home-stat__value">{totalJobs.toLocaleString()}</h3>
          <div className="home-stat__bar"><div className="home-stat__bar-fill" style={{width:"67%"}}/></div>
        </button>
        <button className="home-stat" onClick={()=>onNavigate?.("favorites")}>
          <p className="home-stat__label">{'候选人池'} <UserRound/></p>
          <h3 className="home-stat__value mint">{candidates.length}</h3>
          <p className="home-stat__sub">{'关注人才 · 持续跟踪'}</p>
        </button>
        <button className="home-stat" onClick={()=>onNavigate?.("interviews")}>
          <p className="home-stat__label">{'待安排面试'} <CalendarDays/></p>
          <h3 className="home-stat__value">{pendingInterviews}</h3>
          <p className="home-stat__sub">{pendingInterviews?'需尽快确认面试时间':'暂无待安排面试'}</p>
        </button>
        <button className="home-stat" onClick={()=>onNavigate?.("unified")}>
          <p className="home-stat__label">{'平均匹配度'} <Sparkles/></p>
          <h3 className="home-stat__value mint">{average!==null?average+"%":"--"}</h3>
          <div className="home-stat__bar"><div className="home-stat__bar-fill" style={{width:average!==null?average+"%":"0%"}}/></div>
        </button>
      </div>
      {/* Key Positions */}
      <section className="home-section">
        <div className="home-section__head">
          <div>
            <p className="home-section__head-label">Priority Pipeline</p>
            <h2 className="home-section__head-title">{'重点招聘岗位'}</h2>
          </div>
          <button className="home-section__head-link" onClick={()=>onNavigate?.("jobs")}>{'查看全部岗位'} <ArrowUpRight/></button>
        </div>
        <div className="home-position-grid">
          {topJobs.length?topJobs.map((job,i)=>{
            const badge=badges[i]||badges[0];
            return <button key={job.id} className="home-position-card" onClick={()=>{setSelected(job)}}>
              <div className="home-position-card__img" style={{background:gradients[i]||gradients[0]}}>
                <div className="home-position-card__img-overlay"/>
                <span className="home-position-card__img-badge" style={{background:badge.bg,color:badge.color}}>{badge.text}</span>
              </div>
              <div className="home-position-card__body">
                <div className="home-position-card__score-row">
                  <h4 className="home-position-card__name">{job.name}</h4>
                  <span className="home-position-card__score">{(job.score||85)}{'分'}</span>
                </div>
                <p className="home-position-card__desc">{job.description}</p>
                <div className="skill-tags" style={{marginBottom:14}}>{(job.skills||[]).slice(0,3).map((s:string)=><i key={s}>{s}</i>)}</div>
                <div className="home-position-card__footer">
                  <span style={{fontSize:12,color:"rgba(196,199,200,.5)"}}><MapPin style={{width:14,height:14,marginRight:4,verticalAlign:"middle"}}/>{job.city||'不限'}</span>
                  <span className="home-position-card__footer-btn">{'查看详情'} <ArrowUpRight style={{width:14,height:14}}/></span>
                </div>
              </div>
            </button>;
          }):<div className="home-position-card" style={{gridColumn:"1/-1",padding:60,textAlign:"center",cursor:"default"}}><p style={{color:"rgba(196,199,200,.4)"}}>{'正在加载岗位数据...'}</p></div>}
        </div>
      </section>
      {/* Insights Bento */}
      <section className="home-section" style={{marginBottom:20}}>
        <div className="home-insights">
          <div className="home-quote-card">
            <div className="home-quote-card__icon"><Sparkles/></div>
            <p className="home-quote-card__text">{'“优秀的招聘者不仅仅是填补岗位空缺；他们在构建组织的未来蓝图。”'}</p>
            <p className="home-quote-card__author">— TalentMatch {'智能评估团队'}</p>
          </div>
          <div className="home-insight-card">
            <div className="home-insight-card__head">
              <div className="home-insight-card__head-icon"><Activity/></div>
              <h3 className="home-insight-card__head-title">{'智能洞察'}</h3>
            </div>
            <ul className="home-insight-card__list">
              <li className="home-insight-card__item">
                <div className="home-insight-card__dot"/>
                <div className="home-insight-card__item-content">
                  <h4>{'实时招聘标的'}</h4>
                  <p>{'当前系统共有'} <b style={{color:"#9bf2e9"}}>{totalJobs.toLocaleString()}</b> {'个在招岗位，覆盖多个行业领域。'}</p>
                </div>
              </li>
              <li className="home-insight-card__item">
                <div className="home-insight-card__dot"/>
                <div className="home-insight-card__item-content">
                  <h4>{'人才评估质量'}</h4>
                  <p>{'已完成'} <b style={{color:"#9bf2e9"}}>{assessments.length}</b> {'次智能评估，平均匹配度为'} <b style={{color:"#9bf2e9"}}>{average!==null?average+"%":"--"}</b>{'。'}</p>
                </div>
              </li>
              <li className="home-insight-card__item">
                <div className="home-insight-card__dot"/>
                <div className="home-insight-card__item-content">
                  <h4>{'招聘趋势洞察'}</h4>
                  <p>{'按时间区间查看岗位热度及关键技能的演变，辅助战略规划。'}</p>
                </div>
              </li>
            </ul>
            <button className="home-insight-card__action" onClick={()=>onNavigate?.("evolution")}><TrendingUp/> {'探索更多洞察'}</button>
          </div>
        </div>
      </section>
      {/* Quick Actions */}
      <section className="workspace-shortcuts">
        <button className="spring-hover" onClick={()=>setAdding(true)}><Plus/><span><b>{'发布招聘岗位'}</b><small>{'创建新的招聘需求'}</small></span></button>
        <button className="spring-hover" onClick={()=>onNavigate?.("matching")}><Sparkles/><span><b>{'开始人才评估'}</b><small>{'上传简历并进行匹配'}</small></span></button>
        <button className="spring-hover" onClick={()=>onNavigate?.("graph")}><Route/><span><b>{'人才能力图谱'}</b><small>{'可视化候选人与岗位关系'}</small></span></button>
      </section>
    </div>
    {selected&&<JobDialog job={selected} close={()=>setSelected(null)} onDelete={deleteLocalJob}/>}
    {adding&&<AddJobDialog close={()=>setAdding(false)} save={add}/>}
  </div>;
}


export default function PlatformPage({page,onNavigate,preferredCandidateName,onOpenGraph,isLoggedIn}:{page:PageKey;onNavigate?:(page:PageKey|"matching")=>void;preferredCandidateName?:string;onOpenGraph?:(name:string)=>void;isLoggedIn:boolean}){
  const m=meta[page];
  if(page==="overview")return <HomePage onNavigate={onNavigate} isLoggedIn={isLoggedIn}/>;
  if(page==="capability")return <CapabilityPage onNavigate={onNavigate}/>;
  return <main className="platform-main"><div className="page-heading" key={page}><div><span className="slide-in-left" style={{"--i":0} as any}>{m.eyebrow}</span><h2 className="slide-in-left" style={{"--i":1} as any}>{m.title}</h2><p className="slide-in-left" style={{"--i":2} as any}>{m.desc}</p></div></div><Fragment>{page==="graph"?<TalentGraphPage onCompare={()=>onNavigate?.("compare")} preferredCandidateName={preferredCandidateName}/>:page==="compare"?<CompareRoute onBack={()=>onNavigate?.("graph")}/>:page==="evolution"?<TrendInsightsPage/>:page==="unified"?<AssessmentPage onOpenGraph={onOpenGraph}/>:page==="favorites"?<FavoritesPage onOpenGraph={onOpenGraph}/>:page==="about"?<AboutPage onBack={()=>onNavigate?.("overview")}/>:<JobsPage workspace={false} onNavigate={onNavigate}/>}</Fragment></main>;
}

type GraphNode={id:string;label:string;type:"person"|"skill"|"gap"|"job";score:number;x:number;y:number;desc:string};
type JobFit={score:number;summary:string;matched:string[];gaps:string[];path:string[]};
const educationScore=(education?:string)=>({"高中及以下":35,"专科":52,"本科":72,"硕士":88,"博士":100}[education||""]||45);
const candidateDimensions=(candidate?:CandidateRow)=>{
  const skills=Math.min(100,35+(candidate?.skills?.length||0)*12);
  const experience=Math.min(100,Math.round((candidate?.experienceYears||0)/8*100));
  const education=educationScore(candidate?.education);
  const project=candidate?.projectScore||0;
  const collaboration=candidate?.collaborationScore||0;
  return {skills,experience,education,project,collaboration,overall:Math.round((skills+experience+education+project+collaboration)/5)};
};
const jobProfiles=[
  {id:"job1",label:"高级后端工程师",minYears:5,groups:[["Java","Go"],["微服务","分布式架构"],["Redis","MySQL"],["性能优化","高并发"]]},
  {id:"job2",label:"云原生工程师",minYears:4,groups:[["Kubernetes","K8s"],["Docker","容器"],["Go"],["微服务","云原生"]]},
  {id:"job3",label:"技术架构师",minYears:7,groups:[["分布式架构","系统设计"],["微服务"],["Java","Go"],["技术管理","架构"]]},
];
function buildJobFit(candidate:CandidateRow,profile:typeof jobProfiles[number]):JobFit{
  const evidence=`${(candidate.skills||[]).join(" ")} ${candidate.profileText||""}`.toLowerCase();
  const matched=profile.groups.filter(group=>group.some(skill=>evidence.includes(skill.toLowerCase()))).map(group=>group.join("/"));
  const gaps=profile.groups.filter(group=>!group.some(skill=>evidence.includes(skill.toLowerCase()))).map(group=>group[0]);
  const skillPart=matched.length/profile.groups.length*58;
  const experiencePart=Math.min(1,(candidate.experienceYears||0)/profile.minYears)*22;
  const score=Math.round(Math.min(98,skillPart+experiencePart+(candidate.projectScore||0)*.12+(candidate.collaborationScore||0)*.08));
  const start=(candidate.skills||[])[0]||"现有专业能力";
  const target=gaps[0]||"岗位核心能力";
  const bridge=target.includes("Kubernetes")?"容器与 Docker":target.includes("分布式")?"微服务与系统设计":target.includes("技术管理")?"架构决策与项目推动":target.includes("性能")?"性能监控与压测":"岗位项目实践";
  return {score,matched,gaps,path:gaps.length?[start,bridge,target]:[start,"复杂项目实践",profile.label],summary:score>=85?`核心技能和经验与${profile.label}高度契合，可优先进入后续招聘环节。`:score>=65?`具备部分可迁移能力，补充${gaps.slice(0,2).join("、")||"岗位实践"}后适配度会明显提升。`:`当前能力证据与${profile.label}要求存在较大距离，建议先核实项目深度和关键技能。`};
}
const initialGraphNodes:GraphNode[]=[
  {id:"p",label:"候选人画像",type:"person",score:86,x:2,y:43,desc:"综合候选人档案、项目经历和评估结果形成的核心画像。"},
  {id:"java",label:"Java",type:"skill",score:92,x:31,y:12,desc:"高级熟练，具备大型系统开发经验。"},
  {id:"go",label:"Go",type:"skill",score:84,x:31,y:42,desc:"熟悉并发模型与微服务开发。"},
  {id:"arch",label:"分布式架构",type:"skill",score:88,x:31,y:72,desc:"具备高并发系统架构和重构经验。"},
  {id:"k8s",label:"Kubernetes",type:"gap",score:58,x:52,y:25,desc:"当前能力缺口，建议补充生产环境实践。"},
  {id:"team",label:"团队协作",type:"skill",score:90,x:52,y:61,desc:"具备跨团队协作与项目推动能力。"},
  {id:"job1",label:"高级后端工程师",type:"job",score:91,x:76,y:12,desc:"与候选人技术经验高度匹配。"},
  {id:"job2",label:"云原生工程师",type:"job",score:78,x:76,y:42,desc:"需进一步补充容器平台经验。"},
  {id:"job3",label:"技术架构师",type:"job",score:82,x:76,y:72,desc:"架构能力匹配，管理经验需复核。"},
];
const graphEdges=[["p","java"],["p","go"],["p","arch"],["p","k8s"],["p","team"],["java","job1"],["go","job2"],["arch","job3"]];

const NODE_HALF_W=9, NODE_HALF_H=4; // node visual centre offset in viewBox units (0-100)

export function TalentGraphPage({onCompare,preferredCandidateName,embedded,onBackToMatching}:{onCompare:()=>void;preferredCandidateName?:string;embedded?:boolean;onBackToMatching?:()=>void}){
  const [nodes,setNodes]=useState(initialGraphNodes);const [selectedId,setSelectedId]=useState("p");const [candidates,setCandidates]=useState<CandidateRow[]>([]);const [candidateId,setCandidateId]=useState("");const [favorites,setFavorites]=useState<string[]>([]);const [remoteFits,setRemoteFits]=useState<Record<string,JobFit>>({});const dragging=useRef<string|null>(null);
  const nodeRefs=useRef<Record<string,HTMLButtonElement|null>>({});
  const lineRefs=useRef<Record<string,SVGElement|null>>({});
  const [hoveredNode,setHoveredNode]=useState<string>("");
  const activeCandidate=candidates.find(item=>item.id===candidateId);const dimensions=candidateDimensions(activeCandidate);const jobFits=activeCandidate?Object.fromEntries(jobProfiles.map(profile=>[profile.id,buildJobFit(activeCandidate,profile)])) as Record<string,JobFit>:{};
  const applyCandidate=(candidate?:CandidateRow)=>{if(!candidate)return;const metrics=candidateDimensions(candidate);const fits=Object.fromEntries(jobProfiles.map(profile=>[profile.id,buildJobFit(candidate,profile)])) as Record<string,JobFit>;setNodes(initialGraphNodes.map(node=>node.id==="p"?{...node,label:candidate.name||"匿名候选人",score:metrics.overall,desc:`${candidate.education||"学历未填写"} · ${candidate.experienceYears||0} 年经验 · ${(candidate.skills||[]).join("、")||"技能待补充"}`}:["java","go","arch"].includes(node.id)?{...node,label:candidate.skills?.[["java","go","arch"].indexOf(node.id)]||"待补充技能",score:Math.max(0,metrics.skills-["java","go","arch"].indexOf(node.id)*7),desc:`候选人档案中的能力证据：${candidate.skills?.[["java","go","arch"].indexOf(node.id)]||"尚待补充"}`} :node.id==="k8s"?{...node,label:fits.job2.gaps[0]||"云原生实践",score:fits.job2.gaps.length?45:82,desc:fits.job2.gaps.length?"目标岗位需要、当前档案尚缺少充分证据。":"该能力已有岗位实践证据。"}:node.id==="team"?{...node,score:metrics.collaboration,desc:"来自项目协作、沟通推动和团队交付证据。"}:node.type==="job"?{...node,score:fits[node.id].score,desc:fits[node.id].summary}:node));setSelectedId("p")};
  const fallback:CandidateRow={id:"fallback",name:"张明宇",skills:["Java","Go","分布式架构","Redis","MySQL"],experienceYears:5,education:"硕士",stage:"评估中",createdAt:new Date().toISOString(),projectScore:88,collaborationScore:85,profileText:"张明宇具备5年大型互联网后端开发经验，精通Java/Go多语言开发，曾主导过千万级DAU系统的架构重构。熟悉高并发、分布式事务、容器化部署与微服务治理。拥有扎实的计算机基础与优秀的工程化落地能力。"};
  const [dataLoaded,setDataLoaded]=useState(false);
  const useFallback=useCallback(()=>{setCandidates([fallback]);setCandidateId("fallback");applyCandidate(fallback);setDataLoaded(true)},[]);
  useEffect(()=>{const requested=(preferredCandidateName||sessionStorage.getItem("talentmatch-graph-candidate")||localStorage.getItem("talentmatch-graph-candidate")||"").trim();let cancelled=false;let fallbackCalled=false;const timer=setTimeout(()=>{if(!cancelled&&!dataLoaded&&!fallbackCalled){fallbackCalled=true;useFallback()}},2000);json("/api/hr/state").then(data=>{if(cancelled)return;clearTimeout(timer);const rows:CandidateRow[]=data.candidates||[];const active=rows.find((c:CandidateRow)=>(c.name||"匿名候选人").trim()===requested)||rows[0];if(!active){if(!fallbackCalled){fallbackCalled=true;useFallback()}return}setCandidates(rows);setFavorites(data.favorites||[]);setCandidateId(active.id);applyCandidate(active);setDataLoaded(true);sessionStorage.removeItem("talentmatch-graph-candidate");localStorage.removeItem("talentmatch-graph-candidate")}).catch(()=>{if(cancelled)return;clearTimeout(timer);if(!fallbackCalled){fallbackCalled=true;useFallback()}});return ()=>{cancelled=true;clearTimeout(timer)}},[]);

  const selected=nodes.find(node=>node.id===selectedId)||nodes[0];const selectedFit=selected.type==="job"?(remoteFits[selected.id]||jobFits[selected.id]):null;const isFavorite=Boolean(candidateId&&favorites.includes(candidateId));
  const selectNode=(node:GraphNode)=>{setSelectedId(node.id);if(node.type==="job"&&candidateId)json("/api/graph/job-fit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({candidateId,jobId:node.id})}).then(result=>setRemoteFits(rows=>({...rows,[node.id]:result}))).catch(()=>undefined)};
  const toggleFavorite=async()=>{if(!candidateId)return;await json(`/api/hr/favorites/${candidateId}`,{method:isFavorite?"DELETE":"PUT"});setFavorites(rows=>isFavorite?rows.filter(id=>id!==candidateId):[candidateId,...rows])};

  /* ── 物理公式推理拖拽：无瞬移，节点跟随鼠标的相对偏移保持恒定 ──
         F_ext = cursor_pct - offset_pct  (目标位置)
         直接驱 DOM，无弹簧延迟 = 绝对跟手
         offset 在 pointerdown 时捕获为 cursor% - node%，确保点击后不会跳动
  ── */
  const dragOffset=useRef({dx:0,dy:0});
  const syncLines=(id:string,x:number,y:number)=>{
    graphEdges.forEach(([from,to])=>{
      const key=`${from}-${to}`; const g=lineRefs.current[key]; if(!g)return;
      const lines=g.querySelectorAll("line");
      lines.forEach(l=>{
        if(from===id){l.setAttribute("x1",String(x)); l.setAttribute("y1",String(y));}
        if(to===id)  {l.setAttribute("x2",String(x)); l.setAttribute("y2",String(y));}
      });
    });
  };
  const startDrag=(id:string)=>(event:ReactPointerEvent<HTMLButtonElement>)=>{
    event.preventDefault(); dragging.current=id; setSelectedId(id);
    const el=nodeRefs.current[id]; if(!el)return;
    const canvasRect=event.currentTarget.closest(".graph-canvas.live")?.getBoundingClientRect();
    if(!canvasRect)return;
    const nodePctX=parseFloat(el.style.left)||0;
    const nodePctY=parseFloat(el.style.top)||0;
    const cursorPctX=(event.clientX-canvasRect.left)/canvasRect.width*100;
    const cursorPctY=(event.clientY-canvasRect.top)/canvasRect.height*100;
    dragOffset.current={dx:cursorPctX-nodePctX, dy:cursorPctY-nodePctY};
    (event.target as HTMLElement).setPointerCapture?.(event.pointerId);
  };
  const onCanvasMove=(event:ReactPointerEvent<HTMLDivElement>)=>{
    if(!dragging.current)return;
    const el=nodeRefs.current[dragging.current]; if(!el)return;
    const rect=event.currentTarget.getBoundingClientRect();
    const rawPctX=(event.clientX-rect.left)/rect.width*100;
    const rawPctY=(event.clientY-rect.top)/rect.height*100;
    const pctX=Math.max(1,Math.min(97,rawPctX-dragOffset.current.dx));
    const pctY=Math.max(1,Math.min(97,rawPctY-dragOffset.current.dy));
    el.style.left=pctX+"%"; el.style.top=pctY+"%";
    syncLines(dragging.current, pctX+NODE_HALF_W, pctY+NODE_HALF_H);
  };
  const endDrag=()=>{
    if(!dragging.current)return;
    const id=dragging.current; const el=nodeRefs.current[id];
    if(el){
      const x=parseFloat(el.style.left), y=parseFloat(el.style.top);
      setNodes(rows=>rows.map(node=>node.id===id?{...node,x,y}:node));
    }
    dragging.current=null;
  };

  // 文档级 pointerup：即使鼠标移出画布，释放时也能结束拖拽
  useEffect(()=>{
    const up=()=>{if(dragging.current){const id=dragging.current;const el=nodeRefs.current[id];if(el){const x=parseFloat(el.style.left),y=parseFloat(el.style.top);setNodes(rows=>rows.map(node=>node.id===id?{...node,x,y}:node))}dragging.current=null}};
    document.addEventListener("pointerup",up);
    return ()=>document.removeEventListener("pointerup",up);
  },[]);

  /* ── 常量青色连线（无流动动画）── */
  /* ── 判断连线是否与 hover 节点相连 ── */
  const edgeConnected=(from:string,to:string)=>hoveredNode===""||from===hoveredNode||to===hoveredNode;
  const edgeDimmed=(from:string,to:string)=>hoveredNode!==""&&from!==hoveredNode&&to!==hoveredNode;

  /* ── 点阵粒子背景 Canvas ── */
  const bgCanvasRef=useRef<HTMLCanvasElement|null>(null);
  const dotsRef=useRef<Array<{cx:number;cy:number;x:number;y:number;vx:number;vy:number}>>([]);
  const bgPointer=useRef({x:-9999,y:-9999});
  useEffect(()=>{
    const canvas=bgCanvasRef.current; if(!canvas)return;
    const parent=canvas.parentElement; if(!parent)return;
    const ctx=canvas.getContext("2d"); if(!ctx)return;
    const DOT=4, GAP=14, PROX=130, DAMP=.84, SPRING=.07;
    let anim=0;
    const resize=()=>{
      const rect=parent.getBoundingClientRect();
      const dpr=window.devicePixelRatio||1;
      canvas.width=rect.width*dpr; canvas.height=rect.height*dpr;
      canvas.style.width=rect.width+"px"; canvas.style.height=rect.height+"px";
      ctx.setTransform(dpr,0,0,dpr,0,0);
      const cell=DOT+GAP;
      const cols=Math.floor((rect.width+GAP)/cell);
      const rows=Math.floor((rect.height+GAP)/cell);
      const gw=cell*cols-GAP, gh=cell*rows-GAP;
      const sx=(rect.width-gw)/2+DOT/2, sy=(rect.height-gh)/2+DOT/2;
      dotsRef.current=[];
      for(let y=0;y<rows;y++)for(let x=0;x<cols;x++){
        const cx=sx+x*cell, cy=sy+y*cell;
        dotsRef.current.push({cx,cy,x:cx,y:cy,vx:0,vy:0});
      }
    };
    resize();
    const ro=new ResizeObserver(resize); ro.observe(parent);
    const onMove=(e:MouseEvent)=>{
      const rect=parent.getBoundingClientRect();
      bgPointer.current={x:e.clientX-rect.left,y:e.clientY-rect.top};
    };
    const onLeave=()=>{bgPointer.current={x:-9999,y:-9999}};
    parent.addEventListener("mousemove",onMove,{passive:true});
    parent.addEventListener("mouseleave",onLeave);
    const loop=()=>{
      const {width:w,height:h}=canvas;
      if(w===0||h===0){anim=requestAnimationFrame(loop);return}
      ctx.clearRect(0,0,w/ (window.devicePixelRatio||1),h/ (window.devicePixelRatio||1));
      const pointer=bgPointer.current;
      for(const dot of dotsRef.current){
        dot.vx+=(dot.cx-dot.x)*SPRING; dot.vy+=(dot.cy-dot.y)*SPRING;
        const dx=dot.x-pointer.x, dy=dot.y-pointer.y;
        const dist=Math.hypot(dx,dy);
        if(dist<PROX&&dist>0){const f=(1-dist/PROX)*2.2; dot.vx+=(dx/dist)*f; dot.vy+=(dy/dist)*f}
        dot.vx*=DAMP; dot.vy*=DAMP; dot.x+=dot.vx; dot.y+=dot.vy;
        const alpha=.28+(1-Math.min(1,dist/PROX))*.45;
        ctx.beginPath(); ctx.arc(dot.x,dot.y,DOT/2,0,Math.PI*2);
        ctx.fillStyle=`rgba(82,185,200,${alpha.toFixed(2)})`; ctx.fill();
      }
      anim=requestAnimationFrame(loop);
    };
    anim=requestAnimationFrame(loop);
    return ()=>{cancelAnimationFrame(anim); ro.disconnect(); parent.removeEventListener("mousemove",onMove); parent.removeEventListener("mouseleave",onLeave)};
  },[]);

  /* ── 简历高亮：把技能词用 <mark> 包裹 ── */
  const highlightResume=(text:string,keywords:string[])=>{
    if(!text||!keywords.length)return text||"暂无简历文本";
    const escaped=keywords.map(k=>k.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).filter(Boolean);
    if(!escaped.length)return text;
    const pattern=new RegExp(`(${escaped.join("|")})`,'gi');
    const parts=text.split(pattern);
    return parts.map((part,i)=>pattern.test(` ${part} `)?<mark key={i}>{part}</mark>:part);
  };
  /* ── 同行候选人(同技能) ── */
  const skillPeers=(skillName:string)=>candidates.filter(c=>c.id!==candidateId&&(c.skills||[]).some(s=>s.includes(skillName)||skillName.includes(s))).slice(0,4);
  const tagStyle={fontStyle:"normal" as const,padding:"3px 7px",borderRadius:999,fontSize:10,border:"1px solid rgba(203,188,255,.12)",background:"rgba(255,255,255,.025)",color:"rgba(255,255,255,.45)"};
  const tagMatch={fontStyle:"normal" as const,padding:"3px 7px",borderRadius:999,fontSize:10,border:"1px solid rgba(155,242,233,.18)",background:"rgba(0,221,235,.06)",color:"#9bf2e9"};
  const tagGap={fontStyle:"normal" as const,padding:"3px 7px",borderRadius:999,fontSize:10,border:"1px solid rgba(255,135,148,.18)",background:"rgba(255,90,110,.06)",color:"#ffb9c0"};

  return <>{embedded&&<div className="page-actions" style={{marginBottom:0}}><button className="ghost-action spring-hover" onClick={onBackToMatching}><ArrowLeft/>返回匹配结果</button></div>}{embedded&&dataLoaded&&candidates.length===0?<section className="interactive-graph" style={{display:"flex",alignItems:"center",justifyContent:"center",minHeight:480}}><div style={{display:"flex",flexDirection:"column",alignItems:"center",gap:20,textAlign:"center",padding:40}}><div style={{width:72,height:72,borderRadius:"50%",display:"grid",placeItems:"center",background:"radial-gradient(circle,rgba(0,221,235,.12),transparent 70%)",border:"1px solid rgba(0,221,235,.15)"}}><UserRound style={{width:32,height:32,color:"rgba(0,221,235,.45)"}}/></div><h3 style={{margin:0,fontSize:18,fontWeight:600,color:"rgba(255,255,255,.65)"}}>暂无候选人数据</h3><p style={{margin:0,fontSize:13,lineHeight:1.7,color:"rgba(255,255,255,.35)",maxWidth:420}}>请先在「智能匹配」中上传简历并完成评估，然后从匹配结果点击「查看人才能力图谱」跳转到这里。</p><button className="ghost-action spring-hover" onClick={onBackToMatching} style={{marginTop:8}}><ArrowLeft/>返回智能匹配</button></div></section>:<><div className="page-actions graph-actions"><label><span>查看候选人</span><select value={candidateId} onChange={event=>{setCandidateId(event.target.value);setRemoteFits({});applyCandidate(candidates.find(x=>x.id===event.target.value))}}>{candidates.map(candidate=><option key={candidate.id} value={candidate.id}>{candidate.name||"匿名候选人"}</option>)}</select></label><button className={`ghost-action favorite-action ${isFavorite?"active":""}`} onClick={toggleFavorite}><Heart fill={isFavorite?"currentColor":"none"}/>{isFavorite?"已特别关注":"特别关注"}</button><button className="primary small-primary" onClick={onCompare}><GitCompareArrows/>候选人对比</button></div><section className="interactive-graph"><div className="graph-canvas live" onPointerMove={onCanvasMove} onPointerUp={endDrag} onClick={()=>setSelectedId("")}><canvas ref={bgCanvasRef} className="graph-dot-canvas" style={{position:"absolute",inset:0,zIndex:0,pointerEvents:"none",borderRadius:14}}/><svg className="graph-lines" viewBox="0 0 100 100" preserveAspectRatio="none">{graphEdges.map(([from,to])=>{const a=nodes.find(x=>x.id===from)!;const b=nodes.find(x=>x.id===to)!;const connected=edgeConnected(from,to);const dimmed=edgeDimmed(from,to);const x1=a.x+NODE_HALF_W,y1=a.y+NODE_HALF_H,x2=b.x,y2=b.y+NODE_HALF_H;return <g key={`${from}-${to}`} ref={el=>{lineRefs.current[`${from}-${to}`]=el}} className={dimmed?"graph-edge--dim":""}><line className={`graph-edge--cyan${connected&&hoveredNode!==""?" graph-edge--active":""}`} x1={x1} y1={y1} x2={x2} y2={y2}/></g>})}</svg>{nodes.map(node=>{return <button key={node.id} ref={el=>{nodeRefs.current[node.id]=el}} className={`live-node ${node.type} ${selectedId===node.id?"selected":""} ${hoveredNode===node.id?"node-hovered":""}`} style={{left:`${node.x}%`,top:`${node.y}%`}} onPointerDown={startDrag(node.id)} onPointerEnter={()=>{if(!dragging.current)setHoveredNode(node.id)}} onPointerLeave={()=>{if(!dragging.current)setHoveredNode("")}} onClick={e=>{e.stopPropagation();selectNode(node)}}><span>{node.label}</span><small>{node.score}分</small></button>})}</div>{/* popover */selectedId!==""&&selectedId!=="p"&&(()=>{const node=nodes.find(n=>n.id===selectedId);if(!node)return null;const fit=node.type==="job"?(remoteFits[node.id]||jobFits[node.id]):null;const isPerson=node.type==="person";const nodeEl=nodeRefs.current[node.id];const pctX=parseFloat(nodeEl?.style.left||"0");const pctY=parseFloat(nodeEl?.style.top||"0");return <div className="graph-popover-flyout" style={{left:`${Math.min(pctX+3,68)}%`,top:`${Math.max(8,pctY-5)}%`}} onMouseLeave={()=>setSelectedId("")} onClick={e=>e.stopPropagation()}><div className="graph-popover-flyout__inner"><div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:12}}><div style={{minWidth:0}}><span style={{fontSize:10,fontWeight:500,color:"rgba(155,242,233,.65)",letterSpacing:".08em",marginBottom:4,display:"block"}}>{node.type==="person"?"候选人":node.type==="job"?"岗位匹配":node.type==="gap"?"能力缺口":"核心技能"}</span><b style={{fontSize:16,color:"rgba(255,255,255,.90)",display:"block",marginBottom:4}}>{node.label}</b><small style={{color:"rgba(255,255,255,.45)",fontSize:11}}>{node.score} 分</small></div><div className="popover-score-ring"><span style={{fontFamily:`"SF Pro Rounded","JetBrains Mono",monospace`,fontSize:20,fontWeight:800,lineHeight:1,color:"rgba(255,255,255,.95)",fontVariantNumeric:"tabular-nums",WebkitFontSmoothing:"antialiased"}}>{isPerson?dimensions.overall:node.score}</span><span style={{display:"block",fontSize:7,color:"rgba(6,182,212,.70)",fontWeight:300,transform:"translateY(-3px)"}}>分</span></div></div><div style={{marginTop:14,paddingTop:14,borderTop:"1px solid rgba(255,255,255,.08)"}}>{isPerson?<><div style={{display:"flex",flexWrap:"wrap",gap:5,marginBottom:10}}><i style={tagStyle}>{activeCandidate?.education||"学历未填写"}</i><i style={tagStyle}>{activeCandidate?.experienceYears||0} 年经验</i>{(activeCandidate?.skills||[]).slice(0,4).map((s:string)=><i key={s} style={{...tagStyle,borderColor:"rgba(155,242,233,.18)",background:"rgba(0,221,235,.06)",color:"#9bf2e9"}}>{s}</i>)}</div><div className="score-dimensions" style={{marginBottom:8}}><span>技能<b>{dimensions.skills}</b></span><span>经验<b>{dimensions.experience}</b></span><span>学历<b>{dimensions.education}</b></span><span>项目<b>{dimensions.project}</b></span><span>协作<b>{dimensions.collaboration}</b></span></div><p style={{margin:0,fontSize:10,lineHeight:1.6,color:"rgba(255,255,255,.40)"}}>综合技能、经验、学历、项目与协作能力计算。</p></>:fit?<><p style={{margin:0,fontSize:10,lineHeight:1.6,color:"rgba(255,255,255,.45)",marginBottom:8}}>{fit.summary}</p><div style={{fontSize:9,color:"rgba(255,255,255,.30)",marginBottom:3}}>已验证的匹配证据</div><div style={{display:"flex",flexWrap:"wrap",gap:4,marginBottom:8}}>{fit.matched.length?fit.matched.map((x:string)=><i key={x} style={tagMatch}>{x}</i>):<i style={tagMatch}>证据不足</i>}</div>{fit.gaps.length>0&&<><div style={{fontSize:9,color:"rgba(255,255,255,.30)",marginBottom:3}}>需要补充</div><div style={{display:"flex",flexWrap:"wrap",gap:4,marginBottom:8}}>{fit.gaps.map((x:string)=><i key={x} style={tagGap}>{x}</i>)}</div></>}<div style={{fontSize:9,color:"rgba(255,255,255,.30)",marginBottom:3}}>补齐路径</div><div style={{display:"flex",flexWrap:"wrap",gap:3}}>{fit.path.map((x:string,i:number)=><span key={i} style={{fontSize:9,color:"rgba(255,255,255,.40)",display:"inline-flex",alignItems:"center",gap:2}}>{x}{i<fit.path.length-1&&<span style={{color:"rgba(0,221,235,.4)"}}>→</span>}</span>)}</div></>:<p style={{margin:0,fontSize:10,lineHeight:1.6,color:"rgba(255,255,255,.45)"}}>{node.desc}</p>}</div></div></div>})()}<aside className="node-detail comprehensive-detail">{activeCandidate?<><span>候选人画像</span><h3>{activeCandidate.name||"匿名候选人"}</h3><div className="node-score person">{dimensions.overall}<small>分</small></div><p style={{fontSize:12,lineHeight:1.7,color:"rgba(255,255,255,.50)",margin:"0 0 16px"}}>综合技能覆盖、相关经验、学历背景、项目经历和协作能力计算。</p><div className="score-dimensions"><span>技能<b>{dimensions.skills}</b></span><span>经验<b>{dimensions.experience}</b></span><span>学历<b>{dimensions.education}</b></span><span>项目<b>{dimensions.project}</b></span><span>协作<b>{dimensions.collaboration}</b></span></div>{activeCandidate.profileText?<div style={{marginTop:20,padding:0}}><div style={{fontSize:11,color:"rgba(155,242,233,.55)",letterSpacing:".08em",marginBottom:10,fontWeight:600}}>候选人简历</div><div style={{padding:"14px 15px",borderRadius:10,border:"1px solid rgba(255,255,255,.08)",background:"rgba(0,0,0,.15)",maxHeight:260,overflowY:"auto"}}><pre style={{margin:0,fontSize:10,lineHeight:1.75,color:"rgba(255,255,255,.45)",whiteSpace:"pre-wrap",wordBreak:"break-word",fontFamily:`"SF Pro Display","PingFang SC","Noto Sans SC",sans-serif`}}>{activeCandidate.profileText}</pre></div></div>:<div style={{marginTop:20,padding:"14px 16px",borderRadius:10,border:"1px solid rgba(255,255,255,.06)",background:"rgba(255,255,255,.015)"}}><div style={{fontSize:10,color:"rgba(155,242,233,.55)",letterSpacing:".08em",marginBottom:8,fontWeight:600}}>使用提示</div><p style={{margin:0,fontSize:11,lineHeight:1.7,color:"rgba(255,255,255,.40)"}}>点击图谱中任意节点查看详情。点击岗位节点可展开该候选人对具体岗位的匹配分析和能力缺口。</p></div>}</>:<><div style={{display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",flex:1,gap:16,textAlign:"center",padding:"40px 20px"}}><div style={{width:56,height:56,borderRadius:"50%",display:"grid",placeItems:"center",background:"radial-gradient(circle,rgba(0,221,235,.12),transparent 70%)",border:"1px solid rgba(0,221,235,.15)"}}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="rgba(0,221,235,.45)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg></div><span style={{fontSize:14,fontWeight:600,color:"rgba(255,255,255,.60)"}}>尚未加载候选人数据</span><p style={{margin:0,fontSize:11,lineHeight:1.7,color:"rgba(255,255,255,.35)"}}>请先在"人岗匹配"页面上传简历并完成评估，或等待后端服务启动后自动加载示例数据。</p></div></>}</aside></section></>}</>;
}

function CompareRoute({onBack}:{onBack:()=>void}){return <><div className="page-actions compare-back"><button className="ghost-action spring-hover" onClick={onBack}><ArrowLeft/>返回人岗匹配</button></div><GraphPage/></>}

function ProjectIntro({onOpen}:{onOpen:()=>void}){return <button className="project-intro spring-hover" onClick={onOpen}><Info/><span><b>关于 TalentMatch</b><small>岗位数据、人才评估、知识图谱与向量检索驱动的招聘决策系统</small></span><ArrowUpRight/></button>}

function AboutPage({onBack}:{onBack:()=>void}){return <><div className="page-actions"><button className="ghost-action spring-hover" onClick={onBack}><ArrowLeft/>返回主页</button></div><section className="about-grid"><article><Sparkles/><span>01</span><h3>智能人才评估</h3><p>结合岗位要求、候选人技能、经历、学历与项目证据，形成可解释的人岗匹配结果。</p></article><article><Activity/><span>02</span><h3>能力图谱</h3><p>以左中右关系展示候选人、能力节点和适配岗位，并支持候选人之间的横向比较。</p></article><article><Search/><span>03</span><h3>Milvus 向量检索</h3><p>将人才档案转换为向量写入 Milvus，为相似人才召回、岗位推荐和 RAG 检索提供底层能力。</p></article><article><BriefcaseBusiness/><span>04</span><h3>招聘趋势洞察</h3><p>保留时间维度数据，支持技能热度变化和不同年份的横向对比分析。</p></article></section></>}

function CapabilityPage({onNavigate}:{onNavigate?:(page:PageKey|"matching")=>void}) {
  return (
    <main className="platform-main">
      <div className="page-heading">
        <div>
          <span className="slide-in-left" style={{"--i":0} as any}>JOB CAPABILITY GRAPH</span>
          <h2 className="slide-in-left" style={{"--i":1} as any}>岗位能力图谱</h2>
          <p className="slide-in-left" style={{"--i":2} as any}>展示岗位—技能点—能力维度的全景关系图谱，支持技术栈、级别与版本筛选。</p>
        </div>
      </div>
      <CompetitionErrorBoundary pageName="岗位能力图谱" onNavigateHome={() => onNavigate?.("overview")}>
        <RoleCapabilityGraph />
      </CompetitionErrorBoundary>
    </main>
  );
}

function TrendInsightsPage(){const [mode,setMode]=useState<"change"|"compare">("change");return <><div className="trend-mode-switch"><button type="button" className={mode==="change"?"active":""} onClick={()=>setMode("change")}><Activity/>时间变化图</button><button type="button" className={mode==="compare"?"active":""} onClick={()=>setMode("compare")}><GitCompareArrows/>时间对比图</button></div>{mode==="change"?<CachedEvolutionPage/>:<YearComparisonPage/>}</>}

const monthKey=(value:string)=>/^\d{4}-\d{2}$/.test(value)?value:`${String(value).slice(0,4)}-01`;
const addMonths=(value:string,offset:number)=>{const [year,month]=monthKey(value).split("-").map(Number);const date=new Date(year,month-1+offset,1);return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}`};
const monthPoints=(values:number[],max:number)=>values.map((value,index)=>`${20+index*(960/Math.max(1,values.length-1))},${315-value/max*280}`).join(" ");
function monthlyRows(series:any[],count:number){
  const normalized=series.map(row=>({...row,period:monthKey(String(row.period))})).sort((a,b)=>a.period.localeCompare(b.period));if(!normalized.length)return [];
  const byMonth=new Map(normalized.map(row=>[row.period,row]));const end=normalized.at(-1)!.period;return Array.from({length:count},(_,index)=>{const period=addMonths(end,index-count+1);return byMonth.get(period)||{period,demand:0,sourceCount:0}});
}

function YearComparisonPage(){
  const [data,setData]=useState<any>(null);const [role,setRole]=useState("java-backend-engineer");const [skill,setSkill]=useState("");const [yearA,setYearA]=useState("");const [yearB,setYearB]=useState("");const [loading,setLoading]=useState(false);
  useEffect(()=>{setLoading(true);json(`/api/trends?jobId=${encodeURIComponent(role)}&refresh=0`).then(payload=>{const evolution=payload.evolution||{};setData(evolution);const availableSkills=Array.from(new Set((evolution.series||[]).map((row:any)=>row.skill))) as string[];const years=Array.from(new Set((evolution.series||[]).map((row:any)=>String(row.period).slice(0,4)))).sort() as string[];setSkill(current=>current&&availableSkills.includes(current)?current:availableSkills[0]||"");setYearA(current=>current&&years.includes(current)?current:years.at(-2)||years[0]||"");setYearB(current=>current&&years.includes(current)?current:years.at(-1)||years[0]||"")}).finally(()=>setLoading(false))},[role]);
  const years=Array.from(new Set((data?.series||[]).map((row:any)=>String(row.period).slice(0,4)))).sort() as string[];const skills=Array.from(new Set((data?.series||[]).map((row:any)=>row.skill))) as string[];const valuesFor=(year:string)=>Array.from({length:12},(_,index)=>(data?.series||[]).filter((row:any)=>row.skill===skill&&monthKey(String(row.period))===`${year}-${String(index+1).padStart(2,"0")}`).reduce((sum:number,row:any)=>sum+Number(row.demand||0),0));const valuesA=valuesFor(yearA);const valuesB=valuesFor(yearB);const max=Math.max(1,...valuesA,...valuesB);const totalA=valuesA.reduce((sum,value)=>sum+value,0);const totalB=valuesB.reduce((sum,value)=>sum+value,0);const difference=totalB-totalA;const roleName=(data?.roleOptions||[]).find((item:any)=>item.roleId===role)?.role||data?.title||"岗位";const months=Array.from({length:12},(_,index)=>`${String(index+1).padStart(2,"0")}月`);
  return <section className="year-compare line-compare"><div className="year-compare-head four-fields"><label><span>特定岗位</span><select value={role} onChange={event=>setRole(event.target.value)}>{(data?.roleOptions||[]).map((item:any)=><option value={item.roleId} key={item.roleId}>{item.role}</option>)}</select></label><label><span>技能趋势</span><select value={skill} onChange={event=>setSkill(event.target.value)}>{skills.map(item=><option key={item}>{item}</option>)}</select></label><label><span>起始年份</span><select value={yearA} onChange={event=>setYearA(event.target.value)}>{years.map(year=><option key={year}>{year}</option>)}</select></label><label><span>对比年份</span><select value={yearB} onChange={event=>setYearB(event.target.value)}>{years.map(year=><option key={year}>{year}</option>)}</select></label></div>{loading?<p className="compare-empty">正在读取月度趋势...</p>:years.length<2?<p className="compare-empty">当前数据不足两个年份，暂时无法进行时间对比。</p>:<><div className="chart-title comparison-line-title"><div><h3>{skill||"技能"} · {roleName}</h3><span>按 1—12 月对齐比较 · {yearA} 合计 <b>{totalA}</b> · {yearB} 合计 <b>{totalB}</b></span></div><div className="line-legend"><span className="year-a"><i/>{yearA}</span><span className="year-b"><i/>{yearB}</span></div></div><div className="market-canvas compare-canvas"><div className="axis-labels"><span>{max}</span><span>{Math.round(max*.66)}</span><span>{Math.round(max*.33)}</span><span>0</span></div><svg viewBox="0 0 1000 340" preserveAspectRatio="none"><polyline points={monthPoints(valuesA,max)} fill="none" stroke="#9bf2e9" strokeWidth="4"/><polyline points={monthPoints(valuesB,max)} fill="none" stroke="#a58dff" strokeWidth="4"/>{valuesA.map((value,index)=><circle key={`a-${index}`} cx={20+index*(960/11)} cy={315-value/max*280} r="5" fill="#131318" stroke="#9bf2e9" strokeWidth="3"><title>{yearA}年{months[index]}：{value}</title></circle>)}{valuesB.map((value,index)=><circle key={`b-${index}`} cx={20+index*(960/11)} cy={315-value/max*280} r="5" fill="#131318" stroke="#a58dff" strokeWidth="3"><title>{yearB}年{months[index]}：{value}</title></circle>)}</svg></div><div className="time-axis monthly-axis">{months.map(month=><span key={month}>{month}</span>)}</div><div className="comparison-summary"><GitCompareArrows/><p>{difference>0?`${yearB} 年全年需求比 ${yearA} 年增加 ${difference}；折线按月展示变化，可直接判断增长集中在哪些月份。`:difference<0?`${yearB} 年全年需求比 ${yearA} 年减少 ${Math.abs(difference)}；折线按月展示下降发生的具体月份。`:`两个年份全年需求总量一致，可通过月度折线观察需求高峰出现时间的差异。`}</p></div></>}</section>;
}

function CachedEvolutionPage(){
  const [role,setRole]=useState("java-backend-engineer");const [skill,setSkill]=useState("Java");const [months,setMonths]=useState(12);const [data,setData]=useState<any>(null);const [loading,setLoading]=useState(false);const [cachedAt,setCachedAt]=useState("");const [cacheStatus,setCacheStatus]=useState("");
  const load=async(force=false)=>{setLoading(true);try{const payload=await json(`/api/trends?jobId=${encodeURIComponent(role)}&refresh=${force?1:0}`);const evolution=payload.evolution||{};setData(evolution);setCachedAt(payload.cachedAt||"");setCacheStatus(payload.cacheStatus||"");const available=Array.from(new Set((evolution.series||[]).map((x:any)=>x.skill))) as string[];if(!available.includes(skill))setSkill(available[0]||"")}finally{setLoading(false)}};
  useEffect(()=>{load(false)},[role]);const skills=Array.from(new Set((data?.series||[]).map((x:any)=>x.skill))) as string[];const all=(data?.series||[]).filter((x:any)=>x.skill===skill);const rows=monthlyRows(all,months);const historicalValues=rows.map((row:any)=>Number(row.demand||0));const last=historicalValues.at(-1)||0;const recent=historicalValues.slice(-4);const rawStep=recent.length>1?(recent.slice(1).reduce((sum,value,index)=>sum+value-recent[index],0)/(recent.length-1)):0;const stepLimit=Math.max(1,last*.2);const step=Math.max(-stepLimit,Math.min(stepLimit,rawStep));let projected=last;const forecast=Array.from({length:6},(_,index)=>{projected=Math.max(0,Math.round(projected+step));return {period:addMonths(rows.at(-1)?.period||monthKey(new Date().toISOString().slice(0,7)),index+1),demand:projected}});const combinedValues=[...historicalValues,...forecast.map(item=>item.demand)];const max=Math.max(1,...combinedValues);const totalCount=combinedValues.length;const x=(index:number)=>20+index*(960/Math.max(1,totalCount-1));const y=(value:number)=>315-value/max*280;const historicalPoints=historicalValues.map((value,index)=>`${x(index)},${y(value)}`).join(" ");const forecastPoints=[last,...forecast.map(item=>item.demand)].map((value,index)=>`${x(rows.length-1+index)},${y(value)}`).join(" ");const predictionStart=x(Math.max(0,rows.length-1));const axisRows=[...rows,...forecast];
  return <><div className="page-actions"><span><Clock3/>数据时间：{cachedAt?timeText(new Date(cachedAt)):"等待数据"}</span><button className="ghost-action spring-hover" onClick={()=>load(true)} disabled={loading}><RefreshCw className={loading?"spin":""}/>{loading?"更新中":"获取最新趋势"}</button></div><section className="evolution-panel market-chart"><div className="trend-filter"><label><span>特定岗位</span><select value={role} onChange={e=>setRole(e.target.value)}>{(data?.roleOptions||[]).map((x:any)=><option key={x.roleId} value={x.roleId}>{x.role}（{x.recordCount}）</option>)}</select></label><label><span>技能趋势</span><select value={skill} onChange={e=>setSkill(e.target.value)}>{skills.map(x=><option key={x}>{x}</option>)}</select></label><div><span>历史范围</span>{[[6,"6个月"],[12,"12个月"],[24,"24个月"]].map(([n,l])=><button className={months===n?"active":""} onClick={()=>setMonths(n as number)} key={n}>{l}</button>)}</div></div><div className="chart-title"><div><h3>{skill||"技能"} · {data?.title||"岗位需求趋势"}</h3><span>当前需求量 <b>{last}</b> · 历史按月统计 · 右侧虚线为未来 6 个月预测</span></div><div className="line-legend"><span className="history-line"><i/>历史数据</span><span className="forecast-line"><i/>预测数据（虚线）</span></div></div><div className="market-canvas forecast-canvas"><div className="axis-labels"><span>{max}</span><span>{Math.round(max*.66)}</span><span>{Math.round(max*.33)}</span><span>0</span></div><svg viewBox="0 0 1000 340" preserveAspectRatio="none"><defs><linearGradient id="cachedMarketArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#9bf2e9" stopOpacity=".28"/><stop offset="1" stopColor="#7c5cff" stopOpacity="0"/></linearGradient></defs><rect x={predictionStart} y="0" width={1000-predictionStart} height="340" fill="#7c5cff" opacity=".055"/><polygon points={`${historicalPoints} ${x(rows.length-1)},330 20,330`} fill="url(#cachedMarketArea)"/><polyline points={historicalPoints} fill="none" stroke="#9bf2e9" strokeWidth="4"/><polyline className="forecast-polyline" points={forecastPoints} fill="none" stroke="#b39dff" strokeWidth="4" strokeDasharray="14 10"/><line x1={predictionStart} y1="10" x2={predictionStart} y2="330" stroke="#8f7ad8" strokeWidth="2" strokeDasharray="5 8"/><text x={Math.min(900,predictionStart+12)} y="24" fill="#b9a8f5" fontSize="13">预测区间</text>{rows.map((row:any,index:number)=><circle key={row.period} cx={x(index)} cy={y(Number(row.demand||0))} r="5" fill="#131318" stroke="#9bf2e9" strokeWidth="3"><title>{row.period}：{row.demand||0}</title></circle>)}{forecast.map((row,index)=><circle key={row.period} cx={x(rows.length+index)} cy={y(row.demand)} r="5" fill="#211c30" stroke="#b39dff" strokeWidth="3"><title>{row.period} 预测：{row.demand}</title></circle>)}</svg></div><div className="time-axis monthly-axis forecast-axis">{axisRows.map((row:any,index:number)=><span className={index>=rows.length?"predicted":""} key={row.period}>{row.period.slice(2)}{index===rows.length&&<b>预测</b>}</span>)}</div><div className="forecast-note"><TrendingUp/><p>虚线从最后一个真实月份开始延伸，表示未来 6 个月的需求估算；预测值用于趋势参考，不代表确定的岗位数量。</p></div></section></>;
}

function Stat({label,value,tone="purple",onClick,help}:{label:string;value:string|number;tone?:string;onClick?:()=>void;help?:string}){const content=<><span>{label}</span><div><b className={tone}>{value}</b>{onClick&&<ArrowUpRight/>}</div>{help&&<small>{help}</small>}</>;return onClick?<button className="stat-card actionable spring-hover" onClick={onClick}>{content}</button>:<div className="stat-card">{content}</div>}

function JobsPage({workspace,onNavigate}:{workspace:boolean;onNavigate?:(page:PageKey|"matching")=>void}){
  const pageSize=workspace?6:30;const [remoteJobs,setRemoteJobs]=useState<JobRow[]>([]);const [localJobs,setLocalJobs]=useState<JobRow[]>([]);const [total,setTotal]=useState(0);const [page,setPage]=useState(1);const [candidates,setCandidates]=useState<CandidateRow[]>([]);const [interviews,setInterviews]=useState<InterviewRow[]>([]);const [assessments,setAssessments]=useState<AssessmentRow[]>([]);const [error,setError]=useState("");const [loading,setLoading]=useState(false);const [updated,setUpdated]=useState(timeText());const [query,setQuery]=useState("");const [selected,setSelected]=useState<JobRow|null>(null);const [adding,setAdding]=useState(false);const [candidatePanel,setCandidatePanel]=useState(false);const [interviewPanel,setInterviewPanel]=useState(false);const [crawler,setCrawler]=useState<any>(null);const listPanel=useRef<HTMLDivElement|null>(null);
  const [jobsTab,setJobsTab]=useState<string>(()=>sessionStorage.getItem("talentmatch-jobsTab")||"jobs");
  /* ── Overview data for job management homepage ── */
  const [overview,setOverview]=useState<{discoveryTotal:number|null;discoveryPending:number|null;discoveryError:boolean;evidenceStatus:string|null;evidenceError:boolean;latestVersion:string|null;versionError:boolean}>({discoveryTotal:null,discoveryPending:null,discoveryError:false,evidenceStatus:null,evidenceError:false,latestVersion:null,versionError:false});
  useEffect(()=>{if(workspace)return;
    fetch("/api/platform/storage/api/competition/discoveries").then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}).then(data=>{if(!Array.isArray(data?.items))throw new Error("discoveries.items不是数组");const items=data.items;setOverview(prev=>({...prev,discoveryTotal:items.length,discoveryPending:items.filter((i:any)=>i.review_status==="pending").length,discoveryError:false}))}).catch(()=>setOverview(prev=>({...prev,discoveryError:true})));
    fetch("/api/platform/storage/api/competition/rag/health").then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}).then(data=>{if(!data||typeof data.status!=="string"||typeof data.competencies_indexed!=="number"||typeof data.roles_indexed!=="number"||typeof data.milvus_wired!=="boolean"||typeof data.neo4j_wired!=="boolean")throw new Error("RAG health结构不完整");const label=data.status==="ok"?"正常":data.status==="degraded"?"降级":"不可用";setOverview(prev=>({...prev,evidenceStatus:label,evidenceError:false}))}).catch(()=>setOverview(prev=>({...prev,evidenceError:true})));
    fetch("/api/platform/storage/api/competition/roles/java-developer/versions").then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}).then(data=>{if(!Array.isArray(data?.versions))throw new Error("versions.versions不是数组");const versions:any[]=data.versions;setOverview(prev=>({...prev,latestVersion:versions.length>0?versions[versions.length-1].version_id:"暂无",versionError:false}))}).catch(()=>setOverview(prev=>({...prev,versionError:true})));
  },[workspace]);
  const load=async(targetPage=1,append=false,search=query)=>{setLoading(true);setError("");const searchPart=search.trim()?`&keyword=${encodeURIComponent(search.trim())}`:"";const [jobResult,hrResult,assessmentResult,crawlerResult]=await Promise.allSettled([json(`/api/platform/storage/api/search/jobs?page=${targetPage}&page_size=${pageSize}${searchPart}`),json("/api/hr/state"),json("/api/assessments"),json("/api/crawler/status")]);const hr=hrResult.status==="fulfilled"?hrResult.value:{candidates:[],interviews:[],jobs:[]};const rows=jobResult.status==="fulfilled"?normalizeJobs(jobResult.value):[];const local=(hr.jobs||[]).map((x:any)=>({...x,name:x.name||x.title})).filter((x:JobRow)=>!search.trim()||`${x.name}${x.company}${x.city}`.toLowerCase().includes(search.toLowerCase()));setLocalJobs(local);setRemoteJobs(previous=>append?[...previous,...rows.filter(row=>!previous.some(item=>item.id===row.id))]:rows);setTotal(jobResult.status==="fulfilled"?Number(jobResult.value.total||rows.length):0);setPage(targetPage);setCandidates(hr.candidates||[]);setInterviews(hr.interviews||[]);setAssessments(assessmentResult.status==="fulfilled"?assessmentResult.value.items||[]:[]);if(crawlerResult.status==="fulfilled")setCrawler(crawlerResult.value);if(jobResult.status==="rejected")setError("岗位搜索服务暂未启动，候选人、面试和评估数据仍已正常读取。");setUpdated(timeText());setLoading(false)};
  useEffect(()=>{load(1,false,"")},[]);
  useEffect(()=>{const panel=sessionStorage.getItem("talentmatch-open-hr-panel");if(panel==="interviews")setInterviewPanel(true);if(panel==="candidates")setCandidatePanel(true);if(panel)sessionStorage.removeItem("talentmatch-open-hr-panel")},[]);
  useEffect(()=>{if(workspace)return;const timer=setTimeout(()=>load(1,false,query),350);return ()=>clearTimeout(timer)},[query,workspace]);
  /* scroll auto-load */
  useEffect(()=>{if(workspace)return;const el=listPanel.current;if(!el)return;let busy=false;const onScroll=()=>{if(busy)return;const s=scrollState.current;if(s.loading||!s.hasMore)return;const {scrollTop,scrollHeight,clientHeight}=el;if(scrollTop+clientHeight<scrollHeight-80)return;busy=true;loadFn.current(s.page+1,true,s.query).finally(()=>{busy=false})};el.addEventListener("scroll",onScroll,{passive:true});return ()=>el.removeEventListener("scroll",onScroll)},[workspace]);
  const loadFn=useRef(load);loadFn.current=load;const scrollState=useRef({loading:false,hasMore:true,page:1,query:""});scrollState.current={loading,hasMore:remoteJobs.length<total,page,query};const jobs=[...localJobs,...remoteJobs];const filtered=workspace?jobs.slice(0,6):jobs;
  const average=assessments.length?Math.round(assessments.reduce((sum,x)=>sum+x.score,0)/assessments.length):null;
  const add=async(job:JobRow)=>{const saved=await json("/api/hr/jobs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(job)});setLocalJobs(x=>[{...saved,name:saved.name||saved.title},...x]);setAdding(false);setUpdated(timeText());setSelected({...saved,name:saved.name||saved.title})};
  const deleteLocalJob=async(jobId:string)=>{await json(`/api/hr/jobs/${jobId}`,{method:"DELETE"});setLocalJobs(x=>x.filter(j=>j.id!==jobId));setSelected(null);setUpdated(timeText())};
  const runCrawler=async()=>{try{const state=await json("/api/crawler/refresh",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode:"quick",target:1000})});setCrawler(state);setUpdated(timeText())}catch(e){setError(e instanceof Error?e.message:"岗位采集启动失败")}};
  return <><div className="page-actions"><span><Clock3/>更新时间：{updated}</span>{!workspace&&<button className="ghost-action spring-hover" onClick={()=>load(1,false,query)} disabled={loading}><RefreshCw className={loading?"spin":""}/>{loading?"刷新中":"刷新列表"}</button>}{!workspace&&<button className="ghost-action ai-refresh" onClick={runCrawler} disabled={crawler?.status==="running"}><Sparkles/>{crawler?.status==="running"?"采集并同步中":"快速采集"}</button>}<button className="primary small-primary" onClick={()=>setAdding(true)}><Plus/>新增岗位</button></div>
    <div className="sub-nav">
      <button className={jobsTab==="jobs"?"active":""} onClick={()=>{setJobsTab("jobs");sessionStorage.setItem("talentmatch-jobsTab","jobs")}}>在招岗位</button>
      <button className={jobsTab==="discovery"?"active":""} onClick={()=>{setJobsTab("discovery");sessionStorage.setItem("talentmatch-jobsTab","discovery")}}>新岗位发现</button>
      <button className={jobsTab==="evolution"?"active":""} onClick={()=>{setJobsTab("evolution");sessionStorage.setItem("talentmatch-jobsTab","evolution")}}>岗位能力演化</button>
      <button className={jobsTab==="evidence"?"active":""} onClick={()=>{setJobsTab("evidence");sessionStorage.setItem("talentmatch-jobsTab","evidence")}}>岗位证据审核</button>
    </div>
    {/* ── Overview bar — real API only, show "不可用" on failure ── */}
    {!workspace&&<section className="stats-grid" style={{marginBottom:20}}><Stat label="新岗位候选" value={overview.discoveryError?"不可用":overview.discoveryTotal??"..."} tone={overview.discoveryError?"purple":"mint"} help={overview.discoveryError?"接口异常，无法获取新岗位候选数量":"competition 模块发现的新岗位总数"}/><Stat label="待审核" value={overview.discoveryError?"不可用":overview.discoveryPending??"..."} tone={overview.discoveryError?"purple":"cyan"} help={overview.discoveryError?"接口异常":"待审核的新岗位发现数量"}/><Stat label="最近能力版本" value={overview.versionError?"不可用":overview.latestVersion??"..."} help={overview.versionError?"接口异常，无法获取版本信息":"Java开发工程师岗位最新能力版本"}/><Stat label="证据服务" value={overview.evidenceError?"不可用":overview.evidenceStatus??"..."} tone={overview.evidenceError?"purple":overview.evidenceStatus==="正常"?"mint":"cyan"} help={overview.evidenceError?"接口异常":"轻量确定性证据检索服务状态"}/></section>}
    {jobsTab==="jobs"?<>
    {error&&<div className="service-warning"><AlertTriangle/><div><b>岗位数据未实时更新</b><span>{error}</span></div></div>}
    {crawler&&<div className={`crawler-status ${crawler.status}`}><CircleDot/><span><b>{crawler.message}</b><small>{crawler.status==="running"?`任务进程 ${crawler.pid||"启动中"}`:crawler.finishedAt?`完成时间 ${timeText(new Date(crawler.finishedAt))}`:""}</small></span></div>}
    <section className="stats-grid"><Stat label="在招岗位" value={total} onClick={()=>document.querySelector(".job-card-grid")?.scrollIntoView({behavior:"smooth"})} help={`数据库岗位总量${localJobs.length>0?`，另有本地岗位 ${localJobs.length} 条`:""}`}/><Stat label="候选人" value={candidates.length} tone="mint" onClick={()=>setCandidatePanel(true)} help="点击查看和添加候选人"/><Stat label="待安排面试" value={interviews.filter(x=>x.status==="待进行").length} tone="cyan" onClick={()=>setInterviewPanel(true)} help="点击管理面试安排"/><Stat label="平均匹配度" value={average===null?"--":`${average}%`} onClick={()=>onNavigate?.("unified")} help={average===null?"暂无真实评估记录":"真实评估总分 ÷ 评估人数"}/></section>
    {workspace&&<section className="workspace-shortcuts"><button className="spring-hover" onClick={()=>setAdding(true)}><Plus/><span><b>发布招聘岗位</b><small>创建新的招聘需求</small></span></button><button className="spring-hover" onClick={()=>onNavigate?.("matching")}><Sparkles/><span><b>开始人才评估</b><small>上传简历并进行匹配</small></span></button><button className="spring-hover" onClick={runCrawler} disabled={crawler?.status=="running"}><Sparkles/><span><b>{crawler?.status=="running"?"AI 采集中…":"AI 脚本采集"}</b><small>自动抓取最新岗位数据</small></span></button></section>}
    <section className="wide-panel" ref={listPanel} style={workspace?undefined:{maxHeight:"calc(100vh - 300px)",overflowY:"auto"}}><div className="table-toolbar"><div><h3>{workspace?"重点招聘岗位":"全部招聘岗位"}</h3><span>点击任一岗位查看完整职责与要求 · 滚动到底自动加载</span></div><label className="search-box"><Search/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索岗位、部门或城市..."/></label></div>
      <div className="job-card-grid">{filtered.map(job=><button key={job.id} className="job-card spring-hover" onClick={()=>setSelected(job)}><div><span>{job.type}</span><em>{job.city}</em></div><h3>{job.name}</h3><p>{job.description}</p><div className="skill-tags">{(job.skills||[]).slice(0,3).map(x=><i key={x}>{x}</i>)}</div><footer><span>{job.salary}</span><b>查看详情 <ArrowUpRight/></b></footer></button>)}</div>
      {!workspace&&<div className="job-list-footer"><span>已加载 <b>{remoteJobs.length}</b> / {total} 条岗位</span>{remoteJobs.length<total&&(loading?<div className="cube-loader"><div className="cube-loader__inner cube-loader__inner--color"/><div className="cube-loader__inner cube-loader__inner--glow"/></div>:<span style={{color:"#6e6a78",fontSize:11}}>继续滚动以加载更多</span>)}</div>}
    </section>
    </>:jobsTab==="discovery"?<CompetitionErrorBoundary pageName="新岗位发现" onNavigateHome={()=>{setJobsTab("jobs");sessionStorage.setItem("talentmatch-jobsTab","jobs")}}><CompetitionDiscovery/></CompetitionErrorBoundary>
    :jobsTab==="evolution"?<CompetitionErrorBoundary pageName="岗位能力演化" onNavigateHome={()=>{setJobsTab("jobs");sessionStorage.setItem("talentmatch-jobsTab","jobs")}}><CompetitionRoleEvolution/></CompetitionErrorBoundary>
    :<CompetitionErrorBoundary pageName="岗位证据审核" onNavigateHome={()=>{setJobsTab("jobs");sessionStorage.setItem("talentmatch-jobsTab","jobs")}}><CompetitionEvidence/></CompetitionErrorBoundary>}
    {selected&&<JobDialog job={selected} close={()=>setSelected(null)} onDelete={deleteLocalJob}/>} {adding&&<AddJobDialog close={()=>setAdding(false)} save={add}/>} {candidatePanel&&<CandidateDialog candidates={candidates} close={()=>setCandidatePanel(false)} onChange={load}/>} {interviewPanel&&<InterviewDialog candidates={candidates} interviews={interviews} jobs={jobs} close={()=>setInterviewPanel(false)} onChange={load}/>}</>;
}

function JobDialog({job,close,onDelete,isReadonly}:{job:JobRow;close:()=>void;onDelete?:(id:string)=>void;isReadonly?:boolean}){return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)close()}}><div className="dialog job-dialog"><div className="dialog-head"><div><span>JOB DETAIL</span><h3>{job.name}</h3></div><button onClick={close}><X/></button></div><div className="job-meta"><span><BriefcaseBusiness/>{job.company}</span><span><MapPin/>{job.city}</span><span><CalendarDays/>{job.type}</span></div><section><h4>岗位职责与说明</h4><p>{job.description}</p></section>{job.requirement&&<section><h4>任职要求</h4><p>{job.requirement}</p></section>}<section><h4>核心能力要求</h4><div className="skill-tags">{(job.skills?.length?job.skills:["沟通协作","项目经验","专业能力"]).map(x=><i key={x}>{x}</i>)}</div></section><div className="dialog-summary"><span>薪资范围<b>{job.salary||"面议"}</b></span><span>岗位更新时间<b>{job.updatedAt?timeText(new Date(job.updatedAt)):"未标注"}</b></span></div>{!isReadonly&&job.source==="HR手动创建"&&onDelete&&<button className="ghost-action" style={{color:"#ff6b6b",marginBottom:12}} onClick={()=>{if(confirm("确认删除该岗位？此操作不可恢复。"))onDelete(job.id)}}><Trash2/>删除岗位</button>}{job.sourceUrl&&<a className="job-source-link" href={job.sourceUrl} target="_blank" rel="noreferrer">查看原始招聘页面 <ArrowUpRight/></a>}{isReadonly?<p style={{fontSize:12,color:"rgba(196,199,200,.35)",textAlign:"center",marginTop:16}}>登录后可管理此岗位</p>:<button className="primary" onClick={close}>关闭详情</button>}</div></div>}
function AddJobDialog({close,save}:{close:()=>void;save:(j:JobRow)=>void}){const [form,setForm]=useState({name:"",company:"",city:"",description:"",skills:"",salary:""});const submit=()=>{if(!form.name.trim())return;save({id:`local-${Date.now()}`,name:form.name,company:form.company||"招聘团队",city:form.city||"不限",description:form.description||"暂无岗位说明",skills:form.skills.split(/[,，、]/).filter(Boolean),salary:form.salary||"面议",type:"社会招聘",score:85,updatedAt:new Date().toISOString()})};return <div className="modal-backdrop"><div className="dialog"><div className="dialog-head"><div><span>CREATE JOB</span><h3>新增招聘岗位</h3></div><button onClick={close}><X/></button></div>{[["岗位名称","name","例如：高级后端工程师"],["所属部门","company","例如：核心技术部"],["工作城市","city","例如：上海"],["薪资范围","salary","例如：30K-45K"],["核心技能","skills","使用逗号分隔"]].map(([label,key,placeholder])=><label className="field" key={key}><span>{label}</span><input value={(form as any)[key]} onChange={e=>setForm({...form,[key]:e.target.value})} placeholder={placeholder}/></label>)}<label className="field"><span>岗位说明</span><textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})} placeholder="填写岗位职责和候选人要求..."/></label><button className="primary" disabled={!form.name.trim()} onClick={submit}>发布岗位</button></div></div>}

function CandidateDialog({candidates,close,onChange}:{candidates:CandidateRow[];close:()=>void;onChange:()=>void}){const [form,setForm]=useState({name:"",email:"",phone:""});const add=async()=>{await json("/api/hr/candidates",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)});setForm({name:"",email:"",phone:""});onChange()};return <div className="modal-backdrop"><div className="dialog large-dialog"><div className="dialog-head"><div><span>CANDIDATE PIPELINE</span><h3>候选人管理</h3></div><button onClick={close}><X/></button></div><div className="inline-form"><input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="候选人姓名（可留空）"/><input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})} placeholder="手机"/><input value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="邮箱"/><button onClick={add}><Plus/>添加</button></div><div className="candidate-list">{candidates.map(c=><div key={c.id}><div className="candidate-avatar">{(c.name||"匿").slice(0,1)}</div><span><b>{c.name||"匿名候选人"}</b><small>{c.phone||"未填写手机"} · {c.email||"未填写邮箱"}</small></span><em>{c.stage}</em></div>)}</div></div></div>}
function InterviewDialog({candidates,interviews,jobs,close,onChange}:{candidates:CandidateRow[];interviews:InterviewRow[];jobs:JobRow[];close:()=>void;onChange:()=>void}){
  const [form,setForm]=useState({candidateId:candidates[0]?.id||"",jobTitle:jobs[0]?.name||"",scheduledAt:"",interviewer:"",location:"",tags:"",notes:""});
  const [focused,setFocused]=useState(()=>sessionStorage.getItem("talentmatch-focus-entity")||interviews[0]?.id||"");
  const [resumeCandidate,setResumeCandidate]=useState<CandidateRow|null>(null);
  useEffect(()=>{sessionStorage.removeItem("talentmatch-focus-entity")},[]);
  const add=async()=>{const c=candidates.find(x=>x.id===form.candidateId);await json("/api/hr/interviews",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...form,tags:form.tags.split(/[,，、]/).map(x=>x.trim()).filter(Boolean),candidateName:c?.name||"匿名候选人"})});setForm({...form,scheduledAt:"",tags:"",notes:""});await onChange()};
  const patch=async(id:string,body:Record<string,unknown>)=>{await json(`/api/hr/interviews/${id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});await onChange()};
  const toggleFavorite=async(candidateId:string)=>{const state=await json("/api/hr/state");const active=(state.favorites||[]).includes(candidateId);await json(`/api/hr/favorites/${candidateId}`,{method:active?"DELETE":"PUT"});await onChange()};
  return <div className="modal-backdrop"><div className="dialog large-dialog interview-workbench"><div className="dialog-head"><div><span>INTERVIEW WORKBENCH</span><h3>面试安排与人才跟进</h3></div><button onClick={close}><X/></button></div>
    <div className="interview-form"><label><span>候选人</span><select value={form.candidateId} onChange={e=>setForm({...form,candidateId:e.target.value})}>{candidates.map(c=><option value={c.id} key={c.id}>{c.name||"匿名候选人"}</option>)}</select></label><label><span>目标岗位</span><select value={form.jobTitle} onChange={e=>setForm({...form,jobTitle:e.target.value})}>{jobs.slice(0,30).map(j=><option value={j.name} key={j.id}>{j.name}</option>)}</select></label><label><span>面试时间</span><input type="datetime-local" value={form.scheduledAt} onChange={e=>setForm({...form,scheduledAt:e.target.value})}/></label><label><span>面试官</span><input value={form.interviewer} onChange={e=>setForm({...form,interviewer:e.target.value})} placeholder="姓名或团队"/></label><label><span>地点 / 会议链接</span><input value={form.location} onChange={e=>setForm({...form,location:e.target.value})} placeholder="会议室或在线链接"/></label><label><span>标签</span><input value={form.tags} onChange={e=>setForm({...form,tags:e.target.value})} placeholder="技术面、优先、需复核"/></label><label className="interview-notes"><span>备注</span><input value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})} placeholder="面试重点与联系记录"/></label><button className="primary" disabled={!form.candidateId||!form.scheduledAt} onClick={add}>安排面试</button></div>
    <div className="interview-list">{interviews.map(x=>{const c=candidates.find(row=>row.id===x.candidateId);const active=focused===x.id;return <div key={x.id} className={active?"focused":""} onClick={()=>setFocused(x.id)}><CalendarDays/><span><b>{x.candidateName} · {x.jobTitle}</b><small>{timeText(new Date(x.scheduledAt))} · {x.interviewer||"待分配"}{x.location?` · ${x.location}`:""}</small><span className="interview-tags">{(x.tags||[]).map(tag=><i key={tag}>{tag}</i>)}</span>{active&&<span className="interview-actions"><button onClick={e=>{e.stopPropagation();toggleFavorite(x.candidateId)}}><Star/>关注</button>{c?.phone&&<a href={`tel:${c.phone}`} onClick={e=>e.stopPropagation()}><Phone/>电话</a>}{c?.email&&<a href={`mailto:${c.email}`} onClick={e=>e.stopPropagation()}><Mail/>邮件</a>}<button onClick={e=>{e.stopPropagation();setResumeCandidate(c||null)}}><FileText/>查看简历</button><button onClick={e=>{e.stopPropagation();patch(x.id,{status:x.status==="已完成"?"待进行":"已完成"})}}><CheckCircle2/>{x.status==="已完成"?"恢复待办":"标记完成"}</button></span>}</span><em>{x.status}</em></div>})}</div>
    {resumeCandidate&&<div className="resume-preview"><div className="dialog-head"><div><span>RESUME</span><h3>{resumeCandidate.name} 的简历</h3></div><button onClick={()=>setResumeCandidate(null)}><X/></button></div><p><Mail/> {resumeCandidate.email||"未填写邮箱"}　<Phone/> {resumeCandidate.phone||"未填写电话"}</p><div className="skill-tags">{(resumeCandidate.skills||[]).map(x=><i key={x}>{x}</i>)}</div><pre>{resumeCandidate.profileText||"暂无完整简历正文，可先通过电话或邮件联系候选人补充。"}</pre></div>}
  </div></div>
}

function AssessmentPage({onOpenGraph}:{onOpenGraph?:(name:string)=>void}){
  const [items,setItems]=useState<AssessmentRow[]>([]);const [candidates,setCandidates]=useState<CandidateRow[]>([]);const [favorites,setFavorites]=useState<string[]>([]);const [loading,setLoading]=useState(false);const [updated,setUpdated]=useState(timeText());const [selected,setSelected]=useState<AssessmentRow|null>(null);const [category,setCategory]=useState<"all"|"excellent"|"review"|"average"|null>(null);
  const load=async()=>{setLoading(true);try{const [assessmentData,hrData]=await Promise.all([json("/api/assessments"),json("/api/hr/state")]);setItems(assessmentData.items||[]);setCandidates(hrData.candidates||[]);setFavorites(hrData.favorites||[])}catch{setItems([])}finally{setUpdated(timeText());setLoading(false)}};
  useEffect(()=>{load()},[]);
  const candidateFor=(item:AssessmentRow)=>candidates.find(candidate=>(candidate.name||"匿名候选人")===(item.candidateName?.trim()||"匿名候选人"));
  const toggleFavorite=async(candidate?:CandidateRow)=>{if(!candidate)return;const active=favorites.includes(candidate.id);await json(`/api/hr/favorites/${candidate.id}`,{method:active?"DELETE":"PUT"});setFavorites(rows=>active?rows.filter(id=>id!==candidate.id):[candidate.id,...rows])};
  const average=items.length?Math.round(items.reduce((sum,item)=>sum+item.score,0)/items.length):0;
  const categoryItems=category==="excellent"?items.filter(item=>item.score>=85):category==="review"?items.filter(item=>item.score<85):items;
  const titles={all:["已评估候选人","显示所有完成评估的候选人及其岗位、得分和能力信息。"],excellent:["优秀匹配","显示综合匹配度达到 85 分及以上的重点候选人。"],review:["待复核","显示仍需核实技能、项目深度或岗位适配证据的候选人。"],average:["个人匹配度明细",`当前所有候选人的平均匹配度为 ${average||"--"}%，下方按个人展示具体分数。`]} as const;
  if(category){const [title,desc]=titles[category];return <><div className="page-actions category-actions"><button className="ghost-action spring-hover" onClick={()=>setCategory(null)}><ArrowLeft/>返回评估结果</button></div><section className="category-hero"><span>{category==="average"?`${average}%`:categoryItems.length}</span><div><h3>{title}</h3><p>{desc}</p></div></section><section className="candidate-detail-grid">{categoryItems.map(item=>{const candidate=candidateFor(item);const favorite=Boolean(candidate&&favorites.includes(candidate.id));return <article key={item.id}><div className="candidate-card-head"><div className="candidate-avatar">{(item.candidateName||"匿名").slice(0,1)}</div><span><b>{item.candidateName?.trim()||"匿名候选人"}</b><small>{item.jobTitle||"未指定岗位"} · {timeText(new Date(item.createdAt))}</small></span><em>{item.score}<small>分</small></em></div><div className="candidate-info"><span>匹配结论<b>{item.matchLevel}</b></span><span>学历<b>{candidate?.education||"未填写"}</b></span><span>经验<b>{candidate?.experienceYears?`${candidate.experienceYears} 年`:"未填写"}</b></span><span>当前阶段<b>{candidate?.stage||"待复核"}</b></span></div><div className="skill-tags">{(candidate?.skills||item.highlights?.slice(0,3)||[]).map(skill=><i key={skill}>{skill}</i>)}</div><div className="candidate-card-actions"><button onClick={()=>toggleFavorite(candidate)} disabled={!candidate} className={favorite?"active":""}><Heart fill={favorite?"currentColor":"none"}/>{favorite?"已关注":"特别关注"}</button><button onClick={()=>onOpenGraph?.(item.candidateName?.trim()||"匿名候选人")}><Route/>查看人才能力图谱</button><button onClick={()=>setSelected(item)}>查看评估详情</button></div></article>})}</section>{selected&&<AssessmentDialog item={selected} close={()=>setSelected(null)}/>}</>};
  return <><div className="page-actions"><span><Clock3/>更新时间：{updated}</span><button className="ghost-action spring-hover" onClick={load}><RefreshCw className={loading?"spin":""}/>刷新记录</button></div><section className="stats-grid"><Stat label="已评估候选人" value={items.length} onClick={()=>setCategory("all")} help="查看全部候选人及信息"/><Stat label="优秀匹配" value={items.filter(x=>x.score>=85).length} tone="mint" onClick={()=>setCategory("excellent")} help="查看优秀匹配候选人"/><Stat label="待复核" value={items.filter(x=>x.score<85).length} tone="cyan" onClick={()=>setCategory("review")} help="查看需要复核的候选人"/><Stat label="平均匹配度" value={items.length?`${average}%`:"--"} onClick={()=>setCategory("average")} help="查看每个人的匹配度"/></section><section className="wide-panel"><div className="table-toolbar"><div><h3>候选人评估记录</h3><span>记录来自人岗匹配页面的真实评估结果</span></div></div>{items.length?<div className="assessment-list">{items.map(item=>{const candidate=candidateFor(item);const favorite=Boolean(candidate&&favorites.includes(candidate.id));return <div className="assessment-row" key={item.id}><button className="assessment-main spring-hover" onClick={()=>setSelected(item)}><div className="candidate-avatar">{(item.candidateName||"匿名").slice(0,1)}</div><span><b>{item.candidateName?.trim()||"匿名候选人"}</b><small>{item.jobTitle||"未指定岗位"} · {timeText(new Date(item.createdAt))}</small></span><em className={item.score>=85?"high":"normal"}>{item.score}</em><i>{item.matchLevel}</i><ArrowUpRight/></button><button className={`row-favorite ${favorite?"active":""}`} disabled={!candidate} onClick={()=>toggleFavorite(candidate)} aria-label={`特别关注 ${item.candidateName||"匿名候选人"}`}><Heart fill={favorite?"currentColor":"none"}/></button></div>})}</div>:<div className="empty-records"><UserRound/><h3>还没有候选人评估记录</h3><p>完成人岗匹配评估后，候选人姓名、目标岗位和匹配结果会显示在这里。</p></div>}</section>{selected&&<AssessmentDialog item={selected} close={()=>setSelected(null)}/>}</>
}

function AssessmentDialog({item,close}:{item:AssessmentRow;close:()=>void}){return <div className="modal-backdrop"><div className="dialog"><div className="dialog-head"><div><span>ASSESSMENT DETAIL</span><h3>{item.candidateName||"匿名候选人"}</h3></div><button onClick={close}><X/></button></div><div className="result-hero"><span>{item.score}</span><div><b>{item.matchLevel}</b><small>{item.jobTitle}</small></div></div><section><h4>技能缺口</h4><div className="skill-tags">{(item.skillGaps||[]).map(x=><i key={x}>{x}</i>)}</div></section><section><h4>匹配亮点</h4>{(item.highlights||[]).map(x=><p className="highlight-line" key={x}><CheckCircle2/>{x}</p>)}</section></div></div>}

function FavoritesPage({onOpenGraph}:{onOpenGraph?:(name:string)=>void}){
  const [items,setItems]=useState<Array<CandidateRow&{latestAssessment?:AssessmentRow|null}>>([]);const [loading,setLoading]=useState(true);
  const load=()=>{setLoading(true);json("/api/hr/favorites").then(data=>setItems(data.items||[])).finally(()=>setLoading(false))};useEffect(load,[]);
  const remove=async(id:string)=>{await json(`/api/hr/favorites/${id}`,{method:"DELETE"});setItems(rows=>rows.filter(item=>item.id!==id))};
  return <>{loading?<section className="wide-panel">正在读取特别关注人才...</section>:items.length?<section className="favorite-grid">{items.map(candidate=><article key={candidate.id}><div className="favorite-head"><div className="candidate-avatar">{(candidate.name||"匿").slice(0,1)}</div><span><b>{candidate.name||"匿名候选人"}</b><small>{candidate.stage} · {candidate.education||"学历未填写"} · {candidate.experienceYears||0} 年经验</small></span><Heart fill="currentColor"/></div><div className="favorite-score"><span>最近匹配度<b>{candidate.latestAssessment?.score??"--"}{candidate.latestAssessment&&<small>分</small>}</b></span><span>目标岗位<b>{candidate.latestAssessment?.jobTitle||"尚未评估"}</b></span></div><div className="skill-tags">{(candidate.skills||[]).map(skill=><i key={skill}>{skill}</i>)}</div><div className="favorite-contact"><span><Mail/>{candidate.email||"未填写邮箱"}</span><span>{candidate.phone||"未填写手机"}</span></div><div className="candidate-card-actions"><button onClick={()=>onOpenGraph?.(candidate.name||"匿名候选人")}><Route/>进入人才能力图谱</button><button onClick={()=>remove(candidate.id)}><X/>取消关注</button></div></article>)}</section>:<section className="empty-records wide-panel"><Heart/><h3>还没有特别关注的人才</h3><p>可在人才能力图谱或评估结果中点击”特别关注”，重点候选人会集中显示在这里。</p></section>}</>
}

function GraphPage(){const [candidates,setCandidates]=useState<CandidateRow[]>([]);const [aId,setAId]=useState("");const [bId,setBId]=useState("");const [loading,setLoading]=useState(true);useEffect(()=>{json("/api/hr/state").then(data=>{const rows=data.candidates||[];setCandidates(rows);setAId(rows[0]?.id||"");setBId(rows[1]?.id||rows[0]?.id||"")}).finally(()=>setLoading(false))},[]);const a=candidates.find(x=>x.id===aId);const b=candidates.find(x=>x.id===bId);const edu=(x?:string)=>({"高中及以下":30,"专科":50,"本科":70,"硕士":88,"博士":100}[x||""]||0);const metrics=(c?:CandidateRow)=>[{label:"技能覆盖",value:c?.skills?.length?Math.min(100,35+c.skills.length*12):0,detail:c?.skills?.join("、")||"数据不足"},{label:"相关经验",value:c?.experienceYears?Math.min(100,Math.round(c.experienceYears/8*100)):0,detail:c?.experienceYears?`${c.experienceYears} 年经验`:"数据不足"},{label:"学历背景",value:edu(c?.education),detail:c?.education||"数据不足"},{label:"项目经历",value:c?.projectScore||0,detail:c?.projectScore?"依据项目证据完整度":"数据不足"},{label:"协作能力",value:c?.collaborationScore||0,detail:c?.collaborationScore?"依据团队与协作证据":"数据不足"}];const am=metrics(a),bm=metrics(b);const total=(m:ReturnType<typeof metrics>)=>Math.round(m.reduce((s,x)=>s+x.value,0)/m.length);if(loading)return <div className="wide-panel">正在加载候选人画像...</div>;return <section className="compare-panel"><div className="compare-selectors"><label><span>候选人 A</span><select value={aId} onChange={e=>setAId(e.target.value)}>{candidates.map(c=><option value={c.id} key={c.id}>{c.name||"匿名候选人"}</option>)}</select></label><div>VS</div><label><span>候选人 B</span><select value={bId} onChange={e=>setBId(e.target.value)}>{candidates.map(c=><option value={c.id} key={c.id}>{c.name||"匿名候选人"}</option>)}</select></label></div><div className="compare-summary"><div><span>{a?.name||"候选人 A"}</span><b>{total(am)}<i>分</i></b><small>综合能力指数（0–100）</small></div><p>这是归一化比较指数，不是录用概率。它由技能、经验、学历、项目和协作五个维度等权计算；资料缺失的维度计为 0，并标记“数据不足”。</p><div><span>{b?.name||"候选人 B"}</span><b>{total(bm)}<i>分</i></b><small>综合能力指数（0–100）</small></div></div><div className="bar-compare"><div className="bar-head"><span>{a?.name}</span><span>能力维度（0–100 分）</span><span>{b?.name}</span></div>{am.map((x,i)=><div className="compare-row" key={x.label}><div className="left-bar"><em>{x.value?`${x.value}分`:"--"}</em><i style={{width:`${x.value}%`}}/></div><span><b>{x.label}</b><small>{x.detail}<br/>{bm[i].detail}</small></span><div className="right-bar"><i style={{width:`${bm[i].value}%`}}/><em>{bm[i].value?`${bm[i].value}分`:"--"}</em></div></div>)}</div><div className="advantage-grid"><div><h3>{a?.name} 的对比结论</h3><h4>相对优势</h4>{am.filter((x,i)=>x.value>bm[i].value).map(x=><p key={`a-up-${x.label}`}><CheckCircle2/>{x.label}：{x.detail}</p>)}<h4 className="weak-title">相对短板</h4>{am.filter((x,i)=>x.value<bm[i].value).map(x=><p className="weak-line" key={`a-down-${x.label}`}><AlertTriangle/>{x.label}：低于 {b?.name}</p>)}</div><div><h3>{b?.name} 的对比结论</h3><h4>相对优势</h4>{bm.filter((x,i)=>x.value>am[i].value).map(x=><p key={`b-up-${x.label}`}><CheckCircle2/>{x.label}：{x.detail}</p>)}<h4 className="weak-title">相对短板</h4>{bm.filter((x,i)=>x.value<am[i].value).map(x=><p className="weak-line" key={`b-down-${x.label}`}><AlertTriangle/>{x.label}：低于 {a?.name}</p>)}</div></div></section>}

function EvolutionPage(){const [role,setRole]=useState("java-backend-engineer");const [skill,setSkill]=useState("Java");const [months,setMonths]=useState(12);const [data,setData]=useState<any>(null);const [loading,setLoading]=useState(false);const [updated,setUpdated]=useState(timeText());const load=async()=>{setLoading(true);try{const evolution=await json(`/api/platform/java/api/evolution?jobId=${encodeURIComponent(role)}`);setData(evolution);const skills=Array.from(new Set((evolution.series||[]).map((x:any)=>x.skill))) as string[];if(!skills.includes(skill))setSkill(skills[0]||"");setUpdated(timeText())}finally{setLoading(false)}};useEffect(()=>{load()},[role]);const skills=Array.from(new Set((data?.series||[]).map((x:any)=>x.skill))) as string[];const all=(data?.series||[]).filter((x:any)=>x.skill===skill).sort((a:any,b:any)=>a.period.localeCompare(b.period));const rows=all.slice(-months);const max=Math.max(1,...rows.map((x:any)=>x.demand));const points=rows.map((x:any,i:number)=>`${20+i*(960/Math.max(1,rows.length-1))},${315-x.demand/max*280}`).join(" ");return <><div className="page-actions"><span><Clock3/>更新时间：{updated}</span><button className="ghost-action spring-hover" onClick={load} disabled={loading}><RefreshCw className={loading?"spin":""}/>{loading?"刷新中":"刷新数据"}</button></div><section className="evolution-panel market-chart"><div className="trend-filter"><label><span>特定岗位</span><select value={role} onChange={e=>setRole(e.target.value)}>{(data?.roleOptions||[]).map((x:any)=><option key={x.roleId} value={x.roleId}>{x.role}（{x.recordCount}）</option>)}</select></label><label><span>技能趋势</span><select value={skill} onChange={e=>setSkill(e.target.value)}>{skills.map(x=><option key={x}>{x}</option>)}</select></label><div><span>时间范围</span>{[[6,"6个月"],[12,"12个月"],[24,"24个月"]].map(([n,l])=><button className={months===n?"active":""} onClick={()=>setMonths(n as number)} key={n}>{l}</button>)}</div></div><div className="chart-title"><div><h3>{skill||"技能"} · {data?.title||"岗位需求趋势"}</h3><span>当前需求量 <b>{rows.at(-1)?.demand||0}</b> · 数据点 {rows.length} 个 · 来源证据 {rows.at(-1)?.sourceCount||0}</span></div></div><div className="market-canvas"><div className="axis-labels"><span>{max}</span><span>{Math.round(max*.66)}</span><span>{Math.round(max*.33)}</span><span>0</span></div><svg viewBox="0 0 1000 340" preserveAspectRatio="none"><defs><linearGradient id="marketArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#9bf2e9" stopOpacity=".35"/><stop offset="1" stopColor="#7c5cff" stopOpacity="0"/></linearGradient></defs><polygon points={`${points} 980,330 20,330`} fill="url(#marketArea)"/><polyline points={points} fill="none" stroke="#9bf2e9" strokeWidth="4"/>{rows.map((x:any,i:number)=><circle key={x.period} cx={20+i*(960/Math.max(1,rows.length-1))} cy={315-x.demand/max*280} r="5" fill="#131318" stroke="#cabeff" strokeWidth="3"/>)}</svg></div><div className="time-axis">{rows.map((x:any)=><span key={x.period}>{x.period}</span>)}</div></section></>}
