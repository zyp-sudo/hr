package com.xh202621;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public class KnowledgeService {
    private static final Map<String, String> CORE_CHINESE_ROLES = Map.ofEntries(
            Map.entry("java-backend-engineer", "Java 后端工程师"),
            Map.entry("ai-algorithm-engineer", "AI 算法工程师"),
            Map.entry("backend-engineer", "后端工程师"),
            Map.entry("frontend-engineer", "前端工程师"),
            Map.entry("data-engineer", "数据工程师"),
            Map.entry("cloud-sre-engineer", "云原生 SRE 工程师"),
            Map.entry("product-manager", "产品经理"),
            Map.entry("operations-specialist", "运营"),
            Map.entry("designer", "设计师"),
            Map.entry("testing-engineer", "测试工程师"),
            Map.entry("security-engineer", "安全工程师"),
            Map.entry("mobile-engineer", "移动端工程师")
    );

    private final Path dataDir;
    private final List<Map<String, String>> jobRows;
    private final List<Map<String, String>> skillRows;
    private final List<Map<String, String>> evolutionRows;
    private final List<Map<String, String>> sourceRows;
    private final List<Map<String, String>> discoveryRows;
    private final List<Map<String, String>> resumeRows;
    private final Map<String, List<String>> aliasesBySkill;

    // Cached CSV data — loaded once on startup, never re-read
    private final List<Map<String, String>> kgNodes;
    private final List<Map<String, String>> kgEdges;
    private final List<Map<String, String>> skillTrends;
    private final List<Map<String, String>> roleAliases;
    private final List<Map<String, String>> graphVersions;
    private final List<Map<String, String>> unifiedJobs;
    private final List<Map<String, String>> unifiedJobSkills;
    private final List<Map<String, String>> qualityReport;
    private final List<Map<String, String>> sourceRegistry;
    private final List<Map<String, String>> collectedJobs;
    private final List<Map<String, String>> collectedSources;

    // Pre-computed derived data
    private final List<Map<String, Object>> cachedJobList;
    private final Map<String, Object> cachedGraph;
    private final Map<String, Object> cachedSamples;
    private final Map<String, Object> cachedEtlSummary;

    public KnowledgeService() {
        this(Path.of("data"));
    }

    public KnowledgeService(Path dataDir) {
        this.dataDir = dataDir;
        this.jobRows = CsvTable.read(dataDir.resolve("jobs.csv"));
        this.skillRows = CsvTable.read(dataDir.resolve("job_skills.csv"));
        this.evolutionRows = CsvTable.read(dataDir.resolve("evolution.csv"));
        this.sourceRows = CsvTable.read(dataDir.resolve("data_sources.csv"));
        this.discoveryRows = CsvTable.read(dataDir.resolve("discoveries.csv"));
        this.resumeRows = CsvTable.read(dataDir.resolve("resume_samples.csv"));
        this.aliasesBySkill = loadAliases();

        // Pre-load all CSV files that were previously read on every request
        this.kgNodes = CsvTable.read(dataDir.resolve("kg/nodes.csv"));
        this.kgEdges = CsvTable.read(dataDir.resolve("kg/edges.csv"));
        this.skillTrends = CsvTable.read(dataDir.resolve("kg/skill_trends.csv"));
        this.roleAliases = CsvTable.read(dataDir.resolve("kg/role_aliases.csv"));
        this.graphVersions = CsvTable.read(dataDir.resolve("kg/graph_versions.csv"));
        this.unifiedJobs = CsvTable.read(dataDir.resolve("etl/unified_jobs.csv"));
        this.unifiedJobSkills = CsvTable.read(dataDir.resolve("etl/unified_job_skills.csv"));
        this.qualityReport = CsvTable.read(dataDir.resolve("etl/data_quality_report.csv"));
        this.sourceRegistry = CsvTable.read(dataDir.resolve("source_registry.csv"));
        this.collectedJobs = CsvTable.read(dataDir.resolve("collected_jobs.csv"));
        this.collectedSources = CsvTable.read(dataDir.resolve("collected_sources.csv"));

        // Pre-compute expensive derived data once
        this.cachedJobList = buildJobList();
        this.cachedGraph = buildGraph();
        this.cachedSamples = buildSamples();
        this.cachedEtlSummary = buildEtlSummary();
    }

    public List<Map<String, Object>> jobs() {
        return cachedJobList;
    }

    private List<Map<String, Object>> buildJobList() {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, String> row : jobRows) {
            String jobId = row.get("id");
            result.add(map(
                    "id", jobId,
                    "name", row.get("name"),
                    "type", row.get("type"),
                    "description", row.get("description"),
                    "sourceCount", number(row.get("sourceCount"), 0),
                    "skills", skillsForJob(jobId).stream().map(skill -> skill.get("skill")).toList()
            ));
        }
        return result;
    }

    public Map<String, Object> graph() {
        return cachedGraph;
    }

    private Map<String, Object> buildGraph() {
        List<Map<String, Object>> nodes = new ArrayList<>();
        List<Map<String, Object>> edges = new ArrayList<>();
        Set<String> seenNodes = new LinkedHashSet<>();
        Set<String> seenEdges = new LinkedHashSet<>();

        // 1. Build job → skill → capability edges from seed data (always)
        for (Map<String, String> job : jobRows) {
            addNode(nodes, seenNodes, "job-" + job.get("id"), job.get("name"), "job");
        }
        for (Map<String, String> skill : skillRows) {
            String skillId = id("skill", skill.get("skill"));
            String dimensionId = id("cap", skill.get("dimension"));
            addNode(nodes, seenNodes, skillId, skill.get("skill"), "skill");
            addNode(nodes, seenNodes, dimensionId, skill.get("dimension"), "capability");
            addEdge(edges, seenEdges, "job-" + skill.get("jobId"), skillId,
                    bool(skill.get("required")) ? "requires" : "bonus");
            addEdge(edges, seenEdges, skillId, dimensionId, "belongs_to");
        }

        // 2. Merge capability hierarchy from KG data (capability → part_of → parent capability)
        if (!kgNodes.isEmpty()) {
            for (Map<String, String> row : kgNodes) {
                String type = row.getOrDefault("type", "");
                if ("capability".equals(type)) {
                    addNode(nodes, seenNodes, row.get("id"), row.get("label"), "capability");
                }
            }
        }
        if (!kgEdges.isEmpty()) {
            for (Map<String, String> row : kgEdges) {
                String type = row.getOrDefault("type", "");
                if ("part_of".equals(type)) {
                    String from = row.get("from");
                    String to = row.get("to");
                    if (from != null && !from.equals(to)) {
                        addEdge(edges, seenEdges, from, to, "part_of");
                    }
                }
            }
        }

        return map("nodes", nodes, "edges", edges);
    }

    public Map<String, Object> evolution(String jobId) {
        if (!skillTrends.isEmpty()) {
            String roleId = jobId;
            if (roleId == null || roleId.isBlank()) {
                roleId = "java-backend-engineer";
            }
            String requestedRoleId = canonicalRoleIdForRequest(roleId);
            if (!isCoreChineseRoleId(requestedRoleId)) {
                requestedRoleId = defaultChineseRoleId();
            }
            final String selectedRequestRoleId = requestedRoleId;
            List<Map<String, String>> selectedRows = new ArrayList<>(skillTrends.stream()
                    .filter(row -> selectedRequestRoleId.equals(canonicalRoleIdForTrend(row)))
                    .toList());
            if (selectedRows.isEmpty()) {
                roleId = defaultChineseRoleId();
                final String fallbackRoleId = roleId;
                selectedRows = new ArrayList<>(skillTrends.stream()
                        .filter(row -> fallbackRoleId.equals(canonicalRoleIdForTrend(row)))
                        .toList());
            } else {
                roleId = requestedRoleId;
            }
            final String selectedRoleId = roleId;
            List<Map<String, Object>> mergedRows = mergeTrendRows(selectedRows);
            mergedRows.sort((a, b) -> {
                int byPeriod = String.valueOf(b.getOrDefault("period", "")).compareTo(String.valueOf(a.getOrDefault("period", "")));
                if (byPeriod != 0) {
                    return byPeriod;
                }
                return Integer.compare(asInt(b.get("demand")), asInt(a.get("demand")));
            });
            final int maxDemand = mergedRows.stream()
                    .mapToInt(row -> asInt(row.get("demand")))
                    .max()
                    .orElse(0);
            List<Map<String, Object>> autoSeries = mergedRows.stream()
                    .limit(300)
                    .map(row -> {
                        int demand = asInt(row.get("demand"));
                        int heatIndex = maxDemand == 0 ? 0 : Math.max(4, Math.round(demand * 100f / maxDemand));
                        return map(
                            "period", row.get("period"),
                            "skill", row.get("skill"),
                            "dimension", row.get("dimension"),
                            "demand", demand,
                            "sourceCount", asInt(row.get("sourceCount")),
                            "heatIndex", heatIndex
                        );
                    })
                    .toList();
            String title = canonicalRoleLabel(selectedRoleId);
            return map(
                    "jobId", selectedRoleId,
                    "title", title + " 能力演化",
                    "summary", "已按中文规范岗位合并同义来源；需求为合并后的原始证据次数，热度按当前岗位组最大需求归一。",
                    "maxDemand", maxDemand,
                    "seriesCount", mergedRows.size(),
                    "rawSeriesCount", selectedRows.size(),
                    "mergedAliasCount", uniqueRoleCount(selectedRows),
                    "roleCount", trendRoleCount(),
                    "roleOptions", trendRoleOptions(selectedRoleId),
                    "series", autoSeries
            );
        }

        List<Map<String, Object>> series = new ArrayList<>();
        for (Map<String, String> row : evolutionRows) {
            if (row.get("jobId").equals(jobId)) {
                series.add(map(
                        "period", row.get("period"),
                        "skill", row.get("skill"),
                        "demand", number(row.get("demand"), 0)
                ));
            }
        }
        if (series.isEmpty() && !jobRows.isEmpty()) {
            return evolution(jobRows.get(0).get("id"));
        }
        return map(
                "jobId", jobId,
                "title", jobName(jobId) + "能力演化",
                "summary", "基于 data/evolution.csv 的时间序列样本 当前用于展示岗位技能需求变化趋势。",
                "roleOptions", jobRows.stream()
                        .map(row -> map(
                                "roleId", row.get("id"),
                                "role", row.get("name"),
                                "recordCount", 0,
                                "selected", row.get("id").equals(jobId)
                        ))
                        .toList(),
                "series", series
        );
    }

    private int trendRoleCount() {
        Set<String> roleIds = new LinkedHashSet<>();
        for (Map<String, String> row : skillTrends) {
            String roleId = canonicalRoleIdForTrend(row);
            if (isCoreChineseRoleId(roleId)) {
                roleIds.add(roleId);
            }
        }
        return roleIds.size();
    }

    private List<Map<String, Object>> trendRoleOptions(String selectedRoleId) {
        Map<String, Integer> counts = new LinkedHashMap<>();
        Map<String, String> labels = new LinkedHashMap<>();
        for (Map<String, String> row : skillTrends) {
            String roleId = canonicalRoleIdForTrend(row);
            if (!isCoreChineseRoleId(roleId)) {
                continue;
            }
            counts.merge(roleId, 1, Integer::sum);
            labels.putIfAbsent(roleId, CORE_CHINESE_ROLES.get(roleId));
        }
        List<String> ordered = counts.entrySet().stream()
                .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                .limit(36)
                .map(Map.Entry::getKey)
                .collect(java.util.stream.Collectors.toCollection(ArrayList::new));
        if (selectedRoleId != null && counts.containsKey(selectedRoleId) && !ordered.contains(selectedRoleId)) {
            ordered.add(0, selectedRoleId);
        }
        return ordered.stream()
                .map(roleId -> map(
                        "roleId", roleId,
                        "role", labels.getOrDefault(roleId, CORE_CHINESE_ROLES.getOrDefault(roleId, roleId)),
                        "recordCount", counts.getOrDefault(roleId, 0),
                        "selected", roleId.equals(selectedRoleId)
                ))
                .toList();
    }

    private List<Map<String, Object>> mergeTrendRows(List<Map<String, String>> rows) {
        Map<String, Map<String, Object>> merged = new LinkedHashMap<>();
        for (Map<String, String> row : rows) {
            String period = row.getOrDefault("period", "");
            String skill = row.getOrDefault("skill", "");
            String dimension = row.getOrDefault("dimension", "未分类");
            String key = period + "\t" + skill + "\t" + dimension;
            Map<String, Object> item = merged.computeIfAbsent(key, ignored -> map(
                    "period", period,
                    "skill", skill,
                    "dimension", dimension,
                    "demand", 0,
                    "sourceCount", 0
            ));
            item.put("demand", asInt(item.get("demand")) + number(row.get("demand"), 0));
            item.put("sourceCount", asInt(item.get("sourceCount")) + number(row.get("source_count"), 0));
        }
        return new ArrayList<>(merged.values());
    }

    private List<Map<String, Object>> aliasSamplesFor(List<Map<String, String>> rows) {
        Map<String, Integer> counts = new LinkedHashMap<>();
        Map<String, String> roleIds = new LinkedHashMap<>();
        for (Map<String, String> row : rows) {
            String role = row.getOrDefault("role", "");
            if (role.isBlank()) {
                continue;
            }
            counts.merge(role, 1, Integer::sum);
            roleIds.putIfAbsent(role, row.getOrDefault("role_id", ""));
        }
        return counts.entrySet().stream()
                .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                .limit(12)
                .map(entry -> map(
                        "role", entry.getKey(),
                        "roleId", roleIds.getOrDefault(entry.getKey(), ""),
                        "recordCount", entry.getValue()
                ))
                .toList();
    }

    private int uniqueRoleCount(List<Map<String, String>> rows) {
        Set<String> roles = new LinkedHashSet<>();
        for (Map<String, String> row : rows) {
            String role = row.get("role");
            if (role != null && !role.isBlank()) {
                roles.add(role);
            }
        }
        return roles.size();
    }

    private String canonicalRoleIdForRequest(String roleId) {
        if (roleId == null || roleId.isBlank()) {
            return "java-backend-engineer";
        }
        for (Map<String, String> row : skillTrends) {
            if (roleId.equals(row.get("role_id"))) {
                return canonicalRoleIdForTrend(row);
            }
        }
        return roleId;
    }

    private String canonicalRoleIdForTrend(Map<String, String> row) {
        Map<String, String> alias = roleAliasByName(row.get("role"));
        String canonicalId = alias.get("canonical_role_id");
        if (canonicalId != null && !canonicalId.isBlank()) {
            return canonicalId;
        }
        return row.getOrDefault("role_id", "");
    }

    private String canonicalRoleLabel(String canonicalRoleId) {
        if (CORE_CHINESE_ROLES.containsKey(canonicalRoleId)) {
            return CORE_CHINESE_ROLES.get(canonicalRoleId);
        }
        for (Map<String, String> row : roleAliases) {
            if (canonicalRoleId.equals(row.get("canonical_role_id"))) {
                String label = row.get("canonical_role");
                if (label != null && !label.isBlank()) {
                    return label;
                }
            }
        }
        for (Map<String, String> row : skillTrends) {
            if (canonicalRoleId.equals(row.get("role_id"))) {
                return row.getOrDefault("role", canonicalRoleId);
            }
        }
        return canonicalRoleId;
    }

    private boolean isCoreChineseRoleId(String roleId) {
        return roleId != null && CORE_CHINESE_ROLES.containsKey(roleId);
    }

    private String defaultChineseRoleId() {
        return "java-backend-engineer";
    }

    private Map<String, String> roleAliasByName(String role) {
        if (role == null || role.isBlank()) {
            return Map.of();
        }
        for (Map<String, String> row : roleAliases) {
            if (role.equals(row.get("alias"))) {
                return row;
            }
        }
        return Map.of();
    }

    public Map<String, Object> dataQuality() {
        Map<String, Integer> levelCounts = new LinkedHashMap<>();
        levelCounts.put("A", 0);
        levelCounts.put("B", 0);
        levelCounts.put("C", 0);
        levelCounts.put("D", 0);
        Map<String, Integer> flagCounts = new LinkedHashMap<>();
        double scoreTotal = 0;
        for (Map<String, String> row : unifiedJobs) {
            String level = row.getOrDefault("quality_level", "");
            if (levelCounts.containsKey(level)) {
                levelCounts.put(level, levelCounts.get(level) + 1);
            }
            scoreTotal += decimal(row.getOrDefault("quality_score", "0"), 0);
            for (String flag : split(row.get("quality_flags"))) {
                flagCounts.put(flag, flagCounts.getOrDefault(flag, 0) + 1);
            }
        }
        int totalRecords = unifiedJobs.size();
        double avgScore = totalRecords == 0 ? 0 : round2(scoreTotal / totalRecords);
        int acceptedRecords = levelCounts.get("A") + levelCounts.get("B");
        int blockedRecords = levelCounts.get("C") + levelCounts.get("D");

        Map<String, Map<String, String>> registryById = new LinkedHashMap<>();
        for (Map<String, String> row : sourceRegistry) {
            registryById.put(row.getOrDefault("sourceId", ""), row);
        }

        List<Map<String, Object>> sourceQuality = qualityReport.stream()
                .map(row -> {
                    int records = number(row.get("records"), 0);
                    int issues = qualityIssueCount(row);
                    double issueRate = records == 0 ? 0 : round2(issues * 100.0 / records);
                    double score = decimal(row.get("avg_quality_score"), 0);
                    Map<String, String> registry = registryById.getOrDefault(row.get("source_id"), Map.of());
                    String gate = qualityGate(score, issueRate, number(row.get("level_c"), 0) + number(row.get("level_d"), 0));
                    return map(
                            "id", row.get("source_id"),
                            "name", row.get("source_name"),
                            "type", row.get("source_type"),
                            "count", records,
                            "score", score,
                            "avgQualityScore", score,
                            "levelA", number(row.get("level_a"), 0),
                            "levelB", number(row.get("level_b"), 0),
                            "levelC", number(row.get("level_c"), 0),
                            "levelD", number(row.get("level_d"), 0),
                            "issueCount", issues,
                            "issueRate", issueRate,
                            "majorIssue", majorQualityIssue(row),
                            "gate", gate,
                            "trustWeight", decimal(registry.getOrDefault("trustWeight", "0"), 0),
                            "status", registry.getOrDefault("status", ""),
                            "note", gate + " / " + majorQualityIssue(row)
                    );
                })
                .sorted((a, b) -> {
                    int byGate = String.valueOf(a.get("gate")).compareTo(String.valueOf(b.get("gate")));
                    if (byGate != 0) {
                        return byGate;
                    }
                    return Double.compare(asDouble(b.get("issueRate")), asDouble(a.get("issueRate")));
                })
                .toList();

        List<Map<String, Object>> issueBreakdown = List.of(
                qualityIssue("short_requirement", "岗位要求过短", flagCounts.getOrDefault("short_requirement", 0), "影响技能抽取和能力评分", "补充/清洗 requirement 字段"),
                qualityIssue("short_responsibility", "岗位职责过短", flagCounts.getOrDefault("short_responsibility", 0), "影响岗位画像和职责聚类", "补充 responsibility 或回源抓取详情页"),
                qualityIssue("no_skill_hit", "未识别技能", flagCounts.getOrDefault("no_skill_hit", 0), "影响图谱边和匹配结果", "扩展技能词典并进入人工复核"),
                qualityIssue("duplicate_content", "重复内容", flagCounts.getOrDefault("duplicate_content", 0), "影响趋势热度和来源权重", "按 content_hash 去重后再入图")
        );

        List<Map<String, Object>> problemSamples = unifiedJobs.stream()
                .filter(row -> !row.getOrDefault("quality_flags", "").isBlank())
                .sorted((a, b) -> Integer.compare(number(a.get("quality_score"), 0), number(b.get("quality_score"), 0)))
                .limit(12)
                .map(row -> map(
                        "title", row.get("job_title"),
                        "sourceName", row.get("source_name"),
                        "qualityScore", number(row.get("quality_score"), 0),
                        "qualityLevel", row.get("quality_level"),
                        "qualityFlags", split(row.get("quality_flags")),
                        "skillCount", number(row.get("skill_count"), 0),
                        "sourceUrl", row.get("source_url")
                ))
                .toList();

        return map(
                "totalRecords", totalRecords,
                "avgQualityScore", avgScore,
                "acceptedRecords", acceptedRecords,
                "blockedRecords", blockedRecords,
                "levelCounts", levelCounts,
                "sources", sourceQuality,
                "sourceQuality", sourceQuality,
                "issueBreakdown", issueBreakdown,
                "problemSamples", problemSamples,
                "linkedApplications", List.of(
                        map("name", "统一结果", "count", unifiedJobs.size(), "gate", "A/B 级进入统一 Schema", "impact", "低质记录不参与核心指标口径"),
                        map("name", "能力图谱", "count", kgNodes.size() + kgEdges.size(), "gate", "无技能命中记录不生成 requires 边", "impact", "减少虚假技能关系和重复节点"),
                        map("name", "动态演化", "count", skillTrends.size(), "gate", "按质量等级和去重结果聚合趋势", "impact", "避免重复 JD 抬高热度"),
                        map("name", "人岗匹配", "count", unifiedJobSkills.size(), "gate", "技能证据和质量分共同进入匹配依据", "impact", "低质量岗位降低推荐可信度")
                ),
                "rules", List.of(
                        "A/B 级记录进入主流程，C/D 级进入问题样本和复核池。",
                        "缺少技能命中的记录不生成图谱 requires 关系。",
                        "重复 content_hash 只保留一份用于趋势统计。",
                        "来源质量按均分、问题负载、C/D 占比联合评估，不再只看静态信任分。",
                        "数据源问题会联动影响统一结果、能力图谱、动态演化和人岗匹配。"
                )
        );
    }

    private Map<String, Object> qualityIssue(String key, String label, int count, String impact, String action) {
        return map("key", key, "label", label, "count", count, "impact", impact, "action", action);
    }

    public Map<String, Object> discoverEmergingRole() {
        Map<String, String> row = discoveryRows.isEmpty() ? Map.of() : discoveryRows.get(0);
        return discovery(row);
    }

    public Map<String, Object> etlSummary() {
        return cachedEtlSummary;
    }

    private Map<String, Object> buildEtlSummary() {
        Set<String> sourceTypes = new LinkedHashSet<>();
        Set<String> activeSources = new LinkedHashSet<>();
        Map<String, Integer> levelCounts = new LinkedHashMap<>();
        levelCounts.put("A", 0);
        levelCounts.put("B", 0);
        levelCounts.put("C", 0);
        levelCounts.put("D", 0);
        double scoreTotal = 0;

        for (Map<String, String> row : sourceRegistry) {
            String type = row.getOrDefault("sourceType", "");
            if (!type.isBlank()) {
                sourceTypes.add(type);
            }
        }
        for (Map<String, String> row : unifiedJobs) {
            String sourceId = row.getOrDefault("source_id", "");
            if (!sourceId.isBlank()) {
                activeSources.add(sourceId);
            }
            String level = row.getOrDefault("quality_level", "");
            if (levelCounts.containsKey(level)) {
                levelCounts.put(level, levelCounts.get(level) + 1);
            }
            scoreTotal += decimal(row.getOrDefault("quality_score", "0"), 0);
        }

        List<Map<String, Object>> sources = sourceRegistry.stream()
                .map(row -> map(
                        "sourceId", row.get("sourceId"),
                        "sourceName", row.get("sourceName"),
                        "sourceType", row.get("sourceType"),
                        "status", row.get("status"),
                        "baseUrl", row.get("baseUrl"),
                        "collectionMethod", row.get("collectionMethod"),
                        "trustWeight", decimal(row.getOrDefault("trustWeight", "0"), 0),
                        "licenseNote", row.get("licenseNote")
                ))
                .toList();
        List<Map<String, Object>> quality = qualityReport.stream()
                .map(row -> map(
                        "sourceId", row.get("source_id"),
                        "sourceName", row.get("source_name"),
                        "sourceType", row.get("source_type"),
                        "records", number(row.get("records"), 0),
                        "avgQualityScore", decimal(row.get("avg_quality_score"), 0),
                        "levelA", number(row.get("level_a"), 0),
                        "levelB", number(row.get("level_b"), 0),
                        "levelC", number(row.get("level_c"), 0),
                        "levelD", number(row.get("level_d"), 0),
                        "missingTitle", number(row.get("missing_title"), 0),
                        "missingSourceUrl", number(row.get("missing_source_url"), 0),
                        "missingCollectedAt", number(row.get("missing_collected_at"), 0),
                        "missingPublishedAt", number(row.get("missing_published_at"), 0),
                        "missingCity", number(row.get("missing_city"), 0),
                        "missingCompany", number(row.get("missing_company"), 0),
                        "missingOriginRecordId", number(row.get("missing_origin_record_id"), 0),
                        "shortResponsibility", number(row.get("short_responsibility"), 0),
                        "shortRequirement", number(row.get("short_requirement"), 0),
                        "noSkillHit", number(row.get("no_skill_hit"), 0),
                        "duplicateContent", number(row.get("duplicate_content"), 0),
                        "unknownSource", number(row.get("unknown_source"), 0),
                        "issueCount", qualityIssueCount(row),
                        "majorIssue", majorQualityIssue(row)
                ))
                .toList();
        List<Map<String, Object>> samples = unifiedJobs.stream()
                .limit(100)
                .map(row -> map(
                        "recordId", row.get("record_id"),
                        "sourceId", row.get("source_id"),
                        "sourceType", row.get("source_type"),
                        "sourceName", row.get("source_name"),
                        "originRecordId", row.get("origin_record_id"),
                        "company", row.get("company"),
                        "department", row.get("department"),
                        "product", row.get("product"),
                        "category", row.get("category"),
                        "roleId", row.get("role_id"),
                        "roleName", row.get("role_name"),
                        "title", row.get("job_title"),
                        "jobType", row.get("job_type"),
                        "workYears", row.get("work_years"),
                        "normalizedCategory", row.get("normalized_category"),
                        "city", row.get("city"),
                        "publishedAt", row.get("published_at"),
                        "collectedAt", row.get("collected_at"),
                        "responsibility", row.get("responsibility"),
                        "requirement", row.get("requirement"),
                        "rawText", row.get("raw_text"),
                        "skills", split(row.get("normalized_skills")),
                        "skillCount", number(row.get("skill_count"), 0),
                        "skillEvidence", row.get("skill_evidence"),
                        "capabilityDimensions", split(row.get("capability_dimensions")),
                        "capabilityScores", row.get("capability_scores"),
                        "estimatedApplicationSuccessProbability", decimal(row.get("estimated_application_success_probability"), 0),
                        "relativeAbilityScore", decimal(row.get("relative_ability_score"), 0),
                        "scoringBasis", row.get("scoring_basis"),
                        "qualityScore", number(row.get("quality_score"), 0),
                        "qualityLevel", row.get("quality_level"),
                        "qualityFlags", split(row.get("quality_flags")),
                        "sourceUrl", row.get("source_url"),
                        "contentHash", row.get("content_hash")
                ))
                .toList();

        return map(
                "unifiedJobRecords", unifiedJobs.size(),
                "unifiedSkillRecords", unifiedJobSkills.size(),
                "registeredSources", sourceRegistry.size(),
                "registeredSourceTypes", sourceTypes.stream().toList(),
                "activeSources", activeSources.stream().toList(),
                "avgQualityScore", unifiedJobs.isEmpty() ? 0 : Math.round(scoreTotal * 100.0 / unifiedJobs.size()) / 100.0,
                "levelCounts", levelCounts,
                "sourceRegistry", sources,
                "qualityReport", quality,
                "samples", samples,
                "unifiedSchema", List.of(
                        "record_id", "origin_record_id", "source_id", "source_type", "source_name", "source_url",
                        "collected_at", "published_at", "country", "province", "city", "company", "department",
                        "product", "category", "normalized_category", "job_title", "job_type", "work_years", "responsibility",
                        "requirement", "raw_text", "normalized_skills", "skill_count", "quality_score",
                        "quality_level", "quality_flags", "content_hash"
                ),
                "qualityRules", List.of(
                        "Base score is 100.",
                        "Missing title/source URL/collected time/published time/city deducts points.",
                        "Short responsibility or requirement text deducts points.",
                        "No extracted skill deducts points.",
                        "Duplicate content hash deducts points.",
                        "A >= 85, B = 70-84, C = 55-69, D < 55."
                )
        );
    }

    public Map<String, Object> kgSummary() {
        Map<String, Integer> nodeTypeCounts = new LinkedHashMap<>();
        for (Map<String, String> row : kgNodes) {
            String type = row.getOrDefault("type", "");
            nodeTypeCounts.put(type, nodeTypeCounts.getOrDefault(type, 0) + 1);
        }
        Map<String, Integer> edgeTypeCounts = new LinkedHashMap<>();
        for (Map<String, String> row : kgEdges) {
            String type = row.getOrDefault("type", "");
            edgeTypeCounts.put(type, edgeTypeCounts.getOrDefault(type, 0) + 1);
        }

        List<Map<String, Object>> topNodes = kgNodes.stream()
                .sorted((a, b) -> number(b.get("count"), 0) - number(a.get("count"), 0))
                .limit(30)
                .map(row -> map(
                        "id", row.get("id"),
                        "label", row.get("label"),
                        "type", row.get("type"),
                        "count", number(row.get("count"), 0),
                        "firstSeen", row.get("first_seen"),
                        "lastSeen", row.get("last_seen")
                ))
                .toList();
        List<Map<String, Object>> topEdges = kgEdges.stream()
                .sorted((a, b) -> number(b.get("weight"), 0) - number(a.get("weight"), 0))
                .limit(30)
                .map(row -> map(
                        "from", row.get("from"),
                        "to", row.get("to"),
                        "type", row.get("type"),
                        "weight", number(row.get("weight"), 0),
                        "confidence", decimal(row.get("confidence"), 0),
                        "firstSeen", row.get("first_seen"),
                        "lastSeen", row.get("last_seen")
                ))
                .toList();
        List<Map<String, Object>> aliasSamples = roleAliases.stream()
                .limit(40)
                .map(row -> map(
                        "alias", row.get("alias"),
                        "canonicalRoleId", row.get("canonical_role_id"),
                        "canonicalRole", row.get("canonical_role"),
                        "evidenceCount", number(row.get("evidence_count"), 0)
                ))
                .toList();
        List<Map<String, Object>> trendSamples = skillTrends.stream()
                .limit(80)
                .map(row -> map(
                        "period", row.get("period"),
                        "roleId", row.get("role_id"),
                        "role", row.get("role"),
                        "skill", row.get("skill"),
                        "dimension", row.get("dimension"),
                        "demand", number(row.get("demand"), 0),
                        "sourceCount", number(row.get("source_count"), 0)
                ))
                .toList();
        List<Map<String, Object>> versionSamples = graphVersions.stream()
                .map(row -> map(
                        "versionId", row.get("version_id"),
                        "period", row.get("period"),
                        "nodeCount", number(row.get("node_count"), 0),
                        "edgeCount", number(row.get("edge_count"), 0),
                        "jobCount", number(row.get("job_count"), 0),
                        "skillMentions", number(row.get("skill_mentions"), 0)
                ))
                .toList();

        return map(
                "nodes", kgNodes.size(),
                "edges", kgEdges.size(),
                "roleAliases", roleAliases.size(),
                "skillTrends", skillTrends.size(),
                "versions", graphVersions.size(),
                "nodeTypeCounts", nodeTypeCounts,
                "edgeTypeCounts", edgeTypeCounts,
                "topNodes", topNodes,
                "topEdges", topEdges,
                "aliasSamples", aliasSamples,
                "trendSamples", trendSamples,
                "versionSamples", versionSamples,
                "outputs", List.of(
                        "data/kg/nodes.csv",
                        "data/kg/edges.csv",
                        "data/kg/role_aliases.csv",
                        "data/kg/skill_trends.csv",
                        "data/kg/graph_versions.csv"
                )
        );
    }

    public Map<String, Object> samples() {
        return cachedSamples;
    }

    private Map<String, Object> buildSamples() {
        return map(
                "dataDir", dataDir.toString(),
                "jobs", cachedJobList,
                "skills", skillRows.stream().map(this::skillView).toList(),
                "resumes", resumeRows.stream().map(row -> map(
                        "id", row.get("id"),
                        "name", row.get("name"),
                        "targetJobId", row.get("targetJobId"),
                        "text", row.get("text")
                )).toList(),
                "discoveries", discoveryRows.stream().map(this::discovery).toList()
        );
    }

    public Map<String, Object> architectureSummary() {
        Path collectedJobsPath = dataDir.resolve("collected_jobs.csv");
        Path warehouseManifest = dataDir.resolve("warehouse/architecture_manifest.json");
        Path mysqlSchema = dataDir.resolve("warehouse/mysql_schema.sql");
        Path esNdjson = dataDir.resolve("warehouse/elasticsearch_jobs.ndjson");
        Path chromaDocs = dataDir.resolve("warehouse/chroma_documents.jsonl");
        Path neo4jCypher = dataDir.resolve("warehouse/neo4j_import.cypher");
        Path deepseekOutput = dataDir.resolve("ai/deepseek_extractions.jsonl");
        Path deepseekManifest = dataDir.resolve("ai/deepseek_manifest.json");
        Path resumeOutput = dataDir.resolve("resumes/parsed_resumes.jsonl");
        Path resumeManifest = dataDir.resolve("resumes/resume_parse_manifest.json");
        Path pipelineManifest = dataDir.resolve("pipeline_manifest.json");

        return map(
                "status", "mysql_neo4j_runtime",
                "dataDir", dataDir.toString(),
                "modules", List.of(
                        map(
                                "name", "数据采集",
                                "target", "Scrapy + Playwright",
                                "current", "多源公开招聘适配器 + checkpoint CSV",
                                "status", Files.exists(collectedJobsPath) ? "ready" : "missing",
                                "records", collectedJobs.size(),
                                "outputs", List.of("data/collected_jobs.csv", "data/china_jobs.csv", "data/foreign_jobs.csv")
                        ),
                        map(
                                "name", "ETL 统一 Schema",
                                "target", "Pandas 清洗 + 质量评分",
                                "current", "scripts/etl_unify_jobs.py",
                                "status", unifiedJobs.isEmpty() ? "missing" : "ready",
                                "records", unifiedJobs.size(),
                                "outputs", List.of("data/etl/unified_jobs.csv", "data/etl/unified_job_skills.csv", "data/etl/data_quality_report.csv")
                        ),
                        map(
                                "name", "数据存储",
                                "target", "MySQL + Elasticsearch",
                                "current", "MySQL 8.4 运行时查询（job_kg.job_postings）+ Elasticsearch 检索",
                                "status", Files.exists(mysqlSchema) ? "ready" : "missing",
                                "records", unifiedJobs.size(),
                                "outputs", List.of("MySQL job_kg.job_postings", "/api/jobs", "/api/real-jobs", "data/warehouse/mysql_schema.sql")
                        ),
                        map(
                                "name", "知识图谱",
                                "target", "Neo4j 5.x",
                                "current", "Neo4j 运行时 Cypher 查询（KgNode / KG_RELATION）",
                                "status", kgNodes.isEmpty() || kgEdges.isEmpty() ? "missing" : "ready",
                                "records", kgNodes.size() + kgEdges.size(),
                                "outputs", List.of("Neo4j KgNode", "Neo4j KG_RELATION", "/api/graph", "data/warehouse/neo4j_import.cypher")
                        ),
                        map(
                                "name", "动态演化",
                                "target", "时序图谱版本化查询 + 未来趋势预测",
                                "current", "MVP 仅按 period 聚合历史 skill_trends 和 graph_versions；未训练预测模型",
                                "status", skillTrends.isEmpty() ? "missing" : "partial",
                                "records", skillTrends.size(),
                                "outputs", List.of("data/kg/skill_trends.csv", "data/kg/graph_versions.csv")
                        ),
                        map(
                                "name", "RAG 检索",
                                "target", "LangChain + ChromaDB + DeepSeek API",
                                "current", "MVP 仅导出待向量化 JSONL；没有运行时 ChromaDB/LangChain 检索链",
                                "status", "partial",
                                "records", lineCount(chromaDocs),
                                "outputs", List.of("data/warehouse/chroma_documents.jsonl", "data/ai/deepseek_extractions.jsonl")
                        ),
                        map(
                                "name", "简历解析",
                                "target", "PaddleOCR / Tesseract + PDF/Word 本地解析 + 自定义 NER",
                                "current", "MVP 支持文本型 PDF/DOCX；扫描件依赖未随项目安装的本地 OCR 引擎",
                                "status", Files.exists(resumeOutput) ? "partial" : "missing",
                                "records", lineCount(resumeOutput),
                                "outputs", List.of("data/resumes/parsed_resumes.jsonl", "data/resumes/resume_parse_manifest.json")
                        ),
                        map(
                                "name", "Web/API",
                                "target", "FastAPI + Java 分析服务 + React + TypeScript",
                                "current", "正式前端为 talentmatch-frontend/；_archived-frontends/frontend/app.py、_archived-frontends/frontend-react/、_archived-frontends/frontend-vue/ 已归档",
                                "status", "ready",
                                "records", 0,
                                "outputs", List.of("/api/architecture-summary", "/api/etl-summary", "/api/kg-summary", "/?page=architecture")
                        )
                ),
                "artifacts", List.of(
                        artifact("Pipeline manifest", pipelineManifest),
                        artifact("Warehouse manifest", warehouseManifest),
                        artifact("MySQL schema", mysqlSchema),
                        artifact("Elasticsearch NDJSON", esNdjson),
                        artifact("Chroma documents", chromaDocs),
                        artifact("Neo4j import Cypher", neo4jCypher),
                        artifact("DeepSeek extraction manifest", deepseekManifest),
                        artifact("Local resume parser manifest", resumeManifest)
                ),
                "counts", map(
                        "unifiedJobs", unifiedJobs.size(),
                        "unifiedSkills", unifiedJobSkills.size(),
                        "kgNodes", kgNodes.size(),
                        "kgEdges", kgEdges.size(),
                        "skillTrends", skillTrends.size(),
                        "chromaDocuments", lineCount(chromaDocs),
                        "deepseekExtractions", lineCount(deepseekOutput),
                        "parsedResumes", lineCount(resumeOutput)
                ),
                "buildCommand", "python scripts\\build_full_pipeline.py"
        );
    }

    public Map<String, Object> realChinaJobs() {
        return realChinaJobs(0);
    }

    public Map<String, Object> aiInsight(String topic) {
        String normalizedTopic = normalizeAiTopic(topic);
        Map<String, Object> context = aiContext(normalizedTopic);
        return map(
                "topic", normalizedTopic,
                "title", aiTopicTitle(normalizedTopic),
                "context", context,
                "ai", MatchAiAnalyzer.fromEnvironment().analyze(context)
        );
    }

    private Map<String, Object> aiContext(String topic) {
        if ("quality".equals(topic)) {
            Map<String, Object> quality = dataQuality();
            return map(
                    "type", "data_quality_governance",
                    "language", "zh-CN",
                    "task", "分析数据质量治理状态，指出影响下游应用的主要风险和可执行优化动作。",
                    "metrics", map(
                            "totalRecords", quality.get("totalRecords"),
                            "avgQualityScore", quality.get("avgQualityScore"),
                            "acceptedRecords", quality.get("acceptedRecords"),
                            "blockedRecords", quality.get("blockedRecords")
                    ),
                    "levelCounts", quality.get("levelCounts"),
                    "sourceQuality", limitList(quality.get("sourceQuality"), 8),
                    "issueBreakdown", quality.get("issueBreakdown"),
                    "linkedApplications", quality.get("linkedApplications"),
                    "rules", quality.get("rules")
            );
        }
        if ("etl".equals(topic)) {
            Map<String, Object> etl = cachedEtlSummary;
            return map(
                    "type", "etl_schema_governance",
                    "language", "zh-CN",
                    "task", "分析 ETL 治理和统一 Schema 的落地质量，给出字段、来源、质量闸口和下游复用建议。",
                    "metrics", map(
                            "unifiedJobRecords", etl.get("unifiedJobRecords"),
                            "unifiedSkillRecords", etl.get("unifiedSkillRecords"),
                            "registeredSources", etl.get("registeredSources"),
                            "registeredSourceTypes", etl.get("registeredSourceTypes"),
                            "activeSources", etl.get("activeSources"),
                            "avgQualityScore", etl.get("avgQualityScore"),
                            "levelCounts", etl.get("levelCounts")
                    ),
                    "sourceRegistry", limitList(etl.get("sourceRegistry"), 10),
                    "qualityReport", limitList(etl.get("qualityReport"), 8),
                    "schemaFields", etl.get("unifiedSchema"),
                    "qualityRules", etl.get("qualityRules")
            );
        }
        if ("real_jobs".equals(topic)) {
            Map<String, Object> realJobs = realChinaJobs(1);
            return map(
                    "type", "collected_job_monitoring",
                    "language", "zh-CN",
                    "task", "分析采集岗位数据的覆盖度、来源贡献、热度分布和可用于后续建模的优化动作。",
                    "metrics", map(
                            "recordCount", realJobs.get("recordCount"),
                            "sourceCount", limitList(realJobs.get("sources"), 100).size(),
                            "returnedSampleCount", realJobs.get("returnedCount")
                    ),
                    "sources", realJobs.get("sources"),
                    "topSkills", limitList(realJobs.get("skillStats"), 12),
                    "topCities", limitList(realJobs.get("cityStats"), 12),
                    "topCategories", limitList(realJobs.get("categoryStats"), 12),
                    "topBusinessGroups", limitList(realJobs.get("bgStats"), 12),
                    "workYearDistribution", realJobs.get("workYearStats")
            );
        }
        if ("evolution".equals(topic)) {
            Map<String, Object> evolution = evolution(defaultChineseRoleId());
            return map(
                    "type", "capability_evolution",
                    "language", "zh-CN",
                    "task", "分析能力趋势演化是否可信，指出高热技能、趋势口径和岗位组覆盖的优化方向。",
                    "metrics", map(
                            "selectedRole", evolution.get("jobName"),
                            "seriesCount", evolution.get("seriesCount"),
                            "rawSeriesCount", evolution.get("rawSeriesCount"),
                            "mergedAliasCount", evolution.get("mergedAliasCount"),
                            "maxDemand", evolution.get("maxDemand"),
                            "availableRoles", evolution.get("roleCount"),
                            "versionCount", graphVersions.size()
                    ),
                    "roleOptions", limitList(evolution.get("roleOptions"), 12),
                    "latestTrendSample", limitList(evolution.get("series"), 12)
            );
        }

        Map<String, Object> etl = cachedEtlSummary;
        return map(
                "type", "platform_overview",
                "language", "zh-CN",
                "task", "从平台总览角度分析当前数据资产规模、图谱资产、质量和可落地应用，给出最重要的优化动作。",
                "metrics", map(
                        "collectedJobs", collectedJobs.size(),
                        "unifiedJobs", unifiedJobs.size(),
                        "unifiedSkillEvidence", unifiedJobSkills.size(),
                        "kgNodes", kgNodes.size(),
                        "kgEdges", kgEdges.size(),
                        "skillTrends", skillTrends.size(),
                        "graphVersions", graphVersions.size(),
                        "avgQualityScore", etl.get("avgQualityScore")
                ),
                "sourceTypes", etl.get("registeredSourceTypes"),
                "qualityLevelCounts", etl.get("levelCounts"),
                "topQualityIssues", limitList(etl.get("qualityReport"), 8)
        );
    }

    private static String normalizeAiTopic(String topic) {
        String value = topic == null ? "" : topic.trim().toLowerCase(Locale.ROOT);
        return switch (value) {
            case "quality", "data-quality", "data_quality" -> "quality";
            case "etl", "schema" -> "etl";
            case "real_jobs", "real-jobs", "collection", "collect" -> "real_jobs";
            case "evolution", "trend" -> "evolution";
            default -> "overview";
        };
    }

    private static String aiTopicTitle(String topic) {
        return switch (topic) {
            case "quality" -> "数据质量 AI 建议";
            case "etl" -> "ETL 与统一 Schema AI 建议";
            case "real_jobs" -> "采集岗位 AI 建议";
            case "evolution" -> "能力演化 AI 建议";
            default -> "项目总览 AI 建议";
        };
    }

    public Map<String, Object> realChinaJobs(int limit) {
        List<Map<String, Object>> jobs = new ArrayList<>();
        Map<String, Integer> skillCounts = new LinkedHashMap<>();
        Map<String, Integer> cityCounts = new LinkedHashMap<>();
        Map<String, Integer> categoryCounts = new LinkedHashMap<>();
        Map<String, Integer> bgCounts = new LinkedHashMap<>();
        Map<String, Integer> workYearCounts = new LinkedHashMap<>();

        for (Map<String, String> row : collectedJobs) {
            List<String> skills = split(row.get("skills"));
            for (String skill : skills) {
                skillCounts.put(skill, skillCounts.getOrDefault(skill, 0) + 1);
            }
            String city = row.getOrDefault("city", "");
            if (!city.isBlank()) {
                cityCounts.put(city, cityCounts.getOrDefault(city, 0) + 1);
            }
            countIfPresent(categoryCounts, row.get("category"));
            countIfPresent(bgCounts, row.get("bg"));
            countIfPresent(workYearCounts, row.get("workYears"));
            if (limit <= 0 || jobs.size() < limit) {
                jobs.add(map(
                        "source", row.get("source"),
                        "postId", row.get("postId"),
                        "title", row.get("title"),
                        "company", row.get("company"),
                        "bg", row.get("bg"),
                        "product", row.get("product"),
                        "category", row.get("category"),
                        "city", city,
                        "workYears", row.get("workYears"),
                        "lastUpdateTime", row.get("lastUpdateTime"),
                        "responsibility", row.get("responsibility"),
                        "requirement", row.get("requirement"),
                        "skills", skills,
                        "sourceUrl", row.get("sourceUrl"),
                        "fetchedAt", row.get("fetchedAt")
                ));
            }
        }

        return map(
                "jobs", jobs,
                "recordCount", collectedJobs.size(),
                "returnedCount", jobs.size(),
                "skillStats", topCounts(skillCounts, 20),
                "cityStats", topCounts(cityCounts, 20),
                "categoryStats", topCounts(categoryCounts, 20),
                "bgStats", topCounts(bgCounts, 20),
                "workYearStats", topCounts(workYearCounts, 20),
                "sources", collectedSources.stream().map(row -> map(
                        "source", row.get("source"),
                        "baseUrl", row.get("baseUrl"),
                        "licenseNote", row.get("licenseNote"),
                        "records", number(row.get("records"), 0),
                        "fetchedAt", row.get("fetchedAt")
                )).toList()
        );
    }

    public Map<String, Object> match(String targetJobId, String resumeText) {
        List<Map<String, String>> requiredRows = skillsForJob(targetJobId);
        int totalWeight = requiredRows.stream()
                .filter(row -> bool(row.get("required")))
                .mapToInt(row -> number(row.get("weight"), 1))
                .sum();
        int gainedWeight = 0;
        List<Map<String, Object>> matched = new ArrayList<>();
        List<Map<String, Object>> missing = new ArrayList<>();

        for (Map<String, String> row : requiredRows) {
            if (!bool(row.get("required"))) {
                continue;
            }
            String skill = row.get("skill");
            int weight = number(row.get("weight"), 1);
            List<String> hits = hits(skill, resumeText);
            Map<String, Object> item = map(
                    "skill", skill,
                    "dimension", row.get("dimension"),
                    "level", row.get("level"),
                    "weight", weight,
                    "sources", split(row.get("sources")),
                    "hits", hits
            );
            if (hits.isEmpty()) {
                missing.add(item);
            } else {
                matched.add(item);
                gainedWeight += weight;
            }
        }

        int score = totalWeight == 0 ? 0 : Math.round(gainedWeight * 100f / totalWeight);
        List<Map<String, Object>> dimensions = dimensionScores(requiredRows, matched);
        List<String> suggestions = suggestions(missing);
        Map<String, Object> learningDevelopment = learningDevelopment(targetJobId, score, matched, missing, dimensions);
        Map<String, Object> result = map(
                "targetJobId", targetJobId,
                "targetJobName", jobName(targetJobId),
                "score", score,
                "matchedSkills", matched.stream().map(row -> row.get("skill")).toList(),
                "missingSkills", missing.stream().map(row -> row.get("skill")).toList(),
                "matchedDetails", matched,
                "missingDetails", missing,
                "dimensions", dimensions,
                "suggestions", suggestions,
                "learningDevelopment", learningDevelopment
        );
        result.put("aiAnalysis", MatchAiAnalyzer.fromEnvironment().analyze(map(
                "type", "match",
                "targetJobId", targetJobId,
                "targetJobName", jobName(targetJobId),
                "resumeText", resumeText == null ? "" : resumeText,
                "ruleScore", score,
                "matchedDetails", matched,
                "missingDetails", missing,
                "dimensions", dimensions,
                "suggestions", suggestions,
                "learningDevelopment", learningDevelopment,
                "requiredSkills", requiredRows.stream().map(this::skillView).toList()
        )));
        return result;
    }

    private List<Map<String, String>> skillsForJob(String jobId) {
        return skillRows.stream()
                .filter(row -> row.get("jobId").equals(jobId))
                .toList();
    }

    private Map<String, Object> skillView(Map<String, String> row) {
        return map(
                "jobId", row.get("jobId"),
                "jobName", jobName(row.get("jobId")),
                "skill", row.get("skill"),
                "dimension", row.get("dimension"),
                "level", row.get("level"),
                "weight", number(row.get("weight"), 0),
                "required", bool(row.get("required")),
                "sources", split(row.get("sources")),
                "trend", row.get("trend")
        );
    }

    private Map<String, Object> discovery(Map<String, String> row) {
        return map(
                "jobId", row.getOrDefault("jobId", ""),
                "name", row.getOrDefault("name", ""),
                "confidence", decimal(row.getOrDefault("confidence", "0"), 0),
                "coreResponsibilities", split(row.getOrDefault("coreResponsibilities", "")),
                "requiredSkills", split(row.getOrDefault("requiredSkills", "")),
                "bonusSkills", split(row.getOrDefault("bonusSkills", "")),
                "evidence", split(row.getOrDefault("evidence", ""))
        );
    }

    private List<Map<String, Object>> dimensionScores(List<Map<String, String>> requiredRows, List<Map<String, Object>> matched) {
        Set<String> matchedSkillNames = matched.stream()
                .map(row -> String.valueOf(row.get("skill")))
                .collect(LinkedHashSet::new, LinkedHashSet::add, LinkedHashSet::addAll);
        Map<String, int[]> totals = new LinkedHashMap<>();
        for (Map<String, String> row : requiredRows) {
            if (!bool(row.get("required"))) continue;
            int[] score = totals.computeIfAbsent(row.get("dimension"), key -> new int[2]);
            int weight = number(row.get("weight"), 1);
            score[1] += weight;
            if (matchedSkillNames.contains(row.get("skill"))) {
                score[0] += weight;
            }
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map.Entry<String, int[]> entry : totals.entrySet()) {
            int got = entry.getValue()[0];
            int total = entry.getValue()[1];
            result.add(map("name", entry.getKey(), "score", total == 0 ? 0 : Math.round(got * 100f / total)));
        }
        return result;
    }

    private List<String> hits(String skill, String text) {
        if (skill == null || skill.isBlank() || text == null || text.isBlank()) {
            return List.of();
        }
        String normalizedText = normalizeText(text);
        List<String> candidates = new ArrayList<>();
        candidates.add(skill);
        candidates.addAll(aliasesBySkill.getOrDefault(skill, List.of()));
        List<String> hits = new ArrayList<>();
        for (String candidate : candidates) {
            if (candidate == null || candidate.isBlank()) {
                continue;
            }
            if (normalizedText.contains(normalizeText(candidate))) {
                hits.add(candidate);
            }
        }
        return hits;
    }

    private String normalizeText(String value) {
        if (value == null) {
            return "";
        }
        String normalized = value.toLowerCase(Locale.ROOT);
        normalized = normalized.replaceAll("<[^>]+>", " ");
        normalized = normalized.replace("+", " plus ");
        normalized = normalized.replaceAll("[\\s\\-_/\\\\.()]+", " ");
        normalized = normalized.replaceAll("[^a-z0-9\\u4e00-\\u9fff]+", " ");
        return normalized.replaceAll("\\s+", " ").trim();
    }

    private List<String> suggestions(List<Map<String, Object>> missing) {
        if (missing.isEmpty()) {
            return List.of("匹配度较高 建议补充项目证据 指标结果和业务场景说明。");
        }
        return missing.stream()
                .sorted(Comparator.comparing(row -> -number(String.valueOf(row.get("weight")), 0)))
                .map(row -> "补齐 " + row.get("skill") + "：完成一个可展示项目 并在简历中写清场景 方案 指标和数据来源。")
                .toList();
    }

    private Map<String, Object> learningDevelopment(
            String targetJobId,
            int score,
            List<Map<String, Object>> matched,
            List<Map<String, Object>> missing,
            List<Map<String, Object>> dimensions
    ) {
        if (matched.isEmpty() && missing.isEmpty() && dimensions.isEmpty()) {
            return learningFallback(targetJobId);
        }
        List<Map<String, Object>> prioritySkills = missing.stream()
                .sorted(Comparator.comparing(row -> -number(String.valueOf(row.get("weight")), 0)))
                .limit(6)
                .map(row -> map(
                        "skill", row.get("skill"),
                        "dimension", row.get("dimension"),
                        "level", row.get("level"),
                        "weight", row.get("weight"),
                        "why", "目标岗位必备能力中尚未在简历文本命中。",
                        "learningGoal", "完成一个能说明场景、方案、指标和复盘的项目证据。"
                ))
                .toList();
        List<Map<String, Object>> strengths = matched.stream()
                .sorted(Comparator.comparing(row -> -number(String.valueOf(row.get("weight")), 0)))
                .limit(5)
                .map(row -> map(
                        "skill", row.get("skill"),
                        "dimension", row.get("dimension"),
                        "evidence", row.get("hits"),
                        "nextStep", "把经历写成可验证的项目结果，例如规模、性能、成本、效率或业务指标。"
                ))
                .toList();
        List<Map<String, Object>> weakDimensions = dimensions.stream()
                .sorted(Comparator.comparing(row -> number(String.valueOf(row.get("score")), 0)))
                .limit(3)
                .map(row -> map(
                        "name", row.get("name"),
                        "score", row.get("score"),
                        "action", "围绕该能力维度补一个完整项目，并准备技术取舍和复盘说明。"
                ))
                .toList();
        List<String> missingSkillNames = prioritySkills.stream()
                .map(row -> String.valueOf(row.get("skill")))
                .toList();
        String mainSkillText = missingSkillNames.isEmpty() ? "岗位核心能力" : String.join("、", missingSkillNames.subList(0, Math.min(3, missingSkillNames.size())));
        String stage = score >= 75 ? "冲刺优化期" : score >= 50 ? "重点补齐期" : "系统学习期";
        String summary = score >= 75
                ? "当前基础较好，重点应从技能命中转向项目证据、指标表达和面试叙事。"
                : score >= 50
                ? "已有部分基础，需要围绕高权重缺口做项目化补齐，并把经历转化为岗位语言。"
                : "当前与目标岗位存在明显差距，建议先建立核心技能底座，再进入项目实践。";

        return map(
                "targetRole", jobName(targetJobId),
                "stage", stage,
                "summary", summary,
                "strengths", strengths,
                "prioritySkills", prioritySkills,
                "weakDimensions", weakDimensions,
                "plan", List.of(
                        map(
                                "phase", "第 1-2 周",
                                "title", "补齐基础概念和工具链",
                                "focus", mainSkillText,
                                "actions", List.of(
                                        "梳理目标岗位 JD 中的必备技能，建立技能清单和学习优先级。",
                                        "每天输出一页学习笔记，记录概念、常见问题和可复用命令或代码片段。",
                                        "把简历中已有经历映射到目标岗位能力维度。"
                                ),
                                "deliverable", "一份技能差距表 + 一份目标岗位简历改写草稿"
                        ),
                        map(
                                "phase", "第 3-6 周",
                                "title", "完成可展示项目",
                                "focus", "项目证据与工程实践",
                                "actions", List.of(
                                        "围绕缺口技能做一个小而完整的项目，包含需求、设计、实现、测试和部署。",
                                        "为项目补充 README、架构说明、关键截图和性能或效果指标。",
                                        "把项目复盘写成 STAR 结构，突出问题、方案、结果和取舍。"
                                ),
                                "deliverable", "一个可演示项目 + 一段可直接用于面试的项目讲述"
                        ),
                        map(
                                "phase", "第 7-12 周",
                                "title", "岗位化冲刺",
                                "focus", jobName(targetJobId),
                                "actions", List.of(
                                        "按目标岗位准备高频面试题，覆盖原理、项目、排障和系统设计。",
                                        "每周用真实 JD 反向检查简历命中率，持续调整关键词和项目表达。",
                                        "补充一段能证明学习速度和解决复杂问题能力的经历。"
                                ),
                                "deliverable", "一版目标岗位简历 + 一套面试问答卡片"
                        )
                ),
                "portfolio", List.of(
                        "项目必须能说明业务场景、个人职责、关键方案、量化指标和复盘。",
                        "优先展示与 " + jobName(targetJobId) + " 直接相关的技术栈和问题解决过程。",
                        "缺口技能不要只写“了解”，要用项目证据证明能落地。"
                ),
                "interviewPreparation", List.of(
                        "准备 2 分钟自我介绍，突出与目标岗位最相关的能力。",
                        "为每个缺口技能准备“正在如何补齐”的具体计划。",
                        "为已匹配技能准备至少一个真实项目或练习案例。"
                )
        );
    }

    private Map<String, Object> learningFallback(String targetJobId) {
        String roleName = jobName(targetJobId);
        return map(
                "targetRole", roleName,
                "stage", "待建模评估",
                "summary", "当前目标岗位的技能模板不足，系统无法进行精确缺口评分；建议先按岗位通用能力建立学习计划，并补充岗位技能样本。",
                "strengths", List.of(),
                "prioritySkills", List.of(
                        map("skill", "岗位核心技能", "dimension", "专业能力", "level", "基础到进阶", "weight", 1, "why", "目标岗位缺少可评分技能模板。", "learningGoal", "从真实 JD 中整理 6-10 个高频技能并完成项目化练习。"),
                        map("skill", "项目表达", "dimension", "经验呈现", "level", "进阶", "weight", 1, "why", "简历需要证明能力可落地。", "learningGoal", "准备一个可展示项目，写清场景、职责、方案、指标和复盘。")
                ),
                "weakDimensions", List.of(
                        map("name", "岗位技能模板", "score", 0, "action", "补充该岗位的技能要求和权重后再做精确评估。")
                ),
                "plan", List.of(
                        map(
                                "phase", "第 1-2 周",
                                "title", "建立岗位能力清单",
                                "focus", roleName,
                                "actions", List.of(
                                        "收集 5-10 条目标岗位 JD，提取重复出现的技能和职责。",
                                        "把技能分为必备、加分和项目证据三类。",
                                        "对照简历标记已经有证据和缺少证据的部分。"
                                ),
                                "deliverable", "岗位能力清单 + 简历证据映射表"
                        ),
                        map(
                                "phase", "第 3-6 周",
                                "title", "完成岗位相关项目",
                                "focus", "可证明能力的项目证据",
                                "actions", List.of(
                                        "选择一个与目标岗位最相关的小项目，做完整闭环。",
                                        "记录关键方案、遇到的问题、指标结果和复盘。",
                                        "把项目写入简历并准备 2 分钟讲述。"
                                ),
                                "deliverable", "可展示项目 + 简历项目段落"
                        ),
                        map(
                                "phase", "第 7-12 周",
                                "title", "补齐面试表达",
                                "focus", "岗位化表达",
                                "actions", List.of(
                                        "围绕目标岗位准备高频问题和项目追问。",
                                        "每周用真实 JD 检查简历关键词命中。",
                                        "补充能体现学习速度和解决问题能力的经历。"
                                ),
                                "deliverable", "目标岗位简历 + 面试问答卡片"
                        )
                ),
                "portfolio", List.of(
                        "先补齐岗位技能模板，再用项目证明核心能力。",
                        "作品集重点展示与 " + roleName + " 相关的场景、方案和结果。",
                        "不要只列技术名词，要提供可验证的产出。"
                ),
                "interviewPreparation", List.of(
                        "准备为什么选择该岗位、如何学习补齐缺口的说明。",
                        "准备一个最能证明能力迁移的项目或经历。",
                        "把岗位 JD 中的高频关键词转化为自己的经历表达。"
                )
        );
    }

    private Map<String, List<String>> loadAliases() {
        Map<String, List<String>> result = new LinkedHashMap<>();
        for (Map<String, String> row : CsvTable.read(dataDir.resolve("skill_aliases.csv"))) {
            result.put(row.get("canonical"), split(row.get("aliases")));
        }
        return result;
    }

    private String jobName(String jobId) {
        return jobRows.stream()
                .filter(row -> row.get("id").equals(jobId))
                .findFirst()
                .map(row -> row.get("name"))
                .orElse(jobId);
    }

    private static void addNode(List<Map<String, Object>> nodes, Set<String> seen, String id, String label, String type) {
        if (seen.add(id)) {
            nodes.add(map("id", id, "label", label, "type", type));
        }
    }

    private static void addEdge(List<Map<String, Object>> edges, Set<String> seen, String from, String to, String relation) {
        String key = from + "->" + to + ":" + relation;
        if (seen.add(key)) {
            edges.add(map("from", from, "to", to, "relation", relation));
        }
    }

    private static String id(String prefix, String value) {
        return prefix + "-" + value.toLowerCase(Locale.ROOT)
                .replace(" ", "-")
                .replace("/", "-")
                .replace("_", "-");
    }

    private static boolean bool(String value) {
        return "true".equalsIgnoreCase(value);
    }

    private static int number(String value, int fallback) {
        try {
            return Integer.parseInt(value);
        } catch (RuntimeException e) {
            return fallback;
        }
    }

    private static int asInt(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        return number(String.valueOf(value), 0);
    }

    private static double asDouble(Object value) {
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        return decimal(String.valueOf(value), 0);
    }

    private static double decimal(String value, double fallback) {
        try {
            return Double.parseDouble(value);
        } catch (RuntimeException e) {
            return fallback;
        }
    }

    private static List<String> split(String value) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        List<String> result = new ArrayList<>();
        for (String item : value.split("\\|")) {
            if (!item.isBlank()) {
                result.add(item.trim());
            }
        }
        return result;
    }

    private static int qualityIssueCount(Map<String, String> row) {
        return number(row.get("missing_title"), 0)
                + number(row.get("missing_source_url"), 0)
                + number(row.get("missing_collected_at"), 0)
                + number(row.get("missing_published_at"), 0)
                + number(row.get("missing_city"), 0)
                + number(row.get("missing_company"), 0)
                + number(row.get("missing_origin_record_id"), 0)
                + number(row.get("short_responsibility"), 0)
                + number(row.get("short_requirement"), 0)
                + number(row.get("no_skill_hit"), 0)
                + number(row.get("duplicate_content"), 0)
                + number(row.get("unknown_source"), 0);
    }

    private static String majorQualityIssue(Map<String, String> row) {
        Map<String, Integer> issues = new LinkedHashMap<>();
        issues.put("岗位要求过短", number(row.get("short_requirement"), 0));
        issues.put("岗位职责过短", number(row.get("short_responsibility"), 0));
        issues.put("未识别技能", number(row.get("no_skill_hit"), 0));
        issues.put("重复内容", number(row.get("duplicate_content"), 0));
        issues.put("发布时间缺失", number(row.get("missing_published_at"), 0));
        return issues.entrySet().stream()
                .max(Map.Entry.comparingByValue())
                .filter(entry -> entry.getValue() > 0)
                .map(Map.Entry::getKey)
                .orElse("问题较少");
    }

    private static String qualityGate(double score, double issueRate, int lowLevelRecords) {
        if (score >= 95 && issueRate < 8 && lowLevelRecords == 0) {
            return "可直接入库";
        }
        if (score >= 85 && issueRate < 35) {
            return "需抽检";
        }
        return "限制入库";
    }

    private static double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private static List<Map<String, Object>> topCounts(Map<String, Integer> counts, int limit) {
        return counts.entrySet().stream()
                .sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                .limit(limit)
                .map(entry -> map("name", entry.getKey(), "count", entry.getValue()))
                .toList();
    }

    private static List<?> limitList(Object value, int limit) {
        if (!(value instanceof List<?> list)) {
            return List.of();
        }
        return list.stream().limit(limit).toList();
    }

    private static void countIfPresent(Map<String, Integer> counts, String value) {
        if (value != null && !value.isBlank()) {
            counts.put(value, counts.getOrDefault(value, 0) + 1);
        }
    }

    private static Map<String, Object> artifact(String name, Path path) {
        return map(
                "name", name,
                "path", path.toString().replace("\\", "/"),
                "exists", Files.exists(path),
                "lines", lineCount(path)
        );
    }

    private static long lineCount(Path path) {
        if (!Files.exists(path)) {
            return 0;
        }
        try {
            return Files.lines(path).count();
        } catch (Exception e) {
            return 0;
        }
    }

    private static Map<String, Object> map(Object... kv) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) {
            result.put(String.valueOf(kv[i]), kv[i + 1]);
        }
        return result;
    }
}
