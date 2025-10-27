<#
setup_repo.ps1

Installs Python requirements from the repository's requirements.txt
and creates a Desktop shortcut to the Setup GUI launcher
(`PythonScripts\Setup_GUI\launch_setup_gui.pyw`).

Usage (PowerShell):
  powershell -ExecutionPolicy Bypass -File .\setup_repo.ps1

#>

$ErrorActionPreference = 'Stop'

Write-Host "Starting repository setup..."

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = $scriptDir

# 1) Install requirements if present
$requirements = Join-Path $repoRoot 'requirements.txt'
if (Test-Path $requirements) {
    Write-Host "Installing packages from: $requirements"
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) { $pythonCmd = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $pythonCmd) {
        Write-Error "Python not found in PATH. Please install Python 3 and ensure 'python' or 'py' is available in PATH."
        exit 1
    }
    $pythonPath = $pythonCmd.Source
    Write-Host "Using Python executable: $pythonPath"
    & $pythonPath -m pip install -r $requirements
} else {
    Write-Warning "requirements.txt not found at $requirements. Skipping pip install."
}

# 2) Create Desktop shortcut to the GUI launcher
$launcherRelative = 'PythonScripts\Setup_GUI\launch_setup_gui.pyw'
$launcherPath = Join-Path $repoRoot $launcherRelative
$supportScript = Join-Path $repoRoot 'PythonScripts\Setup_GUI\Support_Scrips\create_desktop_shortcut.ps1'

if (Test-Path $supportScript) {
    Write-Host "Found helper script at: $supportScript - running it to create the Desktop shortcut."
    # Run helper script with bypass to avoid ExecutionPolicy issues
    powershell -NoProfile -ExecutionPolicy Bypass -File $supportScript
} elseif (Test-Path $launcherPath) {
    Write-Host "Creating Desktop shortcut pointing to: $launcherPath"
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop 'Rad Effects Setup GUI.lnk'

    $WshShell = New-Object -ComObject WScript.Shell
    $sc = $WshShell.CreateShortcut($shortcutPath)
    $sc.TargetPath = $launcherPath
    $sc.WorkingDirectory = Split-Path $launcherPath

    # If pythonw is available, use its icon
    $pywCmd = Get-Command pythonw -ErrorAction SilentlyContinue
    if ($pywCmd) { $sc.IconLocation = $pywCmd.Source }
    $sc.Description = 'Launch Rad Effects Setup GUI'
    $sc.Save()
    Write-Host "Created shortcut: $shortcutPath"
} else {
    Write-Warning "Could not find launcher at $launcherPath and no helper script present. No shortcut created."
}

Write-Host "Repository setup finished. If you need a clean virtual environment, create one and re-run the script inside it."
