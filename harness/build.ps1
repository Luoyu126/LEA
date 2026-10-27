# Native Windows build: python gen.py -> gcc (WinLibs MinGW) -> bench.exe
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
& $py gen.py . win
gcc -O2 -o bench.exe bench.c kernels.S
if ($LASTEXITCODE -ne 0) { throw 'build failed' }
