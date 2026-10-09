# ADR-0007 Audio Embedding PostgreSQL / pgvector 통합 검증

## 현재 결과: PASS

2026-10-09 전체 재실행: 현재 validator로 전용 PostgreSQL/pgvector instance에서 production migration을 적용하고 Phase A 실제 6곡의 MSCLAP Embedding을 새로 생성하여 통합 검증했다. 결과는 `validation-result.json`에 기록했으며 최초 BLOCKED 실행은 `validation-result-blocked-initial.json`에 그대로 보존했다.

이번 실행은 Windows CPU에서 수행했다. 전용 `pgvector/pgvector:0.8.6-pg18` 컨테이너, `audio_embedding_validation` database, 전용 validation owner, `127.0.0.1:55432` loopback port 및 임시 저장소를 사용했으며 기존 `backend-postgres-1`, 개발 database와 volume은 사용하지 않았다. Production migration `0001_audio_embeddings.sql` 적용 후 검증했고, 전용 컨테이너는 실행 종료 시 정리했다.

여섯 입력 모두 SHA 확인 전후 일치했고 새 [1,1024] 대표 Embedding을 생성했다. 저장 round-trip은 6/6 exact equality, cosine은 승인 기준 `abs=1e-6`, `rtol=0`에서 30/30 PASS (최대 절대 차이 `1.1920928955078125e-07`), 전체 ranking은 6/6 exact match였으며 TopK 1/2/5도 일치했다. Tie-break, generation compatibility, duplicate/conflict, 명시적 rollback 및 새 connection에서 잔여 row 0건도 통과했다. 실제 통합 관련 테스트는 19 passed였다.

실행 보고의 `tool_sha256`은 당시 사용한 `scripts/database/validate_audio_embedding_postgres.py`의 SHA-256과 일치한다. 이 재실행은 실제 MSCLAP generation과 실제 PostgreSQL 검증을 포함한다. 전체 vector는 tracked evidence에 저장하지 않았다.

2026-10-09 전체 실행은 현재 validator로 Phase A 실제 음악 6곡을 production `AudioEmbeddingGenerator`와 실제 MSCLAP으로 새로 처리하고, 격리된 PostgreSQL/pgvector에 저장·검색했습니다. 승인된 numerical parity 기준 `absolute tolerance = 1e-6`, `relative tolerance = 0`을 실제 30개 directional comparison에 적용해 모두 통과했습니다. 이전 실행의 `REVIEW_REQUIRED` 재판정은 이 새 전체 실행으로 대체되며, 최초 `BLOCKED` 시도는 별도 파일로 보존합니다.

`validation-result.json`에는 이번 전체 재실행의 환경, 실제 generation, migration, 정책 및 측정값이 기록되어 있습니다. 최초 Docker 차단 시도는 [validation-result-blocked-initial.json](validation-result-blocked-initial.json)에 별도 보존합니다.

## 범위와 판정 기준

이번 검증은 ADR-0007의 실제 representative `[1,D]` vector를 production migration 및 repository/search 경로로 저장·검색하는 기술 검증입니다. `[8,D]` chunk vector는 저장하지 않습니다. 이번 실행에서 관측한 `D=1024`는 사용한 MSCLAP 2023 모델의 결과이며 영구 차원 규칙이 아닙니다.

- **Cosine numerical parity:** Python cosine similarity와 PostgreSQL `1 - cosine_distance` 간 절대 차이가 `1e-6` 이하인지 확인합니다. 상대 오차는 적용하지 않습니다 (`rtol=0`). 승인 범위는 이 두 수치의 비교뿐입니다.
- **Ranking parity:** 별도 기준으로 Python 및 PostgreSQL의 전체 candidate ID 순서가 정확히 같아야 합니다. tolerance/epsilon으로 순위 차이를 허용하지 않습니다.
- 위 수치 tolerance는 사용자 표시용 0~100 calibration threshold가 아니며, 검색 품질이나 음악 유사성 평가 기준도 아닙니다.

## 환경 및 격리

