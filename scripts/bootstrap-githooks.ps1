# bootstrap-githooks.ps1 — configura core.hooksPath=.githooks de forma idempotente.
# Uso: .\scripts\bootstrap-githooks.ps1 [raiz-do-repo]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
Set-Location $Root

if (-not (Test-Path -LiteralPath '.githooks' -PathType Container)) {
    [Console]::Error.WriteLine("[git-hygiene] ERRO: pasta .githooks não encontrada em $Root")
    exit 1
}

if (-not (Test-Path -LiteralPath '.git')) {
    [Console]::Error.WriteLine("[git-hygiene] ERRO: $Root não é um repositório git")
    exit 1
}

# Garantir executáveis (bit +x no índice do git; no Windows chmod não se aplica ao disco)
foreach ($hook in 'pre-commit', 'commit-msg', 'pre-push') {
    $path = ".githooks/$hook"
    if (Test-Path -LiteralPath $path) {
        git update-index --chmod=+x -- $path 2>$null | Out-Null
    }
}
$global:LASTEXITCODE = 0

$current = (git config --get core.hooksPath 2>$null)
if ($current -eq '.githooks') {
    Write-Host '[git-hygiene] core.hooksPath já é .githooks (idempotente — nada a fazer).'
    exit 0
}

git config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "[git-hygiene] core.hooksPath=.githooks configurado em $Root"
git config --get core.hooksPath
