' Hidden launcher for Depot Agent scheduled tasks.
' Runs a Python script silently (no console window) and appends stdout+stderr
' to a log file so we can see afterwards what happened.
'
' Usage:  wscript.exe run_hidden.vbs <script.py>  [pyexe]
'   arg 1 = script filename (relative to C:\depot-agent)
'   arg 2 = optional python exe path (default: pythonw.exe from PATH)

Option Explicit

If WScript.Arguments.Count < 1 Then
    WScript.Quit 2
End If

Dim script, pyExe, projDir, logDir, logFile, sh, cmd, exitCode
script  = WScript.Arguments(0)
projDir = "C:\depot-agent"
logDir  = projDir & "\data\logs"

If WScript.Arguments.Count >= 2 Then
    pyExe = WScript.Arguments(1)
Else
    pyExe = "C:\Python314\python.exe"
End If

' Log filename mirrors the script name.
Dim stem
stem = script
If InStr(stem, ".") > 0 Then stem = Left(stem, InStrRev(stem, ".") - 1)
logFile = logDir & "\" & stem & ".log"

Set sh = CreateObject("WScript.Shell")

' Make sure the logs folder exists.
Dim fso
Set fso = CreateObject("Scripting.FileSystemObject")
If Not fso.FolderExists(logDir) Then fso.CreateFolder(logDir)

' Timestamp the log so different runs are distinguishable.
Dim stamp
stamp = "===== " & Now & " =====" & vbCrLf

Dim ts
Set ts = fso.OpenTextFile(logFile, 8, True) ' 8 = ForAppending, True = create if missing
ts.Write stamp
ts.Close

' Run cmd hidden (0), wait for completion (True), capture output to the log.
cmd = "cmd /c """ & _
      "chcp 65001 >nul && " & _
      "set PYTHONIOENCODING=utf-8 && " & _
      "cd /d """ & projDir & """ && " & _
      """" & pyExe & """ """ & projDir & "\" & script & """" & _
      " >> """ & logFile & """ 2>&1"""

exitCode = sh.Run(cmd, 0, True)
WScript.Quit exitCode
