import { Fragment, useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { useHomeHeroMotion } from "./hooks/useHomeHeroMotion";
import type { PointerEvent as ReactPointerEvent } from "react";
import { Activity, AlertTriangle, ArrowLeft, ArrowUpRight, BriefcaseBusiness, CalendarDays, CheckCircle2, CircleDot, Clock3, FileText, GitCompareArrows, Heart, Info, Lock, Mail, MapPin, Phone, Plus, RefreshCw, Route, Search, ShieldAlert, Sparkles, Star, Trash2, TrendingUp, UserRound, X } from "lucide-react";
import SplitText from "./components/SplitText";
import CompetitionDiscovery from "./components/CompetitionDiscovery";
import CompetitionRoleEvolution from "./components/CompetitionRoleEvolution";
import RoleCapabilityGraph from "./components/RoleCapabilityGraph";
import CompetitionRoleWorkspace from "./components/CompetitionRoleWorkspace";
import JobSectionHeader from "./components/JobSectionHeader";
import CompetitionErrorBoundary from "./components/CompetitionErrorBoundary";
import AddJobButton from "./components/AddJobButton";

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
  /* ── Motion & loading state ── */
  const heroRef = useRef<HTMLDivElement>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [showSkeleton, setShowSkeleton] = useState(false);
  const skeletonTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const finishTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dataLoadedRef = useRef(false);
  useHomeHeroMotion(heroRef, isLoggedIn);
  /* ── Demo state (unauthenticated) ── */
  const [demoJobs,setDemoJobs]=useState<JobRow[]>([]);const [demoLoaded,setDemoLoaded]=useState(false);
  const load=async()=>{try{const [jobResult,hrResult,assessResult]=await Promise.allSettled([json("/api/platform/storage/api/search/jobs?page=1&page_size=6"),json("/api/hr/state"),json("/api/assessments")]);const hr=hrResult.status==="fulfilled"?hrResult.value:{candidates:[],interviews:[],jobs:[]};if(jobResult.status==="fulfilled"){setRemoteJobs(normalizeJobs(jobResult.value));setTotal(Number(jobResult.value.total||0))}setLocalJobs((hr.jobs||[]).map((x:any)=>({...x,name:x.name||x.title})));setCandidates(hr.candidates||[]);setInterviews(hr.interviews||[]);if(assessResult.status==="fulfilled")setAssessments(assessResult.value.items||[]);setUpdated(timeText())}catch{}finally{finishLoading()}};
  /* ── Demo data loader — public, no auth ── */
  const loadDemo=async()=>{try{const res=await fetch("/api/platform/storage",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:"/api/home/demo-jobs",method:"GET"})});const data=await res.json();setDemoJobs(normalizeJobs(data));setDemoLoaded(true)}catch{setDemoLoaded(true)}finally{finishLoading()}};
  const finishLoading = () => {
    if (skeletonTimerRef.current) { clearTimeout(skeletonTimerRef.current); skeletonTimerRef.current = null; }
    if (!dataLoadedRef.current) {
      // Clear any pending finish timer before setting a new one
      if (finishTimerRef.current) { clearTimeout(finishTimerRef.current); }
      finishTimerRef.current = setTimeout(() => { setDataLoading(false); dataLoadedRef.current = true; finishTimerRef.current = null; }, 200);
    }
    setShowSkeleton(false);
  };
  useEffect(()=>{
    dataLoadedRef.current = false;
    setDataLoading(true);
    // Show skeleton only if loading takes >180ms
    skeletonTimerRef.current = setTimeout(() => { setShowSkeleton(true); }, 180);
    if(isLoggedIn){load()}else{loadDemo()}
    return () => { if (skeletonTimerRef.current) { clearTimeout(skeletonTimerRef.current); skeletonTimerRef.current = null; } if (finishTimerRef.current) { clearTimeout(finishTimerRef.current); finishTimerRef.current = null; } };
  },[isLoggedIn]);
  const add=async(job:JobRow)=>{const saved=await json("/api/hr/jobs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(job)});setLocalJobs(x=>[{...saved,name:saved.name||saved.title},...x]);setAdding(false);setUpdated(timeText());setSelected({...saved,name:saved.name||saved.title})};
  const deleteLocalJob=async(jobId:string)=>{await json("/api/hr/jobs/"+jobId,{method:"DELETE"});setLocalJobs(x=>x.filter(j=>j.id!==jobId));setSelected(null);setUpdated(timeText())};
  const jobs=[...localJobs,...remoteJobs];const topJobs=isLoggedIn?jobs.slice(0,3):demoJobs.slice(0,6);
  const pendingInterviews=interviews.filter(x=>x.status==="待进行").length;
  const average=assessments.length?Math.round(assessments.reduce((sum,x)=>sum+x.score,0)/assessments.length):null;
  const totalJobs=total+localJobs.length;
  /* ── UNAUTHENTICATED: Demo homepage ── */
  if(!isLoggedIn){
    return <div className="platform-main" style={{padding:0,margin:0,maxWidth:"100%"}}>
      {/* Hero — shares the authenticated visual language while keeping guest actions */}
      <section className="home-hero home-hero--showcase" ref={heroRef}>
        <div className="hero-showcase__particles" aria-hidden="true">
          {[
            {x:10,y:25,s:3,d:.3},{x:16,y:48,s:2,d:.8},{x:8,y:62,s:3,d:1.4},{x:14,y:78,s:2,d:.6},{x:86,y:22,s:3,d:.4},{x:92,y:46,s:2,d:.9},
            {x:88,y:68,s:3,d:1.5},{x:84,y:80,s:2,d:.7},{x:48,y:92,s:3,d:2.0},{x:52,y:88,s:2,d:2.3},
          ].map((p,i)=><div key={i} className="hero-particle" style={{"--px":p.x+"%","--py":p.y+"%","--ps":p.s+"px","--pd":p.d+"s"} as CSSProperties}/>)}
        </div>

        <div className="hero-side-scene hero-side-scene--left" aria-hidden="true">
          <svg className="hero-effect-frame hero-effect-frame--left" viewBox="0 0 540 400" preserveAspectRatio="none">
            <defs>
              <linearGradient id="guestLeftTrackGrad" x1="0" y1="1" x2="1" y2="0">
                <stop offset="0%" stopColor="#8CBCE8" stopOpacity="0.18"/>
                <stop offset="45%" stopColor="#2478C8" stopOpacity="0.70"/>
                <stop offset="100%" stopColor="#7ED9E8" stopOpacity="0.32"/>
              </linearGradient>
            </defs>
            <path d="M510 45 C260 12 54 72 46 210 C40 310 130 370 310 385" fill="none" stroke="url(#guestLeftTrackGrad)" strokeWidth="2.5" strokeLinecap="round"/>
            <path d="M478 60 C255 32 72 84 65 210 C58 298 140 350 292 362" fill="none" stroke="#7EAEDB" strokeOpacity="0.35" strokeWidth="1.2" strokeDasharray="8 10" strokeLinecap="round"/>
            <path d="M458 72 C248 50 86 96 80 210 C74 286 148 334 278 344" fill="none" stroke="#93C5FD" strokeOpacity="0.22" strokeWidth="0.8" strokeDasharray="3 14" strokeLinecap="round"/>
          </svg>
          <figure className="hero-showcase__visual hero-showcase__visual--left">
            <img src="/hero/job-management.png" alt="" draggable="false" />
          </figure>
          <div className="hero-side-particles hero-side-particles--left">
            {[
              {x:6,y:18,s:4,d:.2},{x:10,y:44,s:3,d:.9},{x:4,y:68,s:4,d:1.6},{x:14,y:32,s:3,d:.5},{x:8,y:82,s:4,d:2.1},{x:18,y:56,s:3,d:1.2},
              {x:22,y:40,s:4,d:.8},{x:16,y:74,s:3,d:1.8},
            ].map((p,i)=><div key={i} className="hero-side-particle" style={{"--spx":p.x+"%","--spy":p.y+"%","--sps":p.s+"px","--spd":p.d+"s"} as CSSProperties}/>)}
          </div>
        </div>

        <div className="hero-showcase__center">
          <p className="home-hero__eyebrow">
            <span aria-hidden="true" />
            TALENTMATCH PREVIEW
            <span aria-hidden="true" />
          </p>
          <h1 className="home-hero__title">
            <SplitText text="人岗匹配" tag="span" className="home-hero__title-part" splitType="chars" delay={48} duration={0.85} ease="power3.out" from={{opacity:0,y:36,scale:.93}} to={{opacity:1,y:0,scale:1}} />
            <SplitText text="智能" tag="em" className="home-hero__title-part home-hero__title-accent" splitType="chars" delay={48} duration={0.85} ease="power3.out" from={{opacity:0,y:36,scale:.93}} to={{opacity:1,y:0,scale:1}} initialDelay={100} />
            <SplitText text="评估系统" tag="span" className="home-hero__title-part" splitType="chars" delay={48} duration={0.85} ease="power3.out" from={{opacity:0,y:36,scale:.93}} to={{opacity:1,y:0,scale:1}} initialDelay={200} />
          </h1>
          <p className="home-hero__desc" role="text">
            <SplitText text="登录后可查看完整岗位数据、启动人才评估、使用知识图谱与招聘趋势等全部功能。" className="home-hero__desc-line" tag="span" splitType="chars" delay={22} duration={0.75} ease="power3.out" from={{opacity:0,y:16,scale:.96}} to={{opacity:1,y:0,scale:1}} />
            <SplitText text="当前开放 10 条精选 Demo 岗位，登录即可解锁完整招聘工作台。" className="home-hero__desc-line" tag="span" splitType="chars" delay={22} duration={0.75} ease="power3.out" from={{opacity:0,y:16,scale:.96}} to={{opacity:1,y:0,scale:1}} initialDelay={120} />
          </p>
          <div className="home-hero__actions">
            <button className="home-hero__primary" onClick={()=>window.dispatchEvent(new CustomEvent("auth:open-login"))}><Lock/>登录查看全部数据</button>
            <button className="home-hero__secondary" onClick={()=>document.getElementById("demo-jobs")?.scrollIntoView({behavior:"smooth",block:"start"})}><BriefcaseBusiness/>浏览 Demo 岗位</button>
          </div>
        </div>

        <div className="hero-side-scene hero-side-scene--right" aria-hidden="true">
          <svg className="hero-effect-frame hero-effect-frame--right" viewBox="0 0 540 400" preserveAspectRatio="none">
            <defs>
              <linearGradient id="guestRightMeteorGrad" x1="1" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#5B6EE1" stopOpacity="0.20"/>
                <stop offset="38%" stopColor="#337FD1" stopOpacity="0.75"/>
                <stop offset="78%" stopColor="#75D4E5" stopOpacity="0.34"/>
                <stop offset="100%" stopColor="#75D4E5" stopOpacity="0"/>
              </linearGradient>
            </defs>
            <path d="M86 36 C310 20 494 78 496 214 C497 310 420 368 268 388" fill="none" stroke="url(#guestRightMeteorGrad)" strokeWidth="2.5" strokeLinecap="round"/>
            <path d="M118 54 C320 40 476 94 478 214 C480 292 410 344 290 366" fill="none" stroke="#786FE8" strokeOpacity="0.28" strokeWidth="1.4" strokeDasharray="3 10" strokeLinecap="round"/>
            <path d="M142 68 C330 56 462 106 463 214 C464 278 400 326 304 350" fill="none" stroke="#93C5FD" strokeOpacity="0.20" strokeWidth="0.8" strokeDasharray="2 16" strokeLinecap="round"/>
            <circle cx="86" cy="36" r="4.5" fill="#337FD1" opacity="0.65" className="hero-meteor-head"/>
            <circle cx="86" cy="36" r="9" fill="#337FD1" opacity="0.12"/>
          </svg>
          <figure className="hero-showcase__visual hero-showcase__visual--right">
            <img src="/hero/recruitment-insights.png" alt="" draggable="false" />
          </figure>
          <div className="hero-side-particles hero-side-particles--right">
            {[
              {x:90,y:14,s:4,d:.3},{x:86,y:34,s:3,d:.9},{x:82,y:56,s:4,d:1.5},{x:88,y:28,s:3,d:.6},{x:84,y:72,s:4,d:2.0},{x:92,y:42,s:3,d:1.1},
              {x:80,y:50,s:3,d:1.3},{x:78,y:68,s:4,d:1.8},
            ].map((p,i)=><div key={i} className="hero-side-particle" style={{"--spx":p.x+"%","--spy":p.y+"%","--sps":p.s+"px","--spd":p.d+"s"} as CSSProperties}/>)}
          </div>
        </div>
      </section>
      <div style={{maxWidth:1280,margin:"0 auto",padding:"0 32px 32px"}}>
        {/* Stats — demo */}
        {showSkeleton && dataLoading ? (
        <div className="home-stats home-loading-skeleton" aria-hidden="true">
          {[1,2,3,4].map(i => (
            <div key={i} className="home-skeleton__stat-card">
              <div className="home-skeleton__shimmer home-skeleton__stat-label" />
              <div className="home-skeleton__shimmer home-skeleton__stat-value" />
              <div className="home-skeleton__shimmer home-skeleton__stat-bar" />
            </div>
          ))}
        </div>
        ) : (
        <div className="home-stats">
          <div className="home-stat"><p className="home-stat__label">{'Demo 岗位'} <BriefcaseBusiness/></p><h3 className="home-stat__value">{demoJobs.length}</h3><p className="home-stat__sub">{'MySQL 演示数据'}</p></div>
          <div className="home-stat"><p className="home-stat__label">{'覆盖城市'} <MapPin/></p><h3 className="home-stat__value mint">{new Set(demoJobs.map(j=>j.city)).size}</h3><p className="home-stat__sub">{'北京·上海·深圳·杭州·广州'}</p></div>
          <div className="home-stat"><p className="home-stat__label">{'技能标签'} <Sparkles/></p><h3 className="home-stat__value">{new Set(demoJobs.flatMap(j=>j.skills||[])).size}+</h3><p className="home-stat__sub">{'Java·Go·Python·React·K8s…'}</p></div>
          <div className="home-stat"><p className="home-stat__label">{'登录解锁'} <Lock/></p><h3 className="home-stat__value mint">100%</h3><p className="home-stat__sub">{'全部功能开放使用'}</p></div>
        </div>
        )}
        {/* Demo job cards — all 10 in two rows */}
        <section className="home-section" id="demo-jobs">
          <div className="home-section__head">
            <div><p className="home-section__head-label">Demo Preview</p><h2 className="home-section__head-title">{'精选 Demo 岗位（10 条）'}</h2></div>
            <span style={{fontSize:12,color:"var(--ent-text-muted)"}}>{'数据来源: MySQL demo_homepage_jobs'}</span>
          </div>
          <div className="home-insights guest-demo-capability-preview" style={{margin:"0 0 32px"}}>
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
                <li className="home-insight-card__item"><div className="home-insight-card__dot"/><div className="home-insight-card__item-content"><h4>{'人才能力图谱'}</h4><p>{'可视化候选人的能力、缺口与岗位适配关系。'}</p></div></li>
                <li className="home-insight-card__item"><div className="home-insight-card__dot"/><div className="home-insight-card__item-content"><h4>{'招聘趋势'}</h4><p>{'按时间查看岗位热度及关键技能的演变。'}</p></div></li>
              </ul>
            </div>
          </div>
          <div className="priority-job-grid" style={{gridTemplateColumns:"repeat(auto-fill, minmax(340px, 1fr))"}}>
            {demoLoaded&&demoJobs.length===0?<div className="priority-job-card" style={{gridColumn:"1/-1",padding:60,textAlign:"center",cursor:"default"}}><p style={{color:"var(--ent-text-muted)"}}>{'Demo 数据加载失败，请确认后端服务已启动'}</p></div>:
            demoJobs.map((job,i)=>{
              return <button key={job.id} className="priority-job-card" onClick={()=>setSelected(job)} style={{cursor:"default"}}>
                <span className="priority-job-card__watermark" aria-hidden="true">{String(i+1).padStart(2,"0")}</span>
                <div className="priority-job-card__top">
                  <span className="priority-job-card__location"><MapPin size={12}/>{job.city||'不限'}</span>
                  <span className="priority-job-card__score">{job.score||85}分</span>
                </div>
                <div className="priority-job-card__content">
                  <h3 className="priority-job-card__name">{job.name}</h3>
                  <p className="priority-job-card__desc">{job.description||job.summary}</p>
                </div>
                <div className="priority-job-card__bottom">
                  <span className="priority-job-card__company">{job.company||'招聘团队'}</span>
                  <span className="priority-job-card__detail">查看详情 <ArrowUpRight size={12}/></span>
                </div>
              </button>;
            })}
          </div>
        </section>
      </div>
      {selected&&<JobDialog job={selected} close={()=>setSelected(null)} isReadonly/>}
    </div>;
  }

  /* ── AUTHENTICATED: Full dashboard ── */
  return <div className="platform-main" style={{padding:0,margin:0,maxWidth:"100%"}}>
    {/* ── AUTHENTICATED Hero Showcase ── */}
    <section className="home-hero home-hero--showcase" ref={heroRef}>
      {/* Light ambient particles */}
      <div className="hero-showcase__particles" aria-hidden="true">
        {[
          {x:10,y:25,s:3,d:.3},{x:16,y:48,s:2,d:.8},{x:8,y:62,s:3,d:1.4},{x:14,y:78,s:2,d:.6},{x:86,y:22,s:3,d:.4},{x:92,y:46,s:2,d:.9},
          {x:88,y:68,s:3,d:1.5},{x:84,y:80,s:2,d:.7},{x:48,y:92,s:3,d:2.0},{x:52,y:88,s:2,d:2.3},
        ].map((p,i)=><div key={i} className="hero-particle" style={{"--px":p.x+"%","--py":p.y+"%","--ps":p.s+"px","--pd":p.d+"s"} as CSSProperties}/>)}
      </div>

      {/* ── Left scene: racetrack semi-surround frame + screenshot ── */}
      <div className="hero-side-scene hero-side-scene--left" aria-hidden="true">
        <svg className="hero-effect-frame hero-effect-frame--left" viewBox="0 0 540 400" preserveAspectRatio="none">
          <defs>
            <linearGradient id="leftTrackGrad" x1="0" y1="1" x2="1" y2="0">
              <stop offset="0%" stopColor="#8CBCE8" stopOpacity="0.18"/>
              <stop offset="45%" stopColor="#2478C8" stopOpacity="0.70"/>
              <stop offset="100%" stopColor="#7ED9E8" stopOpacity="0.32"/>
            </linearGradient>
          </defs>
          <path d="M510 45 C260 12 54 72 46 210 C40 310 130 370 310 385" fill="none" stroke="url(#leftTrackGrad)" strokeWidth="2.5" strokeLinecap="round"/>
          <path d="M478 60 C255 32 72 84 65 210 C58 298 140 350 292 362" fill="none" stroke="#7EAEDB" strokeOpacity="0.35" strokeWidth="1.2" strokeDasharray="8 10" strokeLinecap="round"/>
          <path d="M458 72 C248 50 86 96 80 210 C74 286 148 334 278 344" fill="none" stroke="#93C5FD" strokeOpacity="0.22" strokeWidth="0.8" strokeDasharray="3 14" strokeLinecap="round"/>
        </svg>
        <figure className="hero-showcase__visual hero-showcase__visual--left">
          <img src="/hero/job-management.png" alt="" draggable="false" />
        </figure>
        <div className="hero-side-particles hero-side-particles--left">
          {[
            {x:6,y:18,s:4,d:.2},{x:10,y:44,s:3,d:.9},{x:4,y:68,s:4,d:1.6},{x:14,y:32,s:3,d:.5},{x:8,y:82,s:4,d:2.1},{x:18,y:56,s:3,d:1.2},
            {x:22,y:40,s:4,d:.8},{x:16,y:74,s:3,d:1.8},
          ].map((p,i)=><div key={i} className="hero-side-particle" style={{"--spx":p.x+"%","--spy":p.y+"%","--sps":p.s+"px","--spd":p.d+"s"} as CSSProperties}/>)}
        </div>
      </div>

      {/* Center content */}
      <div className="hero-showcase__center">
        <p className="home-hero__eyebrow">
          <span aria-hidden="true" />
          EXECUTIVE DASHBOARD
          <span aria-hidden="true" />
        </p>
        <h1 className="home-hero__title">
          <SplitText text="人岗匹配" tag="span" className="home-hero__title-part" splitType="chars" delay={48} duration={0.85} ease="power3.out" from={{opacity:0,y:36,scale:.93}} to={{opacity:1,y:0,scale:1}} />
          <SplitText text="智能" tag="em" className="home-hero__title-part home-hero__title-accent" splitType="chars" delay={48} duration={0.85} ease="power3.out" from={{opacity:0,y:36,scale:.93}} to={{opacity:1,y:0,scale:1}} initialDelay={100} />
          <SplitText text="评估系统" tag="span" className="home-hero__title-part" splitType="chars" delay={48} duration={0.85} ease="power3.out" from={{opacity:0,y:36,scale:.93}} to={{opacity:1,y:0,scale:1}} initialDelay={200} />
        </h1>
        <p className="home-hero__desc" role="text">
          <SplitText text="精准管理组织人力资本，实时监控招聘流程与精英候选人匹配评分。" className="home-hero__desc-line" tag="span" splitType="chars" delay={22} duration={0.75} ease="power3.out" from={{opacity:0,y:16,scale:.96}} to={{opacity:1,y:0,scale:1}} />
          <SplitText text="集中查看在招岗位、候选人评估与近期招聘进展，驱动数据化招聘决策。" className="home-hero__desc-line" tag="span" splitType="chars" delay={22} duration={0.75} ease="power3.out" from={{opacity:0,y:16,scale:.96}} to={{opacity:1,y:0,scale:1}} initialDelay={120} />
        </p>
        <div className="home-hero__actions">
          <AddJobButton size="large" onClick={()=>setAdding(true)} />
          <button className="home-hero__secondary" onClick={()=>onNavigate?.("evolution")}><TrendingUp/>查看招聘趋势</button>
        </div>
      </div>

      {/* ── Right scene: meteor-trail semi-surround frame + screenshot ── */}
      <div className="hero-side-scene hero-side-scene--right" aria-hidden="true">
        <svg className="hero-effect-frame hero-effect-frame--right" viewBox="0 0 540 400" preserveAspectRatio="none">
          <defs>
            <linearGradient id="rightMeteorGrad" x1="1" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5B6EE1" stopOpacity="0.20"/>
              <stop offset="38%" stopColor="#337FD1" stopOpacity="0.75"/>
              <stop offset="78%" stopColor="#75D4E5" stopOpacity="0.34"/>
              <stop offset="100%" stopColor="#75D4E5" stopOpacity="0"/>
            </linearGradient>
          </defs>
          <path d="M86 36 C310 20 494 78 496 214 C497 310 420 368 268 388" fill="none" stroke="url(#rightMeteorGrad)" strokeWidth="2.5" strokeLinecap="round"/>
          <path d="M118 54 C320 40 476 94 478 214 C480 292 410 344 290 366" fill="none" stroke="#786FE8" strokeOpacity="0.28" strokeWidth="1.4" strokeDasharray="3 10" strokeLinecap="round"/>
          <path d="M142 68 C330 56 462 106 463 214 C464 278 400 326 304 350" fill="none" stroke="#93C5FD" strokeOpacity="0.20" strokeWidth="0.8" strokeDasharray="2 16" strokeLinecap="round"/>
          <circle cx="86" cy="36" r="4.5" fill="#337FD1" opacity="0.65" className="hero-meteor-head"/>
          <circle cx="86" cy="36" r="9" fill="#337FD1" opacity="0.12"/>
        </svg>
        <figure className="hero-showcase__visual hero-showcase__visual--right">
          <img src="/hero/recruitment-insights.png" alt="" draggable="false" />
        </figure>
        <div className="hero-side-particles hero-side-particles--right">
          {[
            {x:90,y:14,s:4,d:.3},{x:86,y:34,s:3,d:.9},{x:82,y:56,s:4,d:1.5},{x:88,y:28,s:3,d:.6},{x:84,y:72,s:4,d:2.0},{x:92,y:42,s:3,d:1.1},
            {x:80,y:50,s:3,d:1.3},{x:78,y:68,s:4,d:1.8},
          ].map((p,i)=><div key={i} className="hero-side-particle" style={{"--spx":p.x+"%","--spy":p.y+"%","--sps":p.s+"px","--spd":p.d+"s"} as CSSProperties}/>)}
        </div>
      </div>
    </section>
    <div style={{maxWidth:1280,margin:"0 auto",padding:"0 32px 32px"}}>
      {/* Stats Grid */}
      {showSkeleton && dataLoading ? (
        <div className="home-stats home-loading-skeleton" aria-hidden="true">
          {[1,2,3,4].map(i => (
            <div key={i} className="home-skeleton__stat-card">
              <div className="home-skeleton__shimmer home-skeleton__stat-label" />
              <div className="home-skeleton__shimmer home-skeleton__stat-value" />
              <div className="home-skeleton__shimmer home-skeleton__stat-bar" />
            </div>
          ))}
        </div>
      ) : (
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
      )}
      {/* Intelligent Insight + Editorial Quote Grid */}
      <section className="home-section home-editorial-section" style={{marginBottom:36}}>
        <div className="home-editorial-grid">
          {/* ── Left: Intelligent Insight Card ── */}
          <div className="insight-card">
            <div className="insight-card__header">
              <div className="insight-card__title-group">
                <span className="insight-card__category">INTELLIGENT INSIGHT</span>
                <h2 className="insight-card__title">智能洞察</h2>
              </div>
              <div className="insight-card__icon-wrap" aria-hidden="true">
                <div className="insight-card__icon-base" />
                <TrendingUp className="insight-card__icon-giant" size={110} strokeWidth={2.5} />
              </div>
            </div>
            <div className="insight-card__body">
              <div className="insight-card__hero-stat">
                <span className="insight-card__stat-number">{totalJobs.toLocaleString()}</span>
                <span className="insight-card__stat-label">当前系统在招岗位，覆盖多个行业与城市。</span>
              </div>
              <div className="insight-card__section-title">人才评估</div>
              <div className="insight-card__details">
                <div className="insight-card__detail">
                  <div className="insight-card__detail-heading">
                    <strong>人才评估质量</strong>
                    <span className="insight-card__detail-badge insight-card__detail-badge--blue">QUALITY</span>
                  </div>
                  <p>已完成 <b>{assessments.length}</b> 次智能评估，平均匹配度为 <b>{average!==null?average+"%" : "--"}</b>。</p>
                </div>
                <div className="insight-card__detail">
                  <div className="insight-card__detail-heading">
                    <strong>招聘趋势洞察</strong>
                    <span className="insight-card__detail-badge">TRENDS</span>
                  </div>
                  <p>按时间区间查看岗位热度及关键技能的演变，辅助招聘规划。</p>
                </div>
              </div>
            </div>
            <button className="insight-card__action" onClick={()=>onNavigate?.("evolution")}>
              <span>探索更多洞察</span>
              <TrendingUp size={16} />
            </button>
          </div>

          {/* ── Right: Magazine Editorial Quote ── */}
          <div className="editorial-quote" role="blockquote">
            <span className="editorial-quote__mark editorial-quote__mark--open" aria-hidden="true">&#x201C;</span>
            <div className="editorial-quote__content">
              <p className="editorial-quote__text">
                <span className="editorial-quote__line">优秀的招聘者</span>
                <span className="editorial-quote__line">不仅仅是填补岗位空缺；</span>
              </p>
              <p className="editorial-quote__text editorial-quote__text--indent">
                <span className="editorial-quote__line">他们在构建组织</span>
                <span className="editorial-quote__line">的未来蓝图。</span>
              </p>
            </div>
            <span className="editorial-quote__mark editorial-quote__mark--close" aria-hidden="true">&#x201D;</span>
            <footer className="editorial-quote__author">
              <span>&mdash; TalentMatch</span>
              <strong>智能评估团队</strong>
              <Sparkles size={13} aria-hidden="true" />
            </footer>
          </div>
        </div>
      </section>
      {/* Key Positions — last section */}
      <section className="home-section home-priority-section">
        <div className="home-section__head">
          <div>
            <p className="home-section__head-label">Priority Pipeline</p>
            <h2 className="home-section__head-title">{'重点招聘岗位'}</h2>
          </div>
          <button className="home-section__head-link" onClick={()=>onNavigate?.("jobs")}>{'查看全部岗位'} <ArrowUpRight/></button>
        </div>
        <div className="priority-job-grid">
          {showSkeleton && dataLoading ? (
            <div className="home-loading-skeleton" aria-hidden="true" style={{display:"contents"}}>
              {[1,2,3].map(i => (
                <div key={i} className="home-skeleton__job-card">
                  <div className="home-skeleton__shimmer home-skeleton__job-watermark" />
                  <div className="home-skeleton__shimmer home-skeleton__job-location" />
                  <div className="home-skeleton__shimmer home-skeleton__job-name" />
                  <div className="home-skeleton__shimmer home-skeleton__job-desc" />
                  <div className="home-skeleton__shimmer home-skeleton__job-desc" />
                  <div className="home-skeleton__job-footer">
                    <div className="home-skeleton__shimmer home-skeleton__job-company" />
                    <div className="home-skeleton__shimmer home-skeleton__job-action" />
                  </div>
                </div>
              ))}
            </div>
          ) : topJobs.length?topJobs.map((job,i)=>{
            return <button key={job.id} className="priority-job-card" onClick={()=>{setSelected(job)}}>
              <span className="priority-job-card__watermark" aria-hidden="true">{String(i+1).padStart(2,"0")}</span>
              <div className="priority-job-card__top">
                <span className="priority-job-card__location"><MapPin size={12}/>{job.city||'不限'}</span>
                <span className="priority-job-card__score">{(job.score||85)}分</span>
              </div>
              <div className="priority-job-card__content">
                <h3 className="priority-job-card__name">{job.name}</h3>
                <p className="priority-job-card__desc">{job.description}</p>
              </div>
              <div className="priority-job-card__bottom">
                <span className="priority-job-card__company">{job.company||'招聘团队'}</span>
                <span className="priority-job-card__detail">查看详情 <ArrowUpRight size={12}/></span>
              </div>
            </button>;
          }):<div className="priority-job-card" style={{gridColumn:"1/-1",padding:60,textAlign:"center",cursor:"default"}}><p style={{color:"var(--ent-text-muted)"}}>{'正在加载岗位数据...'}</p></div>}
          {/* Add new job card placeholder */}
          <button className="priority-add-card" onClick={()=>setAdding(true)}>
            <span className="priority-add-card__watermark" aria-hidden="true">+</span>
            <div className="priority-add-card__icon"><Plus size={22}/></div>
            <span className="priority-add-card__text">添加新岗位</span>
          </button>
        </div>
      </section>
    </div>
    {selected&&<JobDialog job={selected} close={()=>setSelected(null)} onDelete={deleteLocalJob}/>}
    {adding&&<AddJobDialog close={()=>setAdding(false)} save={add}/>}
  </div>;
}


export type JobSectionKey="jobs"|"discovery"|"evolution"|"evidence";
export default function PlatformPage({page,onNavigate,preferredCandidateName,onOpenGraph,isLoggedIn,activeJobSection,onJobSectionChange}:{page:PageKey;onNavigate?:(page:PageKey|"matching")=>void;preferredCandidateName?:string;onOpenGraph?:(name:string)=>void;isLoggedIn:boolean;activeJobSection?:JobSectionKey;onJobSectionChange?:(section:JobSectionKey)=>void}){
  const m=meta[page];
  if(page==="overview")return <HomePage onNavigate={onNavigate} isLoggedIn={isLoggedIn}/>;
  if(page==="capability")return <CapabilityPage onNavigate={onNavigate}/>;
  if(page==="jobs")return <JobsPage workspace={false} onNavigate={onNavigate} activeJobSection={activeJobSection||"jobs"} onJobSectionChange={onJobSectionChange}/>;
  return <main className="platform-main"><div className="page-heading" key={page}><div><span className="slide-in-left" style={{"--i":0} as any}>{m.eyebrow}</span><h2 className="slide-in-left" style={{"--i":1} as any}>{m.title}</h2><p className="slide-in-left" style={{"--i":2} as any}>{m.desc}</p></div></div><Fragment>{page==="graph"?<TalentGraphPage onCompare={()=>onNavigate?.("compare")} preferredCandidateName={preferredCandidateName}/>:page==="compare"?<CompareRoute onBack={()=>onNavigate?.("graph")}/>:page==="evolution"?<TrendInsightsPage/>:page==="unified"?<AssessmentPage onOpenGraph={onOpenGraph}/>:page==="favorites"?<FavoritesPage onOpenGraph={onOpenGraph}/>:page==="about"?<AboutPage onBack={()=>onNavigate?.("overview")}/>:null}</Fragment></main>;
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
  const tagStyle={fontStyle:"normal" as const,padding:"3px 7px",borderRadius:999,fontSize:10,border:"1px solid #DCE3EC",background:"#F4F7FB",color:"#667085"};
  const tagMatch={fontStyle:"normal" as const,padding:"3px 7px",borderRadius:999,fontSize:10,border:"1px solid rgba(7,94,204,.15)",background:"#E8F1FD",color:"#075ECC"};
  const tagGap={fontStyle:"normal" as const,padding:"3px 7px",borderRadius:999,fontSize:10,border:"1px solid rgba(220,38,38,.15)",background:"#FEE2E2",color:"#DC2626"};

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

type TrendPageState={dataTime:string;loading:boolean;error:string;roleName:string;summary:{currentDemand:number|null;peakDemand:number|null;recentChange:number|null;changeDirection:""|"up"|"down";dataPoints:number;hasTwoPoints:boolean}};
function TrendInsightsPage(){
  const [mode,setMode]=useState<"change"|"compare">("change");
  const [pageState,setPageState]=useState<TrendPageState>({dataTime:"",loading:false,error:"",roleName:"",summary:{currentDemand:null,peakDemand:null,recentChange:null,changeDirection:"",dataPoints:0,hasTwoPoints:false}});
  const [refreshTrigger,setRefreshTrigger]=useState(0);
  const m=meta.evolution;const s=pageState.summary;
  const handleRefresh=()=>setRefreshTrigger(t=>t+1);
  return <main className="trends-page">
    <div className="trends-page__inner">
      <section className="trends-page-heading">
        <div className="trends-page-heading__copy">
          <span className="trends-page-heading__eyebrow">{m.eyebrow}</span>
          <h1>{m.title}</h1>
          <p>{m.desc}</p>
        </div>
        <div className="trends-page-heading__actions">
          {pageState.dataTime&&<span className="trends-page-heading__time"><Clock3 size={13}/>数据时间：{pageState.dataTime}</span>}
          <button className="job-actions__secondary" onClick={handleRefresh} disabled={pageState.loading} type="button">
            <RefreshCw className={pageState.loading?"spin":""} size={15}/>
            {pageState.loading?"更新中":"获取最新趋势"}
          </button>
        </div>
      </section>
      {pageState.error&&<div className="trends-error-banner" role="alert"><AlertTriangle size={16}/><span>{pageState.error}</span><button type="button" className="job-actions__secondary" onClick={handleRefresh}>重试</button></div>}
      <section className="trends-summary-grid">
        <MetricCard label="当前需求" value={s.currentDemand!==null?s.currentDemand.toLocaleString():"--"} icon={TrendingUp} tone="blue" description={s.currentDemand!==null?`${pageState.roleName||"岗位"}最新月度需求量`:"暂无可用数据"}/>
        <MetricCard label="历史峰值" value={s.peakDemand!==null?s.peakDemand.toLocaleString():"--"} icon={Activity} tone="mint" description={s.peakDemand!==null?"当前筛选范围内最高月需求":"暂无可用数据"}/>
        <MetricCard label="近期变化" value={s.hasTwoPoints&&s.recentChange!==null?(s.recentChange>0?"+":"")+s.recentChange.toLocaleString():"数据不足"} icon={TrendingUp} tone={s.changeDirection==="up"?"mint":s.changeDirection==="down"?"blue":"blue"} description={s.hasTwoPoints&&s.recentChange!==null?(s.recentChange>0?"较前值上升":s.recentChange<0?"较前值下降":"较前值持平"):"需至少两个有效数据点"}/>
        <MetricCard label="数据覆盖" value={s.dataPoints>0?s.dataPoints.toLocaleString()+" 个月":"--"} icon={CalendarDays} tone="cyan" description={s.dataPoints>0?"含历史值与预测趋势":"暂无数据"}/>
      </section>
      <nav className="trends-view-tabs" role="tablist" aria-label="趋势视图切换">
        <button type="button" role="tab" aria-selected={mode==="change"} className={mode==="change"?"trends-view-tabs__active":""} onClick={()=>setMode("change")}><Activity size={14}/>时间变化图</button>
        <button type="button" role="tab" aria-selected={mode==="compare"} className={mode==="compare"?"trends-view-tabs__active":""} onClick={()=>setMode("compare")}><GitCompareArrows size={14}/>时间对比图</button>
      </nav>
      <section className="trends-workspace">
        {mode==="change"?<CachedEvolutionPage onStateChange={setPageState} refreshTrigger={refreshTrigger}/>:<YearComparisonPage onStateChange={setPageState} refreshTrigger={refreshTrigger}/>}
      </section>
    </div>
  </main>;
}

const monthKey=(value:string)=>/^\d{4}-\d{2}$/.test(value)?value:`${String(value).slice(0,4)}-01`;
const addMonths=(value:string,offset:number)=>{const [year,month]=monthKey(value).split("-").map(Number);const date=new Date(year,month-1+offset,1);return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}`};
const monthPoints=(values:number[],max:number)=>values.map((value,index)=>`${20+index*(960/Math.max(1,values.length-1))},${315-value/max*280}`).join(" ");
function monthlyRows(series:any[],count:number){
  const normalized=series.map(row=>({...row,period:monthKey(String(row.period))})).sort((a,b)=>a.period.localeCompare(b.period));if(!normalized.length)return [];
  const byMonth=new Map(normalized.map(row=>[row.period,row]));const end=normalized.at(-1)!.period;return Array.from({length:count},(_,index)=>{const period=addMonths(end,index-count+1);return byMonth.get(period)||{period,demand:0,sourceCount:0}});
}

function YearComparisonPage({onStateChange,refreshTrigger}:{onStateChange?:(state:TrendPageState)=>void;refreshTrigger?:number}){
  const [data,setData]=useState<any>(null);const [role,setRole]=useState("java-backend-engineer");const [skill,setSkill]=useState("");const [yearA,setYearA]=useState("");const [yearB,setYearB]=useState("");const [loading,setLoading]=useState(false);const [error,setError]=useState("");const [dataTime,setDataTime]=useState("");
  const abortRef=useRef<AbortController|null>(null);
  const load=async()=>{
    if(abortRef.current)abortRef.current.abort();const controller=new AbortController();abortRef.current=controller;
    setLoading(true);setError("");
    try{const payload=await json(`/api/trends?jobId=${encodeURIComponent(role)}&refresh=0`,{signal:controller.signal});if(controller.signal.aborted)return;const evolution=payload.evolution||{};setData(evolution);setDataTime(payload.cachedAt||"");const availableSkills=Array.from(new Set((evolution.series||[]).map((row:any)=>row.skill))) as string[];const years=Array.from(new Set((evolution.series||[]).map((row:any)=>String(row.period).slice(0,4)))).sort() as string[];setSkill(current=>current&&availableSkills.includes(current)?current:availableSkills[0]||"");setYearA(current=>current&&years.includes(current)?current:years.at(-2)||years[0]||"");setYearB(current=>current&&years.includes(current)?current:years.at(-1)||years[0]||"")}
    catch(e:any){if(controller.signal.aborted)return;setError(e?.message||"数据加载失败，请检查网络后重试")}
    finally{if(!controller.signal.aborted)setLoading(false)}
  };
  useEffect(()=>{load();return ()=>{abortRef.current?.abort()}},[role]);
  useEffect(()=>{if(refreshTrigger!==undefined&&refreshTrigger>0)load()},[refreshTrigger]);
  const years=Array.from(new Set((data?.series||[]).map((row:any)=>String(row.period).slice(0,4)))).sort() as string[];const skills=Array.from(new Set((data?.series||[]).map((row:any)=>row.skill))) as string[];
  const valuesFor=(year:string)=>Array.from({length:12},(_,index)=>(data?.series||[]).filter((row:any)=>row.skill===skill&&monthKey(String(row.period))===`${year}-${String(index+1).padStart(2,"0")}`).reduce((sum:number,row:any)=>sum+(Number(row.demand)||0),0));
  const valuesA=valuesFor(yearA);const valuesB=valuesFor(yearB);const max=Math.max(1,...valuesA,...valuesB);const totalA=valuesA.reduce((sum,value)=>sum+value,0);const totalB=valuesB.reduce((sum,value)=>sum+value,0);const difference=totalB-totalA;const roleName=(data?.roleOptions||[]).find((item:any)=>item.roleId===role)?.role||data?.title||"岗位";const months=Array.from({length:12},(_,index)=>`${String(index+1).padStart(2,"0")}月`);
  const dataForA=valuesA.some(v=>v>0);const dataForB=valuesB.some(v=>v>0);
  useEffect(()=>{
    if(!onStateChange)return;const allMonthly=[...valuesA,...valuesB].filter(v=>v>0);const peakDemand=allMonthly.length?Math.max(...allMonthly):null;
    onStateChange({dataTime:dataTime?timeText(new Date(dataTime)):"",loading,error,roleName,summary:{currentDemand:totalB,peakDemand,recentChange:yearA&&yearB?Math.abs(difference):null,changeDirection:difference>0?"up":difference<0?"down":"",dataPoints:allMonthly.length,hasTwoPoints:!!(dataForA&&dataForB)}});
  },[dataTime,loading,error,roleName,totalB,difference,yearA,yearB,valuesA.join(","),valuesB.join(",")]);
  return <div className="trends-chart-card">
    <header className="trends-toolbar trends-toolbar--four">
      <label className="trends-toolbar__field"><span>特定岗位</span><select value={role} onChange={e=>setRole(e.target.value)}>{(data?.roleOptions||[]).map((item:any)=><option value={item.roleId} key={item.roleId}>{item.role}</option>)}</select></label>
      <label className="trends-toolbar__field"><span>技能趋势</span><select value={skill} onChange={e=>setSkill(e.target.value)}>{skills.map((item:string)=><option key={item}>{item}</option>)}</select></label>
      <label className="trends-toolbar__field"><span>起始年份</span><select value={yearA} onChange={e=>setYearA(e.target.value)}>{years.map((year:string)=><option key={year}>{year}</option>)}</select></label>
      <label className="trends-toolbar__field"><span>对比年份</span><select value={yearB} onChange={e=>setYearB(e.target.value)}>{years.map((year:string)=><option key={year}>{year}</option>)}</select></label>
    </header>
    {loading&&!data?<div className="trends-empty"><div className="trends-spinner"/><p>正在读取月度趋势...</p></div>
    :!data&&error?<div className="trends-empty" role="alert"><AlertTriangle size={20}/><p>{error}</p><button type="button" className="job-actions__secondary" onClick={load}>重试</button></div>
    :!data&&years.length<2?<div className="trends-empty"><CalendarDays size={20}/><p>当前数据不足两个年份，暂时无法进行时间对比。</p></div>
    :!data?<div className="trends-empty"><CalendarDays size={20}/><p>暂无对比数据。</p></div>
    :<>
      {error&&<div className="trends-error-banner" role="alert" style={{marginBottom:16}}><AlertTriangle size={14}/><span>{error}</span><button type="button" className="job-actions__secondary" onClick={load} style={{marginLeft:"auto"}}>重试</button></div>}
      {years.length<2?<div className="trends-empty"><CalendarDays size={20}/><p>当前数据不足两个年份，暂时无法进行时间对比。</p></div>
      :<>
      <div className="trends-chart-header"><div><h3 className="trends-chart-title">{skill||"技能"} · {roleName}</h3><span className="trends-chart-subtitle">按 1—12 月对齐比较 · {yearA} 合计 <b>{totalA}</b> · {yearB} 合计 <b>{totalB}</b></span></div><div className="trends-chart-legend"><span className="trends-legend-year-a"><i/>{yearA}</span><span className="trends-legend-year-b"><i/>{yearB}</span></div></div>
      <div className="trends-canvas trends-canvas--compare">
        <div className="trends-canvas__axis"><span>{max}</span><span>{Math.round(max*.66)}</span><span>{Math.round(max*.33)}</span><span>0</span></div>
        <svg viewBox="0 0 1000 340" preserveAspectRatio="none" aria-label={`${yearA}年与${yearB}年${skill||"技能"}月度需求对比`}>
          <polyline points={monthPoints(valuesA,max)} fill="none" stroke="#075ECC" strokeWidth="3"/>
          <polyline points={monthPoints(valuesB,max)} fill="none" stroke="#C00072" strokeWidth="3"/>
          {valuesA.map((value,index)=><circle key={`a-${index}`} cx={20+index*(960/11)} cy={315-value/max*280} r="5" fill="#FFFFFF" stroke="#075ECC" strokeWidth="3"><title>{yearA}年{months[index]}：{value}</title></circle>)}
          {valuesB.map((value,index)=><circle key={`b-${index}`} cx={20+index*(960/11)} cy={315-value/max*280} r="5" fill="#FFFFFF" stroke="#C00072" strokeWidth="3"><title>{yearB}年{months[index]}：{value}</title></circle>)}
        </svg>
      </div>
      <div className="trends-canvas__timeaxis">{months.map((month:string)=><span key={month}>{month}</span>)}</div>
      <div className="trends-insight"><GitCompareArrows size={16}/><p>{difference>0?`${yearB} 年全年需求比 ${yearA} 年增加 ${difference}；折线按月展示变化，可直接判断增长集中在哪些月份。`:difference<0?`${yearB} 年全年需求比 ${yearA} 年减少 ${Math.abs(difference)}；折线按月展示下降发生的具体月份。`:`两个年份全年需求总量一致，可通过月度折线观察需求高峰出现时间的差异。`}</p></div>
      {loading&&data&&<div className="trends-chart-card__busy" aria-live="polite">更新中...</div>}
    </>}
    </>
  }
  </div>;
}

function CachedEvolutionPage({onStateChange,refreshTrigger}:{onStateChange?:(state:TrendPageState)=>void;refreshTrigger?:number}){
  const [role,setRole]=useState("java-backend-engineer");const [skill,setSkill]=useState("Java");const [months,setMonths]=useState(12);const [data,setData]=useState<any>(null);const [loading,setLoading]=useState(false);const [error,setError]=useState("");const [dataTime,setDataTime]=useState("");
  const abortRef=useRef<AbortController|null>(null);
  const load=async(force=false)=>{
    if(abortRef.current)abortRef.current.abort();const controller=new AbortController();abortRef.current=controller;
    setLoading(true);setError("");
    try{const payload=await json(`/api/trends?jobId=${encodeURIComponent(role)}&refresh=${force?1:0}`,{signal:controller.signal});if(controller.signal.aborted)return;const evolution=payload.evolution||{};setData(evolution);setDataTime(payload.cachedAt||"");const available=Array.from(new Set((evolution.series||[]).map((x:any)=>x.skill))) as string[];if(!available.includes(skill))setSkill(available[0]||"")}
    catch(e:any){if(controller.signal.aborted)return;setError(e?.message||"数据加载失败，请检查网络后重试")}
    finally{if(!controller.signal.aborted)setLoading(false)}
  };
  useEffect(()=>{load(false);return ()=>{abortRef.current?.abort()}},[role]);
  useEffect(()=>{if(refreshTrigger!==undefined&&refreshTrigger>0)load(true)},[refreshTrigger]);
  const skills=Array.from(new Set((data?.series||[]).map((x:any)=>x.skill))) as string[];const all=(data?.series||[]).filter((x:any)=>x.skill===skill);const rows=monthlyRows(all,months);const historicalValues=rows.map((row:any)=>Number(row.demand)||0);const last=historicalValues.at(-1)||0;const recent=historicalValues.slice(-4);const rawStep=recent.length>1?(recent.slice(1).reduce((sum,value,index)=>sum+value-recent[index],0)/(recent.length-1)):0;const stepLimit=Math.max(1,last*.2);const step=Math.max(-stepLimit,Math.min(stepLimit,rawStep));let projected=last;const forecast=Array.from({length:6},(_,index)=>{projected=Math.max(0,Math.round(projected+step));return {period:addMonths(rows.at(-1)?.period||monthKey(new Date().toISOString().slice(0,7)),index+1),demand:projected}});const combinedValues=[...historicalValues,...forecast.map(item=>item.demand)];const max=Math.max(1,...combinedValues);const totalCount=combinedValues.length;
  const safeX=(i:number)=>20+i*(960/Math.max(1,totalCount-1));const safeY=(v:number)=>315-(v/max)*280;
  const historyLinePoints=historicalValues.map((value,index)=>`${safeX(index)},${safeY(value)}`).join(" ");
  const forecastPoints=[last,...forecast.map(item=>item.demand)].map((value,index)=>`${safeX(rows.length-1+index)},${safeY(value)}`).join(" ");
  const predictionStart=historicalValues.length?safeX(Math.max(0,rows.length-1)):0;const axisRows=[...rows,...forecast];
  const roleName=data?.title||"岗位";const hasData=historicalValues.length>0;const hasMultiple=historicalValues.length>=2;
  useEffect(()=>{
    if(!onStateChange)return;const valid=historicalValues.filter(v=>isFinite(v)&&v>0);
    const currentDemand=valid.length?valid[valid.length-1]:null;const peakDemand=valid.length?Math.max(...valid):null;
    const hasTwo=valid.length>=2;const prev=hasTwo?valid[valid.length-2]:null;const curr=hasTwo?valid[valid.length-1]:null;
    const diff=hasTwo&&prev!==null&&curr!==null?curr-prev:null;
    onStateChange({dataTime:dataTime?timeText(new Date(dataTime)):"",loading,error,roleName,summary:{currentDemand,peakDemand,recentChange:diff!==null?Math.abs(diff):null,changeDirection:diff!==null&&diff>0?"up":diff!==null&&diff<0?"down":"",dataPoints:valid.length,hasTwoPoints:hasTwo}});
  },[dataTime,loading,error,roleName,historicalValues.join(","),months]);
  return <div className="trends-chart-card">
    <header className="trends-toolbar">
      <label className="trends-toolbar__field"><span>特定岗位</span><select value={role} onChange={e=>setRole(e.target.value)}>{(data?.roleOptions||[]).map((x:any)=><option key={x.roleId} value={x.roleId}>{x.role}（{x.recordCount}）</option>)}</select></label>
      <label className="trends-toolbar__field"><span>技能趋势</span><select value={skill} onChange={e=>setSkill(e.target.value)}>{skills.map((x:string)=><option key={x}>{x}</option>)}</select></label>
      <div className="trends-toolbar__range"><span>历史范围</span><div className="trends-toolbar__pills">{[[6,"6个月"],[12,"12个月"],[24,"24个月"]].map(([n,l])=><button type="button" className={months===n?"trends-pill--active":""} onClick={()=>setMonths(n as number)} key={n}>{l}</button>)}</div></div>
    </header>
    {loading&&!data?<div className="trends-empty"><div className="trends-spinner"/><p>正在读取趋势数据...</p></div>
    :!hasData&&error?<div className="trends-empty" role="alert"><AlertTriangle size={20}/><p>{error}</p><button type="button" className="job-actions__secondary" onClick={()=>load(true)}>重试</button></div>
    :!hasData?<div className="trends-empty"><CalendarDays size={20}/><p>暂无趋势数据，请切换岗位或技能后重试。</p></div>
    :<>
      {error&&<div className="trends-error-banner" role="alert" style={{marginBottom:16}}><AlertTriangle size={14}/><span>{error}</span><button type="button" className="job-actions__secondary" onClick={()=>load(true)} style={{marginLeft:"auto"}}>重试</button></div>}
      <div className="trends-chart-header"><div><h3 className="trends-chart-title">{skill||"技能"} · {roleName}</h3><span className="trends-chart-subtitle">当前需求量 <b>{last}</b> · 历史按月统计 · 虚线为未来 6 个月预测</span></div><div className="trends-chart-legend"><span className="trends-legend-history"><i/>历史数据</span><span className="trends-legend-forecast"><i/>预测数据</span></div></div>
      <div className="trends-canvas trends-canvas--forecast">
        <div className="trends-canvas__axis"><span>{max}</span><span>{Math.round(max*.66)}</span><span>{Math.round(max*.33)}</span><span>0</span></div>
        <svg viewBox="0 0 1000 340" preserveAspectRatio="none" aria-label={`${skill||"技能"}历史趋势与未来6个月预测`}>
          <defs><linearGradient id="trendsMarketArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#075ECC" stopOpacity=".14"/><stop offset="1" stopColor="#075ECC" stopOpacity="0"/></linearGradient></defs>
          {hasMultiple&&predictionStart>0&&<rect x={predictionStart} y="0" width={1000-predictionStart} height="340" fill="#E8F1FD" opacity=".5"/>}
          {hasMultiple&&historyLinePoints&&<polygon points={`${historyLinePoints} ${safeX(rows.length-1)},330 20,330`} fill="url(#trendsMarketArea)"/>}
          {hasMultiple&&<polyline points={historyLinePoints} fill="none" stroke="#075ECC" strokeWidth="3"/>}
          {!hasMultiple&&hasData&&<circle cx={safeX(0)} cy={safeY(historicalValues[0])} r="6" fill="#075ECC"><title>{rows[0]?.period}：{historicalValues[0]}</title></circle>}
          <polyline className="trends-forecast-line" points={forecastPoints} fill="none" stroke="#C00072" strokeWidth="3" strokeDasharray="12 8"/>
          {predictionStart>0&&<line x1={predictionStart} y1="10" x2={predictionStart} y2="330" stroke="#C00072" strokeWidth="1.5" strokeDasharray="4 6" opacity=".4"/>}
          {predictionStart>0&&<text x={Math.min(900,predictionStart+12)} y="22" fill="#C00072" fontSize="12" fontFamily="'Noto Sans SC',sans-serif">预测区间</text>}
          {rows.map((row:any,index:number)=><circle key={row.period} cx={safeX(index)} cy={safeY(Number(row.demand||0))} r="5" fill="#FFFFFF" stroke="#075ECC" strokeWidth="2.5"><title>{row.period}：{row.demand||0}</title></circle>)}
          {forecast.map((row,index)=><circle key={row.period} cx={safeX(rows.length+index)} cy={safeY(row.demand)} r="5" fill="#FDE8F2" stroke="#C00072" strokeWidth="2.5"><title>{row.period} 预测：{row.demand}</title></circle>)}
        </svg>
      </div>
      <div className="trends-canvas__timeaxis">{axisRows.map((row:any,index:number)=><span className={index>=rows.length?"trends-timeaxis--predicted":""} key={row.period}>{row.period.slice(2)}{index===rows.length&&<b>预测</b>}</span>)}</div>
      <div className="trends-insight"><TrendingUp size={16}/><p>虚线从最后一个真实月份开始延伸，表示未来 6 个月的需求估算；预测值用于趋势参考，不代表确定的岗位数量。</p></div>
      {loading&&data&&<div className="trends-chart-card__busy" aria-live="polite">更新中...</div>}
    </>}
  </div>;
}

function Stat({label,value,tone="purple",onClick,help}:{label:string;value:string|number;tone?:string;onClick?:()=>void;help?:string}){const content=<><span>{label}</span><div><b className={tone}>{value}</b>{onClick&&<ArrowUpRight/>}</div>{help&&<small>{help}</small>}</>;return onClick?<button className="stat-card actionable spring-hover" onClick={onClick}>{content}</button>:<div className="stat-card">{content}</div>}

function MetricCard({label,value,icon:Icon,tone="blue",onClick,description,ariaLabel}:{label:string;value:number|string;icon?:React.ComponentType<{size?:number}>;tone?:"blue"|"mint"|"cyan";onClick?:()=>void;description?:string;ariaLabel?:string}){
  const valueClass=tone==="mint"?"job-stat-card__value job-stat-card__value--mint":tone==="cyan"?"job-stat-card__value job-stat-card__value--cyan":"job-stat-card__value";
  const content=<>
    <p className="job-stat-card__label">{label} {Icon&&<Icon size={16}/>}</p>
    <h3 className={valueClass}>{typeof value==="number"?value.toLocaleString():value}</h3>
    {description&&<p className="job-stat-card__sub">{description}</p>}
  </>;
  return onClick?<button className="job-stat-card" onClick={onClick} aria-label={ariaLabel||label}>{content}</button>:<div className="job-stat-card" role="status" aria-label={ariaLabel||label}>{content}</div>;
}

function JobsPage({workspace,onNavigate,activeJobSection,onJobSectionChange}:{workspace:boolean;onNavigate?:(page:PageKey|"matching")=>void;activeJobSection?:JobSectionKey;onJobSectionChange?:(section:JobSectionKey)=>void}){
  const pageSize=workspace?6:30;const [remoteJobs,setRemoteJobs]=useState<JobRow[]>([]);const [localJobs,setLocalJobs]=useState<JobRow[]>([]);const [total,setTotal]=useState(0);const [page,setPage]=useState(1);const [candidates,setCandidates]=useState<CandidateRow[]>([]);const [interviews,setInterviews]=useState<InterviewRow[]>([]);const [assessments,setAssessments]=useState<AssessmentRow[]>([]);const [error,setError]=useState("");const [loading,setLoading]=useState(false);const [updated,setUpdated]=useState(timeText());const [query,setQuery]=useState("");const [selected,setSelected]=useState<JobRow|null>(null);const [adding,setAdding]=useState(false);const [candidatePanel,setCandidatePanel]=useState(false);const [interviewPanel,setInterviewPanel]=useState(false);const [crawler,setCrawler]=useState<any>(null);const loadMoreRef=useRef<HTMLDivElement|null>(null);const loadingMoreRef=useRef(false);const requestSeqRef=useRef(0);
  const [jobsTab,setJobsTab]=useState<string>(()=>{const s=activeJobSection||sessionStorage.getItem("talentmatch-job-section")||"jobs";if(s==="evidence"){sessionStorage.setItem("talentmatch-job-section","evolution");return"evolution"}return s});
  useEffect(()=>{if(activeJobSection)setJobsTab(activeJobSection)},[activeJobSection]);
  /* ── Overview data for job management homepage ── */
  const [overview,setOverview]=useState<{discoveryTotal:number|null;discoveryPending:number|null;discoveryError:boolean}>({discoveryTotal:null,discoveryPending:null,discoveryError:false});
  useEffect(()=>{if(workspace)return;
    fetch("/api/platform/storage/api/competition/discoveries").then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}).then(data=>{if(!Array.isArray(data?.items))throw new Error("discoveries.items不是数组");const items=data.items;setOverview(prev=>({...prev,discoveryTotal:items.length,discoveryPending:items.filter((i:any)=>i.review_status==="pending").length,discoveryError:false}))}).catch(()=>setOverview(prev=>({...prev,discoveryError:true})));
  },[workspace]);
  const load=async(targetPage=1,append=false,search=query)=>{setLoading(true);setError("");const searchPart=search.trim()?`&keyword=${encodeURIComponent(search.trim())}`:"";const [jobResult,hrResult,assessmentResult,crawlerResult]=await Promise.allSettled([json(`/api/platform/storage/api/search/jobs?page=${targetPage}&page_size=${pageSize}${searchPart}`),json("/api/hr/state"),json("/api/assessments"),json("/api/crawler/status")]);const hr=hrResult.status==="fulfilled"?hrResult.value:{candidates:[],interviews:[],jobs:[]};const rows=jobResult.status==="fulfilled"?normalizeJobs(jobResult.value):[];const local=(hr.jobs||[]).map((x:any)=>({...x,name:x.name||x.title})).filter((x:JobRow)=>!search.trim()||`${x.name}${x.company}${x.city}`.toLowerCase().includes(search.toLowerCase()));setLocalJobs(local);setRemoteJobs(previous=>append?[...previous,...rows.filter(row=>!previous.some(item=>item.id===row.id))]:rows);setTotal(jobResult.status==="fulfilled"?Number(jobResult.value.total||rows.length):0);setPage(targetPage);setCandidates(hr.candidates||[]);setInterviews(hr.interviews||[]);setAssessments(assessmentResult.status==="fulfilled"?assessmentResult.value.items||[]:[]);if(crawlerResult.status==="fulfilled")setCrawler(crawlerResult.value);if(jobResult.status==="rejected")setError("岗位搜索服务暂未启动，候选人、面试和评估数据仍已正常读取。");setUpdated(timeText());setLoading(false)};
  useEffect(()=>{load(1,false,"")},[]);
  useEffect(()=>{const panel=sessionStorage.getItem("talentmatch-open-hr-panel");if(panel==="interviews")setInterviewPanel(true);if(panel==="candidates")setCandidatePanel(true);if(panel)sessionStorage.removeItem("talentmatch-open-hr-panel")},[]);
  useEffect(()=>{if(workspace)return;const timer=setTimeout(()=>load(1,false,query),350);return ()=>clearTimeout(timer)},[query,workspace]);
  /* IntersectionObserver auto-load when sentinel enters viewport */
  const hasMore=remoteJobs.length<total&&!workspace;
  useEffect(()=>{const sentinel=loadMoreRef.current;if(!sentinel||workspace)return;const observer=new IntersectionObserver(entries=>{const entry=entries[0];if(!entry||!entry.isIntersecting)return;if(loading||!hasMore||loadingMoreRef.current)return;loadingMoreRef.current=true;requestSeqRef.current++;const seq=requestSeqRef.current;load(page+1,true,query).finally(()=>{loadingMoreRef.current=false;if(requestSeqRef.current===seq)loadingMoreRef.current=false})},{root:null,rootMargin:"400px 0px",threshold:0.01});observer.observe(sentinel);return ()=>observer.disconnect()},[workspace,loading,hasMore,page,query]);
  const jobs=[...localJobs,...remoteJobs];const filtered=workspace?jobs.slice(0,6):jobs;
  const average=assessments.length?Math.round(assessments.reduce((sum,x)=>sum+x.score,0)/assessments.length):null;
  const add=async(job:JobRow)=>{const saved=await json("/api/hr/jobs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(job)});setLocalJobs(x=>[{...saved,name:saved.name||saved.title},...x]);setAdding(false);setUpdated(timeText());setSelected({...saved,name:saved.name||saved.title})};
  const deleteLocalJob=async(jobId:string)=>{await json(`/api/hr/jobs/${jobId}`,{method:"DELETE"});setLocalJobs(x=>x.filter(j=>j.id!==jobId));setSelected(null);setUpdated(timeText())};
  const runCrawler=async()=>{try{const state=await json("/api/crawler/refresh",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode:"quick",target:1000})});setCrawler(state);setUpdated(timeText());load(1,false,query)}catch(e){setError(e instanceof Error?e.message:"岗位采集启动失败")}};
  const m=meta.jobs;
  return <main className="platform-main" style={{padding:0,margin:0,maxWidth:"100%"}}>
    <div style={{maxWidth:1280,margin:"0 auto",padding:"0 32px 32px"}}>
      {/* ── Left-aligned heading ── */}
      <section className="jobs-page-heading">
        <div className="jobs-page-heading__copy">
          <span className="jobs-page-heading__eyebrow">{m.eyebrow}</span>
          <h1><SplitText text={m.title} tag="span" splitType="chars" delay={38} duration={0.75} ease="power3.out" from={{opacity:0,y:28,scale:.94}} to={{opacity:1,y:0,scale:1}} /></h1>
          <p><SplitText text={m.desc} tag="span" splitType="chars" delay={18} duration={0.65} ease="power3.out" from={{opacity:0,y:12,scale:.97}} to={{opacity:1,y:0,scale:1}} /></p>
        </div>
        <div className="jobs-page-heading__actions">
          <span className="job-actions__time"><Clock3 size={13}/>更新时间：{updated}</span>
          {!workspace&&<button className="job-actions__secondary" onClick={runCrawler} disabled={crawler?.status==="running"}><Sparkles size={15}/>{crawler?.status==="running"?"采集中…":"快速采集"}</button>}
        </div>
      </section>
      {/* ── Discovery overview stats (2 cards) ── */}
      {!workspace&&<div className="jobs-discovery-metrics">
        <MetricCard label="新岗位候选" value={overview.discoveryError?"不可用":overview.discoveryTotal??"..."} icon={Sparkles} tone={overview.discoveryError?"blue":"mint"} description={overview.discoveryError?"接口异常":"competition 模块发现的新岗位总数"} onClick={()=>onJobSectionChange?.("discovery")} ariaLabel="查看新岗位候选"/>
        <MetricCard label="待审核" value={overview.discoveryError?"不可用":overview.discoveryPending??"..."} tone={overview.discoveryError?"blue":"cyan"} description={overview.discoveryError?"接口异常":"待审核的新岗位发现数量"} onClick={()=>onJobSectionChange?.("discovery")} ariaLabel="查看待审核岗位"/>
      </div>}
      {jobsTab==="jobs"?<>
        {error&&<div className="service-warning"><AlertTriangle/><div><b>岗位数据未实时更新</b><span>{error}</span></div></div>}
        {/* ── Main stat cards (4 cards) ── */}
        <div className="jobs-overview-metrics">
          <MetricCard label="在招岗位" value={total} icon={BriefcaseBusiness} tone="blue" description={`数据库岗位总量${localJobs.length>0?`，另有本地岗位 ${localJobs.length} 条`:""}`} onClick={()=>{const el=document.getElementById("all-jobs-section");el?.scrollIntoView({behavior:"smooth",block:"start"})}} ariaLabel="滚动到全部招聘岗位"/>
          <MetricCard label="候选人" value={candidates.length} icon={UserRound} tone="mint" onClick={()=>setCandidatePanel(true)} description="点击查看和添加候选人" ariaLabel="打开候选人管理"/>
          <MetricCard label="待安排面试" value={interviews.filter(x=>x.status==="待进行").length} icon={CalendarDays} tone="cyan" onClick={()=>onNavigate?.("interviews")} description="点击进入面试管理" ariaLabel="打开面试管理"/>
          <MetricCard label="平均匹配度" value={average===null?"--":`${average}%`} icon={Sparkles} tone="mint" onClick={()=>{sessionStorage.setItem("talentmatch-assessment-target","average");onNavigate?.("unified")}} description={average===null?"暂无真实评估记录":"查看个人匹配度明细"} ariaLabel="查看个人匹配度明细"/>
        </div>
        {/* ── All jobs section ── */}
        <section className="all-jobs-section" id="all-jobs-section">
          <JobSectionHeader
            eyebrow="ALL POSITIONS"
            title={workspace ? "重点招聘岗位" : "全部招聘岗位"}
            sticky
          />
          <div className="all-jobs-toolbar">
            <label className="all-jobs-search"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索岗位、部门或城市..."/></label>
            <AddJobButton onClick={()=>setAdding(true)} />
          </div>
          <div className="all-jobs-grid">
            {filtered.map((job,i)=><button key={job.id} className="priority-job-card" onClick={()=>setSelected(job)}>
              <span className="priority-job-card__watermark" aria-hidden="true">{String(i+1).padStart(2,"0")}</span>
              <div className="priority-job-card__top">
                <span className="priority-job-card__location"><MapPin size={12}/>{job.city||'不限'}</span>
                <span className="priority-job-card__score">{(job.score||85)}分</span>
              </div>
              <div className="priority-job-card__content">
                <h3 className="priority-job-card__name">{job.name}</h3>
                <p className="priority-job-card__desc">{job.description||job.summary}</p>
              </div>
              <div className="priority-job-card__bottom">
                <span className="priority-job-card__company">{job.company||'招聘团队'}</span>
                <span className="priority-job-card__detail">查看详情 <ArrowUpRight size={12}/></span>
              </div>
            </button>)}
          </div>
          {loading&&hasMore&&<div className="all-jobs-loading"><div className="cube-loader"><div className="cube-loader__inner cube-loader__inner--color"/></div><span>加载中…</span></div>}
          {!hasMore&&filtered.length>0&&!workspace&&<p className="all-jobs-end">没有更多岗位</p>}
          <div ref={loadMoreRef} className="all-jobs-sentinel" aria-hidden="true"/>
        </section>
      </>:jobsTab==="discovery"?<CompetitionErrorBoundary pageName="新岗位发现" onNavigateHome={()=>{setJobsTab("jobs");sessionStorage.setItem("talentmatch-jobsTab","jobs")}}><CompetitionDiscovery/></CompetitionErrorBoundary>
      :jobsTab==="evolution"?<CompetitionErrorBoundary pageName="岗位能力管理" onNavigateHome={()=>{setJobsTab("jobs");sessionStorage.setItem("talentmatch-jobsTab","jobs")}}><CompetitionRoleWorkspace/></CompetitionErrorBoundary>
      :<>{/* fallback to jobs overview */}</>}
    </div>
    {selected&&<JobDialog job={selected} close={()=>setSelected(null)} onDelete={deleteLocalJob}/>} {adding&&<AddJobDialog close={()=>setAdding(false)} save={add}/>} {candidatePanel&&<CandidateDialog candidates={candidates} close={()=>setCandidatePanel(false)} onChange={load}/>} {interviewPanel&&<InterviewDialog candidates={candidates} interviews={interviews} jobs={jobs} close={()=>setInterviewPanel(false)} onChange={load}/>}
  </main>;
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
  useEffect(()=>{const target=sessionStorage.getItem("talentmatch-assessment-target");if(target==="average"){setCategory("average");sessionStorage.removeItem("talentmatch-assessment-target")}},[]);
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
