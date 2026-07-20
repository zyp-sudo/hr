import { AimOutlined, ApartmentOutlined, BookOutlined, CheckCircleOutlined, FireOutlined, WarningOutlined } from '@ant-design/icons';
import { Background, BackgroundVariant, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow, type Edge, type Node, type NodeProps } from '@xyflow/react';
import { Card, Progress, Tag } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { talentApi } from '../api/client';
import { abilityScore } from '../data/mock';
import type { JobMatch, SkillRank, SkillStatus } from '../types/domain';

type NodeCategory = SkillStatus | 'user';

interface TalentNodeData extends Record<string, unknown> {
  title: string;
  subtitle: string;
  category: NodeCategory;
  score?: number;
  tags?: string[];
}

type TalentNode = Node<TalentNodeData, 'talentNode'>;
type GraphData = Awaited<ReturnType<typeof talentApi.getGraph>>;

const categoryMeta: Record<NodeCategory, { label: string; color: string; bg: string; border: string; icon: JSX.Element }> = {
  user: { label: '用户中心', color: '#22d3ee', bg: 'linear-gradient(135deg, rgba(8,145,178,0.95), rgba(37,99,235,0.72))', border: 'rgba(103,232,249,0.8)', icon: <AimOutlined /> },
  owned: { label: '已有技能', color: '#10b981', bg: 'linear-gradient(135deg, rgba(16,185,129,0.22), rgba(15,23,42,0.94))', border: 'rgba(16,185,129,0.58)', icon: <CheckCircleOutlined /> },
  gap: { label: '能力缺口', color: '#ef4444', bg: 'linear-gradient(135deg, rgba(239,68,68,0.24), rgba(15,23,42,0.94))', border: 'rgba(239,68,68,0.62)', icon: <WarningOutlined /> },
  learning: { label: '推荐学习', color: '#3b82f6', bg: 'linear-gradient(135deg, rgba(59,130,246,0.24), rgba(15,23,42,0.94))', border: 'rgba(59,130,246,0.62)', icon: <BookOutlined /> },
  required: { label: '岗位需求', color: '#8b5cf6', bg: 'linear-gradient(135deg, rgba(139,92,246,0.28), rgba(15,23,42,0.94))', border: 'rgba(196,181,253,0.64)', icon: <ApartmentOutlined /> }
};

