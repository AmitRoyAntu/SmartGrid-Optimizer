@echo off
REM ============================================================================
REM GridWise LLM — Windows Benchmark Runner
REM Mirrors scripts/run_benchmarks.sh for Windows CMD / PowerShell.
REM
REM Reads scenarios from tests\sample_payloads.json (key: "sample_scenarios"),
REM POSTs each to /optimize-energy, validates the response shape.
REM
REM Usage:
REM   scripts\run_benchmarks.bat
REM   scripts\run_benchmarks.bat https://smartgrid-optimizer.onrender.com
REM
REM Requires: curl.exe (built into Windows 10/11) and PowerShell.
REM ============================================================================

setlocal EnableDelayedExpansion

set "BASE_URL=%~1"
if "%BASE_URL%"=="" set "BASE_URL=http://localhost:8000"
set "PAYLOAD_FILE=tests\sample_payloads.json"
set "ENDPOINT=%BASE_URL%/optimize-energy"
set "HEALTH_ENDPOINT=%BASE_URL%/health"

REM Prefer curl.exe over PowerShell's curl alias (which is Invoke-WebRequest)
set "CURL=curl.exe"
where !CURL! >nul 2>&1
if errorlevel 1 (
    set "CURL=curl"
    where !CURL! >nul 2>&1
)
if errorlevel 1 (
    echo [FAIL ] curl not found on PATH. Install curl or run from Git Bash. 1>&2
    exit /b 2
)

REM Write the PowerShell helpers to a script file ONCE so cmd.exe doesn't
REM mangle the parentheses in inline -Command blocks.
set "PS_EXTRACT=%TEMP%\gw_extract.ps1"
set "PS_VALIDATE=%TEMP%\gw_validate.ps1"

> "!PS_EXTRACT!" echo $j = Get-Content -Raw '%PAYLOAD_FILE%' ^| ConvertFrom-Json
>>"!PS_EXTRACT!" echo if (-not $j.sample_scenarios) ^{
>>"!PS_EXTRACT!" echo     Write-Error 'No sample_scenarios key found'
>>"!PS_EXTRACT!" echo     exit 1
>>"!PS_EXTRACT!" echo ^}
>>"!PS_EXTRACT!" echo $j.sample_scenarios ^| ForEach-Object ^{
>>"!PS_EXTRACT!" echo     Write-Output $_.scenario_id
>>"!PS_EXTRACT!" echo ^}

> "!PS_VALIDATE!" echo param($bodyFile)
>>"!PS_VALIDATE!" echo if (-not (Test-Path $bodyFile)) ^{
>>"!PS_VALIDATE!" echo     Write-Output 'PARSE_ERROR:no-body-file'
>>"!PS_VALIDATE!" echo     exit 0
>>"!PS_VALIDATE!" echo ^}
>>"!PS_VALIDATE!" echo try ^{
>>"!PS_VALIDATE!" echo     $raw = [System.IO.File]::ReadAllText($bodyFile)
>>"!PS_VALIDATE!" echo     if ([string]::IsNullOrWhiteSpace($raw)) ^{
>>"!PS_VALIDATE!" echo         Write-Output 'PARSE_ERROR:empty-body'
>>"!PS_VALIDATE!" echo         exit 0
>>"!PS_VALIDATE!" echo     ^}
>>"!PS_VALIDATE!" echo     $j = $raw ^| ConvertFrom-Json
>>"!PS_VALIDATE!" echo     $required = 'scenario_id','directive_interpretation','hourly_plan','total_grid_kwh','total_cost_bdt','peak_grid_kwh','plan_summary'
>>"!PS_VALIDATE!" echo     $missing = @($required ^| Where-Object { -not ($j.PSObject.Properties.Name -contains $_) })
>>"!PS_VALIDATE!" echo     if ($missing.Count -gt 0) ^{
>>"!PS_VALIDATE!" echo         Write-Output ('MISSING:' + ($missing -join ','))
>>"!PS_VALIDATE!" echo     ^} else ^{
>>"!PS_VALIDATE!" echo         Write-Output ('PLAN_LEN:' + $j.hourly_plan.Count)
>>"!PS_VALIDATE!" echo         Write-Output ('TOTAL_GRID:' + $j.total_grid_kwh)
>>"!PS_VALIDATE!" echo         Write-Output ('TOTAL_COST:' + $j.total_cost_bdt)
>>"!PS_VALIDATE!" echo         Write-Output ('PEAK_GRID:' + $j.peak_grid_kwh)
>>"!PS_VALIDATE!" echo         Write-Output ('DIR_COUNT:' + $j.directive_interpretation.Count)
>>"!PS_VALIDATE!" echo     ^}
>>"!PS_VALIDATE!" echo ^} catch ^{
>>"!PS_VALIDATE!" echo     Write-Output ('PARSE_ERROR:' + $_.Exception.Message)
>>"!PS_VALIDATE!" echo ^}

echo [run-bench] Base URL:    %BASE_URL%
echo [run-bench] Endpoint:    %ENDPOINT%
echo [run-bench] Payloads:    %PAYLOAD_FILE%
echo [run-bench] curl:        !CURL!
echo.

