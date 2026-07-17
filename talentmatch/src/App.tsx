import { useCallback, useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import PlatformPage, { type PageKey } from "./PlatformPages";
import { ArrowUpRight, Bell, CalendarDays, Check, ChevronDown, FileImage, FileText, FileUp, Handshake, Plus, Sparkles, UserRound, UserRoundPlus, X } from "lucide-react";
import TalentMatchCard, { ScoreDisplay, MatchMetricBar, AIRecommendation } from "./components/TalentMatchCard";
import CandidateCard, { type CardData } from "./components/CandidateCard";
import LoginModal from "./components/LoginModal";
import type { AssessmentViewModel } from "./types";
import { isLoggedIn, getSavedUser, logout, type AuthUser } from "./auth";

type Job = { id:string; name:string; description?:string };
type Assessment = AssessmentViewModel;
type Candidate = { name:string; phone:string; email:string };
type Notice = { id:string;type:"interview"|"resume";title:string;detail:string;time:string };

const jobs:Job[]=[
  {id:"backend",name:"高级后端工程师"},{id:"ai",name:"AI 算法工程师"},
  {id:"frontend",name:"资深前端工程师"},{id:"product",name:"高级产品经理"},
];
const nav:Array<{label:string;key:PageKey|"matching"}>=[
  {label:"主页",key:"overview"},{label:"岗位管理",key:"jobs"},{label:"人岗匹配",key:"matching"},
  {label:"人才图谱",key:"graph"},{label:"评估结果",key:"unified"},{label:"特别关注",key:"favorites"},{label:"招聘趋势",key:"evolution"},
];
const radarLabels=["技术能力","项目经验","团队协作","教育背景","软技能"];

function Radar({values}:{values:number[]}){
  const point=(i:number,scale:number)=>{const a=-Math.PI/2+i*Math.PI*2/5;return `${150+Math.cos(a)*112*scale},${145+Math.sin(a)*112*scale}`};
  return <div className="radar-wrap"><svg viewBox="0 0 300 290" role="img" aria-label="候选人能力雷达图">
    {[1,.66,.33].map(s=><polygon key={s} points={values.map((_,i)=>point(i,s)).join(" ")} className="radar-grid"/>)}
    {values.map((_,i)=><line key={i} x1="150" y1="145" x2={point(i,1).split(",")[0]} y2={point(i,1).split(",")[1]} className="radar-line"/>)}
    <polygon points={values.map((v,i)=>point(i,v/100)).join(" ")} className="radar-value"/>
    {radarLabels.map((label,i)=>{const [x,y]=point(i,1.22).split(",").map(Number);return <text key={label} x={x} y={y} textAnchor="middle" dominantBaseline="middle">{label}</text>})}
  </svg></div>;
}

export default function App(){
  const [jobOptions,setJobOptions]=useState(jobs); const [activePage,setActivePage]=useState<PageKey|"matching">("overview");
  const [job,setJob]=useState(jobs[0]); const [jobText,setJobText]=useState(jobs[0].name);const [open,setOpen]=useState(false); const [resume,setResume]=useState(""); const [fileName,setFileName]=useState("");
  const [loading,setLoading]=useState(false); const [parsing,setParsing]=useState(false); const [ocrProgress,setOcrProgress]=useState(0); const [toast,setToast]=useState(""); const [graphCandidateName,setGraphCandidateName]=useState("");
  const [assessment,setAssessment]=useState<Assessment|null>(null); const [apiOnline,setApiOnline]=useState(false); const [candidate,setCandidate]=useState<Candidate>({name:"",phone:"",email:""}); const [candidateOpen,setCandidateOpen]=useState(false);
  const [profile,setProfile]=useState({skills:"",years:"",education:"本科",fresh:"否",experience:""});
  /* ── Auth state ── */
  const [authUser, setAuthUser] = useState<AuthUser | null>(getSavedUser);
  const [loginModalOpen, setLoginModalOpen] = useState(false);
  const [notices,setNotices]=useState<Notice[]>([]);const [noticeOpen,setNoticeOpen]=useState(false);const [unread,setUnread]=useState(0);
  /* ── Canvas multi-candidate state ── */
  const [candidateCards,setCandidateCards]=useState<CardData[]>([]);
  const [activeResultId,setActiveResultId]=useState<string|null>(null);
  const [cardCounter,setCardCounter]=useState(0);
  const fileRef=useRef<HTMLInputElement>(null);
  const dropzoneRef=useRef<HTMLButtonElement>(null);
  const fabFileRef=useRef<HTMLInputElement>(null);
  const [fabUploading,setFabUploading]=useState(false);
  const [fabProgress,setFabProgress]=useState(0);
  const loadNotices=(markRead=false)=>fetch("/api/notifications").then(r=>r.json()).then(data=>{setNotices(data.items||[]);setUnread(markRead?0:Number(data.unread||0))}).catch(()=>undefined);
  useEffect(()=>{fetch("/api/health").then(r=>{if(!r.ok)throw new Error();return r.json()}).then(()=>setApiOnline(true)).catch(()=>setApiOnline(false));fetch("/api/jobs").then(r=>r.json()).then(data=>{if(Array.isArray(data.items))setJobOptions(data.items.map((x:{id:string;title:string})=>({id:x.id,name:x.title}))) }).catch(()=>undefined);loadNotices()},[]);

  /* 全局鼠标跟踪 — 驱动 .mouse-glow-tracker 跟随鼠标 */
  useEffect(()=>{
    const onMove=(e:MouseEvent)=>{
      document.documentElement.style.setProperty("--mx",e.clientX+"px");
      document.documentElement.style.setProperty("--my",e.clientY+"px");
    };
    window.addEventListener("mousemove",onMove,{passive:true});
    return ()=>window.removeEventListener("mousemove",onMove);
  },[]);
  /* ── Auth: listen for session-expired events (kicked out by another login) ── */
  useEffect(() => {
    const onExpired = () => {
      setAuthUser(null);
      notify("会话已失效，您的账号在另一处登录了");
    };
    const onOpenLogin = () => setLoginModalOpen(true);
    window.addEventListener("auth:session-expired", onExpired);
    window.addEventListener("auth:open-login", onOpenLogin);
    return () => {
      window.removeEventListener("auth:session-expired", onExpired);
      window.removeEventListener("auth:open-login", onOpenLogin);
    };
  }, []);
  const notify=(message:string)=>{setToast(message);window.setTimeout(()=>setToast(""),3000)};
  const selectJob=(next:Job)=>{setJob(next);setJobText(next.name);setAssessment(null);setOpen(false)};
  const chooseFile=async(file?:File)=>{if(!file)return;setFileName(file.name);setParsing(true);setOcrProgress(0);try{
    let text="";
    if(file.type.startsWith("image/")||/\.(png|jpe?g|webp|bmp)$/i.test(file.name)){
      const {createWorker}=await import("tesseract.js");
      const worker=await createWorker("chi_sim+eng",1,{logger:m=>{if(m.status==="recognizing text")setOcrProgress(Math.round((m.progress||0)*100))}});
      try{const result=await worker.recognize(file);text=result.data.text.trim()}finally{await worker.terminate()}
      if(!text)throw new Error("未能从图片中识别到文字，请上传清晰的简历图片");
    }else{
      const form=new FormData();form.append("resume",file);const response=await fetch("/api/resumes/parse",{method:"POST",body:form});const data=await response.json();if(!response.ok)throw new Error(data.error||"简历解析失败");text=data.text;
    }
    setResume(text);setAssessment(null);notify(`已识别 ${file.name}，共 ${text.length} 字`);
  }catch(error){setFileName("");notify(error instanceof Error?error.message:"简历识别失败")}finally{setParsing(false);setOcrProgress(0)}};
  const evaluate=async()=>{if(resume.trim().length<30){notify("请先上传简历、选择模板或输入完整候选人经历");return}setLoading(true);try{
    if(!jobText.trim()){notify("请选择或输入目标岗位");setLoading(false);return}const response=await fetch("/api/evaluate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({jobId:job.id,jobTitle:jobText.trim(),resumeText:resume,candidateName:candidate.name.trim()||"匿名候选人"})});const data=await response.json();if(!response.ok)throw new Error(data.error||"智能评估失败");
    setAssessment({score:data.score,level:data.matchLevel,industry:data.experienceMatch.relevance,title:data.experienceMatch.alignment,gaps:data.skillGaps,strengths:data.highlights,radar:[data.radar.technical,data.radar.experience,data.radar.collaboration,data.radar.education,data.radar.softSkills]});notify("智能评估已完成，结果已保存");
  }catch(error){notify(error instanceof Error?error.message:"智能评估失败")}finally{setLoading(false)}};
  const hasCandidateInput=Boolean(candidate.name||candidate.phone||candidate.email||resume||fileName||profile.skills||profile.years||profile.experience);
  const clearCandidateInput=()=>{setCandidate({name:"",phone:"",email:""});setProfile({skills:"",years:"",education:"本科",fresh:"否",experience:""});setResume("");setFileName("");setAssessment(null);notify("已清空候选人信息")};
  /* ── Canvas helpers ── */
  const addCandidateCard=useCallback(()=>{
    const idx=cardCounter;
    setCardCounter(c=>c+1);
    const newCard:CardData={
      id:crypto.randomUUID(),
      name:"",skills:"",years:"",education:"本科",experience:"",resumeText:"",
      x:80+(idx%3)*40,y:40+(idx%4)*35,
      result:null,evaluating:false,
    };
    setCandidateCards(prev=>[...prev,newCard]);
  },[cardCounter]);
  const updateCard=useCallback((id:string,patch:Partial<CardData>)=>{
    setCandidateCards(prev=>prev.map(c=>c.id===id?{...c,...patch}:c));
  },[]);
  const deleteCard=useCallback((id:string)=>{
    setCandidateCards(prev=>prev.filter(c=>c.id!==id));
    setActiveResultId(prev=>prev===id?null:prev);
  },[]);
  const evaluateCard=useCallback(async(id:string)=>{
    const card=candidateCards.find(c=>c.id===id);
    if(!card||card.resumeText.length<30){notify("请先填写候选人简历内容（至少30字）");return}
    if(!jobText.trim()){notify("请先在左侧选择目标岗位");return}
    updateCard(id,{evaluating:true});
    try{
      const response=await fetch("/api/evaluate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({jobId:job.id,jobTitle:jobText.trim(),resumeText:card.resumeText,candidateName:card.name.trim()||"匿名候选人"})});
      const data=await response.json();
      if(!response.ok)throw new Error(data.error||"智能评估失败");
      const result:Assessment={
        score:data.score,
        level:data.matchLevel,
        industry:data.experienceMatch.relevance,
        title:data.experienceMatch.alignment,
        gaps:data.skillGaps,
        strengths:data.highlights,
        radar:[data.radar.technical,data.radar.experience,data.radar.collaboration,data.radar.education,data.radar.softSkills],
      };
      updateCard(id,{evaluating:false,result});
      setActiveResultId(id);
      notify(`${card.name||"匿名候选人"} 评估完成`);
    }catch(error){
      updateCard(id,{evaluating:false});
      notify(error instanceof Error?error.message:"智能评估失败");
    }
  },[candidateCards,job,jobText,updateCard,notify]);
  const clearAllCards=()=>{
    setCandidateCards([]);
    setActiveResultId(null);
    notify("已清空所有候选人卡片");
  };
  /* ── FAB: one-click resume upload → auto-extract → pre-fill card ── */
  const handleFabUpload=async(file?:File)=>{
    if(!file||fabUploading)return;
    setFabUploading(true);setFabProgress(0);
    try{
      let text="";
      if(file.type.startsWith("image/")||/\.(png|jpe?g|webp|bmp)$/i.test(file.name)){
        const {createWorker}=await import("tesseract.js");
        const worker=await createWorker("chi_sim+eng",1,{logger:m=>{if(m.status==="recognizing text")setFabProgress(Math.round((m.progress||0)*40))}});
        try{const result=await worker.recognize(file);text=result.data.text.trim()}finally{await worker.terminate()}
        if(!text)throw new Error("未能从图片识别文字，请上传清晰简历图片或PDF/DOCX文件");
      }else{
        setFabProgress(10);
        const form=new FormData();form.append("resume",file);
        const response=await fetch("/api/resumes/parse",{method:"POST",body:form});
        const data=await response.json();
        if(!response.ok)throw new Error(data.error||"简历解析失败");
        text=data.text;
        setFabProgress(50);
      }
      if(text.length<20)throw new Error("解析出的文本内容过短，请确认简历文件内容完整");
      setFabProgress(60);
      // Extract structured fields via AI
      const extractResponse=await fetch("/api/resumes/extract",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({resumeText:text})});
      const extracted=await extractResponse.json();
      if(!extractResponse.ok)throw new Error(extracted.error||"简历信息提取失败");
      setFabProgress(90);
      // Auto-create candidate card
      const idx=cardCounter;
      setCardCounter(c=>c+1);
      const skillsText=Array.isArray(extracted.skills)?extracted.skills.join("，"):String(extracted.skills||"");
      const newCard:CardData={
        id:crypto.randomUUID(),
        name:extracted.name||"",
        skills:skillsText,
        years:String(extracted.years||""),
        education:extracted.education||"本科",
        experience:extracted.experience||"",
        resumeText:text,
        x:80+(idx%3)*40,y:40+(idx%4)*35,
        result:null,evaluating:false,
      };
      setCandidateCards(prev=>[...prev,newCard]);
      setFabProgress(100);
      const nameSuffix=extracted.name?`「${extracted.name}」`:"";
      const skillsCount=Array.isArray(extracted.skills)?extracted.skills.length:0;
      notify(`已识别 ${nameSuffix} 的简历${skillsCount?`，提取 ${skillsCount} 项技能`:"并自动填充"}`);
    }catch(error){
      notify(error instanceof Error?error.message:"简历上传处理失败，请重试");
    }finally{
      setFabUploading(false);
      window.setTimeout(()=>setFabProgress(0),600);
    }
  };
  const activeCard=candidateCards.find(c=>c.id===activeResultId);
  const hasAnyCard=candidateCards.length>0;
  return <div className="app-shell">
    {/* ---- 氛围光层 ---- */}
    <div className="ambient"/>

    {/* ---- Apple-style 多层散景光源 ---- */}
    <div className="light-source-primary"/>
    <div className="light-source-secondary"/>
    <div className="light-source-tertiary"/>
    <div className="light-source-quaternary"/>
    <div className="light-source-quinary"/>

    {/* ---- 鼠标跟随光晕 ---- */}
    <div className="mouse-glow-tracker" id="mouse-glow-tracker"/>

    <header><div className="brand"><div className="logo"><Handshake/></div><h1>人岗匹配智能评估系统</h1></div><div className="header-actions"><span className={`api ${apiOnline?"online":"offline"}`}><i/>{apiOnline?"服务已连接":"服务未连接"}</span><div className="notification-wrap"><button className="notification-button" aria-label="通知" onClick={()=>{setNoticeOpen(x=>!x);loadNotices(true)}}><Bell/>{unread>0&&<i>{Math.min(unread,99)}</i>}</button>{noticeOpen&&<div className="notification-panel"><div className="notification-head"><span><b>招聘通知</b><small>面试安排与新简历</small></span><button onClick={()=>setNoticeOpen(false)}><X/></button></div><div className="notification-list">{notices.length?notices.map(item=><button key={item.id} onClick={()=>{setActivePage("overview");setNoticeOpen(false)}}>{item.type==="interview"?<CalendarDays/>:<FileText/>}<span><b>{item.title}</b><small>{item.detail}</small><time>{new Intl.DateTimeFormat("zh-CN",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(item.time))}</time></span></button>):<p>暂时没有新通知</p>}</div></div>}</div>{authUser?<span className="avatar" aria-label={authUser.name} title={`${authUser.name} · ${authUser.email}\n点击退出登录`} onClick={async()=>{await logout();setAuthUser(null);notify("已退出登录")}} style={{cursor:"pointer"}}>{authUser.name[0]}</span>:<button className="header-login-btn spring-hover" onClick={()=>setLoginModalOpen(true)}>登录</button>}</div></header>
    <nav>{nav.map(item=><button className={activePage===item.key||(item.key==="graph"&&activePage==="compare")?"active":""} key={item.key} onClick={()=>{if(!authUser&&item.key!=="overview"){setLoginModalOpen(true);notify("请先登录后查看")}else{setActivePage(item.key)}}}>{item.label}</button>)}</nav>
    {activePage!=="matching"?<PlatformPage key={activePage} page={activePage} onNavigate={setActivePage} isLoggedIn={!!authUser} preferredCandidateName={graphCandidateName} onOpenGraph={name=>{setGraphCandidateName(name);setActivePage("graph")}}/>:<>
      <main className="match-canvas-layout">
      {/* ════════ Left sidebar — job selector + controls ════════ */}
      <aside className="match-sidebar">
        <div className="match-sidebar__head">
          <h2>选择目标岗位</h2>
          <span className="match-sidebar__hint">岗位将应用于所有候选人卡片</span>
        </div>
        <div className="select-wrap job-combobox">
          <input value={jobText} onFocus={()=>setOpen(true)} onChange={e=>{const value=e.target.value;setJobText(value);const exact=jobOptions.find(x=>x.name===value);setJob(exact||{id:"custom",name:value});setOpen(true)}} placeholder="选择岗位，或直接输入…"/>
          {jobText&&<button className="job-clear" aria-label="清空" onClick={()=>{setJobText("");setJob({id:"custom",name:""});setOpen(true)}}><X/></button>}
          <button className="job-toggle" aria-label="展开岗位列表" onClick={()=>setOpen(!open)}><ChevronDown/></button>
          {open&&<div className="options">{jobOptions.filter(j=>!jobText||j.name.includes(jobText)||jobText===job.name).map(j=><button key={j.id} onClick={()=>selectJob(j)}>{j.name}{j.id===job.id&&<Check/>}</button>)}</div>}
        </div>
        <div className="match-sidebar__job-info">
          {job.id!=="custom"&&<p className="match-sidebar__job-desc">{jobs.find(j=>j.id===job.id)?.description}</p>}
        </div>
        <div className="match-sidebar__actions">
          <button className="match-sidebar__add spring-hover" onClick={addCandidateCard}>
            <Plus/> 添加候选人
          </button>
          {hasAnyCard&&<button className="match-sidebar__clear" onClick={clearAllCards}>
            <X/> 清空全部
          </button>}
        </div>
        <div className="match-sidebar__stats">
          <span>{candidateCards.length} 位候选人</span>
          <span>{candidateCards.filter(c=>c.result).length} 已评估</span>
          {activeCard?.name&&<span className="candidate-chip"><UserRound/>{activeCard.name}</span>}
        </div>
      </aside>

      {/* ════════ Center canvas — draggable cards ════════ */}
      <div className="match-workspace">
        {!hasAnyCard?(
          <div className="match-workspace__empty">
            <div className="match-workspace__empty-icon"><UserRoundPlus/></div>
            <h3>添加候选人开始评估</h3>
            <p>点击左侧「添加候选人」按钮，在画布上创建候选人卡片。</p>
            <p>每个卡片可以自由拖拽定位、独立填写信息、单独发起评估。</p>
            <div className="match-workspace__empty-steps">
              <span><b>01</b> 选择岗位</span>
              <span><b>02</b> 添加候选人卡片</span>
              <span><b>03</b> 填写信息并评估</span>
              <span><b>04</b> 查看右侧匹配结果</span>
            </div>
          </div>
        ):(
          candidateCards.map(card=>(
            <CandidateCard
              key={card.id}
              card={card}
              onUpdate={updateCard}
              onDelete={deleteCard}
              onEvaluate={evaluateCard}
              onSelect={setActiveResultId}
              isSelected={activeResultId===card.id}
            />
          ))
        )}
      </div>

      {/* ════════ Right panel — results (slides in) ════════ */}
      {activeCard?.result&&(
        <aside className="match-result-panel">
          <div className="match-result-panel__header">
            <h2>{activeCard.name||"匿名候选人"}</h2>
            <button className="match-result-panel__close" onClick={()=>setActiveResultId(null)} aria-label="关闭结果面板"><X/></button>
          </div>
          <div className="match-result-panel__score">
            <TalentMatchCard
              candidateName={activeCard.name||"匿名候选人"}
              subtitle="匹配分析"
              overallScore={activeCard.result.score}
              matchLevel={activeCard.result.level}
              expandable defaultExpanded={false}
              expandedContent={<div style={{display:"flex",flexDirection:"column",gap:16}}>
                <AIRecommendation text={activeCard.result.level==="卓越匹配"?"候选人的核心技术栈、项目经验与行业背景与目标岗位高度契合，综合能力模型在各项维度上均表现突出。建议优先安排面试。":activeCard.result.level==="优秀匹配"?"候选人在关键技术领域具备扎实基础，多个维度得分均衡。核心技能覆盖岗位要求的绝大部分能力项，建议尽快推进面试流程。":activeCard.result.level==="良好匹配"?"候选人具备岗位所需的基础能力框架，部分关键技能尚有提升空间。建议重点考察候选人的学习能力和成长潜力。":activeCard.result.level==="待观察"?"候选人与目标岗位存在一定差距，核心技能覆盖不足。建议同时关注其他匹配度更高的候选人。":"候选人当前的能力模型与岗位要求存在明显差距。建议暂缓推进或与用人部门沟通调整岗位要求。"}/>
              </div>}
            >
              <div style={{background:"transparent",border:"none",boxShadow:"none",padding:0,backdropFilter:"none",WebkitBackdropFilter:"none"}}>
                <h3 style={{fontFamily:`"SF Pro Display","PingFang SC","Noto Sans SC",sans-serif`,fontWeight:600,fontSize:15,color:"rgba(255,255,255,0.90)",margin:"0 0 18px"}}>综合匹配得分</h3>
                <div className="score-ring" style={{"--score":`${activeCard.result.score*3.6}deg`} as CSSProperties}>
                  <div>
                    <span style={{fontFamily:`"SF Pro Rounded","JetBrains Mono",monospace`,fontSize:62,fontWeight:800,lineHeight:1,color:"rgba(255,255,255,0.95)",fontVariantNumeric:"tabular-nums"}}>{activeCard.result.score}</span>
                    <span style={{marginTop:14,color:"rgba(255,255,255,0.65)",fontSize:14,fontWeight:400}}>{activeCard.result.level}</span>
                  </div>
                </div>
              </div>
            </TalentMatchCard>
            <div className="match-result-panel__radar">
              <h3>能力项匹配度</h3>
              <Radar values={activeCard.result.radar}/>
            </div>
          </div>
          <div className="match-result-panel__details">
            <section>
              <h3>经验匹配</h3>
              <MatchMetricBar label="行业相关性" value={activeCard.result.industry} tone={activeCard.result.industry>=85?"mint":activeCard.result.industry>=70?"cyan":"purple"}/>
              <MatchMetricBar label="职级对标" value={activeCard.result.title} tone={activeCard.result.title>=85?"mint":activeCard.result.title>=70?"cyan":"purple"}/>
            </section>
            <section>
              <h3>技能缺口</h3>
              <div className="match-result-panel__tags">{activeCard.result.gaps.map(g=><span key={g} className="match-result-panel__tag gap">{g}</span>)}</div>
            </section>
            <section>
              <h3>匹配亮点</h3>
              {activeCard.result.strengths.map(s=><p key={s} className="match-result-panel__highlight"><Check/><span>{s}</span></p>)}
            </section>
          </div>
          <button className="match-result-panel__graph" onClick={()=>{const graphCandidate=activeCard.name.trim()||"匿名候选人";setGraphCandidateName(graphCandidate);sessionStorage.setItem("talentmatch-graph-candidate",graphCandidate);localStorage.setItem("talentmatch-graph-candidate",graphCandidate);setActivePage("graph")}}><UserRound/> 查看人才图谱 <ArrowUpRight/></button>
        </aside>
      )}
    </main>
    {/* ════════ FAB: 一键添加简历 ──────── */}
    <input ref={fabFileRef} type="file" hidden accept=".pdf,.doc,.docx,.txt,.md,.png,.jpg,.jpeg,.webp,.bmp" onChange={e=>{handleFabUpload(e.target.files?.[0]);e.target.value=""}}/>
    <div className={`fab-container${fabUploading?" fab-container--uploading":""}`}>
      {fabUploading?(
        <div className="fab-progress">
          <div className="fab-progress__ring" style={{"--progress":fabProgress} as CSSProperties}>
            <div className="fab-progress__inner">
              <span className="fab-progress__text">{fabProgress<40?"识别中…":fabProgress<60?"解析中…":fabProgress<90?"AI提取中…":"完成"}</span>
              <span className="fab-progress__pct">{fabProgress}%</span>
            </div>
          </div>
        </div>
      ):(
        <button
          className="fab-button spring-hover"
          onClick={()=>fabFileRef.current?.click()}
          onDragOver={e=>{e.preventDefault();e.currentTarget.classList.add("fab-button--drag-over")}}
          onDragLeave={e=>{e.currentTarget.classList.remove("fab-button--drag-over")}}
          onDrop={e=>{e.preventDefault();e.currentTarget.classList.remove("fab-button--drag-over");handleFabUpload(e.dataTransfer.files[0])}}
          title="一键上传简历 — 支持 PDF / DOCX / TXT / PNG / JPG"
          aria-label="一键上传简历"
        >
          <FileUp/>
          <span>一键添加简历</span>
        </button>
      )}
    </div>
  </>}
    {candidateOpen&&<div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)setCandidateOpen(false)}}><div className="dialog"><div className="dialog-head"><div><span>CANDIDATE PROFILE</span><h3>候选人档案</h3></div><button onClick={()=>setCandidateOpen(false)}><X/></button></div><label className="field"><span>姓名</span><input value={candidate.name} onChange={e=>setCandidate({...candidate,name:e.target.value})} placeholder="未填写将显示匿名候选人"/></label><label className="field"><span>手机</span><input value={candidate.phone} onChange={e=>setCandidate({...candidate,phone:e.target.value})} placeholder="选填"/></label><label className="field"><span>邮箱</span><input value={candidate.email} onChange={e=>setCandidate({...candidate,email:e.target.value})} placeholder="选填"/></label><label className="field"><span>核心技能</span><input value={profile.skills} onChange={e=>setProfile({...profile,skills:e.target.value})} placeholder="如 Java、Python、产品设计" /></label><label className="field"><span>工作年限</span><input value={profile.years} onChange={e=>setProfile({...profile,years:e.target.value})} placeholder="相关工作年限" /></label><label className="field"><span>学历</span><select value={profile.education} onChange={e=>setProfile({...profile,education:e.target.value})}><option>高中及以下</option><option>专科</option><option>本科</option><option>硕士</option><option>博士</option></select></label><label className="field"><span>项目/工作经历</span><textarea value={profile.experience} onChange={e=>setProfile({...profile,experience:e.target.value})} placeholder="项目、实习或工作经历摘要" /></label><button className="primary" onClick={async()=>{const response=await fetch("/api/hr/candidates",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...candidate,skills:profile.skills,experienceYears:Number(profile.years||0),education:profile.education,profileText:resume})});const saved=await response.json().catch(()=>null);setCandidateOpen(false);notify(saved?.vectorCapture?.status==="stored"?"候选人已保存并写入人才向量库":candidate.name?`已保存候选人：${candidate.name}`:"已保存为匿名候选人")}}>保存候选人</button></div></div>}
    {toast&&<div className="toast"><span>{toast}</span><button onClick={()=>setToast("")}><X/></button></div>}

    {/* ---- 简历拖拽粒子溶解动画 ---- */}

    {/* ---- Auth: Login modal ---- */}
    <LoginModal
      open={loginModalOpen}
      onClose={() => setLoginModalOpen(false)}
      onLoginSuccess={(user) => { setAuthUser(user); notify(`欢迎回来，${user.name}`); }}
    />
  </div>;
}

function Metric({label,value}:{label:string;value:number}){
  return <MatchMetricBar label={label} value={value} tone={value>=85?"mint":value>=70?"cyan":"purple"}/>;
}
