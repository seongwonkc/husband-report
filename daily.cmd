@echo off
REM ─────────────────────────────────────────────────────────────
REM  남편 리포트 자동 갱신 — 매일 저녁 8시쯤 실행됩니다.
REM  등록:  schtasks /Create /TN "HusbandReport" /TR "D:\GitHub\husband-report\daily.cmd" /SC DAILY /ST 19:57 /F
REM  해제:  schtasks /Delete /TN "HusbandReport" /F
REM  즉시 실행: schtasks /Run /TN "HusbandReport"
REM
REM  숫자·시간·온도계는 자동으로 갱신됩니다.
REM  한국어 설명(days\*.json)은 Claude 가 써야 하므로, 아직 안 쓴 날은
REM  사이트에 "정리 중" 으로 표시됩니다.
REM ─────────────────────────────────────────────────────────────
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0" || exit /b 1
if not exist logs mkdir logs

for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"') do set TODAY=%%i
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).AddDays(-1).ToString('yyyy-MM-dd')"') do set YDAY=%%i

echo. >> logs\daily.log
echo ===== %DATE% %TIME% ===== >> logs\daily.log

REM 어제치를 다시 훑습니다 — 어제 저녁 8시 이후에 한 일은
REM 어제 실행분에 안 잡혔기 때문입니다.
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
