Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Change to the app directory
WshShell.CurrentDirectory = scriptDir

' Check if node_modules exists in frontend folder
If Not fso.FolderExists(scriptDir & "\frontend\node_modules") Then
    MsgBox "Dependencies not installed!" & vbCrLf & vbCrLf & _
           "Please run 'first_time_setup.bat' first to install dependencies." & vbCrLf & vbCrLf & _
           "Location: " & scriptDir & "\first_time_setup.bat", _
           vbExclamation, "Setup Required"
    WScript.Quit
End If

' Start Flask Backend in minimized window (window mode 7 = minimized, no taskbar)
WshShell.Run "cmd /c cd /d """ & scriptDir & "\backend"" && start /min """" python app.py", 7, False

' Wait 4 seconds for backend to start
WScript.Sleep 4000

' Start React Frontend in minimized window
WshShell.Run "cmd /c cd /d """ & scriptDir & "\frontend"" && start /min """" npm start", 7, False

' Wait 8 seconds for frontend to start (React takes longer)
WScript.Sleep 8000

' Start the Python process monitor in hidden mode
WshShell.Run "pythonw.exe """ & scriptDir & "\monitor_and_cleanup.py""", 0, False

' Wait a moment for monitor to start
WScript.Sleep 1000

' Open the browser to the app
WshShell.Run "http://localhost:3000", 1, False
