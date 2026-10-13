# Local fallback setup on Windows. The cloud job (GitHub Actions) does the scheduled collection;
# this machine only runs the board on login so you can open it and refresh by hand.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repo

# 1. Python environment (standard library only, nothing to install).
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 环境创建失败' }
}
if (-not (Test-Path -LiteralPath $venvPython)) { throw '未找到 Python 环境' }
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'

# 2. .env: carry over the three local settings from the old project folder if this repo has none.
$envFile = Join-Path $repo '.env'
$oldEnv = Join-Path (Split-Path -Parent $repo) '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    $keys = 'AI_NEWS_DATA_ROOT','AI_NEWS_TLS_BACKEND','AI_NEWS_PROXY','AI_NEWS_BACKUP_ROOT'
    $lines = @()
    if (Test-Path -LiteralPath $oldEnv) { $lines = Get-Content -LiteralPath $oldEnv | Where-Object { $k = ($_ -split '=',2)[0].Trim(); $keys -contains $k } }
    if (-not $lines) { $lines = Get-Content -LiteralPath (Join-Path $repo '.env.example') | Where-Object { $_ -match '^AI_NEWS_' } }
    $lines | Set-Content -LiteralPath $envFile -Encoding UTF8
}

# 3. Login task points at this repo; the local 4-hour collection task is removed so cloud and local don't both collect.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$startup = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + (Join-Path $PSScriptRoot 'start_news_board.py') + '"') -WorkingDirectory $repo
$login = New-ScheduledTaskTrigger -AtLogOn -User $identity
$managed = 'Personal AI news board managed task'
$existing = Get-ScheduledTask -TaskName 'AI News Board - Login' -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -ne $managed) { throw '任务名已被占用，未覆盖：AI News Board - Login' }
Register-ScheduledTask -TaskName 'AI News Board - Login' -Action $startup -Trigger $login -Principal $principal -Settings $settings -Description $managed -Force | Out-Null
$collect = Get-ScheduledTask -TaskName 'AI News Board - Collect' -ErrorAction SilentlyContinue
if ($collect -and $collect.Description -eq $managed) { Unregister-ScheduledTask -TaskName 'AI News Board - Collect' -Confirm:$false }

# 4. Local data says "no local schedule", so the local page doesn't warn about missed local runs.
$dataRoot = & $venvPython -c 'from ai_news_pipeline.runtime import data_root; print(data_root())'
if ($LASTEXITCODE -ne 0) { throw '读取本机数据目录失败' }
New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
'{"enabled": false, "note": "Scheduled collection runs on GitHub Actions"}' | Set-Content -LiteralPath (Join-Path $dataRoot 'schedule.json') -Encoding UTF8
& $venvPython scripts/build_site_data.py
if ($LASTEXITCODE -ne 0) { throw '本机页面数据生成失败' }

Write-Output '本机备用已就绪：登录后自动启动 http://127.0.0.1:8766/ ；本机 4 小时采集任务已移除，定时采集由 GitHub Actions 负责。'
Write-Output '如本地服务正在运行，请在任务管理器结束 pythonw 进程后运行：.venv\Scripts\pythonw.exe scripts\start_news_board.py'
