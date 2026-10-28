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
    Write-Error "Main worktree의 main branch에서 실행해야 합니다."
    exit 1
}

# Main clean 확인
$status = git status --porcelain

if ($status) {
    Write-Error "Main working tree가 clean 상태가 아닙니다."
    exit 1
}

# Worker 정보 계산
$issueSlug = $Issue.ToLower()
$nameSlug = $Name.ToLower()

$parent = Split-Path $repo -Parent
$repoName = Split-Path $repo -Leaf

$workerPath = Join-Path $parent "$repoName-$issueSlug"
$workerBranch = "feat/$issueSlug-$nameSlug"

if (-not (Test-Path $workerPath)) {
    Write-Error "Worker worktree가 존재하지 않습니다: $workerPath"
    exit 1
}

# Worker clean 확인
Write-Host ""
Write-Host "Worker 상태를 확인합니다..."

$workerStatus = git -C $workerPath status --porcelain

if ($workerStatus) {
    Write-Error "Worker working tree가 clean 상태가 아닙니다. Worker를 삭제하지 않습니다."
    exit 1
}

# origin/main 최신화
Write-Host ""
Write-Host "Main을 최신 상태로 갱신합니다..."

git fetch origin

if ($LASTEXITCODE -ne 0) {
    Write-Error "git fetch origin에 실패했습니다."
    exit $LASTEXITCODE
}

git pull --ff-only origin main

if ($LASTEXITCODE -ne 0) {
    Write-Error "main 최신화에 실패했습니다."
    exit $LASTEXITCODE
}

# VS Code Workspace에서 Worker 제거
Write-Host ""
Write-Host "VS Code Workspace에서 Worker를 제거합니다..."

code --remove $workerPath

if ($LASTEXITCODE -ne 0) {
    Write-Warning "VS Code Workspace에서 Worker 제거에 실패했습니다."
}

# Git worktree 제거
Write-Host ""
Write-Host "Worker worktree를 제거합니다..."

git worktree remove $workerPath

if ($LASTEXITCODE -ne 0) {
    Write-Error "Worker worktree 제거에 실패했습니다."
    exit $LASTEXITCODE
}

# Local feature branch 제거
Write-Host ""
Write-Host "Local feature branch를 제거합니다..."

git branch -d $workerBranch

if ($LASTEXITCODE -ne 0) {
    Write-Warning "Local branch를 삭제하지 못했습니다. merge 여부를 확인하세요."
}

# Worktree metadata 정리
git worktree prune

Write-Host ""
Write-Host "Worker 정리 완료"
Write-Host "Branch   : $workerBranch"
Write-Host "Worktree : $workerPath"
Write-Host ""
Write-Host "Worker Codex 터미널이 남아 있으면 VS Code 터미널의 휴지통 버튼으로 종료하세요."