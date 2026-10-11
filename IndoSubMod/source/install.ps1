param(
    [string]$InstallRootBase64,
    [string]$InstallOfflineModel = '1',
    [string]$InstallOllama = '1',
    [string]$CreateDesktopShortcut = '1'
)
function ConvertTo-SetupBoolean([string]$Value, [string]$Name) {
    switch -Regex ($Value.Trim().ToLowerInvariant()) {
        '^(1|true|yes)$' { return $true }
        '^(0|false|no)$' { return $false }
        default { throw "Invalid boolean value for $Name`: $Value" }
    }
}
$InstallOfflineModel = ConvertTo-SetupBoolean $InstallOfflineModel 'InstallOfflineModel'
$InstallOllama = ConvertTo-SetupBoolean $InstallOllama 'InstallOllama'
$CreateDesktopShortcut = ConvertTo-SetupBoolean $CreateDesktopShortcut 'CreateDesktopShortcut'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'Continue'
$env:PYTHONUTF8 = '1'
if (-not [string]::IsNullOrWhiteSpace($InstallRootBase64)) {
    $InstallRoot = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($InstallRootBase64))
}
if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    $appRoot = Join-Path $env:LOCALAPPDATA 'Programs\IndoSubMod'
} else {
    $appRoot = [IO.Path]::GetFullPath($InstallRoot)
}
$pythonHome = Join-Path $appRoot 'python'
$venv = Join-Path $appRoot '.venv'
$source = Join-Path $appRoot 'source'
$appInstall = Join-Path $appRoot 'app'
$versionSource = Join-Path $PSScriptRoot 'IndoSubMod_version.py'
$versionText = Get-Content -LiteralPath $versionSource -Raw
if ($versionText -notmatch 'APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') { throw 'Could not read the IndoSubMod semantic version.' }
$appVersion = $Matches[1]
$installLogDirectory = Join-Path $env:LOCALAPPDATA 'IndoSubMod'
New-Item -ItemType Directory -Force -Path $installLogDirectory | Out-Null
$installTempDirectory = Join-Path $installLogDirectory 'Temp'
New-Item -ItemType Directory -Force -Path $installTempDirectory | Out-Null
$pythonInstaller = Join-Path $installTempDirectory 'IndoSubMod-Python-3.12.10.exe'
$env:TEMP = $installTempDirectory
$env:TMP = $installTempDirectory
$pythonInstallerLog = Join-Path $installLogDirectory 'python-install.log'
$installLog = Join-Path $installLogDirectory 'install.log'
$legacyInstallLog = Join-Path $env:LOCALAPPDATA 'IndoSub\install.log'
if (-not (Test-Path -LiteralPath $installLog) -and (Test-Path -LiteralPath $legacyInstallLog)) {
    Copy-Item -LiteralPath $legacyInstallLog -Destination $installLog
}
$transcriptStarted = $false
try {
    Start-Transcript -Path $installLog -Append -Force | Out-Null
    $transcriptStarted = $true
} catch { }

function Say([string]$Message) {
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}
function Report-SetupProgress([int]$Percent) {
    Write-Output "IndoSubMod_PROGRESS|$Percent"
}
function Report-SetupStage([string]$Stage) {
    Write-Output "IndoSubMod_STAGE|$Stage"
}

