Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Change to the app directory
WshShell.CurrentDirectory = scriptDir

' Start Flask Backend in a new window
WshShell.Run "cmd /c cd /d """ & scriptDir & "\backend"" && start ""Flask Backend"" cmd /k python app.py", 1, False

' Wait 3 seconds for backend to start
WScript.Sleep 3000

' Start React Frontend in a new window
WshShell.Run "cmd /c cd /d """ & scriptDir & "\frontend"" && start ""React Frontend"" cmd /k npm start", 1, False

' Wait 2 seconds for frontend to start
WScript.Sleep 2000

' Open the browser to the app
WshShell.Run "http://localhost:3000", 1, False

' Show a notification
MsgBox "CRM Log Summary Dashboard is starting!" & vbCrLf & vbCrLf & _
       "Backend: http://localhost:5000" & vbCrLf & _
       "Frontend: http://localhost:3000" & vbCrLf & vbCrLf & _
       "The app will open in your browser shortly.", _
       vbInformation, "CRM Log Summary"
