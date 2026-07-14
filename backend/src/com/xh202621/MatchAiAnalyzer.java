package com.xh202621;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

public interface MatchAiAnalyzer {
    Map<String, Object> analyze(Map<String, Object> context);

    static MatchAiAnalyzer fromEnvironment() {
        Map<String, String> localEnv = readLocalEnv();
        String enabled = config(localEnv, "MATCH_AI_ENABLED", "false");
        String apiKey = config(localEnv, "MATCH_AI_API_KEY", "");
        String baseUrl = config(localEnv, "MATCH_AI_BASE_URL", "");
        String endpoint = config(localEnv, "MATCH_AI_API_URL", "");
        String model = config(localEnv, "MATCH_AI_MODEL", "deepseek-chat");
        String provider = config(localEnv, "MATCH_AI_PROVIDER", "openai-compatible");
        int timeoutSeconds = parseInt(config(localEnv, "MATCH_AI_TIMEOUT_SECONDS", "30"), 30);

        boolean explicitlyEnabled = "true".equalsIgnoreCase(enabled) || "1".equals(enabled);
        boolean configured = !apiKey.isBlank() && (!endpoint.isBlank() || !baseUrl.isBlank());
        if (!explicitlyEnabled || !configured) {
            return new DisabledMatchAiAnalyzer(explicitlyEnabled, configured, provider, model);
        }
        String url = endpoint.isBlank() ? baseUrl.replaceAll("/+$", "") + "/v1/chat/completions" : endpoint;
        return new OpenAiCompatibleMatchAiAnalyzer(url, apiKey, provider, model, timeoutSeconds);
    }

    private static String config(Map<String, String> localEnv, String key, String fallback) {
        String value = env(key, "");
        if (value.isBlank()) {
            value = localEnv.getOrDefault(key, "");
        }
        return value.isBlank() ? fallback : value.trim();
    }

    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private static Map<String, String> readLocalEnv() {
        Path path = Path.of("scripts", "local-env.ps1");
        if (!Files.exists(path)) {
            return Map.of();
        }
        Map<String, String> result = new LinkedHashMap<>();
        try {
            for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
                String trimmed = line.trim();
                if (!trimmed.startsWith("$env:") || !trimmed.contains("=")) {
                    continue;
                }
                int equals = trimmed.indexOf('=');
                String key = trimmed.substring(5, equals).trim();
                String value = trimmed.substring(equals + 1).trim();
                if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
                    value = value.substring(1, value.length() - 1);
                }
                if (!key.isBlank()) {
                    result.put(key, value);
                }
            }
        } catch (IOException e) {
            return Map.of();
        }
        return result;
    }

    private static int parseInt(String value, int fallback) {
        try {
            return Integer.parseInt(value);
        } catch (RuntimeException e) {
            return fallback;
        }
    }
}

final class DisabledMatchAiAnalyzer implements MatchAiAnalyzer {
    private final boolean explicitlyEnabled;
    private final boolean configured;
    private final String provider;
    private final String model;

    DisabledMatchAiAnalyzer(boolean explicitlyEnabled, boolean configured, String provider, String model) {
        this.explicitlyEnabled = explicitlyEnabled;
        this.configured = configured;
        this.provider = provider;
        this.model = model;
    }

    @Override
    public Map<String, Object> analyze(Map<String, Object> context) {
        return map(
                "enabled", false,
                "configured", configured,
                "status", "disabled",
                "provider", provider,
                "model", model,
                "message", explicitlyEnabled
                        ? "MATCH_AI_ENABLED is true, but MATCH_AI_API_KEY and MATCH_AI_BASE_URL or MATCH_AI_API_URL are not fully configured."
                        : "Set MATCH_AI_ENABLED=true plus MATCH_AI_API_KEY and MATCH_AI_BASE_URL or MATCH_AI_API_URL to enable AI analysis."
        );
    }

    private static Map<String, Object> map(Object... kv) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) {
            result.put(String.valueOf(kv[i]), kv[i + 1]);
        }
        return result;
    }
}

final class OpenAiCompatibleMatchAiAnalyzer implements MatchAiAnalyzer {
    private final String url;
    private final String apiKey;
    private final String provider;
    private final String model;
    private final Duration timeout;
    private final HttpClient client;

    OpenAiCompatibleMatchAiAnalyzer(String url, String apiKey, String provider, String model, int timeoutSeconds) {
        this.url = url;
        this.apiKey = apiKey;
        this.provider = provider;
        this.model = model;
        this.timeout = Duration.ofSeconds(Math.max(5, timeoutSeconds));
        this.client = HttpClient.newBuilder().connectTimeout(this.timeout).build();
    }

    @Override
    public Map<String, Object> analyze(Map<String, Object> context) {
        try {
            String responseBody = post(context);
            String content = Json.field(responseBody, "content", "");
            return map(
                    "enabled", true,
                    "configured", true,
                    "status", "ok",
                    "provider", provider,
                    "model", model,
                    "content", content,
                    "rawResponse", responseBody
            );
        } catch (IOException e) {
            return error("io_error", e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return error("interrupted", e);
        } catch (RuntimeException e) {
            return error("runtime_error", e);
        }
    }

    private String post(Map<String, Object> context) throws IOException, InterruptedException {
        Map<String, Object> payload = map(
                "model", model,
                "messages", messages(context),
                "temperature", 0.2,
                "response_format", map("type", "json_object")
        );
        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                .timeout(timeout)
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(Json.stringify(payload)))
                .build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("AI API returned HTTP " + response.statusCode() + ": " + response.body());
        }
        return response.body();
    }

    private Object messages(Map<String, Object> context) {
        return java.util.List.of(
                map(
                        "role", "system",
                        "content", "You are an analyst for a Chinese recruitment data platform, capability graph, ETL pipeline, data quality workflow, and job-resume matching product. Return compact JSON only. Use Chinese for user-facing text. Ground every finding in the provided context and do not invent facts."
                ),
                map(
                        "role", "user",
                        "content", "Analyze this platform context. If type is match, improve the match diagnosis without inventing resume facts. Otherwise return JSON with summary, key_findings, risks, recommended_actions, and quick_wins:\n" + Json.stringify(context)
                )
        );
    }

    private Map<String, Object> error(String status, Exception e) {
        return map(
                "enabled", true,
                "configured", true,
                "status", status,
                "provider", provider,
                "model", model,
                "message", e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()
        );
    }

    private static Map<String, Object> map(Object... kv) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) {
            result.put(String.valueOf(kv[i]), kv[i + 1]);
        }
        return result;
    }
}
