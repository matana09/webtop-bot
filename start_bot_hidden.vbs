' Starts the bot with no visible window. Paths are relative to this file,
' so the project can live anywhere.
Set fso = CreateObject("Scripting.FileSystemObject")
botDir = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FolderExists(botDir & "\logs") Then fso.CreateFolder botDir & "\logs"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d """ & botDir & """ && python bot.py >> logs\bot.log 2>&1", 0, False
