package com.xh202621;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class CsvTable {
    private CsvTable() {
    }

    public static List<Map<String, String>> read(Path path) {
        try {
            if (!Files.exists(path)) {
                return List.of();
            }
            List<String> lines = Files.readAllLines(path, StandardCharsets.UTF_8).stream()
                    .filter(line -> !line.isBlank())
                    .toList();
            if (lines.isEmpty()) {
                return List.of();
            }
            List<String> headers = parseLine(lines.get(0));
            if (!headers.isEmpty()) {
                headers.set(0, headers.get(0).replace("\uFEFF", ""));
            }
            List<Map<String, String>> rows = new ArrayList<>();
            for (int i = 1; i < lines.size(); i++) {
                List<String> values = parseLine(lines.get(i));
                Map<String, String> row = new LinkedHashMap<>();
                for (int col = 0; col < headers.size(); col++) {
                    row.put(headers.get(col), col < values.size() ? values.get(col) : "");
                }
                rows.add(row);
            }
            return rows;
        } catch (IOException e) {
            throw new IllegalStateException("Failed to read CSV: " + path, e);
        }
    }

    private static List<String> parseLine(String line) {
        List<String> result = new ArrayList<>();
        StringBuilder cell = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    cell.append('"');
                    i++;
                } else {
                    quoted = !quoted;
                }
            } else if (c == ',' && !quoted) {
                result.add(cell.toString().trim());
                cell.setLength(0);
            } else {
                cell.append(c);
            }
        }
        result.add(cell.toString().trim());
        return result;
    }
}
