$ErrorActionPreference = 'Stop'

# Compute repo root relative to this file
$thisDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $thisDir '..\\..\\..\\..')

$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Rad Effects Setup GUI.lnk'
# Prefer launching setup_gui.py via pythonw.exe directly (no console window)
$pythonw = 'C:\\Program Files\\Python313\\pythonw.exe'
if (-not (Test-Path $pythonw)) {
    # Fallback to pythonw.exe on PATH if installed elsewhere (PowerShell 5.1 compatible)
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd) { $pythonw = $cmd.Source }
}
if (-not $pythonw -or -not (Test-Path $pythonw)) {
    throw "pythonw.exe not found. Ensure Python is installed or update create_desktop_shortcut.ps1."
}

$guiScript = Join-Path $thisDir '..\setup_gui.py'
if (-not (Test-Path $guiScript)) {
    throw "GUI script not found: $guiScript"
}

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($shortcutPath)
$sc.TargetPath = $pythonw
$sc.Arguments = '"' + $guiScript + '"'
$sc.WorkingDirectory = $repoRoot.ToString()
$sc.IconLocation = "$pythonw,0"
$sc.Description = 'Launch Rad Effects Setup GUI'
$sc.WindowStyle = 1  # Normal window
$sc.Save()

Write-Host "Shortcut created: $shortcutPath"
