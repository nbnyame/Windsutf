Dim objShell
Set objShell = CreateObject("WScript.Shell")

Dim backendDir
backendDir = "C:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM\LogSummaryApp\backend"

Dim logFile
logFile = backendDir & "\backend_task.log"

Dim cmd
cmd = "cmd /c """ & "cd /d " & backendDir & " && python app.py >> " & logFile & " 2>&1"""

objShell.Run cmd, 0, False

Set objShell = Nothing
