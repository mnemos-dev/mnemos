@echo off
rem Mnemos auto-refine + recall-briefing statusline snippet (v1.0).
rem Add a "call %USERPROFILE%\.claude\mnemos-statusline.cmd" line to your
rem statusline batch script.
rem
rem Reads %MNEMOS_VAULT%\.mnemos-hook-status.json and prints a short fragment.
rem
rem v1.0 narrative-first pivot: only `refining`, `briefing`, and `idle` phases.
rem `idle` shows last_ok note count + identity_last_refreshed marker (when set)
rem + backlog. Mirrors statusline_snippet.sh exactly.

if "%MNEMOS_VAULT%"=="" goto :eof
set "STATUS_FILE=%MNEMOS_VAULT%\.mnemos-hook-status.json"
if not exist "%STATUS_FILE%" goto :eof

rem Require PowerShell (always present on modern Windows). We render the
rem same four phases as the bash snippet: refining / briefing / idle (with
rem optional identity marker) / fallback for unknown phases.
for /f "delims=" %%i in ('powershell -NoProfile -Command "try { $j = Get-Content -Raw '%STATUS_FILE%' | ConvertFrom-Json; $idr = if ($j.PSObject.Properties.Name -contains 'identity_last_refreshed') { $j.identity_last_refreshed } else { '' }; $lastOk = if ($j.PSObject.Properties.Name -contains 'last_ok') { $j.last_ok } else { 0 }; $bk = if ($j.PSObject.Properties.Name -contains 'backlog') { $j.backlog } else { 0 }; switch ($j.phase) { 'refining' { '  mnemos: refining...' } 'briefing' { '  mnemos: briefing...' } 'idle' { if ($idr) { '  mnemos: {0} notes . identity {1} . backlog {2}' -f $lastOk, $idr, $bk } else { '  mnemos: {0} notes . backlog {1}' -f $lastOk, $bk } } default { '  mnemos: ' + $j.phase } } } catch {}"') do echo %%i
