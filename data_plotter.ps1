<#
PowerShell setup script for Excel Plotter
- Creates (or reuses) a virtual environment in the repository
- Installs packages from requirements.txt into the venv
- Generates a simple cartoon-style icon and writes it to the user's Desktop
- Creates a Desktop shortcut named "Excel Plotter" that launches the plotter with the venv Python

Usage: run this script from PowerShell (unrestricted execution policy may be required):
  Open PowerShell as the user who should receive the desktop icon and run:
    .\data_plotter.ps1

This script tries to be safe and idempotent (won't re-create the venv if it already exists).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Helper to write status
function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg){ Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

try{
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    Write-Info "Repository root: $scriptDir"

    # Find a Python executable. Prefer 'python' then the py launcher.
    $pythonPath = $null
    try{
        $pyCmd = Get-Command python -ErrorAction SilentlyContinue
        if($pyCmd){ $pythonPath = $pyCmd.Source }
    } catch{}
    if(-not $pythonPath){
        try{
            $pyCmd = Get-Command py -ErrorAction SilentlyContinue
            if($pyCmd){
                # ask py for the recommended 3.x executable path
                $pyExe = (& py -3 -c "import sys;print(sys.executable)") 2>$null
                if($pyExe){ $pythonPath = $pyExe.Trim() }
            }
        } catch{}
    }
    if(-not $pythonPath){
        Write-Err "No Python executable found in PATH. Please install Python 3.8+ and re-run this script."; exit 2
    }
    Write-Info "Using Python: $pythonPath"

    # Virtual environment path inside repo
    $venvPath = Join-Path $scriptDir 'venv'
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'

    # Utility: prefer pythonw.exe (no console) when available next to a python executable
    function Get-Runner($pythonExePath){
        try{
            $dir = Split-Path -Parent $pythonExePath
            $pyw = Join-Path $dir 'pythonw.exe'
            if (Test-Path $pyw){ return $pyw }
        } catch{}
        return $pythonExePath
    }

    if(-not (Test-Path $venvPath)){
        Write-Info "Creating virtual environment at: $venvPath"
        & $pythonPath -m venv $venvPath
        if($LASTEXITCODE -ne 0){ Write-Err "Failed to create virtual environment."; exit 3 }
    } else {
        Write-Info "Virtualenv already exists at $venvPath"
    }

    if(-not (Test-Path $venvPython)){
        Write-Err "Could not find python inside virtualenv (expected: $venvPython)"; exit 4
    }

    # Upgrade pip and install requirements
    Write-Info "Ensuring pip/setuptools/wheel are up-to-date in the venv"
    & $venvPython -m pip install --upgrade pip setuptools wheel | Write-Info

    $reqFile = Join-Path $scriptDir 'requirements.txt'
    if(-not (Test-Path $reqFile)){
        Write-Warn "requirements.txt not found at $reqFile. Skipping pip installs."
    } else {
        Write-Info "Installing packages from requirements.txt"
        & $venvPython -m pip install -r $reqFile
        if($LASTEXITCODE -ne 0){ Write-Warn "pip reported non-zero exit code. Check the output above for details." }
    }

    # Prepare desktop paths
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop 'Excel Plotter.lnk'
    $iconPath = Join-Path $desktop 'excel_plotter.ico'

    # Create a simple cartoon icon programmatically (64x64)
    Write-Info "Generating icon at $iconPath"
    Add-Type -AssemblyName System.Drawing
    $bmp = New-Object System.Drawing.Bitmap 64,64
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::White)

    # draw axes
    $penAxis = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(200,200,200)),2
    $g.DrawLine($penAxis,8,56,56,56) # x axis
    $g.DrawLine($penAxis,12,8,12,56) # y axis

    # draw a little plot line
    $penPlot = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(30,144,255)),2
    $g.DrawLines($penPlot,([System.Drawing.Point[]]@( 
        [System.Drawing.Point]::new(14,48),
        [System.Drawing.Point]::new(22,36),
        [System.Drawing.Point]::new(30,40),
        [System.Drawing.Point]::new(38,28),
        [System.Drawing.Point]::new(46,32)
    )))

    # draw cartoon figure: head
    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::Black),2
    $g.DrawEllipse($pen,34,6,18,18)
    # body
    $g.DrawLine($pen,43,24,43,40)
    # arm holding a pen
    $g.DrawLine($pen,43,30,50,26)
    # pen tip - small line
    $penTip = New-Object System.Drawing.Pen ([System.Drawing.Color]::Black),3
    $g.DrawLine($penTip,51,25,54,23)

    $g.Dispose()

    # save bitmap to icon file via Icon.FromHandle
    try{
        $hIcon = $bmp.GetHicon()
        $icon = [System.Drawing.Icon]::FromHandle($hIcon)
        $fs = [System.IO.File]::Open($iconPath, [System.IO.FileMode]::Create)
        $icon.Save($fs)
        $fs.Close()
        # release handle
        [System.Runtime.InteropServices.Marshal]::Release($hIcon) | Out-Null
    } catch{
        Write-Warn "Could not write .ico file via System.Drawing. Falling back to saving a PNG file instead. Error: $_"
        $pngPath = [System.IO.Path]::ChangeExtension($iconPath, '.png')
        $bmp.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
        $iconPath = $pngPath
    }
    $bmp.Dispose()

    # Build target invocation: run the excel_plotter_fixed.py with a python runner (prefer pythonw to avoid console window)
    $plotterScript = Join-Path $scriptDir 'PythonScripts\Setup_GUI\Data Processing\excel_plotter_fixed.py'
    if(-not (Test-Path $plotterScript)){
        Write-Warn "Plotter script not found at expected path: $plotterScript. Shortcut will still be created but may fail to launch until the file is present."
    }

    # Create or update shortcut on Desktop
    Write-Info "Creating desktop shortcut: $shortcutPath"
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut($shortcutPath)

    # Prefer a pythonw runner (no console). If a venv exists, prefer its runner; otherwise fall back to the discovered system python.
    $targetRunner = $null
    if (Test-Path (Join-Path $venvPath 'Scripts')){
        # if the venv python exists use it
        if (Test-Path $venvPython){ $targetRunner = Get-Runner $venvPython }
    }
    if (-not $targetRunner){ $targetRunner = Get-Runner $pythonPath }

    $shortcut.TargetPath = $targetRunner
    $shortcut.WorkingDirectory = $scriptDir
    $shortcut.Arguments = "`"$plotterScript`""
    if (Test-Path $iconPath){ $shortcut.IconLocation = $iconPath }
    $shortcut.Description = 'Excel Plotter (launches the GUI)'
    $shortcut.Save()

    Write-Info "Setup complete. You can launch 'Excel Plotter' from your Desktop."
    Write-Info "If the shortcut fails to run, open a PowerShell prompt and run:`n    & `"$venvPython`" `"$plotterScript`""

} catch{
    Write-Err "Setup failed: $_"
    exit 1
}
