# 人岗匹配评分校准方案

## 问题诊断

当前系统存在 **3 条评分路径**，每条都有基准膨胀问题，导致空输入也能得 78 分：

### 路径追踪

```
React 前端 (talentmatch-frontend/App.tsx:67)
  → POST /api/evaluate {jobId, jobTitle, resumeText, candidateName}
    → talentmatch-frontend/server.ts:195  Express /api/evaluate handler
      ├── 无 AI key → fallbackAssessment() → 基准分 78
      └── 有 AI key → LLM (DeepSeek/Gemini) → 无校准 prompt → 同样虚高
```

### 🐛 Bug #1：硬编码 78 分基准（最直接的原因）

**文件**：`talentmatch-frontend/server.ts:85-89`

```typescript
function fallbackAssessment(job, resumeText) {
  const signals = job.requirements.filter(r =>
    r.split(/[、/]/).some(k =>
      k.length > 2 && resumeText.toLowerCase().includes(k.toLowerCase())
    )
  ).length;
  const score = Math.min(94, 78 + signals * 4 + Math.min(6, Math.floor(resumeText.length / 800)));
  //             ^^         ^^             
  //             上限94     基准78 ← 这里是问题
}
```

空简历：`signals = 0`，`text.length / 800 = 0` → `Math.min(94, 78 + 0 + 0)` = **78**。

这个 `78` 没有任何校准依据，是一个拍脑袋的"还行"默认值。

### 🐛 Bug #2：LLM prompt 无校准锚点

**文件**：`talentmatch-frontend/server.ts:207`

```
岗位要求：${job.requirements.join("；")}\n简历：${resumeText}
```

LLM（无论 DeepSeek 还是 Gemini）天然偏向给出中庸分数。没有要求 LLM 按证据逐项打分，也没有"无证据则 0 分"的指令。

### 🐛 Bug #3：Java 后端的 LLM prompt 同样缺乏校准

**文件**：`backend/src/com/xh202621/MatchAiAnalyzer.java:184-195`

System prompt 只说了"Ground every finding in the provided context"，但：
- 没有要求逐维度评分
- 没有锚定规则：技能未命中 → 该维度 0 分
- 没有对 resumeText 为空的防御

---

## 校准方案

### 方案 A：修复 fallback 函数（立即生效，无 AI 依赖）

**文件**：`talentmatch-frontend/server.ts`

```typescript
function fallbackAssessment(job: typeof jobs[number], resumeText: string) {
  // 1. 计算真实信号命中数
  const keywords = job.requirements
    .flatMap(r => r.split(/[、/，,]/))
    .filter(k => k.length > 2);
  const hitKeywords = keywords.filter(k =>
    resumeText.toLowerCase().includes(k.toLowerCase())
  );
  const signalRate = keywords.length ? hitKeywords.length / keywords.length : 0;

  // 2. 文本长度贡献：0–5 分（鼓励提交真实内容）
  const textChars = resumeText.length;
  const textBonus = Math.min(5, Math.floor(textChars / 200)); // 每200字+1分，上限5

  // 3. 技能覆盖贡献：0–55 分（核心维度）
  const skillCoverage = Math.round(signalRate * 55);

  // 4. 基础分：只有当提供了证据时才给
  //    完全空输入 = 0 分
  const baseScore = signalRate > 0 ? 20 : 0;

  // 5. 组合：0-100 分
  const score = Math.min(95, baseScore + skillCoverage + textBonus);

  // 6. 匹配等级
  const matchLevel = score >= 80 ? "优秀匹配" : score >= 60 ? "良好匹配" : score >= 30 ? "待观察" : "差距较大";

  // 7. 雷达图也按真实信号缩放（非固定80+）
  const radarBase = Math.max(0, Math.round(score * 0.75));
  return {
    score,
    matchLevel,
    radar: {
      technical: Math.min(95, radarBase + (signalRate > 0.3 ? 10 : 0)),
      experience: Math.min(95, radarBase + (textChars > 500 ? 8 : 0)),
      collaboration: 50, // 软技能需要专门证据，不应默认给高分
      education: 50,
      softSkills: 50,
    },
    experienceMatch: {
      relevance: Math.round(signalRate * 80),
      alignment: Math.round(signalRate * 75),
    },
    skillGaps: signalRate > 0
      ? keywords.filter(k => !resumeText.toLowerCase().includes(k.toLowerCase())).slice(0, 5)
      : ["未提供有效技能证据，无法进行缺口分析"],
    highlights: signalRate > 0
      ? [`候选人简历命中 ${hitKeywords.length}/${keywords.length} 项岗位关键词`, ...hitKeywords.slice(0, 3).map(k => `具备 ${k} 相关经验`)]
      : ["简历中未检测到与岗位要求匹配的关键技能"],
  };
}
```

**效果**：
| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| 完全空简历 | 78 分 | **0-5 分** |
| 1/3 技能命中 | 82 分 | **~38 分** |
| 全部技能命中 | 90+ | **~80-95 分** |

---

### 方案 B：校准 LLM prompt（AI API 启用时）

