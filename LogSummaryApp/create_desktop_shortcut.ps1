# PowerShell script to create a desktop shortcut for the CRM Log Summary App

$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "CRM Log Summary.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "C:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM\LogSummaryApp\launch_hidden.vbs"
$Shortcut.WorkingDirectory = "C:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM\LogSummaryApp"
$Shortcut.Description = "Launch CRM Log Summary Dashboard"
$Shortcut.IconLocation = "C:\Windows\System32\shell32.dll,13"
$Shortcut.Save()

Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "Location: $ShortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now double-click 'CRM Log Summary' on your desktop to launch the app." -ForegroundColor Yellow
