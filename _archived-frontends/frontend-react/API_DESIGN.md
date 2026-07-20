# API Design

Base path: `/api`

## GET `/api/dashboard`

Returns user capability score, radar dimensions, skill rank, recommended jobs, and trend.

## GET `/api/ability-graph`

Returns graph nodes and edges.

```ts
type NodeCategory = "user" | "owned" | "gap" | "learning" | "required";
```

## GET `/api/job-matches`

Returns job matching list with match rate, matched skills, missing skills, and learning path.

## GET `/api/growth-path`

Returns skill learning tree, dependencies, and staged milestones.

## GET `/api/enterprise-analytics`

Returns skill demand heatmap, talent gap statistics, and industry trend series.

## POST `/api/ai-match-analysis`

Body:

```json
{
  "resumeText": "...",
  "targetJobId": "job-1"
}
```

Response:

```json
{
  "matchRate": 88,
  "matchedSkills": ["SQL", "Python"],
  "missingSkills": ["RAG"],
  "learningPath": ["Build one RAG evaluation project"]
}
```
