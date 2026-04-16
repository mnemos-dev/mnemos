@echo off
rem Add a "call %USERPROFILE%\.claude\mnemos-statusline.cmd" line to your
rem statusline batch script.
rem
rem Reads %MNEMOS_VAULT%\.mnemos-hook-status.json and prints a short fragment.

if "%MNEMOS_VAULT%"=="" goto :eof
set "STATUS_FILE=%MNEMOS_VAULT%\.mnemos-hook-status.json"
if not exist "%STATUS_FILE%" goto :eof

rem Require PowerShell (always present on modern Windows). The render block
rem mirrors statusline_snippet.sh: 10-min idle TTL, "last refine Xm ago"
rem message when last_finished_at is present, softened "busy" wording.
for /f "delims=" %%i in ('powershell -NoProfile -Command "try { $j = Get-Content -Raw '%STATUS_FILE%' | ConvertFrom-Json; $now = (Get-Date).ToUniversalTime(); $elapsed = ''; if ($j.started_at) { $delta = [int]($now - [DateTime]::Parse($j.started_at).ToUniversalTime()).TotalSeconds; $elapsed = '{0}m{1}s' -f [int]($delta/60), ($delta %% 60) }; if ($j.phase -eq 'idle' -and $j.updated_at) { $idle = [int]($now - [DateTime]::Parse($j.updated_at).ToUniversalTime()).TotalSeconds; if ($idle -gt 600) { exit } }; $hasOk = $j.PSObject.Properties.Name -contains 'last_ok'; $hasSkip = $j.PSObject.Properties.Name -contains 'last_skip'; switch ($j.phase) { 'refining' { '  mnemos: refining {0}/{1} · {2} · backlog {3}' -f $j.current, $j.total, $elapsed, $j.backlog } 'mining' { '  mnemos: mining · {0} · backlog {1}' -f $elapsed, $j.backlog } 'busy' { '  mnemos: other session active' } 'idle' { if ($j.last_finished_at) { $ago = [int]($now - [DateTime]::Parse($j.last_finished_at).ToUniversalTime()).TotalMinutes; if ($j.last_outcome -eq 'noop') { '  mnemos: idle {0}m · backlog {1}' -f $ago, $j.backlog } elseif ($j.last_outcome -eq 'failed') { '  mnemos: last refine {0}m ago · FAIL · backlog {1}' -f $ago, $j.backlog } elseif (($j.last_outcome -eq 'ok' -or $j.last_outcome -eq 'skip') -and $hasOk -and $hasSkip) { if ($j.last_ok -gt 0 -and $j.last_skip -gt 0) { '  mnemos: last refine {0}m ago · {1} notes · {2} skipped · backlog {3}' -f $ago, $j.last_ok, $j.last_skip, $j.backlog } elseif ($j.last_ok -gt 0) { '  mnemos: last refine {0}m ago · {1} notes · backlog {2}' -f $ago, $j.last_ok, $j.backlog } else { '  mnemos: last refine {0}m ago · 0 notes ({1} skipped) · backlog {2}' -f $ago, $j.last_skip, $j.backlog } } else { $label = switch ($j.last_outcome) { 'ok' {'OK'} 'skip' {'SKIP'} default { $j.last_outcome } }; '  mnemos: last refine {0}m ago · {1} notes · {2} · backlog {3}' -f $ago, $j.total, $label, $j.backlog } } else { '  mnemos: done (backlog ' + $j.backlog + ')' } } default { '  mnemos: ' + $j.phase } } } catch {}"') do echo %%i
