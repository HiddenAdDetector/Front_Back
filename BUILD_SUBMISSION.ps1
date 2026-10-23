$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root 'frontend'
$backend = Join-Path $root 'backend-spring'
$detector = Join-Path $root 'Detection_Engine'
$package = Join-Path $root 'submission\AdSentinel'
$python = if ($env:ADSENTINEL_BUILD_PYTHON) { $env:ADSENTINEL_BUILD_PYTHON } else { 'python' }

Push-Location $frontend
try {
    npm run build
} finally {
    Pop-Location
}

Push-Location $detector
try {
    & $python -m PyInstaller --noconfirm --clean --onefile --name detector_cli `
        --hidden-import google.genai --hidden-import google.genai.types `
        --hidden-import dotenv --collect-submodules google.genai detector_cli.py
} finally {
    Pop-Location
}

Push-Location $backend
try {
    mvn clean package -DskipTests
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force $package | Out-Null
Copy-Item (Join-Path $backend 'target\adsentinel-backend-0.1.0.jar') (Join-Path $package 'AdSentinel.jar') -Force
Copy-Item (Join-Path $detector 'dist\detector_cli.exe') (Join-Path $package 'detector_cli.exe') -Force
Copy-Item (Join-Path $root 'START.bat') (Join-Path $package 'START.bat') -Force
Copy-Item (Join-Path $detector '.env.example') (Join-Path $package '.env.example') -Force
Copy-Item (Join-Path $root 'USER_GUIDE.md') (Join-Path $package 'USER_GUIDE.md') -Force

$javaHomeLine = (& java -XshowSettings:properties -version 2>&1 | Select-String 'java.home =').ToString()
$javaHome = ($javaHomeLine -split '=', 2)[1].Trim()
$jlink = Join-Path $javaHome 'bin\jlink.exe'
$jmods = Join-Path $javaHome 'jmods'
$runtime = Join-Path $package 'runtime'
if (Test-Path $runtime) {
    Remove-Item -LiteralPath $runtime -Recurse -Force
}
& $jlink --module-path $jmods --add-modules ALL-MODULE-PATH --strip-debug `
    --no-header-files --no-man-pages --compress=zip-6 --output $runtime

Write-Host "Submission package created: $package"
