<#
.SYNOPSIS
    安装 Windows 计划任务 —— 每日自动生成小红书文案。

.DESCRIPTION
    在 Windows Task Scheduler 中创建一个每日任务，于每个交易日收盘后
    （默认 16:00）自动运行文案生成脚本。

.PARAMETER TaskName
    计划任务名称，默认 "XHS-Daily-Copy-Generator"

.PARAMETER RunTime
    每日运行时间（HH:mm），默认 "16:00"

.PARAMETER PythonPath
    Python 解释器路径。默认使用项目 .venv 中的 python.exe

.PARAMETER WorkingDir
    项目根目录，默认为脚本所在目录的上级目录

.EXAMPLE
    .\install_scheduled_task.ps1

.EXAMPLE
    .\install_scheduled_task.ps1 -RunTime "17:00" -TaskName "My-XHS-Task"
#>

param(
    [string]$TaskName = "XHS-Daily-Copy-Generator",
    [string]$RunTime = "16:00",
    [string]$PythonPath = "",
    [string]$WorkingDir = ""
)

# 自动检测路径
if (-not $WorkingDir) {
    $WorkingDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
if (-not $PythonPath) {
    $PythonPath = Join-Path $WorkingDir ".venv\Scripts\python.exe"
}

Write-Host "════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  安装小红书文案每日生成任务" -ForegroundColor Cyan
Write-Host "════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "任务名称   : $TaskName"
Write-Host "运行时间   : 每日 $RunTime"
Write-Host "Python 路径: $PythonPath"
Write-Host "工作目录   : $WorkingDir"
Write-Host ""

# 检查 Python 是否存在
if (-not (Test-Path $PythonPath)) {
    Write-Error "Python 解释器未找到: $PythonPath"
    Write-Host "请先安装虚拟环境: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

# 移除已存在的同名任务
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "检测到已存在同名任务，正在移除..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 创建任务操作
$action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -WorkingDirectory $WorkingDir `
    -Argument "-m xhs_generator.scheduler.task_scheduler --run-once"

# 创建触发器（每日执行）
$trigger = New-ScheduledTaskTrigger -Daily -At $RunTime

# 任务配置：允许在电池供电时运行、隐藏窗口、失败后重试
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

# 注册任务（以当前用户身份运行）
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "每日自动生成券商营业部小红书文案（市场热点/新闻/IPO/投顾/投教）" `
    -Force

Write-Host ""
Write-Host "✅ 任务已成功安装！" -ForegroundColor Green
Write-Host ""
Write-Host "可通过以下方式管理：" -ForegroundColor Gray
Write-Host "  - 查看: taskschd.msc  → 搜索 '$TaskName'"
Write-Host "  - 手动运行: Get-ScheduledTask -TaskName '$TaskName' | Start-ScheduledTask"
Write-Host "  - 移除: .\scripts\remove_scheduled_task.ps1"
Write-Host ""
Write-Host "下次执行时间: $(Get-ScheduledTask -TaskName $TaskName | Select-Object -ExpandProperty Triggers | Select-Object -First 1 | Get-ScheduledTaskInfo | Select-Object -ExpandProperty NextRunTime)" -ForegroundColor Gray
