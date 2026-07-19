@echo off
rem Friendly entry point for people building from Windows Explorer.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if errorlevel 1 pause
