package com.xh202621;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.Executors;

public class App {
    private static final int PORT = number(System.getenv("BACKEND_PORT"), 8081);
    private static final KnowledgeService knowledgeService = new KnowledgeService();

    public static void main(String[] args) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(PORT), 0);
        server.createContext("/api/health", App::handleHealth);
        server.createContext("/api/jobs", App::handleJobs);
        server.createContext("/api/graph", App::handleGraph);
        server.createContext("/api/evolution", App::handleEvolution);
        server.createContext("/api/data-quality", App::handleDataQuality);
        server.createContext("/api/etl-summary", App::handleEtlSummary);
        server.createContext("/api/kg-summary", App::handleKgSummary);
        server.createContext("/api/architecture-summary", App::handleArchitectureSummary);
        server.createContext("/api/samples", App::handleSamples);
        server.createContext("/api/real-jobs", App::handleRealJobs);
        server.createContext("/api/match", App::handleMatch);
        server.createContext("/api/ai-insight", App::handleAiInsight);
        server.createContext("/api/discover", App::handleDiscover);
        server.createContext("/", App::handleRoot);
        server.setExecutor(Executors.newFixedThreadPool(8));
        server.start();
        System.out.println("Java backend listening on http://localhost:" + PORT);
    }

    private static void handleRoot(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        respond(exchange, 200, Json.stringify(Map.of(
                "service", "xh-202621-backend",
                "status", "ok",
                "frontend", "http://localhost:3000",
                "apis", Map.of(
                        "health", "/api/health",
                        "jobs", "/api/jobs",
                        "graph", "/api/graph",
                        "evolution", "/api/evolution?jobId=java-backend-engineer",
                        "etlSummary", "/api/etl-summary",
                        "kgSummary", "/api/kg-summary",
                        "architectureSummary", "/api/architecture-summary",
                        "realJobs", "/api/real-jobs",
                        "aiInsight", "/api/ai-insight?topic=quality"
                )
        )));
    }

    private static void handleHealth(HttpExchange exchange) throws IOException {
        if (!preflight(exchange)) return;
        respond(exchange, 200, "{\"status\":\"ok\",\"service\":\"xh-202621-backend\"}");
    }

    private static void handleJobs(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        respond(exchange, 200, Json.stringify(Map.of("jobs", knowledgeService.jobs())));
    }

    private static void handleGraph(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        respond(exchange, 200, Json.stringify(knowledgeService.graph()));
    }

    private static void handleEvolution(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        String jobId = queryParams(exchange.getRequestURI()).getOrDefault("jobId", "java-backend-engineer");
        respond(exchange, 200, Json.stringify(knowledgeService.evolution(jobId)));
    }

    private static void handleDataQuality(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        respond(exchange, 200, Json.stringify(knowledgeService.dataQuality()));
    }

    private static void handleEtlSummary(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        respond(exchange, 200, Json.stringify(knowledgeService.etlSummary()));
    }

    private static void handleKgSummary(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        respond(exchange, 200, Json.stringify(knowledgeService.kgSummary()));
    }

    private static void handleArchitectureSummary(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        respond(exchange, 200, Json.stringify(knowledgeService.architectureSummary()));
    }

    private static void handleSamples(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        respond(exchange, 200, Json.stringify(knowledgeService.samples()));
    }

    private static void handleRealJobs(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        int limit = number(queryParams(exchange.getRequestURI()).get("limit"), 0);
        respond(exchange, 200, Json.stringify(knowledgeService.realChinaJobs(limit)));
    }

    private static void handleDiscover(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "POST")) return;
        respond(exchange, 200, Json.stringify(knowledgeService.discoverEmergingRole()));
    }

    private static void handleMatch(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "POST")) return;
        String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
        String targetJobId = Json.field(body, "targetJobId", "java-backend-engineer");
        String resumeText = Json.field(body, "resumeText", "");
        respond(exchange, 200, Json.stringify(knowledgeService.match(targetJobId, resumeText)));
    }

    private static void handleAiInsight(HttpExchange exchange) throws IOException {
        if (!preflight(exchange) || !requireMethod(exchange, "GET")) return;
        String topic = queryParams(exchange.getRequestURI()).getOrDefault("topic", "overview");
        respond(exchange, 200, Json.stringify(knowledgeService.aiInsight(topic)));
    }

    private static boolean preflight(HttpExchange exchange) throws IOException {
        exchange.getResponseHeaders().add("Access-Control-Allow-Origin", "*");
        exchange.getResponseHeaders().add("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
        exchange.getResponseHeaders().add("Access-Control-Allow-Headers", "Content-Type");
        exchange.getResponseHeaders().add("Cache-Control", "public, max-age=30");
        if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(204, -1);
            return false;
        }
        return true;
    }

    private static boolean requireMethod(HttpExchange exchange, String method) throws IOException {
        if (!method.equalsIgnoreCase(exchange.getRequestMethod())) {
            respond(exchange, 405, Json.stringify(Map.of("error", "Method not allowed")));
            return false;
        }
        return true;
    }

    private static Map<String, String> queryParams(URI uri) {
        Map<String, String> result = new LinkedHashMap<>();
        String query = uri.getRawQuery();
        if (query == null || query.isBlank()) return result;
        for (String part : query.split("&")) {
            String[] kv = part.split("=", 2);
            if (kv.length == 2) {
                result.put(kv[0], kv[1].replace("+", " "));
            }
        }
        return result;
    }

    private static int number(String value, int fallback) {
        if (value == null || value.isBlank()) return fallback;
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private static void respond(HttpExchange exchange, int code, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(code, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }
}
