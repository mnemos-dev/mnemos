@echo off
rem Add a "call %USERPROFILE%\.claude\mnemos-statusline.cmd" line to your
rem statusline batch script.
rem
rem Reads %MNEMOS_VAULT%\.mnemos-hook-status.json and prints a short fragment.

if "%MNEMOS_VAULT%"=="" goto :eof
set "STATUS_FILE=%MNEMOS_VAULT%\.mnemos-hook-status.json"
if not exist "%STATUS_FILE%" goto :eof

rem Require PowerShell (always present on modern Windows)
for /f "delims=" %%i in ('powershell -NoProfile -Command "try { $j = Get-Content -Raw '%STATUS_FILE%' | ConvertFrom-Json; $elapsed = ''; if ($j.started_at) { $delta = [int]((Get-Date).ToUniversalTime() - [DateTime]::Parse($j.started_at).ToUniversalTime()).TotalSeconds; $elapsed = '{0}m{1}s' -f [int]($delta/60), ($delta %% 60) }; switch ($j.phase) { 'starting' { '  mnemos: starting ' + $elapsed } 'refining' { '  mnemos: refining {0}/{1} · {2} · backlog {3}' -f $j.current, $j.total, $elapsed, $j.backlog } 'mining' { '  mnemos: mining · {0} · backlog {1}' -f $elapsed, $j.backlog } 'busy' { '  mnemos: auto-refine busy' } 'idle' { '  mnemos: done (backlog ' + $j.backlog + ')' } default { '  mnemos: ' + $j.phase } } } catch {}"') do echo %%i
