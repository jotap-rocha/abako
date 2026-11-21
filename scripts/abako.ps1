# abako.ps1 - invólucro fino da operação local (ADR 056). Sem lógica de negócio.
# Uso:  .\scripts\abako.ps1 <subcomando>      (veja: .\scripts\abako.ps1 ajuda)
# Faz só quatro coisas: acha a raiz do repositório, põe a letra do drive em MAIÚSCULO
# (com 'd:' minúsculo o Vitest carrega módulos duplicados e falha), chama o Python da .venv
# com `-m scripts.operacao` e devolve o mesmo código de saída.
# Compatível com Windows PowerShell 5.1 e PowerShell 7. Arquivo em UTF-8 com BOM (o 5.1 precisa).

$ErrorActionPreference = 'Stop'

# Saída em UTF-8 para o terminal mostrar os acentos que o Python imprime.
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $OutputEncoding = [Console]::OutputEncoding
} catch {
    # Sem console (ex.: redirecionado): segue com a codificação atual.
}
$env:PYTHONIOENCODING = 'utf-8'

function Get-RaizNormalizada {
    param([string]$Caminho)
    if ($Caminho -match '^[A-Za-z]:') {
        return $Caminho.Substring(0, 1).ToUpperInvariant() + $Caminho.Substring(1)
    }
    return $Caminho
}

$raiz = Get-RaizNormalizada (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $raiz '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    [Console]::Error.WriteLine("abako: Python da .venv não encontrado em $python")
    [Console]::Error.WriteLine('Crie o ambiente virtual primeiro (veja docs/operacao/subir-e-atualizar.md).')
    exit 1
}

Push-Location -LiteralPath $raiz
try {
    & $python -m scripts.operacao @args
    $codigo = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $codigo
