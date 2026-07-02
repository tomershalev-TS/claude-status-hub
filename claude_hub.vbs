Set WshShell = CreateObject("WScript.Shell")
' Update paths below to match your Python and project location
WshShell.Run """pythonw.exe"" """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\claude_hub.py""", 0, False
