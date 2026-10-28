param(
    [Parameter(Mandatory = $true)]
    [string]$Issue,

    [Parameter(Mandatory = $true)]
    [string]$Name
)

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding
$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# 1. Main 저장소 확인
# ------------------------------------------------------------

$repo = git rev-parse --show-toplevel

if (-not $repo) {
    Write-Error "Git 저장소 안에서 실행해야 합니다."
    exit 1
}

$repo = $repo.Trim()

$currentBranch = (git branch --show-current).Trim()

if ($currentBranch -ne "main") {
    Write-Error "Main worktree의 main branch에서 실행해야 합니다. 현재 branch: $currentBranch"
    exit 1
}

$status = git status --porcelain

if ($status) {
    Write-Error "Main working tree가 clean 상태가 아닙니다."
    exit 1
}

# ------------------------------------------------------------
# 2. Worker 정보 계산
# ------------------------------------------------------------

$issueSlug = $Issue.ToLower()
$nameSlug = $Name.ToLower()

$parent = Split-Path $repo -Parent
$repoName = Split-Path $repo -Leaf

$workerPath = Join-Path $parent "$repoName-$issueSlug"
$workerBranch = "feat/$issueSlug-$nameSlug"

Write-Host ""
Write-Host "Worker 정리 대상"
Write-Host "Branch   : $workerBranch"
Write-Host "Worktree : $workerPath"

# ------------------------------------------------------------
# 3. Main 최신화
# ------------------------------------------------------------

Write-Host ""
Write-Host "origin/main 최신 상태를 확인합니다..."

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

# ------------------------------------------------------------
# 4. Worker branch 존재 여부 확인
# ------------------------------------------------------------

$branchExists = git branch --list $workerBranch

if (-not $branchExists) {
    Write-Host ""
    Write-Host "Local feature branch는 이미 제거되어 있습니다."
}
else {
    # --------------------------------------------------------
    # 5. Worker branch가 main에 merge됐는지 확인
    # --------------------------------------------------------

    git merge-base --is-ancestor $workerBranch main

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Worker branch가 아직 main에 merge되지 않았습니다. Worker를 삭제하지 않습니다."
        exit 1
    }

    Write-Host ""
    Write-Host "Worker branch가 main에 merge된 것을 확인했습니다."
}

# ------------------------------------------------------------
# 6. Worker working tree 상태 확인
# ------------------------------------------------------------

if (Test-Path $workerPath) {

    Write-Host ""
    Write-Host "Worker working tree 상태를 확인합니다..."

    $workerStatus = git -C $workerPath status --porcelain

    if ($workerStatus) {
        Write-Error "Worker working tree가 clean 상태가 아닙니다. Worker를 삭제하지 않습니다."
        exit 1
    }
}
else {
    Write-Host ""
    Write-Host "Worker 디렉터리는 이미 제거되어 있습니다."
}

# ------------------------------------------------------------
# 7. VS Code Workspace에서 Worker 제거
# ------------------------------------------------------------

if (Test-Path $workerPath) {

    Write-Host ""
    Write-Host "VS Code Workspace에서 Worker를 제거합니다..."

    code --remove $workerPath

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "VS Code Workspace에서 Worker 제거에 실패했습니다."
    }
}

# ------------------------------------------------------------
# 8. Git worktree 제거
# ------------------------------------------------------------

$normalizedWorkerPath = $workerPath.Replace('\', '/')
$worktreeList = git worktree list --porcelain

$workerRegistered =
    $worktreeList -match [regex]::Escape($normalizedWorkerPath)

if ($workerRegistered) {

    Write-Host ""
    Write-Host "Worker worktree를 제거합니다..."
    Write-Host "삭제가 실패하면 Worker Codex/터미널이 해당 폴더를 사용 중인지 확인하세요."

    git worktree remove $workerPath

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Worker worktree 제거에 실패했습니다. Worker 터미널 또는 Codex를 종료한 뒤 다시 실행하세요."
        exit $LASTEXITCODE
    }
}
else {
    Write-Host ""
    Write-Host "Git worktree 등록은 이미 제거되어 있습니다."
}

# ------------------------------------------------------------
# 9. stale worktree metadata 정리
# ------------------------------------------------------------

git worktree prune

# ------------------------------------------------------------
# 10. Local feature branch 제거
# ------------------------------------------------------------

$branchExists = git branch --list $workerBranch

if ($branchExists) {

    Write-Host ""
    Write-Host "Local feature branch를 제거합니다..."

    git branch -d $workerBranch

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Local feature branch 제거에 실패했습니다."
        exit $LASTEXITCODE
    }
}
else {
    Write-Host ""
    Write-Host "Local feature branch는 이미 제거되어 있습니다."
}

# ------------------------------------------------------------
# 11. 최종 상태 확인
# ------------------------------------------------------------

Write-Host ""
Write-Host "최종 상태를 확인합니다..."

git worktree list

Write-Host ""
Write-Host "Worker 정리 완료"
Write-Host "Branch   : $workerBranch"
Write-Host "Worktree : $workerPath"
Write-Host ""
Write-Host "VS Code에 종료된 Worker 터미널이 남아 있으면 해당 터미널만 닫으세요."