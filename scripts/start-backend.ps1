javac -encoding UTF-8 -d backend/out backend/src/com/xh202621/*.java

$LocalEnv = Join-Path $PSScriptRoot "local-env.ps1"
if (Test-Path $LocalEnv) {
  . $LocalEnv
}

java -cp backend/out com.xh202621.App
