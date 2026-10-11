$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$dir = Split-Path -Parent $scriptDir
$sourceDir = Join-Path $dir 'source'
$output = Join-Path $dir 'IndoSubModSetup.exe'
$versionText = Get-Content -LiteralPath (Join-Path $sourceDir 'IndoSubMod_version.py') -Raw
if ($versionText -notmatch 'APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') { throw 'Could not read the IndoSubMod semantic version.' }
$appVersion = $Matches[1]
$guiSource = Join-Path $sourceDir 'setup_gui.cs'
$icon = Join-Path $sourceDir 'IndoSubMod.ico'
$banner = Join-Path $sourceDir 'IndoSubModBanner.png'
$logo = Join-Path $sourceDir 'IndoSubModLogo.png'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
if (-not (Test-Path $csc)) { throw 'The Windows .NET Framework C# compiler was not found.' }

$stage = Join-Path $env:TEMP ("IndoSubModSetupBuild-" + [guid]::NewGuid().ToString('N'))
$payload = Join-Path $stage 'payload'
$zip = Join-Path $stage 'IndoSubModPayload.zip'
$builtOutput = Join-Path $stage 'IndoSubModSetup.exe'
New-Item -ItemType Directory -Path $payload -Force | Out-Null
try {
    foreach ($name in @('IndoSubMod.py','requirements.txt','install.ps1','prepare_models.py','IndoSubMod_version.py','IndoSubMod.ico','IndoSubModBanner.png','IndoSubModLogo.png','AILautanModBanner.png','uninstall.ps1')) {
        Copy-Item -LiteralPath (Join-Path $sourceDir $name) -Destination (Join-Path $payload $name)
    }
    foreach ($scriptName in @('install.ps1','uninstall.ps1')) {
        $scriptPath = Join-Path $payload $scriptName
        $parseTokens = $null
        $parseErrors = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$parseTokens, [ref]$parseErrors)
        if ($parseErrors.Count -gt 0) {
            $messages = ($parseErrors | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
            throw "PowerShell syntax validation failed for $scriptName`:$([Environment]::NewLine)$messages"
        }
    }
    $generatedGui = Join-Path $stage 'setup_gui.generated.cs'
    $guiCode = [IO.File]::ReadAllText($guiSource, [Text.Encoding]::UTF8).Replace('__APP_VERSION__', $appVersion)
    $assemblyVersion = $appVersion + '.0'
    $assemblyMetadata = "`r`n[assembly: AssemblyVersion(`"$assemblyVersion`" )]`r`n[assembly: AssemblyFileVersion(`"$assemblyVersion`" )]`r`n[assembly: AssemblyProduct(`"IndoSubMod`" )]`r`n[assembly: AssemblyTitle(`"IndoSubMod Setup`" )]`r`n"
    $guiCode = $guiCode.Replace('using System.Runtime.InteropServices;', 'using System.Runtime.InteropServices;' + $assemblyMetadata)
    [IO.File]::WriteAllText($generatedGui, $guiCode, (New-Object System.Text.UTF8Encoding($false)))
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($payload, $zip, [IO.Compression.CompressionLevel]::Optimal, $false)
    $resourceArg = "/resource:$zip,IndoSubModPayload.zip"
    $bannerResourceArg = "/resource:$banner,IndoSubModBanner.png"
    $logoResourceArg = "/resource:$logo,IndoSubModLogo.png"
    & $csc /nologo /target:winexe /platform:anycpu /optimize+ "/out:$builtOutput" "/win32icon:$icon" $resourceArg $bannerResourceArg $logoResourceArg /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll $generatedGui
    if ($LASTEXITCODE -ne 0) { throw "C# installer compilation failed with exit code $LASTEXITCODE." }
    if (-not (Test-Path $builtOutput)) { throw 'The GUI installer EXE was not created.' }
    Copy-Item -LiteralPath $builtOutput -Destination $output -Force
    Write-Host "Created single-file IndoSubMod v$appVersion GUI installer: $output"
} finally {
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