# Keep the visible setup console in front between installer stages. Windows may
# deny foreground activation in some situations, so this is deliberately best-effort.
if (-not ('IndoSubModSetup.Native' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
namespace IndoSubModSetup {
  public static class Native {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
    [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
    [DllImport("shell32.dll", CharSet=CharSet.Unicode)] public static extern void SHChangeNotify(uint eventId, uint flags, string path, IntPtr item2);
  }
}
'@
}
function Bring-SetupToFront {
    $handle = [IndoSubModSetup.Native]::GetConsoleWindow()
    if ($handle -ne [IntPtr]::Zero) {
        [void][IndoSubModSetup.Native]::ShowWindowAsync($handle, 9)
        [void][IndoSubModSetup.Native]::SetForegroundWindow($handle)
    }
}
function Invoke-NativeTool([string]$FilePath, [string[]]$Arguments) {
    $priorPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $capturedOutput = (& $FilePath @Arguments 2>&1 | Out-String)
        $capturedExitCode = $LASTEXITCODE
        return [pscustomobject]@{ ExitCode = $capturedExitCode; Output = $capturedOutput }
    } finally { $ErrorActionPreference = $priorPreference }
}

$appRootFull = [IO.Path]::GetFullPath($appRoot).TrimEnd('\')
$driveRoot = [IO.Path]::GetPathRoot($appRootFull).TrimEnd('\')
if ([string]::IsNullOrWhiteSpace($appRootFull) -or $appRootFull -eq $driveRoot) {
    throw 'Choose an IndoSubMod installation folder inside a drive, not the drive root.'
}
$uninstallKeyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\IndoSubMod'
$legacyUninstallKeyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\IndoSub'
$previousAppInstall = $null
try { $previousAppInstall = (Get-ItemProperty -Path $uninstallKeyPath -Name InstallLocation -ErrorAction SilentlyContinue).InstallLocation } catch { }
if (-not $previousAppInstall) {
    try { $previousAppInstall = (Get-ItemProperty -Path $legacyUninstallKeyPath -Name InstallLocation -ErrorAction SilentlyContinue).InstallLocation } catch { }
}
if (-not $previousAppInstall) {
    $legacyDefaultRoot = Join-Path $env:LOCALAPPDATA 'Programs\IndoSub'
    $legacyDefaultApp = Join-Path $legacyDefaultRoot 'app'
    if (Test-Path -LiteralPath (Join-Path $legacyDefaultApp 'IndoSub.exe') -PathType Leaf) { $previousAppInstall = $legacyDefaultApp }
}
$previousRoot = $null
if ($previousAppInstall) {
    try { $previousRoot = [IO.Path]::GetFullPath([IO.Directory]::GetParent($previousAppInstall).FullName).TrimEnd('\') } catch { }
}
$legacyDefaultRoot = Join-Path $env:LOCALAPPDATA 'Programs\IndoSub'
if (-not $previousRoot -and (Test-Path -LiteralPath (Join-Path $legacyDefaultRoot 'python\python.exe') -PathType Leaf)) {
    $previousRoot = [IO.Path]::GetFullPath($legacyDefaultRoot).TrimEnd('\')
    $previousAppInstall = Join-Path $previousRoot 'app'
}
$pythonRuntimeMarker = Join-Path $source 'python-runtime.path'
$pythonCandidates = @()
if (Test-Path -LiteralPath $pythonRuntimeMarker -PathType Leaf) {
    try { $pythonCandidates += (Get-Content -LiteralPath $pythonRuntimeMarker -Raw -ErrorAction Stop).Trim() } catch { }
}
if ($previousRoot) { $pythonCandidates += (Join-Path $previousRoot 'python') }
$pythonCandidates += (Join-Path $env:LOCALAPPDATA 'Programs\IndoSub\python')
$pythonCandidates += $pythonHome
$pythonCandidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312')
if ($env:ProgramFiles) { $pythonCandidates += (Join-Path $env:ProgramFiles 'Python312') }
$registeredPythonKeys = @(
    'HKCU:\Software\Python\PythonCore\3.12\InstallPath',
    'HKLM:\Software\Python\PythonCore\3.12\InstallPath',
    'HKLM:\Software\WOW6432Node\Python\PythonCore\3.12\InstallPath'
)
foreach ($keyPath in $registeredPythonKeys) {
    try {
        $key = Get-Item -LiteralPath $keyPath -ErrorAction SilentlyContinue
        if ($key) { $registeredPath = $key.GetValue(''); if ($registeredPath) { $pythonCandidates += $registeredPath } }
    } catch { }
}
$reusedPythonHome = $null
$incompleteManagedPythonHome = $null
foreach ($candidate in ($pythonCandidates | Where-Object { $_ } | Select-Object -Unique)) {
    $candidateExe = Join-Path $candidate 'python.exe'
    if (-not (Test-Path -LiteralPath $candidateExe -PathType Leaf)) { continue }
    try {
        $versionResult = Invoke-NativeTool $candidateExe @('--version')
        $runtimeVersion = $versionResult.Output.Trim()
        $versionExitCode = $versionResult.ExitCode
        if ($versionExitCode -eq 0 -and $runtimeVersion -match '^Python 3\.12\.') {
            $hasStandardLibrary = (Test-Path -LiteralPath (Join-Path $candidate 'Lib\encodings\__init__.py') -PathType Leaf) -or
                (Test-Path -LiteralPath (Join-Path $candidate 'python312.zip') -PathType Leaf)
            $runtimeCheck = 'Python standard-library files are missing.'
            $runtimeCheckExitCode = 1
            if ($hasStandardLibrary) {
                # Avoid quotes inside the -c payload: Windows PowerShell 5.1
                # strips them during native argument forwarding in some cases.
                $runtimeResult = Invoke-NativeTool $candidateExe @('-c', 'import encodings, venv, ensurepip; print(731042)')
                $runtimeCheck = $runtimeResult.Output.Trim()
                $runtimeCheckExitCode = $runtimeResult.ExitCode
            }
            if ($hasStandardLibrary -and $runtimeCheckExitCode -eq 0 -and $runtimeCheck -match '^731042$') {
                $reusedPythonHome = [IO.Path]::GetFullPath($candidate)
                break
            }
            $candidateFullPath = [IO.Path]::GetFullPath($candidate)
            $knownLegacyPython = [IO.Path]::GetFullPath((Join-Path (Join-Path $env:LOCALAPPDATA 'Programs\IndoSub') 'python'))
            $managedLegacyPython = $candidateFullPath.Equals($knownLegacyPython, [StringComparison]::OrdinalIgnoreCase) -or
                ($previousRoot -and $candidateFullPath.Equals([IO.Path]::GetFullPath((Join-Path $previousRoot 'python')), [StringComparison]::OrdinalIgnoreCase))
            $managedCurrentPython = $candidateFullPath.Equals([IO.Path]::GetFullPath($pythonHome), [StringComparison]::OrdinalIgnoreCase)
            if ($managedLegacyPython -or $managedCurrentPython) {
                $incompleteManagedPythonHome = $candidateFullPath
                Write-Host "Found an incomplete IndoSubMod-managed Python runtime at $candidateFullPath. $runtimeCheck"
            }
        }
    } catch { }
}
if ($reusedPythonHome) { $pythonHome = $reusedPythonHome }
if (Test-Path -LiteralPath $appRootFull -PathType Leaf) {
    throw 'The selected installation path is a file. Choose a folder.'
}
function Test-RecognizedIndoSubModRecoveryRoot([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return $false }
    $entries = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction Stop)
    if ($entries.Count -eq 0) { return $true }
    $allowedNames = @('app', '.venv', 'python', 'source')
    foreach ($entry in $entries) {
        if ($allowedNames -notcontains $entry.Name -or -not $entry.PSIsContainer) { return $false }
    }
    $hasAppBinary = (Test-Path -LiteralPath (Join-Path $Path 'app\IndoSubMod.exe') -PathType Leaf) -or
        (Test-Path -LiteralPath (Join-Path $Path 'app\IndoSub.exe') -PathType Leaf)
    $hasSourceSignature = ((Test-Path -LiteralPath (Join-Path $Path 'source\IndoSubMod_version.py') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $Path 'source\IndoSubMod.py') -PathType Leaf)) -or
        ((Test-Path -LiteralPath (Join-Path $Path 'source\indosub_version.py') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $Path 'source\indosub.py') -PathType Leaf))
    $hasRuntimeSignature = (Test-Path -LiteralPath (Join-Path $Path 'python\python.exe') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $Path '.venv\Scripts\python.exe') -PathType Leaf)
    return ($hasAppBinary -or $hasSourceSignature -or $hasRuntimeSignature)
}

$defaultAppRoot = Join-Path $env:LOCALAPPDATA 'Programs\IndoSubMod'
$folderExists = Test-Path -LiteralPath $appRootFull -PathType Container
$folderHasEntries = $false
if ($folderExists) { $folderHasEntries = (@(Get-ChildItem -LiteralPath $appRootFull -Force).Count -gt 0) }
$isRegisteredInstall = ($previousRoot -and $previousRoot.Equals($appRootFull, [StringComparison]::OrdinalIgnoreCase))
$isRecognizedRecovery = Test-RecognizedIndoSubModRecoveryRoot $appRootFull
if ($folderHasEntries -and -not $isRegisteredInstall -and -not $isRecognizedRecovery) {
    throw "The selected folder contains user files and is not recognized as an IndoSubMod installation: $appRootFull`nChoose an empty folder or the default application folder: $defaultAppRoot`nFiles in the selected folder were not changed.`n`nFolder tersebut berisi file pengguna dan tidak dikenali sebagai instalasi IndoSubMod.`nPilih folder kosong atau folder aplikasi standar.`nFile di folder yang dipilih tidak diubah."
}

function Assert-ManagedChildPath([string]$Parent, [string]$Path, [string]$ExpectedLeaf) {
    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd('\')
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($fullPath) -ne $parentFull -or [IO.Path]::GetFileName($fullPath) -ne $ExpectedLeaf) {
        throw "Safety check failed for managed IndoSubMod path: $fullPath"
    }
    return $fullPath
}

try {
    try { $Host.UI.RawUI.WindowTitle = "IndoSubMod Setup v$appVersion" } catch { }
    Bring-SetupToFront
    Say "Installing IndoSubMod v$appVersion for your Windows account"
    Report-SetupProgress 3
    Write-Host "Installation log: $installLog" -ForegroundColor DarkGray
    Write-Host "Installation folder: $appRootFull" -ForegroundColor DarkGray
    New-Item -ItemType Directory -Force -Path $appRoot | Out-Null
    $writeProbe = Join-Path $appRootFull ('.IndoSubMod-write-' + [guid]::NewGuid().ToString('N'))
    try { [IO.File]::WriteAllText($writeProbe, 'IndoSubMod'); Remove-Item -LiteralPath $writeProbe -Force }
    catch { Remove-Item -LiteralPath $writeProbe -Force -ErrorAction SilentlyContinue; throw "Cannot write to selected installation folder: $appRootFull. Choose a folder your Windows account can write to." }
    New-Item -ItemType Directory -Force -Path $source | Out-Null
    Copy-Item (Join-Path $PSScriptRoot 'IndoSubMod.py') (Join-Path $source 'IndoSubMod.py') -Force
    Copy-Item (Join-Path $PSScriptRoot 'prepare_models.py') (Join-Path $source 'prepare_models.py') -Force
    Copy-Item (Join-Path $PSScriptRoot 'requirements.txt') (Join-Path $source 'requirements.txt') -Force
    Copy-Item $versionSource (Join-Path $source 'IndoSubMod_version.py') -Force
    Copy-Item (Join-Path $PSScriptRoot 'IndoSubMod.ico') (Join-Path $source 'IndoSubMod.ico') -Force
    Copy-Item (Join-Path $PSScriptRoot 'IndoSubModBanner.png') (Join-Path $source 'IndoSubModBanner.png') -Force
    Copy-Item (Join-Path $PSScriptRoot 'IndoSubModLogo.png') (Join-Path $source 'IndoSubModLogo.png') -Force
    Copy-Item (Join-Path $PSScriptRoot 'AILautanModBanner.png') (Join-Path $source 'AILautanModBanner.png') -Force

    $python = Join-Path $pythonHome 'python.exe'
    if (-not $reusedPythonHome -and $incompleteManagedPythonHome) { $pythonHome = $incompleteManagedPythonHome; $python = Join-Path $pythonHome 'python.exe' }
    if (-not $reusedPythonHome) {
        Report-SetupStage 'python_download'
        Say 'Downloading Python 3.12 (one-time setup; download progress follows)'
        Report-SetupProgress 8
        Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $pythonInstaller
        $pythonSignature = Get-AuthenticodeSignature -LiteralPath $pythonInstaller
        if ($pythonSignature.Status -ne 'Valid' -or -not $pythonSignature.SignerCertificate -or $pythonSignature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
            throw 'The downloaded Python installer did not pass the Python Software Foundation signature check. The file was not executed.'
        }
        if ($incompleteManagedPythonHome) { Say 'Repairing the incomplete IndoSubMod Python runtime' } else { Say 'Installing private Python runtime' }
        Report-SetupProgress 14
        New-Item -ItemType Directory -Force -Path $pythonHome | Out-Null
        Remove-Item -LiteralPath $pythonInstallerLog -Force -ErrorAction SilentlyContinue
        $pythonArgs = @('/quiet', '/log', ('"' + $pythonInstallerLog + '"'), 'InstallAllUsers=0', ('TargetDir="' + $pythonHome + '"'), 'Include_launcher=0', 'Include_lib=1', 'Include_pip=1', 'Include_tcltk=1', 'Include_test=0', 'Include_tools=1', 'PrependPath=0', 'Shortcuts=0')
        if ($incompleteManagedPythonHome) { $pythonArgs = @('/repair') + $pythonArgs }
        $proc = Start-Process -FilePath $pythonInstaller -ArgumentList $pythonArgs -WindowStyle Hidden -PassThru
        $proc.WaitForExit()
        if ($proc.ExitCode -ne 0) { throw "Python installer exited with code $($proc.ExitCode)." }
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            throw "Python installer returned success but did not create python.exe at $python. See its diagnostic log: $pythonInstallerLog"
        }
        $runtimeResult = Invoke-NativeTool $python @('-c', 'import encodings, venv, ensurepip; print(731042)')
        $runtimeCheck = $runtimeResult.Output.Trim()
        if ($runtimeResult.ExitCode -ne 0 -or $runtimeCheck -notmatch '^731042$') { throw "Python runtime repair/installation did not pass its standard-library check. See: $pythonInstallerLog`n$runtimeCheck" }
    $pythonRuntimeHome = [IO.Path]::GetFullPath((Split-Path -Parent $python))
    [IO.File]::WriteAllText($pythonRuntimeMarker, $pythonRuntimeHome, (New-Object System.Text.UTF8Encoding($false)))
    if ($reusedPythonHome) { Say "Reusing verified Python 3.12 runtime at $pythonRuntimeHome" }
        Bring-SetupToFront
    }

    if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
        Say 'Preparing the application environment'
        Report-SetupProgress 22
        $venvResult = Invoke-NativeTool $python @('-m', 'venv', $venv)
        if ($venvResult.ExitCode -ne 0) { throw "Could not create the application environment.`n$($venvResult.Output)" }
    }
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    Say 'Downloading offline speech and translation components'
    Report-SetupStage 'dependencies'
    Report-SetupProgress 30
    Bring-SetupToFront
    $dependencyResult = Invoke-NativeTool $venvPython @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', (Join-Path $source 'requirements.txt'))
    if ($dependencyResult.ExitCode -ne 0) { throw "Could not download the required application components. Check the internet connection and try again.`n$($dependencyResult.Output)" }
    Say 'Checking the offline CPU translation runtime'
    $torchResult = Invoke-NativeTool $venvPython @('-c', 'import torch; torch.ones(1)')
    if ($torchResult.ExitCode -ne 0) {
        Say 'Repairing the CPU translation runtime from the official PyTorch repository'
        $torchInstallResult = Invoke-NativeTool $venvPython @('-m', 'pip', 'install', '--disable-pip-version-check', '--force-reinstall', '--no-deps', '--index-url', 'https://download.pytorch.org/whl/cpu', 'torch')
        if ($torchInstallResult.ExitCode -ne 0) { throw "Could not install the official CPU PyTorch runtime. Check the internet connection and review the installation log.`n$($torchInstallResult.Output)" }
        $torchResult = Invoke-NativeTool $venvPython @('-c', 'import torch; torch.ones(1)')
        if ($torchResult.ExitCode -ne 0) { throw "The official CPU PyTorch runtime did not pass its import check.`n$($torchResult.Output)" }
    }
    Report-SetupProgress 36

    if ($InstallOllama) {
        $ollamaModel = 'qwen2.5:1.5b'
        $ollamaInstaller = Join-Path $installTempDirectory 'OllamaSetup.exe'
        $ollamaExe = $null
        $ollamaCandidates = @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'),
            (Join-Path $env:ProgramFiles 'Ollama\ollama.exe')
        )
        $ollamaCommand = Get-Command 'ollama.exe' -ErrorAction SilentlyContinue
        if ($ollamaCommand) { $ollamaExe = $ollamaCommand.Source }
        if (-not $ollamaExe) { $ollamaExe = $ollamaCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1 }

        if (-not $ollamaExe) {
            Report-SetupStage 'ollama_download'
            Say 'Downloading the official Ollama installer'
            Report-SetupProgress 38
            Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $ollamaInstaller
            $ollamaSignature = Get-AuthenticodeSignature -LiteralPath $ollamaInstaller
            if ($ollamaSignature.Status -ne 'Valid' -or -not $ollamaSignature.SignerCertificate -or $ollamaSignature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Ollama Inc\.(,|$)') {
                Remove-Item -LiteralPath $ollamaInstaller -Force -ErrorAction SilentlyContinue
                throw 'The Ollama installer failed publisher signature verification. It was not executed.'
            }
            Say 'Installing Ollama from the verified official installer'
            Report-SetupProgress 42
            $ollamaInstallProcess = Start-Process -FilePath $ollamaInstaller -ArgumentList '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES' -WindowStyle Hidden -PassThru -Wait
            if ($ollamaInstallProcess.ExitCode -ne 0) { throw "The Ollama installer exited with code $($ollamaInstallProcess.ExitCode)." }
            Remove-Item -LiteralPath $ollamaInstaller -Force -ErrorAction SilentlyContinue
            $ollamaCommand = Get-Command 'ollama.exe' -ErrorAction SilentlyContinue
            if ($ollamaCommand) { $ollamaExe = $ollamaCommand.Source }
            if (-not $ollamaExe) { $ollamaExe = $ollamaCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1 }
            if (-not $ollamaExe) { throw 'Ollama setup completed but ollama.exe could not be located.' }
        } else {
            Say "Using the existing Ollama installation at $ollamaExe"
        }

        Report-SetupStage 'ollama_model'
        Say "Checking the local translation model $ollamaModel"
        Report-SetupProgress 45
        $ollamaAvailable = $false
        for ($attempt = 0; $attempt -lt 45; $attempt++) {
            try {
                $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
                $ollamaAvailable = $true
                break
            } catch { Start-Sleep -Seconds 1 }
        }
        if (-not $ollamaAvailable) {
            Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
            for ($attempt = 0; $attempt -lt 45; $attempt++) {
                try {
                    $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
                    $ollamaAvailable = $true
                    break
                } catch { Start-Sleep -Seconds 1 }
            }
        }
        if (-not $ollamaAvailable) { throw 'Ollama did not start its local API at 127.0.0.1:11434.' }
        $modelListResult = Invoke-NativeTool $ollamaExe @('list')
        $installedModels = $modelListResult.Output
        if ($modelListResult.ExitCode -ne 0) { throw "Could not list local Ollama models.`n$installedModels" }
        if ($installedModels -notmatch '(?m)^qwen2\.5:1\.5b\s') {
            Say "Downloading the local translation model $ollamaModel (about 1 GB)"
            Report-SetupProgress 47
            $modelPullResult = Invoke-NativeTool $ollamaExe @('pull', $ollamaModel)
            if (-not [string]::IsNullOrWhiteSpace($modelPullResult.Output)) {
                $modelPullResult.Output -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { Write-Host $_ }
            }
            if ($modelPullResult.ExitCode -ne 0) { throw "Could not download the Ollama model $ollamaModel. Check the internet connection and disk space, then rerun setup." }
        } else {
            Say "The local translation model $ollamaModel is already installed"
        }
        Report-SetupProgress 55
    }

    Say 'Stopping IndoSubMod and removing stale build files'
    $managedPrefix = $appRootFull + '\'
    $previousPrefix = if ($previousRoot) { $previousRoot + '\' } else { $null }
    foreach ($process in (Get-Process -Name 'IndoSubMod','IndoSub' -ErrorAction SilentlyContinue)) {
        $processPath = $null
        try { $processPath = $process.MainModule.FileName } catch { }
        if ($processPath) {
            $fullProcessPath = [IO.Path]::GetFullPath($processPath)
            if ($fullProcessPath.StartsWith($managedPrefix, [StringComparison]::OrdinalIgnoreCase) -or
                ($previousPrefix -and $previousRoot -ne $appRootFull -and $fullProcessPath.StartsWith($previousPrefix, [StringComparison]::OrdinalIgnoreCase))) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                try { Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue } catch { }
            }
        }
    }
    $buildPath = Assert-ManagedChildPath $source (Join-Path $source 'build') 'build'
    $distPath = Assert-ManagedChildPath $source (Join-Path $source 'dist') 'dist'
    $specPath = Assert-ManagedChildPath $source (Join-Path $source 'IndoSubMod.spec') 'IndoSubMod.spec'
    $existingBundleExe = Join-Path $distPath 'IndoSubMod\IndoSubMod.exe'
    $sourceAppFile = Get-Item -LiteralPath (Join-Path $source 'IndoSubMod.py')
    $sourceVersionFile = Get-Item -LiteralPath (Join-Path $source 'IndoSubMod_version.py')
    $sourceIconFile = Get-Item -LiteralPath (Join-Path $source 'IndoSubMod.ico')
    $sourceBannerFile = Get-Item -LiteralPath (Join-Path $source 'IndoSubModBanner.png')
    $sourceLogoFile = Get-Item -LiteralPath (Join-Path $source 'IndoSubModLogo.png')
    $sourceBrandLogoFile = Get-Item -LiteralPath (Join-Path $source 'AILautanModBanner.png')
    $reuseBuiltApp = (Test-Path -LiteralPath $existingBundleExe) -and
        ((Get-Item -LiteralPath $existingBundleExe).Length -gt 10000000) -and
        ((Get-Item -LiteralPath $existingBundleExe).LastWriteTime -ge $sourceAppFile.LastWriteTime) -and
        ((Get-Item -LiteralPath $existingBundleExe).LastWriteTime -ge $sourceBannerFile.LastWriteTime) -and
        ((Get-Item -LiteralPath $existingBundleExe).LastWriteTime -ge $sourceLogoFile.LastWriteTime) -and
        ((Get-Item -LiteralPath $existingBundleExe).LastWriteTime -ge $sourceBrandLogoFile.LastWriteTime) -and
        ((Get-Item -LiteralPath $existingBundleExe).LastWriteTime -ge $sourceVersionFile.LastWriteTime) -and
        ((Get-Item -LiteralPath $existingBundleExe).LastWriteTime -ge $sourceIconFile.LastWriteTime)
    if (-not $reuseBuiltApp) {
        Remove-Item -LiteralPath $buildPath, $distPath, $specPath -Recurse -Force -ErrorAction SilentlyContinue
    }

    if ($reuseBuiltApp) {
        Say 'Reusing the verified IndoSubMod.exe built in the previous setup attempt'
        Report-SetupProgress 70
    } else {
        Say 'Building IndoSubMod.exe'
        Report-SetupStage 'build'
        Bring-SetupToFront
        $iconPath = Join-Path $source 'IndoSubMod.ico'
            $iconData = "$iconPath;."
            $bannerData = "$(Join-Path $source 'IndoSubModBanner.png');."
            $logoData = "$(Join-Path $source 'IndoSubModLogo.png');."
            $brandLogoData = "$(Join-Path $source 'AILautanModBanner.png');."
        Push-Location $source
        try {
            $pyInstallerArgs = @('-m','PyInstaller','--noconfirm','--clean','--onedir','--noconsole','--name','IndoSubMod','--icon',$iconPath,'--add-data',$iconData,'--add-data',$bannerData,'--add-data',$logoData,'--add-data',$brandLogoData,'--collect-all','faster_whisper','--collect-all','ctranslate2','--collect-all','av','--collect-all','onnxruntime','--collect-all','argostranslate','--collect-all','sentencepiece','--collect-all','keyring','--collect-all','imageio_ffmpeg','--collect-binaries','torch','--hidden-import','keyring.backends.Windows','IndoSubMod.py')
            $buildResult = Invoke-NativeTool $venvPython $pyInstallerArgs
            if ($buildResult.ExitCode -ne 0) { throw "EXE build failed.`n$($buildResult.Output)" }
        } finally { Pop-Location }
        Report-SetupProgress 70
    }

    $bundle = Join-Path $source 'dist\IndoSubMod'
    $exe = Join-Path $bundle 'IndoSubMod.exe'
    if (-not (Test-Path $exe)) { throw 'The IndoSubMod.exe file was not created.' }
    $stageInstall = Assert-ManagedChildPath $appRoot (Join-Path $appRoot 'app.new') 'app.new'
    $backupInstall = Assert-ManagedChildPath $appRoot (Join-Path $appRoot 'app.previous') 'app.previous'
    $appInstallFull = Assert-ManagedChildPath $appRoot $appInstall 'app'
    $shortcutIconName = "IndoSubMod-$appVersion.ico"
    Remove-Item -LiteralPath $stageInstall, $backupInstall -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $stageInstall | Out-Null
    Get-ChildItem -LiteralPath $bundle -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $stageInstall -Recurse -Force
    }
    Copy-Item (Join-Path $PSScriptRoot 'IndoSubMod.ico') (Join-Path $stageInstall $shortcutIconName) -Force

    if ($InstallOfflineModel) {
        Say 'Downloading the selected speech and offline translation models'
        Report-SetupStage 'models'
    } else {
        Say 'Downloading the required speech recognition model'
        Report-SetupStage 'speech_model'
    }
    Report-SetupProgress 78
    Bring-SetupToFront
    $modelArguments = @()
    if (-not $InstallOfflineModel) { $modelArguments += '--skip-offline-translation' }
    $modelResult = Invoke-NativeTool $venvPython (@((Join-Path $source 'prepare_models.py')) + $modelArguments)
    if ($modelResult.ExitCode -ne 0) { throw "Offline model preparation failed. Check the internet connection and run IndoSubModSetup.exe again.`n$($modelResult.Output)" }
    Report-SetupProgress 88

    Say 'Replacing the previous IndoSubMod version'
    Report-SetupStage 'replace'
    Report-SetupProgress 91
    if (Test-Path -LiteralPath $appInstallFull) { Move-Item -LiteralPath $appInstallFull -Destination $backupInstall }
    try {
        Move-Item -LiteralPath $stageInstall -Destination $appInstallFull
    } catch {
        if ((Test-Path -LiteralPath $backupInstall) -and -not (Test-Path -LiteralPath $appInstallFull)) {
            Move-Item -LiteralPath $backupInstall -Destination $appInstallFull
        }
        throw
    }
    Remove-Item -LiteralPath $backupInstall -Recurse -Force -ErrorAction SilentlyContinue
    $legacyExe = Join-Path $appRoot 'IndoSubMod.exe'
    if ((Test-Path -LiteralPath $legacyExe) -and ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($legacyExe)) -eq $appRootFull)) {
        Remove-Item -LiteralPath $legacyExe -Force
    }

    $desktop = [Environment]::GetFolderPath('DesktopDirectory')
    $shortcutPath = Join-Path $desktop 'IndoSubMod.lnk'
    $shortcutIconPath = Join-Path $appInstallFull $shortcutIconName
    $shell = New-Object -ComObject WScript.Shell
    if ($CreateDesktopShortcut) {
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = Join-Path $appInstallFull 'IndoSubMod.exe'
        $shortcut.WorkingDirectory = $appInstallFull
        $shortcut.IconLocation = "$shortcutIconPath,0"
        $shortcut.Description = "IndoSubMod v$appVersion — Indonesian video subtitles"
        $shortcut.Save()
        [IndoSubModSetup.Native]::SHChangeNotify(0x00002000, 0x0005, $shortcutPath, [IntPtr]::Zero)
        $legacyShortcutPath = Join-Path $desktop 'IndoSub.lnk'
        if (Test-Path -LiteralPath $legacyShortcutPath) {
            $legacyShortcut = $shell.CreateShortcut($legacyShortcutPath)
            if ($previousRoot -and [IO.Path]::GetFullPath($legacyShortcut.TargetPath).StartsWith($previousRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $legacyShortcutPath -Force
                [IndoSubModSetup.Native]::SHChangeNotify(0x00002000, 0x0005, $legacyShortcutPath, [IntPtr]::Zero)
            }
        }
    } elseif (Test-Path -LiteralPath $shortcutPath) {
        $existingShortcut = $shell.CreateShortcut($shortcutPath)
        $existingTarget = [IO.Path]::GetFullPath($existingShortcut.TargetPath)
        if ($existingTarget.StartsWith($appRootFull + '\', [StringComparison]::OrdinalIgnoreCase) -or
            ($previousRoot -and $existingTarget.StartsWith($previousRoot + '\', [StringComparison]::OrdinalIgnoreCase))) {
            Remove-Item -LiteralPath $shortcutPath -Force
            [IndoSubModSetup.Native]::SHChangeNotify(0x00002000, 0x0005, $shortcutPath, [IntPtr]::Zero)
        }
    }
    $legacyShortcutPath = Join-Path $desktop 'IndoSub.lnk'
    if (Test-Path -LiteralPath $legacyShortcutPath) {
        $legacyShortcut = $shell.CreateShortcut($legacyShortcutPath)
        $legacyTarget = $legacyShortcut.TargetPath
        if ($legacyTarget -and $previousRoot -and [IO.Path]::GetFullPath($legacyTarget).StartsWith($previousRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $legacyShortcutPath -Force
            [IndoSubModSetup.Native]::SHChangeNotify(0x00002000, 0x0005, $legacyShortcutPath, [IntPtr]::Zero)
        }
    }

    Say 'Registering IndoSubMod in Windows installed apps'
    Report-SetupStage 'register'
    Report-SetupProgress 96
    $uninstallScript = Join-Path $appInstallFull 'uninstall.ps1'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination $uninstallScript -Force
    $uninstallKeyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\IndoSubMod'
    New-Item -Path $uninstallKeyPath -Force | Out-Null
    New-ItemProperty -Path $uninstallKeyPath -Name DisplayName -Value 'IndoSubMod' -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallKeyPath -Name DisplayVersion -Value $appVersion -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallKeyPath -Name Publisher -Value 'AI Lautan Mod' -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallKeyPath -Name InstallLocation -Value $appInstallFull -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallKeyPath -Name DisplayIcon -Value (Join-Path $appInstallFull $shortcutIconName) -PropertyType String -Force | Out-Null
    $installRootArgument = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($appRootFull))
    $uninstallCommand = "`"$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe`" -NoProfile -ExecutionPolicy Bypass -File `"$uninstallScript`" -InstallRootBase64 $installRootArgument"
    New-ItemProperty -Path $uninstallKeyPath -Name UninstallString -Value $uninstallCommand -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $uninstallKeyPath -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path $uninstallKeyPath -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null

    Say 'Installation complete'
    Report-SetupProgress 100
    Write-Host "Installed application: $(Join-Path $appInstallFull 'IndoSubMod.exe')" -ForegroundColor Green
    Write-Host "Desktop shortcut: $shortcutPath" -ForegroundColor Green
    Write-Host "Shortcut icon: $shortcutIconPath" -ForegroundColor Green
    Write-Host 'Uninstall entry: Windows Settings > Apps > Installed apps > IndoSubMod' -ForegroundColor Green
    Write-Host 'Starting IndoSubMod now…' -ForegroundColor Green
    $appProcess = Start-Process -FilePath (Join-Path $appInstallFull 'IndoSubMod.exe') -PassThru
    $windowReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 500
        $appProcess.Refresh()
        if ($appProcess.MainWindowHandle -ne [IntPtr]::Zero) {
            [void][IndoSubModSetup.Native]::ShowWindowAsync($appProcess.MainWindowHandle, 9)
            [void][IndoSubModSetup.Native]::SetForegroundWindow($appProcess.MainWindowHandle)
            $windowReady = $true
            break
        }
    }
    if ($windowReady) {
        Write-Host 'IndoSubMod is running. Setup will close automatically.' -ForegroundColor Green
    } elseif ($appProcess.HasExited) {
        throw "The application exited during startup. Review the installation log: $installLog"
    } else {
        Write-Host 'The app process is running and still initializing. Setup will close automatically.' -ForegroundColor Yellow
    }
    Remove-Item -LiteralPath $legacyUninstallKeyPath -Recurse -Force -ErrorAction SilentlyContinue
    if ($previousRoot -and $previousRoot -ne $appRootFull -and
        [IO.Path]::GetFullPath($previousAppInstall) -eq [IO.Path]::GetFullPath((Join-Path $previousRoot 'app')) -and
        (Test-RecognizedIndoSubModRecoveryRoot $previousRoot) -and
        ((Test-Path -LiteralPath (Join-Path $previousRoot 'app\IndoSubMod.exe')) -or
        (Test-Path -LiteralPath (Join-Path $previousRoot 'app\IndoSub.exe')) -or
        (Test-Path -LiteralPath (Join-Path $previousRoot 'source\indosub.py')))) {
        Say 'Removing the previous IndoSubMod installation folder'
        $oldManagedNames = @('app','.venv','source')
        if (-not $pythonHome.StartsWith($previousRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { $oldManagedNames += 'python' }
        foreach ($name in $oldManagedNames) {
            $oldManagedPath = Join-Path $previousRoot $name
            if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($oldManagedPath)).TrimEnd('\') -eq $previousRoot -and (Test-Path -LiteralPath $oldManagedPath)) {
                Remove-Item -LiteralPath $oldManagedPath -Recurse -Force
            }
        }
        if (-not (Get-ChildItem -LiteralPath $previousRoot -Force | Select-Object -First 1)) { Remove-Item -LiteralPath $previousRoot -Force }
    }
} catch {
    Write-Host "`nInstallation failed: $_" -ForegroundColor Red
    Write-Host "Log: $installLog" -ForegroundColor Yellow
    Write-Host 'This setup window will close automatically in 20 seconds. After resolving the issue, run IndoSubModSetup.exe again.'
    Bring-SetupToFront
    Start-Sleep -Seconds 20
    exit 1
} finally {
    if ($transcriptStarted) { try { Stop-Transcript | Out-Null } catch { } }
    Remove-Item $pythonInstaller -Force -ErrorAction SilentlyContinue
}