**文件**：`talentmatch-frontend/server.ts:207`（非 Google provider）

改前：
```
你是专业招聘评估专家。只返回JSON，字段为candidateName,score,matchLevel,radar,experienceMatch,skillGaps,highlights。

岗位：${job.title}
要求：${job.requirements.join("；")}
简历：${resumeText}
```

改后：
```
你是专业招聘评估专家。你需要严格依据候选人简历证据进行人岗匹配评估。

## 评分规则（必须严格遵守）
1. score 为 0-100 的整数，由以下加权计算：
   - 技能匹配（权重 0.45）：简历中明确提及的岗位要求技能 / 总要求技能数 × 45
   - 经验相关性（权重 0.25）：按工作年限、项目描述与岗位的匹配程度 0-25
   - 学历匹配（权重 0.15）：按学历与岗位要求匹配程度 0-15
   - 项目深度（权重 0.15）：按项目复杂度、规模、指标与岗位匹配程度 0-15
2. 锚定规则：
   - 如果简历中没有任何与岗位要求技能相关的证据，score 必须 ≤ 20
   - 如果简历文本 < 100 字，score 必须 ≤ 30
   - 雷达图每个维度必须有简历中的对应证据，无证据则该维度 ≤ 30
   - skillGaps 必须是简历中确实缺少的岗位要求技能
   - highlights 必须引用简历中的具体内容，不得编造

## 岗位信息
岗位名称：${job.title}
岗位要求：${job.requirements.join("；")}

## 候选人简历
${resumeText || "（未提供简历内容，所有维度应评分为 0）"}
```

**关键改动**：
- 强制加权计算，禁止拍脑袋给总分
- 明确锚定规则（空输入 ≤ 20 分）
- 要求 radar 维度有证据支撑，无证据 ≤ 30
- 空简历明确指示"应评分为 0"

---

### 方案 C：Java 后端的 AI 分析 prompt 增强

**文件**：`backend/src/com/xh202621/MatchAiAnalyzer.java:184-195`

当前 system prompt 太通用，建议改为：

```java
private Object messages(Map<String, Object> context) {
    String typeValue = String.valueOf(context.getOrDefault("type", ""));
    boolean isMatch = "match".equals(typeValue);
    
    String systemPrompt = isMatch
        ? "你是中文招聘数据平台的人岗匹配分析师。你必须遵守以下规则：\n"
          + "1. 只基于上下文中提供的 ruleScore、matchedDetails、missingDetails 进行分析\n"
          + "2. 不得编造候选人简历中没有的技能或经历\n"
          + "3. 如果 ruleScore 为 0 或 resumeText 为空，明确标注"简历证据不足，无法进行深度分析"\n"
          + "4. 输出 JSON 包含：summary（基于证据的综合评语）、calibration_notes（评分可信度说明）\n"
          + "5. 使用中文，简洁专业"
        : "你是中文招聘数据平台的分析师。返回紧凑 JSON。使用中文。所有发现必须基于提供的上下文，不得编造。";
    
    String userPrompt = isMatch
        ? "请基于以下人岗匹配证据进行分析。如果 ruleScore 很低或简历为空，请如实指出证据不足，不要给出模糊的正面评价。\n\n"
          + "上下文：\n" + Json.stringify(context)
        : "分析此平台上下文。若类型为 match，改进匹配诊断但不得编造简历事实。否则返回 summary、key_findings、risks、recommended_actions 和 quick_wins 的 JSON：\n"
          + Json.stringify(context);
    
    return java.util.List.of(
        map("role", "system", "content", systemPrompt),
        map("role", "user", "content", userPrompt)
    );
}
```

---

## 实施优先级

| 优先级 | 方案 | 影响范围 | 工作量 | 效果 |
|--------|------|----------|--------|------|
| **P0** | 方案 A | React 前端 fallback 评分 | 30 min | 立即解决无 AI 时的 78 分问题 |
| **P1** | 方案 B | React 前端 LLM 路径 | 15 min | 解决有 AI 时的虚高问题 |
| **P2** | 方案 C | Java 后端 AI 分析 | 30 min | 提升 Web 页匹配分析的准确性 |
| - | 移除硬编码 78 | `server.ts:87` | 1 min | 最简单但需配合方案 A |

## 验证方法

修改后，用以下场景测试：

```
# 测试 1：完全空简历
curl -X POST http://localhost:3000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{"jobId":"backend","jobTitle":"高级后端工程师","resumeText":"","candidateName":"测试"}'
# 期望：score ≤ 20

# 测试 2：核心技能完全匹配
curl -X POST http://localhost:3000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{"jobId":"backend","jobTitle":"高级后端工程师","resumeText":"5年Java开发经验，精通Spring Boot、微服务架构、Docker、Kubernetes，负责过高并发系统设计","candidateName":"张工"}'
# 期望：score ≥ 75

# 测试 3：部分匹配
curl -X POST http://localhost:3000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{"jobId":"ai","jobTitle":"AI算法工程师","resumeText":"2年Python开发经验，熟悉基本的数据分析","candidateName":"李工"}'
# 期望：30 ≤ score ≤ 55
```
