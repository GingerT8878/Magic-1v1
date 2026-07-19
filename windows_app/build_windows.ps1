# Build a self-contained x64 Windows folder and portable ZIP.
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BuildRoot = Join-Path $Root "build\windows"
$DistRoot = Join-Path $Root "dist\windows"
$Venv = Join-Path $BuildRoot ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Icon = Join-Path $PSScriptRoot "AppIcon.ico"
$EncodedIcon = Join-Path $PSScriptRoot "AppIcon.ico.b64"

if (-not (Test-Path $Icon) -and (Test-Path $EncodedIcon)) {
    $IconBytes = [Convert]::FromBase64String(
        (Get-Content $EncodedIcon -Raw).Trim()
    )
    [IO.File]::WriteAllBytes($Icon, $IconBytes)
}

if (-not (Test-Path $Python)) {
    py -3.11 -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Python -m pip install `
    -r (Join-Path $Root "requirements.txt") `
    -r (Join-Path $PSScriptRoot "requirements-windows.txt")

if (Test-Path $DistRoot) {
    Remove-Item $DistRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $DistRoot | Out-Null

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $DistRoot `
    --workpath (Join-Path $BuildRoot "work") `
    (Join-Path $PSScriptRoot "Magic1v1Windows.spec")

$PortableFolder = Join-Path $DistRoot "Magic 1v1"
$PortableZip = Join-Path $DistRoot "Magic 1v1 Windows x64.zip"
Compress-Archive -Path $PortableFolder -DestinationPath $PortableZip -Force

Write-Host ""
Write-Host "Windows application:"
Write-Host "  $PortableFolder\Magic 1v1.exe"
Write-Host "Portable distribution:"
Write-Host "  $PortableZip"
