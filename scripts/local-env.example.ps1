# Copy this file to scripts/local-env.ps1 and fill in your private key.
# scripts/local-env.ps1 is ignored by git.

# Runtime storage (change passwords outside local development).
$env:MYSQL_URL = "mysql+pymysql://root:password@localhost:3307/job_kg?charset=utf8mb4"
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USERNAME = "neo4j"
$env:NEO4J_PASSWORD = "password123"
$env:NEO4J_DATABASE = "neo4j"
$env:JAVA_BACKEND_URL = "http://localhost:8081"

$env:MATCH_AI_ENABLED = "true"
$env:MATCH_AI_PROVIDER = "deepseek"
$env:MATCH_AI_API_KEY = "paste-your-api-key-here"
$env:MATCH_AI_BASE_URL = "https://api.deepseek.com"
$env:MATCH_AI_MODEL = "deepseek-chat"
$env:MATCH_AI_TIMEOUT_SECONDS = "30"
