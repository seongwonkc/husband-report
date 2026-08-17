@echo off
REM ============================================================
REM  Husband report - daily auto update (runs ~19:57 KST)
REM
REM  register : schtasks /Create /TN HusbandReport /TR D:\GitHub\husband-report\daily.cmd /SC DAILY /ST 19:57 /F
REM  run now  : schtasks /Run /TN HusbandReport
REM  remove   : schtasks /Delete /TN HusbandReport /F
REM
REM  Numbers, times, thermometer and chibi level update by themselves.
REM  The Korean write-ups in days\*.json still need Claude; days without
REM  them show a 'still being written' note on the site.
REM
REM  NOTE: this file must keep CRLF line endings (see .gitattributes).
REM        cmd.exe misparses LF-only batch files.
REM ============================================================
setlocal
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0"
if errorlevel 1 exit /b 1
if not exist logs mkdir logs

for /f "delims=" %%i in ('python -c "import datetime;print(datetime.date.today())"') do set TODAY=%%i
for /f "delims=" %%i in ('python -c "import datetime;print(datetime.date.today()-datetime.timedelta(days=1))"') do set YDAY=%%i

echo. >> logs\daily.log
echo ===== %DATE% %TIME% (today=%TODAY% yesterday=%YDAY%) ===== >> logs\daily.log

REM Re-scan yesterday too: work done after last night's 8pm run
REM was not captured by that run.
python report.py collect %YDAY%  >> logs\daily.log 2>&1
python report.py collect %TODAY% >> logs\daily.log 2>&1
python report.py build           >> logs\daily.log 2>&1
if errorlevel 1 (
  echo BUILD FAILED >> logs\daily.log
  exit /b 1
)

git add -A >> logs\daily.log 2>&1
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "auto: report update %TODAY%" >> logs\daily.log 2>&1
  git push origin main >> logs\daily.log 2>&1
  echo PUSHED >> logs\daily.log
) else (
  echo no changes >> logs\daily.log
)

endlocal
