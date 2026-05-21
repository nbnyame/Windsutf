# Adds the CRM Dashboard Flask backend to the Windows Startup folder.
# Run this script ONCE. After that the backend starts automatically at every logon.
# No admin rights required.

$vbsSource  = "C:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM\LogSummaryApp\start_backend_hidden.vbs"
$startupDir = [System.Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupDir "CRM Dashboard Backend.lnk"

# Create a .lnk shortcut pointing to wscript.exe with the VBS as argument
$shell    = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = "wscript.exe"
$shortcut.Arguments        = "`"$vbsSource`""
$shortcut.WorkingDirectory = Split-Path $vbsSource
$shortcut.WindowStyle      = 7  # Minimized (no window flash)
$shortcut.Description      = "CRM Dashboard Flask Backend"
$shortcut.Save()

if (Test-Path $shortcutPath) {
    Write-Host ""
    Write-Host "Startup shortcut created successfully." -ForegroundColor Green
    Write-Host "Location: $shortcutPath"
    Write-Host ""
    Write-Host "The Flask backend will now start automatically at every logon."
    Write-Host ""
    Write-Host "Starting it now..."
    Start-Process "wscript.exe" -ArgumentList "`"$vbsSource`""
    Start-Sleep -Seconds 4
    $running = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host "Backend is running on port 5000." -ForegroundColor Cyan
    } else {
        Write-Host "Backend may still be starting - check http://localhost:5000/api/health" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "To remove from startup later, delete:"
    Write-Host "  $shortcutPath"
} else {
    Write-Host "Failed to create startup shortcut." -ForegroundColor Red
}
