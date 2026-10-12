param([string]$InstallRootBase64)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
if ([string]::IsNullOrWhiteSpace($InstallRootBase64)) {
    $InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\IndoSubMod'
} else {
    $InstallRoot = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($InstallRootBase64))
}
$expectedRoot = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
$driveRoot = [IO.Path]::GetPathRoot($expectedRoot).TrimEnd('\')
$uninstallKeyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\IndoSubMod'
$registeredInstall = $null
try { $registeredInstall = (Get-ItemProperty -Path $uninstallKeyPath -Name InstallLocation -ErrorAction Stop).InstallLocation } catch { }
$registeredRoot = $null
if ($registeredInstall) { try { $registeredRoot = [IO.Path]::GetFullPath([IO.Directory]::GetParent($registeredInstall).FullName).TrimEnd('\') } catch { } }
if ($expectedRoot -eq $driveRoot -or $registeredRoot -ne $expectedRoot -or -not (Test-Path -LiteralPath (Join-Path $expectedRoot 'app\IndoSubMod.exe'))) {
    throw "Safety check failed. Refusing to remove unexpected path: $expectedRoot"
}

$answer = [System.Windows.MessageBox]::Show(
    'Remove IndoSubMod and its downloaded application/model files? Translation feedback and installation logs in LocalAppData\IndoSubMod will be kept.',
    'Uninstall IndoSubMod', [System.Windows.MessageBoxButton]::YesNo, [System.Windows.MessageBoxImage]::Warning)
if ($answer -ne 'Yes') { exit 0 }

foreach ($process in (Get-Process -Name IndoSubMod -ErrorAction SilentlyContinue)) {
    $processPath = $null
    try { $processPath = $process.MainModule.FileName } catch { }
    if ($processPath -and [IO.Path]::GetFullPath($processPath).StartsWith($expectedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}

$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$shortcutPath = Join-Path $desktop 'IndoSubMod.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $target = [IO.Path]::GetFullPath($shortcut.TargetPath)
        if ($target.StartsWith($expectedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $shortcutPath -Force
        }
    } catch { Write-Warning "Could not remove desktop shortcut: $_" }
}

Remove-Item -LiteralPath $uninstallKeyPath -Recurse -Force -ErrorAction SilentlyContinue
foreach ($name in @('app','.venv','python','source')) {
    $managedPath = Join-Path $expectedRoot $name
    if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($managedPath)).TrimEnd('\') -eq $expectedRoot -and (Test-Path -LiteralPath $managedPath)) {
        Remove-Item -LiteralPath $managedPath -Recurse -Force
    }
}
if ((Test-Path -LiteralPath $expectedRoot -PathType Container) -and -not (Get-ChildItem -LiteralPath $expectedRoot -Force | Select-Object -First 1)) {
    Remove-Item -LiteralPath $expectedRoot -Force
}
[System.Windows.MessageBox]::Show('IndoSubMod was removed. Translation feedback and install logs were kept.', 'Uninstall IndoSubMod', [System.Windows.MessageBoxButton]::OK, [System.Windows.MessageBoxImage]::Information) | Out-Null
