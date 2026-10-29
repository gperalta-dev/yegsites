# Puts the chat server on Cloudflare and points the realty demo's chat at it.  Run: pwsh -File deploy.ps1
# The first run downloads wrangler (Cloudflare's tool) and opens the browser to log in to Cloudflare.
# The Claude API key comes from the .env file and is piped to Cloudflare as a secret, never printed or saved here.
param(
  [string]$EnvFile = 'C:\dev\money-town\money-town\.env',
  [string[]]$KeyNames = @('REALTY_CHAT_API_KEY', 'CLAUDE_API_KEY_FOR_AGENTS')
)
Set-Location $PSScriptRoot
function wrangler { npx --yes wrangler@4 @args }

$key = $null
foreach ($name in $KeyNames) {
  $line = Get-Content $EnvFile | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -First 1
  if ($line) { $key = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'"); Write-Host "Using $name from $EnvFile"; break }
}
if (-not $key) { Write-Host "No $($KeyNames -join ' or ') in $EnvFile"; exit 1 }

if ((wrangler whoami 2>&1 | Out-String) -match 'not authenticated') { wrangler login }

Write-Host 'Deploying...'
$out = wrangler deploy 2>&1 | Out-String
Write-Host $out
$url = [regex]::Match($out, 'https://[\w.-]+\.workers\.dev').Value
if ($LASTEXITCODE -or -not $url) { Write-Host 'No workers.dev address came back. Open dash.cloudflare.com > Workers & Pages once so the account gets one, then run this again.'; exit 1 }

$key | npx --yes wrangler@4 secret put ANTHROPIC_API_KEY
Remove-Variable key
if ($LASTEXITCODE) { Write-Host 'The key did not go in. Run this again.'; exit 1 }

$page = (Resolve-Path (Join-Path $PSScriptRoot '..\index.html')).Path
$html = [IO.File]::ReadAllText($page) -replace "const CHAT_URL = '[^']*';", "const CHAT_URL = '$url/chat';"
[IO.File]::WriteAllText($page, $html)
Write-Host "The demo's chat now points at $url/chat"

Write-Host 'Asking it one question...'
Start-Sleep -Seconds 5
$body = '{"messages":[{"role":"user","content":"Is the backyard fenced?"}],"rate":4.5,"years":25,"per":"m"}'
try { (Invoke-WebRequest "$url/chat" -UseBasicParsing -Method Post -Body $body -ContentType 'application/json' -Headers @{ Origin = 'https://southsites.ca' }).Content }
catch { Write-Host "No answer yet ($($_.Exception.Message)). Wait a minute and open the demo." }