실제 MSCLAP 실행은 Windows CPU 환경(Python 3.11.16, `msclap 1.3.3`, `torch/torchaudio 2.1.2+cpu`)에서 수행했습니다. 별도의 일회성 Docker container `audio-embedding-validation-postgres`와 `audio_embedding_validation` DB를 사용했고 PostgreSQL 18.6 / pgvector 0.8.6을 관측했습니다. `app/repository/migrations`의 production migration `0001_audio_embeddings.sql`을 적용하고 checksum/history와 schema를 확인했습니다. 기존 `backend-postgres-1`, 개발 DB 및 업무 volume은 사용하지 않았습니다.

검증 transaction을 명시적으로 rollback했고 새 connection에서 validation row 0개를 확인했습니다. 전용 container와 ephemeral storage도 정리했습니다. 기존 개발 DB에 연결하거나 이를 변경하지 않았습니다.

## 재현 가능한 실행 절차 (PowerShell)

아래 절차는 기존 개발/업무 DB와 분리된 일회성 PostgreSQL을 준비합니다. Docker Engine이 응답하는지 먼저 확인하고 기존 backend-postgres-1, Compose container, named volume 또는 5432 port를 재사용하지 마세요.

~~~powershell
docker version
$container = 'audio-embedding-validation-postgres'
$database = 'audio_embedding_validation'
$dbUser = 'audio_validation'
$dbPort = '55432'
$cidFile = Join-Path $env:TEMP ("audio-validation-" + [guid]::NewGuid().ToString('N') + '.cid')
$existing = docker ps --all --quiet --filter "name=^/$container$"
if ($LASTEXITCODE -ne 0) { throw 'docker ps failed; refusing to proceed.' }
if ($existing) { throw "Container '$container' already exists; refusing to reuse or remove it." }
$env:VALIDATION_DB_PASSWORD = [guid]::NewGuid().ToString('N')
$containerId = $null
$containerOwned = $false
try {
  docker run --cidfile $cidFile --detach --name $container --publish 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql:rw,size=268435456 --env "POSTGRES_DB=audio_embedding_validation" --env "POSTGRES_USER=audio_validation" --env "POSTGRES_PASSWORD=$env:VALIDATION_DB_PASSWORD" --health-cmd "pg_isready -U audio_validation -d audio_embedding_validation" --health-interval 2s --health-timeout 3s --health-retries 30 pgvector/pgvector:0.8.6-pg18
  $dockerRunExitCode = $LASTEXITCODE
  if (Test-Path -LiteralPath $cidFile) {
    $candidateId = (Get-Content -LiteralPath $cidFile -Raw).Trim()
    if ($candidateId -match '^[0-9a-f]{12,64}$') {
      $containerId = $candidateId
      $containerOwned = $true
    } else {
      throw 'The cidfile does not contain a valid Docker container ID; refusing name-based cleanup.'
    }
  }
  if ($dockerRunExitCode -ne 0) { throw 'docker run failed to start the dedicated validation container.' }
  if (-not $containerOwned) { throw 'docker run succeeded but did not create a valid container ID file.' }

  $deadline = (Get-Date).AddMinutes(2)
  while ($true) {
    $health = docker inspect --format '{{.State.Health.Status}}' $containerId 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'docker inspect failed while checking container health.' }
    $health = "$health".Trim()
    if ($health -eq 'healthy') { break }
    if ($health -eq 'unhealthy') { throw 'Validation PostgreSQL container became unhealthy.' }
    if ($health -ne 'starting') { throw "Unexpected container health status: '$health'." }
    if ((Get-Date) -ge $deadline) { throw 'Timed out waiting for validation PostgreSQL container to become healthy.' }
    Start-Sleep -Seconds 2
  }

  docker exec $containerId psql -v ON_ERROR_STOP=1 -U $dbUser -d $database -c "COMMENT ON DATABASE audio_embedding_validation IS 'nsu-capstone-ai:audio-embedding-postgres-validation:v1';"
  if ($LASTEXITCODE -ne 0) { throw 'Failed to set the validation database ownership marker.' }
  docker exec $containerId psql -v ON_ERROR_STOP=1 -U $dbUser -d $database -c 'CREATE EXTENSION IF NOT EXISTS vector;'
  if ($LASTEXITCODE -ne 0) { throw 'Failed to enable pgvector in the validation database.' }
  $env:DB_HOST = '127.0.0.1'
  $env:DB_PORT = $dbPort
  $env:DB_NAME = $database
  $env:DB_USER = $dbUser
  $env:DB_PASSWORD = $env:VALIDATION_DB_PASSWORD
