Option Explicit

Dim shell, fileSystem, root, launcher, executable
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

root = fileSystem.GetParentFolderName(WScript.ScriptFullName)
launcher = fileSystem.BuildPath(fileSystem.BuildPath(root, "dashboard"), "launcher.py")
shell.CurrentDirectory = root

On Error Resume Next
For Each executable In Array("pyw.exe", "pythonw.exe")
    Err.Clear
    shell.Run Quote(executable) & " " & Quote(launcher), 0, False
    If Err.Number = 0 Then WScript.Quit 0
Next
On Error GoTo 0

MsgBox "Python 3 is required to start Local Service Dashboard.", vbCritical, "Local Service Dashboard"
WScript.Quit 1

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function
