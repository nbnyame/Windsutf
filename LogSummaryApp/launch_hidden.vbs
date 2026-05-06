Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Run the Python launcher completely hidden
WshShell.Run "pythonw.exe """ & scriptDir & "\start_servers.py""", 0, False
