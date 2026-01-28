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

# Ensure we are running elevated for system-wide installs
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Re-launching with Administrator privileges for system-wide install..."
    $scriptPath = $MyInvocation.MyCommand.Definition
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" -Verb RunAs
    exit
}

function Get-Python313Path {
    $pyPath = $null

    # Prefer python if it is already 3.13
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        try {
            $ver = & $pythonCmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($ver -eq '3.13') { return $pythonCmd.Source }
        } catch {}
    }

    # Try py launcher for 3.13
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $path = & $pyLauncher.Source -3.13 -c "import sys; print(sys.executable)" 2>$null
            if ($path) { return $path }
        } catch {}
    }

    return $null
}

# 0) Ensure Python 3.13 is available (system-wide)
$pythonPath = Get-Python313Path
if (-not $pythonPath) {
    Write-Host "Python 3.13 not found. Attempting system-wide install via winget..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Error "winget is not available. Please install Python 3.13 manually, then re-run this script."
        exit 1
    }

    & $winget.Source install -e --id Python.Python.3.13 --scope machine
    $pythonPath = Get-Python313Path
    if (-not $pythonPath) {
        Write-Error "Python 3.13 install did not complete. Please install Python 3.13 manually, then re-run this script."
        exit 1
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = $scriptDir

# 1) Install requirements if present
$requirements = Join-Path $repoRoot 'requirements.txt'
if (Test-Path $requirements) {
    Write-Host "Installing packages from: $requirements"
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