# Guard database identity before migration/write; never fall back to a development DB.
# Keep credentials in this PowerShell process and out of logs/evidence.
  # Apply the production migration path; schema is not created by hand.
  python -m scripts.database.migrate_embeddings
  if ($LASTEXITCODE -ne 0) { throw 'Production migration failed.' }

  # Run actual Phase A input validation, MSCLAP generation and PostgreSQL integration tests.
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
  python -m scripts.database.validate_audio_embedding_postgres --expected-database audio_embedding_validation --run-integration-tests --report "docs/experiments/audio-embedding-postgres-validation/validation-result-$runId.json"
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL/MSCLAP validation failed; inspect the report before cleanup.' }
} finally {
  if ($containerOwned) {
    docker rm --force $containerId 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Warning "Could not remove validation container ID $containerId automatically." }
  }
  Remove-Item -LiteralPath $cidFile -Force -ErrorAction SilentlyContinue
  Remove-Item Env:VALIDATION_DB_PASSWORD, Env:DB_PASSWORD, Env:DB_HOST, Env:DB_PORT, Env:DB_NAME, Env:DB_USER -ErrorAction SilentlyContinue
}
~~~

검증 CLI는 실제 연결에서 database name, 접속 user와 database owner 일치, 위 ownership marker를 확인한 뒤에만 쓰기와 migration을 허용합니다. 이름·loopback host·별도 port·전용 user·owner·marker 중 하나라도 다르면 실행이 차단됩니다. 전용 DB에 접속할 수 없거나 health polling이 실패해도 기존 개발 DB로 전환하지 않으며, `finally`는 `docker run --cidfile`에서 성공적으로 확인한 해당 container ID만 정리합니다. 이름이 이미 사용 중이면 시작 전에 중단하고 그 container는 건드리지 않습니다.

## 결과

- Phase A 6개 입력 manifest identity·SHA 확인 및 실행 전후 SHA 보존: 6/6 통과.
- Production generator: 실제 6곡 모두 `[1,1024]`, finite/non-zero, generation profile 확인 통과.
- 저장 round-trip: 6/6 exact equality 및 canonical float32 digest 일치. 차원·norm 유지, 저장 차이는 0.
- Cosine numerical parity: directional comparison 30/30 통과. 6개는 exact equality, 최대 absolute difference는 `1.1920928955078125e-07`.
- Ranking parity: 6/6 query에서 전체 candidate 순서 일치. TopK 1/2/5 일치.
- Synthetic cosine 의미(동일/직교/반대), production `music_id COLLATE "C"` tie-break, generation mismatch 제외 및 compatible control 유지, duplicate 재사용/conflict와 원본 보존, rollback 및 새 연결 row 0개: 모두 통과.

세부 입력 SHA, checkpoint/package 환경, 생성 profile, 각 comparison, 순위, migration, 격리 결과는 [validation-result.json](validation-result.json)에 있습니다. evidence의 `tool_sha256`은 실제 전체 PostgreSQL/MSCLAP 실행에 사용한 validator 파일의 SHA-256이며 실행 source와 일치합니다. 전체 vector는 Git evidence에 포함하지 않습니다.

## 한계와 제외 범위

이 검증은 한 번의 Windows CPU와 PostgreSQL 18.6/pgvector 0.8.6 실행의 저장/검색 기술 parity를 확인합니다. 다른 OS, CPU/GPU, package 또는 PostgreSQL 환경의 동일 수치 재현성을 보장하지 않습니다. 전체 similarity distribution, 검색/추천 품질, 0~100 calibration, API 및 backend lifecycle은 검증하지 않았습니다. 기존 dev/test Embedding도 삭제하거나 재생성하지 않았습니다. 재생성 대상과 입력 mapping을 확인하고 별도 승인을 받기 전에는 해당 데이터 작업을 수행하지 않습니다.
