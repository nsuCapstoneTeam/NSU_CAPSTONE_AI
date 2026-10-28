param(
    [Parameter(Mandatory = $true)]
    [string]$Issue,

    [Parameter(Mandatory = $true)]
    [string]$Name
)

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding

$ErrorActionPreference = "Stop"

# 현재 Git 저장소 루트
$repo = git rev-parse --show-toplevel

if (-not $repo) {
    Write-Error "Git 저장소 안에서 실행해야 합니다."
    exit 1
}

$repo = $repo.Trim()

# Main branch 확인
$branch = git branch --show-current

if ($branch -ne "main") {
    Write-Error "Main worktree의 main branch에서 실행해야 합니다. 현재 branch: $branch"
    exit 1
}

# Main working tree가 clean한지 확인
$status = git status --porcelain

if ($status) {
    Write-Error "Main working tree가 clean 상태가 아닙니다. 먼저 변경사항을 정리하세요."
    exit 1
}

# 최신 remote 정보 확인
git fetch origin

# 작업 이름 정리
$issueSlug = $Issue.ToLower()
$nameSlug = $Name.ToLower()

$parent = Split-Path $repo -Parent
$repoName = Split-Path $repo -Leaf

$workerPath = Join-Path $parent "$repoName-$issueSlug"
$workerBranch = "feat/$issueSlug-$nameSlug"

# 동일 worktree/branch 존재 여부 확인
if (Test-Path $workerPath) {
    Write-Error "이미 Worker 경로가 존재합니다: $workerPath"
    exit 1
}

$existingBranch = git branch --list $workerBranch

if ($existingBranch) {
    Write-Error "이미 branch가 존재합니다: $workerBranch"
    exit 1
}

Write-Host ""
Write-Host "Worker 생성 시작"
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

# 현재 VS Code Workspace에 Worker 폴더 추가
code --add $workerPath

Write-Host ""
Write-Host "Worker 생성 완료"
Write-Host "Branch   : $workerBranch"
Write-Host "Worktree : $workerPath"
Write-Host ""
Write-Host "다음 단계: Worker 전용 터미널에서 Codex를 실행하세요."