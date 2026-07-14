# Copy this file to scripts/local-env.ps1 and fill in your private key.
# scripts/local-env.ps1 is ignored by git.

$env:MATCH_AI_ENABLED = "true"
$env:MATCH_AI_PROVIDER = "deepseek"
$env:MATCH_AI_API_KEY = "paste-your-api-key-here"
$env:MATCH_AI_BASE_URL = "https://api.deepseek.com"
$env:MATCH_AI_MODEL = "deepseek-chat"
$env:MATCH_AI_TIMEOUT_SECONDS = "30"
