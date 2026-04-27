$ErrorActionPreference = 'Stop'

# Compute repo root relative to this file
# This file lives at <repo>\PythonScripts\Setup_GUI\Support_Scrips, so
# the repo root is three levels up.
$thisDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $thisDir '..\..\..')

# Desktop shortcut name and path
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Setup_GUI.lnk'
# Prefer the project's venv pythonw.exe (no console window, correct deps),
# then a real system Python, and finally pythonw.exe on PATH (skipping the
# Microsoft Store WindowsApps stub which is not a usable interpreter).
$candidates = @(
    (Join-Path $repoRoot '.venv\Scripts\pythonw.exe'),
    'C:\Program Files\Python313\pythonw.exe',
    'C:\Program Files\Python312\pythonw.exe',
    'C:\Program Files\Python311\pythonw.exe',
    'C:\Program Files\Python310\pythonw.exe'
)
$pythonw = $null
foreach ($c in $candidates) {
    if ($c -and (Test-Path $c)) { $pythonw = (Resolve-Path $c).Path; break }
}
if (-not $pythonw) {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -and ($cmd.Source -notmatch 'WindowsApps')) {
        $pythonw = $cmd.Source
    }
}
if (-not $pythonw -or -not (Test-Path $pythonw)) {
    throw "pythonw.exe not found. Create the project venv (setup_repo.ps1) or install Python."
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
$iconFile = Join-Path $thisDir 'Shortcut Icon.ico'
if (Test-Path $iconFile) {
    # Use the provided ICO file for the shortcut icon
    $sc.IconLocation = "$iconFile,0"
} else {
    # Fallback to pythonw.exe icon if the ICO isn't present
    $sc.IconLocation = "$pythonw,0"
}
$sc.Description = 'Launch Rad Effects Setup GUI'
$sc.WindowStyle = 1  # Normal window
$sc.Save()

Write-Host "Shortcut created: $shortcutPath"
