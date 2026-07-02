# Claude Status Hub

A floating overlay widget that shows real-time status of your Claude Code sessions. Each session gets its own colored circle on screen that changes color based on what Claude is doing.

![Status Colors](https://img.shields.io/badge/green-idle-brightgreen) ![Status Colors](https://img.shields.io/badge/yellow-working-yellow) ![Status Colors](https://img.shields.io/badge/red-waiting%20for%20permission-red)

## Features

- Real-time status circles for each active Claude Code session
- Color-coded: green (idle), yellow (thinking/running), red (waiting for your permission)
- Audio alert (3 beeps) when a session needs your attention and VS Code is not visible
- Double-click a circle to bring its VS Code window to focus
- Tooltip shows session name on hover
- Drag circles anywhere on screen
- Right-click for options (remove, quit)
- Starts silently in background (no terminal window)
- Auto-start with Windows via Startup folder

## Requirements

- Windows 10/11 or macOS
- Python 3.10+
- PyQt5

## Installation

1. Clone the repo:
   ```
   git clone https://github.com/tomershalev-TS/claude-status-hub.git
   cd claude-status-hub
   ```

2. Install PyQt5:
   ```
   pip install PyQt5
   ```

3. Run the installer (auto-adds hooks to your Claude Code settings):
   ```
   python3 install.py
   ```

   Or manually add hooks to `~/.claude/settings.json`:
   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "*",
           "hooks": [
             {
               "type": "command",
               "command": "py",
               "args": ["C:\\path\\to\\claude-status-hub\\hooks\\hook_notify.py", "running"],
               "timeout": 3
             }
           ]
         }
       ],
       "PostToolUse": [
         {
           "matcher": "*",
           "hooks": [
             {
               "type": "command",
               "command": "py",
               "args": ["C:\\path\\to\\claude-status-hub\\hooks\\hook_notify.py", "thinking"],
               "timeout": 3
             }
           ]
         }
       ],
       "Stop": [
         {
           "matcher": "*",
           "hooks": [
             {
               "type": "command",
               "command": "py",
               "args": ["C:\\path\\to\\claude-status-hub\\hooks\\hook_notify.py", "idle"],
               "timeout": 3
             }
           ]
         }
       ],
       "PermissionRequest": [
         {
           "matcher": "*",
           "hooks": [
             {
               "type": "command",
               "command": "py",
               "args": ["C:\\path\\to\\claude-status-hub\\hooks\\hook_notify.py", "waiting"],
               "timeout": 3
             }
           ]
         }
       ]
     }
   }
   ```
   Replace `C:\\path\\to\\claude-status-hub` with the actual path where you cloned the repo.
   On macOS, use `python3` instead of `py` and forward slashes in paths.

4. Start the hub:

   **Windows:**
   ```
   start "" "C:\path\to\Python\pythonw.exe" "C:\path\to\claude-status-hub\claude_hub.py"
   ```

   **macOS:**
   ```
   python3 /path/to/claude-status-hub/claude_hub.py &
   ```

## Auto-start

**Windows:** Double-click `claude_hub.vbs` or copy it to your Startup folder:
```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

**macOS:** Add to Login Items, or create a LaunchAgent plist:
```
~/Library/LaunchAgents/com.claude-status-hub.plist
```

## How it works

1. The hub runs an HTTP server on `localhost:5111`
2. Claude Code hooks send POST requests with session status on each event
3. The hub displays floating circles and updates colors in real-time
4. Double-click uses Win32 API (Windows) or AppleScript (macOS) to find and focus the correct VS Code window

## Architecture

```
Claude Code Session ──hook──> hook_notify.py ──HTTP POST──> claude_hub.py (GUI)
```

## License

MIT
