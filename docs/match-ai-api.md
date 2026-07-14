# Match AI API Hook

The `/api/match` response now always includes an `aiAnalysis` object.

By default the hook is disabled and no remote request is sent. Enable it with:

You can configure the same values from the Web UI:

```text
http://localhost:8501/?page=settings
```

The settings page writes `scripts/local-env.ps1`, which is ignored by git. Leaving the API key field blank keeps the existing saved key.

Manual PowerShell configuration:

```powershell
$env:MATCH_AI_ENABLED='true'
$env:MATCH_AI_API_KEY='your-api-key'
$env:MATCH_AI_BASE_URL='https://api.deepseek.com'
$env:MATCH_AI_MODEL='deepseek-chat'
```

You can also bypass `MATCH_AI_BASE_URL` and provide the full chat completions URL:

```powershell
$env:MATCH_AI_API_URL='https://api.deepseek.com/v1/chat/completions'
```

Optional variables:

- `MATCH_AI_PROVIDER`: display/provider label, default `openai-compatible`
- `MATCH_AI_TIMEOUT_SECONDS`: request timeout, default `30`

The adapter sends an OpenAI-compatible chat-completions payload containing the current rule-based match result, matched and missing skills, dimension scores, suggestions, required skills, and the resume text. The AI response is returned under:

```json
{
  "aiAnalysis": {
    "enabled": true,
    "configured": true,
    "status": "ok",
    "provider": "openai-compatible",
    "model": "deepseek-chat",
    "content": "...",
    "rawResponse": "..."
  }
}
```

When disabled, `aiAnalysis.status` is `disabled`, so the existing local matching flow remains fully offline.
