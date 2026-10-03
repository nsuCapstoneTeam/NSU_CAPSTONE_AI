param([switch]$ExtractOnly)
$ErrorActionPreference = 'Stop'
$fmaRoot = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'datasets/fma'
New-Item -ItemType Directory -Force $fmaRoot | Out-Null
$fmaArchiveRoot = Join-Path $fmaRoot 'archives'
New-Item -ItemType Directory -Force $fmaArchiveRoot | Out-Null
$archives = @(
    @{ Name = 'fma_metadata'; SHA1 = 'f0df49ffe5f2a6008d7dc83c6915b31835dfe733' },
    @{ Name = 'fma_small'; SHA1 = 'ade154f733639d52e35e32f5593efe5be76c6d70' }
)
foreach ($archive in $archives) {
    $zipPath = Join-Path $fmaArchiveRoot ($archive.Name + '.zip')
    if (-not $ExtractOnly) {
        & curl.exe --fail --location --retry 3 --continue-at - --output $zipPath ('https://os.unil.cloud.switch.ch/fma/' + $archive.Name + '.zip')
        if ($LASTEXITCODE -ne 0) { throw "Download failed: $($archive.Name). Run this script again to resume." }
    }
    Write-Host "Checking SHA1: $($archive.Name)"
    # 중단 후 재개한 다운로드도 공식 체크섬이 맞아야 압축을 풀어 불완전한 음원 사용을 막는다.
    if ((Get-FileHash -LiteralPath $zipPath -Algorithm SHA1).Hash.ToLowerInvariant() -ne $archive.SHA1) {
        throw "SHA1 mismatch: $zipPath. Do not use this archive."
    }
    # FMA metadata ZIP의 bzip2 압축은 Expand-Archive가 지원하지 않아 tar를 사용한다.
    # 원본 데이터가 Git에 포함되지 않도록 작업 공간의 제외된 데이터 폴더에만 압축을 푼다.
    if ($archive.Name -eq 'fma_metadata') {
        & tar.exe -xf $zipPath -C $fmaRoot 'fma_metadata/tracks.csv'
    } else {
        & tar.exe -xf $zipPath -C $fmaRoot
    }
    if ($LASTEXITCODE -ne 0) { throw "Extraction failed: $($archive.Name)" }
}
$trackFile = Join-Path $fmaRoot 'fma_metadata/tracks.csv'
$audioRoot = Join-Path $fmaRoot 'fma_small'
$count = @(Get-ChildItem -LiteralPath $audioRoot -Recurse -Filter '*.mp3').Count
if ((Get-Item -LiteralPath $trackFile).Length -eq 0 -or $count -ne 8000) {
    throw "Incomplete dataset: expected nonempty tracks.csv and 8000 MP3 files; found $count MP3 files."
}
Write-Host "FMA ready: $fmaRoot ($count MP3 files; official SHA1 verified)"
