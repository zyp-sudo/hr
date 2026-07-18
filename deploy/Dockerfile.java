# =============================================================================
# Java Knowledge-Graph & Analytics Backend — Competition Image
# Port: 8081  |  Entry: com.xh202621.App  |  JDK: 17
# =============================================================================

# ---- build stage ------------------------------------------------------------
FROM eclipse-temurin:17-jdk AS build

WORKDIR /src
COPY backend/src/ /src/
RUN javac -d /out $(find . -name "*.java")

# ---- run stage --------------------------------------------------------------
FROM eclipse-temurin:17-jre

LABEL org.xh202621.service="java-backend"
LABEL org.xh202621.port="8081"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r xh && useradd -r -g xh -d /app xh

WORKDIR /app

# ---- compiled classes -------------------------------------------------------
COPY --from=build /out/ /app/

# ---- CSV data (read-only at runtime via volume mount, baked as fallback) ----
COPY --chown=xh:xh data/ /app/data/

USER xh

# ---- health check -----------------------------------------------------------
HEALTHCHECK --interval=15s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -fsS http://localhost:8081/api/health || exit 1

# ---- run --------------------------------------------------------------------
EXPOSE 8081
CMD ["java", "-Xmx512m", "com.xh202621.App"]