function TalentNodeCard({ data, selected }: NodeProps<TalentNode>) {
  const meta = categoryMeta[data.category];
  const isUser = data.category === 'user';
  return (
    <div
      className={`talent-node-card ${selected ? 'talent-node-selected' : ''}`}
      style={{
        width: isUser ? 190 : data.category === 'required' ? 210 : 162,
        background: meta.bg,
        borderColor: meta.border,
        boxShadow: selected ? `0 0 0 1px ${meta.color}, 0 0 36px ${meta.color}44` : '0 18px 44px rgba(0,0,0,0.28)'
      }}
    >
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-white">{data.title}</div>
          <div className="mt-1 truncate text-xs text-slate-400">{data.subtitle}</div>
        </div>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg" style={{ color: meta.color, background: `${meta.color}1f` }}>
          {meta.icon}
        </div>
      </div>
      {typeof data.score === 'number' ? (
        <div className="mt-3">
          <div className="mb-1 flex justify-between text-[11px] text-slate-400">
            <span>{isUser ? '综合评分' : '能力强度'}</span>
            <span style={{ color: meta.color }}>{data.score}%</span>
          </div>
          <Progress percent={data.score} showInfo={false} size="small" strokeColor={meta.color} trailColor="rgba(148,163,184,0.18)" />
        </div>
      ) : null}
      {data.tags?.length ? (
        <div className="mt-3 flex flex-wrap gap-1">
          {data.tags.slice(0, 2).map((tag) => (
            <span key={tag} className="rounded border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-300">{tag}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

const nodeTypes = { talentNode: TalentNodeCard };

function makeGraph(skillRanks: SkillRank[], jobMatches: JobMatch[]) {
  const skillStatusByName = new Map(skillRanks.map((skill) => [skill.name, skill.status]));
  const matchedSkillSet = new Set(jobMatches.flatMap((job) => job.matchedSkills));
  const missingSkillSet = new Set(jobMatches.flatMap((job) => job.missingSkills));
  const allSkillNames = Array.from(new Set([...skillRanks.map((skill) => skill.name), ...matchedSkillSet, ...missingSkillSet]));

  const inferSkillStatus = (name: string): SkillStatus => skillStatusByName.get(name) ?? (missingSkillSet.has(name) ? 'gap' : matchedSkillSet.has(name) ? 'owned' : 'learning');
  const skillScore = (name: string) => skillRanks.find((skill) => skill.name === name)?.score ?? (missingSkillSet.has(name) ? 42 : 68);

  const skillNodes: TalentNode[] = allSkillNames.map((skill, index) => {
    const status = inferSkillStatus(skill);
    const column = index % 2;
    const row = Math.floor(index / 2);
    return {
      id: `skill-${skill}`,
      type: 'talentNode',
      position: { x: 80 + column * 230, y: 72 + row * 128 },
      data: { title: skill, subtitle: categoryMeta[status].label, category: status, score: skillScore(skill), tags: status === 'gap' ? ['优先补齐'] : status === 'learning' ? ['推荐学习'] : ['已验证'] }
    };
  });

  const jobNodes: TalentNode[] = jobMatches.map((job, index) => ({
    id: job.id,
    type: 'talentNode',
    position: { x: 790, y: 108 + index * 190 },
    data: { title: job.title, subtitle: `${job.company} · ${job.city} · ${job.salary}`, category: 'required', score: job.matchRate, tags: [`匹配 ${job.matchRate}%`, job.city] }
  }));

  const nodes: TalentNode[] = [
    { id: 'user', type: 'talentNode', position: { x: 470, y: 295 }, data: { title: '候选人画像', subtitle: '真实岗位数据驱动', category: 'user', score: abilityScore, tags: ['可投递', '成长中'] } },
    ...skillNodes,
    ...jobNodes
  ];

  const userEdges: Edge[] = allSkillNames.map((skill) => {
    const status = inferSkillStatus(skill);
    return {
      id: `user-${skill}`,
      source: 'user',
      target: `skill-${skill}`,
      type: 'straight',
      animated: status === 'learning' || status === 'gap',
      markerEnd: { type: MarkerType.ArrowClosed, color: categoryMeta[status].color },
      style: { stroke: categoryMeta[status].color, strokeWidth: status === 'gap' ? 2.4 : 1.8, opacity: 0.8 }
    };
  });

  const jobEdges: Edge[] = jobMatches.flatMap((job) =>
    [...job.matchedSkills, ...job.missingSkills].map((skill) => {
      const isMissing = job.missingSkills.includes(skill);
      const color = isMissing ? categoryMeta.gap.color : categoryMeta.required.color;
      return {
        id: `${skill}-${job.id}`,
        source: `skill-${skill}`,
        target: job.id,
        type: 'straight',
        animated: isMissing,
        markerEnd: { type: MarkerType.ArrowClosed, color },
        style: { stroke: color, strokeWidth: isMissing ? 2.3 : 1.6, opacity: isMissing ? 0.92 : 0.58 }
      };
    })
  );

  const statusCounts = allSkillNames.reduce(
    (acc, skill) => {
      acc[inferSkillStatus(skill)] += 1;
      return acc;
    },
    { owned: 0, gap: 0, learning: 0, required: jobMatches.length } as Record<SkillStatus, number>
  );

  return { nodes, edges: [...userEdges, ...jobEdges], allSkillNames, statusCounts };
}

export default function KnowledgeGraph() {
  const [data, setData] = useState<GraphData | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState('user');

  useEffect(() => {
    talentApi.getGraph().then(setData);
  }, []);

  const graph = useMemo(() => makeGraph(data?.skillRanks ?? [], data?.jobMatches ?? []), [data]);
  const selectedNode = useMemo(() => graph.nodes.find((node) => node.id === selectedNodeId) ?? graph.nodes[0], [graph.nodes, selectedNodeId]);
  const selectedMeta = categoryMeta[selectedNode?.data.category ?? 'user'];

  if (!data) {
    return <div className="glass-panel rounded-xl p-6 text-slate-300">正在连接后端图谱数据...</div>;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-cyan-300/70">Capability Knowledge Graph</div>
          <h1 className="m-0 mt-2 text-2xl font-semibold text-white">能力知识图谱</h1>
          <p className="mt-2 text-slate-400">中心节点为用户，技能节点围绕用户展开，并连接推荐岗位需求。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Tag color={data.backendConnected ? 'green' : 'orange'}>{data.backendConnected ? '后端已连接' : 'Mock兜底'}</Tag>
          {(['owned', 'gap', 'learning', 'required'] as NodeCategory[]).map((category) => (
            <span key={category} className="rounded-md border px-3 py-1" style={{ borderColor: categoryMeta[category].border, color: categoryMeta[category].color, background: `${categoryMeta[category].color}18` }}>
              {categoryMeta[category].label}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        <Card className="glass-panel !rounded-xl"><div className="text-sm text-slate-400">图谱节点</div><div className="mt-2 text-3xl font-semibold text-white">{graph.nodes.length}</div></Card>
        <Card className="glass-panel !rounded-xl"><div className="text-sm text-slate-400">已有技能</div><div className="mt-2 text-3xl font-semibold text-emerald-300">{graph.statusCounts.owned}</div></Card>
        <Card className="glass-panel !rounded-xl"><div className="text-sm text-slate-400">能力缺口</div><div className="mt-2 text-3xl font-semibold text-red-300">{graph.statusCounts.gap}</div></Card>
        <Card className="glass-panel !rounded-xl"><div className="text-sm text-slate-400">推荐岗位</div><div className="mt-2 text-3xl font-semibold text-violet-300">{data.jobMatches.length}</div></Card>
      </div>

      <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="glass-panel relative h-[720px] overflow-hidden rounded-xl border-cyan-400/20">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_45%_45%,rgba(34,211,238,0.14),transparent_34%),radial-gradient(circle_at_76%_18%,rgba(139,92,246,0.16),transparent_30%)]" />
          <ReactFlow nodes={graph.nodes} edges={graph.edges} nodeTypes={nodeTypes} fitView minZoom={0.45} maxZoom={1.6} onNodeClick={(_, node) => setSelectedNodeId(node.id)} defaultEdgeOptions={{ type: 'straight' }} proOptions={{ hideAttribution: true }}>
            <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} color="#24415f" />
            <MiniMap pannable zoomable nodeColor={(node) => categoryMeta[(node.data as TalentNodeData).category].color} maskColor="rgba(2,6,23,0.72)" style={{ background: '#08111f', border: '1px solid #1d2b44', borderRadius: 12 }} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        <div className="space-y-4">
          <Card className="glass-panel !rounded-xl" title={<span className="text-white">节点智能解读</span>}>
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ color: selectedMeta.color, background: `${selectedMeta.color}1f` }}>{selectedMeta.icon}</div>
              <div className="min-w-0">
                <div className="truncate text-lg font-semibold text-white">{selectedNode?.data.title}</div>
                <div className="mt-1 text-sm text-slate-400">{selectedNode?.data.subtitle}</div>
              </div>
            </div>
            <div className="mt-5">
              <div className="mb-2 flex justify-between text-sm text-slate-400"><span>{selectedMeta.label}</span><span style={{ color: selectedMeta.color }}>{selectedNode?.data.score ?? 0}%</span></div>
              <Progress percent={selectedNode?.data.score ?? 0} showInfo={false} strokeColor={selectedMeta.color} trailColor="#1d2b44" />
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {selectedNode?.data.tags?.map((tag) => <Tag key={tag} color="blue">{tag}</Tag>)}
              <Tag color="cyan">{selectedMeta.label}</Tag>
            </div>
          </Card>

          <Card className="glass-panel !rounded-xl" title={<span className="text-white">AI 建议</span>}>
            <div className="space-y-3 text-sm text-slate-300">
              <div className="rounded-lg border border-line bg-panel2 p-3"><FireOutlined className="mr-2 text-cyan-300" />优先补齐红色缺口节点，它们直接影响高匹配岗位的投递成功率。</div>
              <div className="rounded-lg border border-line bg-panel2 p-3"><BookOutlined className="mr-2 text-blue-300" />蓝色学习节点建议形成项目证据，再同步到简历标签。</div>
              <div className="rounded-lg border border-line bg-panel2 p-3"><ApartmentOutlined className="mr-2 text-violet-300" />紫色岗位节点越集中，说明该能力簇的市场需求越强。</div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
