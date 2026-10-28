param(
    [Parameter(Mandatory = $true)]
    [string]$Issue,

    [Parameter(Mandatory = $true)]
    [string]$Name
)

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
$ErrorActionPreference = "Stop"

# Git 저장소 루트 확인
$repo = git rev-parse --show-toplevel

if (-not $repo) {
    Write-Error "Git 저장소 안에서 실행해야 합니다."
    exit 1
}

$repo = $repo.Trim()

# main branch 확인
$currentBranch = (git branch --show-current).Trim()

if ($currentBranch -ne "main") {
    Write-Error "Main worktree의 main branch에서 실행해야 합니다. 현재 branch: $currentBranch"
    exit 1
}

# Main working tree clean 확인
$status = git status --porcelain

if ($status) {
    Write-Error "Main working tree가 clean 상태가 아닙니다. 먼저 변경사항을 정리하세요."
    exit 1
}

# origin 최신 정보 확인
Write-Host ""
Write-Host "origin 최신 상태를 확인합니다..."

git fetch origin

if ($LASTEXITCODE -ne 0) {
    Write-Error "git fetch origin에 실패했습니다."
    exit $LASTEXITCODE
}

# Worker 정보 생성
$issueSlug = $Issue.ToLower()
$nameSlug = $Name.ToLower()

$parent = Split-Path $repo -Parent
$repoName = Split-Path $repo -Leaf

$workerPath = Join-Path $parent "$repoName-$issueSlug"
$workerBranch = "feat/$issueSlug-$nameSlug"
$workerDisplayName = "WORKER-$($Issue.ToUpper())"

# 중복 경로 확인
if (Test-Path $workerPath) {
    Write-Error "이미 Worker 경로가 존재합니다: $workerPath"
    exit 1
}

# 중복 branch 확인
$existingBranch = git branch --list $workerBranch

if ($existingBranch) {
    Write-Error "이미 branch가 존재합니다: $workerBranch"
    exit 1
}

Write-Host ""
Write-Host "Worker 생성"
Write-Host "Issue    : $Issue"
Write-Host "Branch   : $workerBranch"
Write-Host "Worktree : $workerPath"
Write-Host ""

# Worktree + feature branch 생성
git worktree add $workerPath -b $workerBranch main

if ($LASTEXITCODE -ne 0) {
    Write-Error "Git worktree 생성에 실패했습니다."
    exit $LASTEXITCODE
}

# Worker 전용 VS Code 설정 생성
$workerVscodePath = Join-Path $workerPath ".vscode"

if (-not (Test-Path $workerVscodePath)) {
    New-Item -ItemType Directory -Path $workerVscodePath | Out-Null
}

$taskPath = Join-Path $workerVscodePath "tasks.json"

# Codex CLI가 있는지 확인
$codexCommand = Get-Command codex -ErrorAction SilentlyContinue

if ($codexCommand) {

    $escapedWorkerPath = $workerPath.Replace('\', '\\')

    $taskJson = @"
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "$workerDisplayName",
      "type": "shell",
      "command": "codex",
      "options": {
        "cwd": "$escapedWorkerPath"
      },
      "presentation": {
        "echo": false,
        "reveal": "always",
        "focus": true,
        "panel": "dedicated",
        "showReuseMessage": false,
        "clear": false
      },
      "runOptions": {
        "runOn": "folderOpen"
      },
      "problemMatcher": []
    }
  ]
}
"@

}
else {

    Write-Warning "Codex CLI를 찾지 못했습니다. Worker 터미널만 생성하도록 설정합니다."

    $escapedWorkerPath = $workerPath.Replace('\', '\\')

    $taskJson = @"
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "$workerDisplayName",
      "type": "shell",
      "command": "powershell",
      "args": [
        "-NoExit"
      ],
      "options": {
        "cwd": "$escapedWorkerPath"
      },
      "presentation": {
        "echo": false,
        "reveal": "always",
        "focus": true,
        "panel": "dedicated",
        "showReuseMessage": false,
        "clear": false
      },
      "runOptions": {
        "runOn": "folderOpen"
      },
      "problemMatcher": []
    }
  ]
}
"@
}

Set-Content `
    -Path $taskPath `
    -Value $taskJson `
    -Encoding UTF8

# Worker 전용 tasks.json을 Git 대상에서 제외
$gitDir = (git -C $workerPath rev-parse --git-dir).Trim()

if (-not [System.IO.Path]::IsPathRooted($gitDir)) {
    $gitDir = Join-Path $workerPath $gitDir
}

$excludePath = Join-Path $gitDir "info\exclude"
$excludeDir = Split-Path $excludePath -Parent

if (-not (Test-Path $excludeDir)) {
    New-Item -ItemType Directory -Path $excludeDir -Force | Out-Null
}

$excludeEntry = ".vscode/tasks.json"

if (Test-Path $excludePath) {
    $excludeContent = Get-Content $excludePath
}
else {
    $excludeContent = @()
}

if ($excludeContent -notcontains $excludeEntry) {
    Add-Content -Path $excludePath -Value $excludeEntry
}

# 현재 VS Code Workspace에 Worker 추가
code --add $workerPath

if ($LASTEXITCODE -ne 0) {
    Write-Warning "Worker는 생성됐지만 VS Code Workspace 추가에 실패했습니다."
}

Write-Host ""
Write-Host "Worker 생성 완료"
Write-Host "Name     : $workerDisplayName"
Write-Host "Branch   : $workerBranch"
Write-Host "Worktree : $workerPath"
Write-Host ""
Write-Host "Automatic Tasks가 허용되어 있으면 Worker 터미널이 자동 실행됩니다."