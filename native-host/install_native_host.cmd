@echo off
setlocal
echo Registering native messaging host for Chrome...
reg import "%~dp0register_native_host_windows.reg"
echo Registering native messaging host for Edge...
reg import "%~dp0register_native_host_edge.reg"
echo Done.
echo NOTE: Ensure allowed_origins in lan_share_host_windows.json uses your extension ID (see chrome://extensions).
