$ports = @(8080, 8081, 3000, 8501)
$pids = @()

try {
  $targets = Get-CimInstance Win32_Process -ErrorAction Stop |
    Where-Object {
      $_.CommandLine -like '*com.xh202621.App*' -or
      $_.CommandLine -like '*uvicorn app.main:app*' -or
      $_.CommandLine -like '*_archived-frontends/frontend/app.py*' -or
      $_.CommandLine -like '*frontend\app.py*' -or
      $_.CommandLine -like '*talentmatch*server.ts*' -or
      $_.CommandLine -like '*talentmatch*server.cjs*'
    }
  $pids += $targets | ForEach-Object { $_.ProcessId }
} catch {
  Write-Output 'Process command-line lookup is unavailable; falling back to project ports.'
}

foreach ($line in netstat -ano) {
  foreach ($port in $ports) {
    if ($line -match "LISTENING\s+(\d+)$" -and $line -match ":$port\s") {
      $pids += [int]$Matches[1]
    }
  }
}

$uniquePids = $pids | Where-Object { $_ -and $_ -ne 0 } | Select-Object -Unique

foreach ($pidToStop in $uniquePids) {
  Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
  Write-Output "Stopped process $pidToStop"
}

if (-not $uniquePids) {
  Write-Output 'No matching dev service process found.'
}
