# 注册 Windows 计划任务：按 .env 中的 SCHEDULE_TIME / SCHEDULE_DAYS 运行周报脚本
#
# 用法：
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\scripts\install_scheduled_task.ps1
#   .\scripts\install_scheduled_task.ps1 -At 18:00
#   .\scripts\install_scheduled_task.ps1 -At 09:15 -Days "Mon,Wed,Fri"
#
# 参数优先于 .env；都未指定时默认 17:30、周一至周五。

param(
    [string]$At = "",
    [string]$Days = "",
    [string]$TaskName = "WorkReportWeekly"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Bat = Join-Path $Root "scripts\run_scheduled.bat"
$EnvFile = Join-Path $Root ".env"

if (-not (Test-Path $Bat)) {
    throw "找不到入口脚本: $Bat"
}

function Read-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key
    )
    if (-not (Test-Path $Path)) {
        return $null
    }
    foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
        $trim = $line.Trim()
        if (-not $trim -or $trim.StartsWith("#")) {
            continue
        }
        $idx = $trim.IndexOf("=")
        if ($idx -lt 1) {
            continue
        }
        $k = $trim.Substring(0, $idx).Trim()
        if ($k -ne $Key) {
            continue
        }
        $v = $trim.Substring($idx + 1).Trim()
        # 去掉成对引号
        if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
            $v = $v.Substring(1, $v.Length - 2)
        }
        return $v
    }
    return $null
}

function Convert-ScheduleDays {
    param([string]$Raw)
    $map = @{
        "Mon" = "Monday"; "Monday" = "Monday"; "周一" = "Monday"; "1" = "Monday"
        "Tue" = "Tuesday"; "Tuesday" = "Tuesday"; "周二" = "Tuesday"; "2" = "Tuesday"
        "Wed" = "Wednesday"; "Wednesday" = "Wednesday"; "周三" = "Wednesday"; "3" = "Wednesday"
        "Thu" = "Thursday"; "Thursday" = "Thursday"; "周四" = "Thursday"; "4" = "Thursday"
        "Fri" = "Friday"; "Friday" = "Friday"; "周五" = "Friday"; "5" = "Friday"
        "Sat" = "Saturday"; "Saturday" = "Saturday"; "周六" = "Saturday"; "6" = "Saturday"
        "Sun" = "Sunday"; "Sunday" = "Sunday"; "周日" = "Sunday"; "0" = "Sunday"; "7" = "Sunday"
    }
    $result = @()
    foreach ($part in ($Raw -split "[,;，\s]+")) {
        $p = $part.Trim()
        if (-not $p) { continue }
        if (-not $map.ContainsKey($p)) {
            throw "无法识别的星期: '$p'，请使用 Mon,Tue,Wed,Thu,Fri,Sat,Sun"
        }
        $day = $map[$p]
        if ($result -notcontains $day) {
            $result += $day
        }
    }
    if ($result.Count -eq 0) {
        throw "SCHEDULE_DAYS 为空"
    }
    return $result
}

function Normalize-Time {
    param([string]$Raw)
    $t = $Raw.Trim()
    if ($t -notmatch '^\d{1,2}:\d{2}$') {
        throw "时间格式无效: '$Raw'，请使用 HH:mm，例如 17:30"
    }
    $parts = $t.Split(":")
    $h = [int]$parts[0]
    $m = [int]$parts[1]
    if ($h -lt 0 -or $h -gt 23 -or $m -lt 0 -or $m -gt 59) {
        throw "时间超出范围: '$Raw'"
    }
    return "{0:D2}:{1:D2}" -f $h, $m
}

# 解析时间：命令行 > .env > 默认
if (-not $At) {
    $At = Read-DotEnvValue -Path $EnvFile -Key "SCHEDULE_TIME"
}
if (-not $At) {
    $At = "17:30"
}
$At = Normalize-Time -Raw $At

# 解析星期：命令行 > .env > 默认
if (-not $Days) {
    $Days = Read-DotEnvValue -Path $EnvFile -Key "SCHEDULE_DAYS"
}
if (-not $Days) {
    $Days = "Mon,Tue,Wed,Thu,Fri"
}
$DayList = Convert-ScheduleDays -Raw $Days

# 若已存在则先删除
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "已移除旧任务: $TaskName"
}

$Action = New-ScheduledTaskAction -Execute $Bat -WorkingDirectory $Root
# -At 接受 "HH:mm" 字符串
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayList -At $At
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "放假前最后一个工作日自动生成 GitLab 周报（时间可配置）" `
    -Force | Out-Null

$DaysDisplay = ($DayList -join ",")
Write-Host "已注册计划任务: $TaskName"
Write-Host "  触发时间: $At"
Write-Host "  触发星期: $DaysDisplay"
Write-Host "  配置来源: $(if (Test-Path $EnvFile) { $EnvFile } else { '默认值' })（可用 -At / -Days 覆盖）"
Write-Host "  脚本: $Bat"
Write-Host "  工作目录: $Root"
Write-Host ""
Write-Host "修改时间后请重新运行本脚本以更新计划任务。"
Write-Host "手动测试: schtasks /Run /TN $TaskName"
Write-Host "查看日志: $Root\logs\"
Write-Host "删除任务: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
