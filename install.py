"""
Auto-installer: adds Claude Status Hub hooks to your Claude Code settings.
Run: python3 install.py
"""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HOOK_SCRIPT = os.path.join(SCRIPT_DIR, "hooks", "hook_notify.py")

# find python command
python_cmd = sys.executable

# Claude Code settings path
if sys.platform == "win32":
    settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
else:
    settings_path = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")

hooks_to_add = {
    "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": python_cmd, "args": [HOOK_SCRIPT, "running"], "timeout": 3}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": python_cmd, "args": [HOOK_SCRIPT, "thinking"], "timeout": 3}]}],
    "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": python_cmd, "args": [HOOK_SCRIPT, "idle"], "timeout": 3}]}],
    "PermissionRequest": [{"matcher": "*", "hooks": [{"type": "command", "command": python_cmd, "args": [HOOK_SCRIPT, "waiting"], "timeout": 3}]}],
}

def main():
    print(f"Claude Status Hub Installer")
    print(f"Settings: {settings_path}")
    print(f"Hook script: {HOOK_SCRIPT}")
    print(f"Python: {python_cmd}")
    print()

    if not os.path.exists(HOOK_SCRIPT):
        print(f"ERROR: hook_notify.py not found at {HOOK_SCRIPT}")
        sys.exit(1)

    # load or create settings
    if os.path.exists(settings_path):
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    else:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        settings = {}

    # add hooks
    if "hooks" not in settings:
        settings["hooks"] = {}

    for event, config in hooks_to_add.items():
        if event in settings["hooks"]:
            print(f"  [skip] {event} - already configured")
        else:
            settings["hooks"][event] = config
            print(f"  [added] {event}")

    # write back
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

    print()
    print("Done! Restart your Claude Code sessions for hooks to take effect.")
    print()
    print("To start the hub:")
    if sys.platform == "win32":
        print(f'  start "" "pythonw.exe" "{os.path.join(SCRIPT_DIR, "claude_hub.py")}"')
    else:
        print(f'  python3 "{os.path.join(SCRIPT_DIR, "claude_hub.py")}" &')


if __name__ == "__main__":
    main()