REM --- /health pre-flight ---
echo [run-bench] Checking %HEALTH_ENDPOINT% ...
!CURL! -s -o "%TEMP%\gw_health_body.json" -w "%%{http_code}" --max-time 30 "%HEALTH_ENDPOINT%" > "%TEMP%\gw_health_code.txt" 2>nul
set /p HEALTH_CODE=<"%TEMP%\gw_health_code.txt"
if "!HEALTH_CODE!"=="" set "HEALTH_CODE=000"
if not "!HEALTH_CODE!"=="200" (
    echo [FAIL ] /health returned !HEALTH_CODE! ^(expected 200^). 1>&2
    if exist "%TEMP%\gw_health_body.json" (
        echo ----- response body -----
        type "%TEMP%\gw_health_body.json"
        echo.
        echo -------------------------
    )
    exit /b 3
)
echo [ OK  ] /health is 200
echo.

REM --- Extract list of scenarios ---
powershell -NoProfile -ExecutionPolicy Bypass -File "!PS_EXTRACT!" > "%TEMP%\gw_scenarios.txt" 2>nul
if errorlevel 1 (
    echo [FAIL ] Failed to read scenarios from %PAYLOAD_FILE% 1>&2
    type "%TEMP%\gw_scenarios.txt" 2>nul
    exit /b 2
)

set TOTAL=0
set PASSED=0
set FAILED=0
set FAILED_SCENARIOS=

for /f "usebackq delims=" %%S in ("%TEMP%\gw_scenarios.txt") do (
    set /a TOTAL+=1
    set "SCENARIO_ID=%%S"

    echo [run-bench] ----------------------------------------------------
    echo [run-bench] Scenario: !SCENARIO_ID!

    set "BODY_FILE=%TEMP%\gw_!SCENARIO_ID!_body.json"
    set "REQ_FILE=%TEMP%\gw_!SCENARIO_ID!_req.json"
    set "PARSE_FILE=%TEMP%\gw_!SCENARIO_ID!_parse.txt"

    REM Extract this scenario as a single JSON object
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$j = Get-Content -Raw '%PAYLOAD_FILE%' | ConvertFrom-Json;" ^
        "$sub = $j.sample_scenarios | Where-Object { $_.scenario_id -eq '!SCENARIO_ID!' } | Select-Object -First 1;" ^
        "if ($null -eq $sub) { Write-Error 'not found'; exit 1 };" ^
        "$sub | ConvertTo-Json -Compress -Depth 50" > "!REQ_FILE!" 2>nul

    if errorlevel 1 (
        echo [FAIL ] Could not extract scenario !SCENARIO_ID! from JSON 1>&2
        set /a FAILED+=1
        set "FAILED_SCENARIOS=!FAILED_SCENARIOS! !SCENARIO_ID!"
    ) else (
        REM POST via curl.exe
        set START_MS=
        for /f %%I in ('powershell -NoProfile -Command "[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()"') do set START_MS=%%I

        !CURL! -s -o "!BODY_FILE!" -w "%%{http_code}" ^
            --max-time 60 ^
            -H "Content-Type: application/json" ^
            -X POST ^
            --data-binary "@!REQ_FILE!" ^
            "%ENDPOINT%" > "%TEMP%\gw_!SCENARIO_ID!_code.txt" 2>nul

        set /p HTTP_CODE=<"%TEMP%\gw_!SCENARIO_ID!_code.txt"
        if "!HTTP_CODE!"=="" set "HTTP_CODE=000"

        for /f %%I in ('powershell -NoProfile -Command "[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()"') do set END_MS=%%I
        set /a LATENCY_MS=END_MS - START_MS

        if exist "!BODY_FILE!" (
            for %%Z in ("!BODY_FILE!") do set "RESP_BYTES=%%~zZ"
        ) else (
            set "RESP_BYTES=0"
        )

        echo.
        echo   HTTP:    !HTTP_CODE!
        echo   Latency: !LATENCY_MS! ms
        echo   Size:    !RESP_BYTES! bytes

        REM Validate using the pre-written PS script file (no inline parens)
        powershell -NoProfile -ExecutionPolicy Bypass -File "!PS_VALIDATE!" -bodyFile "!BODY_FILE!" > "!PARSE_FILE!" 2>nul

        echo.
        type "!PARSE_FILE!"
        echo.

        set "ERRORS="
        if not "!HTTP_CODE!"=="200" set "ERRORS=!ERRORS! HTTP_!HTTP_CODE!"
        findstr /b "PARSE_ERROR" "!PARSE_FILE!" >nul && set "ERRORS=!ERRORS! PARSE_ERROR"
        findstr /b "MISSING:" "!PARSE_FILE!" >nul && set "ERRORS=!ERRORS! MISSING_FIELDS"

        REM Latency check
        if !LATENCY_MS! gtr 5000 set "ERRORS=!ERRORS! LATENCY_OVER_5000MS"

        if "!ERRORS!"=="" (
            echo [ OK  ] !SCENARIO_ID! passed
            set /a PASSED+=1
        ) else (
            echo [FAIL ] !SCENARIO_ID! errors:!ERRORS! 1>&2
            set /a FAILED+=1
            set "FAILED_SCENARIOS=!FAILED_SCENARIOS! !SCENARIO_ID!"
        )
    )
)

echo [run-bench] ============================================================
echo [run-bench] Summary: !PASSED!/!TOTAL! passed, !FAILED! failed
echo [run-bench] Endpoint:  %BASE_URL%

REM Clean up temp PS scripts
del "!PS_EXTRACT!" 2>nul
del "!PS_VALIDATE!" 2>nul

if !FAILED! gtr 0 (
    echo [FAIL ] Failed scenarios:!FAILED_SCENARIOS! 1>&2
    endlocal & exit /b 1
)

echo [ OK  ] All benchmarks passed
endlocal & exit /b 0
