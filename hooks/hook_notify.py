"""
Hook helper - reads session data from Claude Code stdin JSON and notifies the hub.
Usage: py hook_notify.py <status>
"""
import sys
import json
import os
import urllib.request

STATUS = sys.argv[1] if len(sys.argv) > 1 else "idle"
HUB_URL = "http://127.0.0.1:5111"

try:
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}
except Exception:
    data = {}

session_id = data.get("session_id", str(os.getpid()))
project_dir = data.get("cwd", os.getcwd())

# extract project name from transcript_path
# folder format: path with : removed and / or \ replaced by -
# e.g. C:\Users\john\myproject -> C--Users-john-myproject
transcript = data.get("transcript_path", "")
if transcript:
    folder = os.path.basename(os.path.dirname(transcript))
    # build the encoded home prefix dynamically
    # format: C:\Users\name -> C--Users-name (: becomes -, \ becomes -)
    home = os.path.expanduser("~")
    home_encoded = home.replace(":", "-").replace("\\", "-").replace("/", "-")
    prefix = home_encoded + "-"
    if folder.startswith(prefix):
        project_name = folder[len(prefix):]
        if project_name:
            project_dir = home.replace("\\", "/") + "/" + project_name

# hub handles session name from VS Code window title
session_name = ""

# hub captures foreground window title on update
window_title = ""

payload = json.dumps({
    "session": str(session_id),
    "status": STATUS,
    "path": project_dir,
    **({"name": session_name} if session_name else {}),
    **({"window_title": window_title} if window_title else {})
}).encode()

try:
    req = urllib.request.Request(
        HUB_URL, data=payload,
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=2)
except Exception:
    pass
