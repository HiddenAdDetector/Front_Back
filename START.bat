@echo off
setlocal
cd /d "%~dp0"

set "JAVA_CMD=%~dp0runtime\bin\java.exe"
if not exist "%JAVA_CMD%" set "JAVA_CMD=java"

if not exist "%~dp0AdSentinel.jar" (
  echo [ERROR] AdSentinel.jar was not found in this folder.
  pause
  exit /b 1
)
if not exist "%~dp0detector_cli.exe" (
  echo [ERROR] detector_cli.exe was not found in this folder.
  pause
  exit /b 1
)

echo AdSentinel is starting...
echo The dashboard will open automatically at http://127.0.0.1:8080
echo result.json will be saved in: %CD%

if not "%ADSENTINEL_NO_BROWSER%"=="1" start "" /min powershell -NoProfile -WindowStyle Hidden -Command "$u='http://127.0.0.1:8080'; for($i=0;$i -lt 60;$i++){try{$r=Invoke-WebRequest -UseBasicParsing ($u+'/api/health') -TimeoutSec 1;if($r.StatusCode -eq 200){Start-Process $u;break}}catch{};Start-Sleep -Milliseconds 500}"

"%JAVA_CMD%" --enable-native-access=ALL-UNNAMED -jar "%~dp0AdSentinel.jar" "--detector.cli.path=%CD%\detector_cli.exe" "--submission.output.dir=%CD%"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo AdSentinel stopped with exit code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
