param([string]$Compiler = 'C:\Program Files\mingw64\bin\g++.exe')
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $Compiler)) { throw 'Provide the path to a native Windows C++20 compiler with -Compiler.' }
Push-Location $PSScriptRoot
try {
    & $Compiler -std=c++20 -O2 -static cam_tools.cpp -o cam-tools.exe
    if ($LASTEXITCODE -ne 0) { throw 'Native tool compilation failed.' }
    & $Compiler -std=c++20 -O2 -static tests/core_tests.cpp -o core-tests.exe
    if ($LASTEXITCODE -ne 0) { throw 'Native test compilation failed.' }
    & .\core-tests.exe tests/python-parity.json
    if ($LASTEXITCODE -ne 0) { throw 'Native parity tests failed.' }
    & $Compiler -std=c++20 -O2 -static analysis_name_tests.cpp -o analysis-name-tests.exe
    if ($LASTEXITCODE -ne 0) { throw 'Summary filename test compilation failed.' }
    & .\analysis-name-tests.exe
    if ($LASTEXITCODE -ne 0) { throw 'Summary filename tests failed.' }
} finally { Pop-Location }
