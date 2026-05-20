Option Explicit

Dim fso, shell, scriptDir, pythonExe, logDir, logFile, command

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = scriptDir

pythonExe = fso.BuildPath(scriptDir, ".venv\Scripts\python.exe")
logDir = fso.BuildPath(scriptDir, "logs")
logFile = fso.BuildPath(logDir, "app_run.log")

If Not fso.FileExists(pythonExe) Then
    MsgBox "Virtual environment not found. Please run setup_windows.bat first.", vbExclamation, "SEM Microcrack Studio"
    WScript.Quit 1
End If

If Not fso.FolderExists(logDir) Then
    fso.CreateFolder(logDir)
End If

command = "%ComSpec% /c " & Chr(34) & Chr(34) & pythonExe & Chr(34) & " app.py > " & Chr(34) & logFile & Chr(34) & " 2>&1" & Chr(34)

shell.Run command, 0, False
