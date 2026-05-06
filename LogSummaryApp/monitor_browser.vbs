Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Wait a bit for browser to open
WScript.Sleep 8000

' Monitor loop - check every 5 seconds if browser is accessing localhost:3000
Dim browserRunning
browserRunning = True
Dim checkCount
checkCount = 0

While browserRunning
    WScript.Sleep 5000
    checkCount = checkCount + 1
    
    ' Check if any browser process is running and if port 3000 is being accessed
    ' We'll use a simpler approach: check if the React dev server is still serving requests
    On Error Resume Next
    
    ' Try to check if processes are still running
    Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
    Set colProcesses = objWMIService.ExecQuery("SELECT * FROM Win32_Process WHERE CommandLine LIKE '%npm start%' OR CommandLine LIKE '%react-scripts%'")
    
    ' If React process is gone, cleanup
    If colProcesses.Count = 0 And checkCount > 3 Then
        browserRunning = False
    End If
    
    ' Also check if Flask is still running
    Set colFlaskProcesses = objWMIService.ExecQuery("SELECT * FROM Win32_Process WHERE CommandLine LIKE '%app.py%'")
    
    ' After 2 minutes of monitoring, if no activity detected, assume browser closed
    If checkCount > 24 Then
        ' Check one more time if processes exist
        If colProcesses.Count = 0 Then
            browserRunning = False
        End If
    End If
    
    On Error Goto 0
Wend

' Cleanup: Kill Flask and Node processes
On Error Resume Next
WshShell.Run "taskkill /F /IM python.exe /FI ""WINDOWTITLE eq Flask Backend""", 0, False
WshShell.Run "taskkill /F /IM node.exe", 0, False
WshShell.Run "taskkill /F /IM python.exe /FI ""COMMANDLINE eq *app.py*""", 0, False
On Error Goto 0

WScript.Quit
