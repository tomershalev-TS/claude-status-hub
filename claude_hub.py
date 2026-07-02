"""
Claude Status Hub - Floating overlay showing real-time status of Claude Code sessions.
Each session gets its own small colored circle, stacked vertically.
Double-click opens VS Code in the project directory.
"""

import sys
import json
import os
import subprocess
import threading

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

if IS_MAC:
    os.environ["QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM"] = "1"

if IS_WIN:
    import winsound
    import ctypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from PyQt5.QtCore import Qt, QPoint, QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication, QWidget, QMenu, QAction, QToolTip
from PyQt5.QtGui import QPainter, QColor, QBrush, QFont, QPen

PORT = 5111

STATUS_COLORS = {
    "idle": QColor(0, 200, 80),        # green
    "thinking": QColor(255, 230, 0),   # bright yellow
    "running": QColor(255, 230, 0),    # bright yellow (same as thinking)
    "waiting": QColor(220, 40, 40),    # red - waiting for permission
}

CIRCLE_SIZE = 70
CIRCLE_SPACING = 10
MARGIN = 8


class SignalBridge(QObject):
    """Thread-safe bridge between HTTP server thread and Qt GUI thread."""
    update_signal = pyqtSignal(str, str, str, str, str)  # session_id, status, project_path, name, window_title
    remove_signal = pyqtSignal(str)            # session_id


class SessionCircle:
    def __init__(self, session_id, project_name, project_path):
        self.session_id = session_id
        self.project_name = project_name
        self.project_path = project_path
        self.window_title = ""
        self.status = "idle"
        self.color = STATUS_COLORS["idle"]

    def set_status(self, status):
        prev = self.status
        # don't let thinking/running overwrite waiting (permission still pending)
        if prev == "waiting" and status in ("thinking", "running"):
            return
        self.status = status
        self.color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
        if status == "waiting" and prev != "waiting":
            project_path = self.project_path
            def _maybe_play():
                if not _is_vscode_visible_by_path(project_path):
                    _play_waiting_sound()
            threading.Thread(target=_maybe_play, daemon=True).start()
            self._waiting_since = threading.Timer(60, self._waiting_timeout)
            self._waiting_since.daemon = True
            self._waiting_since.start()
        elif status != "waiting":
            if hasattr(self, "_waiting_since"):
                self._waiting_since.cancel()

    def _waiting_timeout(self):
        if self.status == "waiting":
            self.status = "idle"
            self.color = STATUS_COLORS["idle"]


class HubWidget(QWidget):
    def __init__(self, bridge):
        super().__init__()
        self.sessions = {}  # session_id -> SessionCircle
        self.bridge = bridge
        self.drag_offset = None

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._update_geometry()
        self._position_bottom_right()

        bridge.update_signal.connect(self._on_update)
        bridge.remove_signal.connect(self._on_remove)

    def _position_bottom_right(self):
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - CIRCLE_SIZE - MARGIN * 2 - 20
        y = screen.height() // 2
        self.move(x, y)

    def _update_geometry(self):
        count = max(len(self.sessions), 1)
        h = count * (CIRCLE_SIZE + CIRCLE_SPACING) + MARGIN * 2
        w = CIRCLE_SIZE + MARGIN * 2
        self.setFixedSize(w, h)

    def _on_update(self, session_id, status, project_path, name, window_title):
        new_name = name if name else _extract_project_name(project_path)
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionCircle(session_id, new_name, project_path)
            self._update_geometry()
        else:
            current = self.sessions[session_id].project_name
            if new_name not in ("…", "????", "home") and current in ("…", "????", "home"):
                self.sessions[session_id].project_name = new_name
                self.sessions[session_id].project_path = project_path

        # save window_title - only if not taken by another session
        s = self.sessions[session_id]
        if window_title and not s.window_title:
            taken = any(
                other.window_title == window_title and other.session_id != session_id
                for other in self.sessions.values()
            )
            if not taken:
                s.window_title = window_title
                display = window_title.replace(" - Visual Studio Code", "").strip()
                if display:
                    s.project_name = display[:25]

        s.set_status(status)
        self.update()
        self.show()

    def _on_remove(self, session_id):
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._update_geometry()
            self.update()
            if not self.sessions:
                self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        for i, session in enumerate(self.sessions.values()):
            x = MARGIN
            y = MARGIN + i * (CIRCLE_SIZE + CIRCLE_SPACING)

            # circle
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(session.color))
            painter.drawEllipse(x, y, CIRCLE_SIZE, CIRCLE_SIZE)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.drag_offset and event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.pos() - self.drag_offset)
        else:
            session = self._session_at(event.pos())
            if session:
                QToolTip.showText(event.globalPos(), session.project_name)
            else:
                QToolTip.hideText()

    def mouseReleaseEvent(self, event):
        self.drag_offset = None

    def mouseDoubleClickEvent(self, event):
        session = self._session_at(event.pos())
        if session:
            _focus_or_open_vscode(session.project_path, session.project_name, session.window_title)

    def contextMenuEvent(self, event):
        session = self._session_at(event.pos())
        menu = QMenu(self)
        if session:
            open_action = menu.addAction(f"Open VS Code: {session.project_name}")
            open_action.triggered.connect(
                lambda: _focus_or_open_vscode(session.project_path, session.project_name, session.window_title)
            )
            remove_action = menu.addAction("Remove")
            remove_action.triggered.connect(lambda: self._on_remove(session.session_id))
            menu.addSeparator()

        quit_action = menu.addAction("Quit Hub")
        quit_action.triggered.connect(QApplication.quit)
        menu.exec_(event.globalPos())

    def _session_at(self, pos):
        for i, session in enumerate(self.sessions.values()):
            y_start = MARGIN + i * (CIRCLE_SIZE + CIRCLE_SPACING)
            y_end = y_start + CIRCLE_SIZE
            if y_start <= pos.y() <= y_end:
                return session
        return None


def _is_vscode_visible_by_path(project_path):
    """Returns True if the foreground window is any VS Code window."""
    if IS_WIN:
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if "Visual Studio Code" in buf.value:
                    return True
        except Exception:
            pass
    elif IS_MAC:
        try:
            out = subprocess.check_output([
                "osascript", "-e",
                'tell application "System Events" to get name of first application process whose frontmost is true'
            ], timeout=3, stderr=subprocess.DEVNULL).decode().strip()
            if "Code" in out:
                return True
        except Exception:
            pass
    return False


def _play_waiting_sound():
    import time
    if IS_WIN:
        for _ in range(3):
            winsound.Beep(880, 200)
            time.sleep(0.15)
    elif IS_MAC:
        for _ in range(3):
            subprocess.Popen(["afplay", "/System/Library/Sounds/Ping.aiff"])
            time.sleep(0.3)


def _focus_or_open_vscode(project_path, project_name="", window_title=""):
    norm = project_path.replace("/", "\\").rstrip("\\") if (project_path and IS_WIN) else (project_path or "")

    if IS_WIN:
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
        found = [None]

        # strategy: 1) exact saved title, 2) words from project_name
        saved_title = window_title.lower() if window_title else ""
        search_words = [w for w in project_name.lower().replace("-", " ").replace("_", " ").split() if len(w) > 2] if project_name and project_name not in ("…", "????", "home") else []

        def enum_cb(hwnd, _):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0 and user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                title_lower = title.lower()
                if "visual studio code" in title_lower:
                    # 1) exact saved title match
                    if saved_title and saved_title == title_lower:
                        found[0] = hwnd
                        return False
                    # 2) all project name words found in title
                    if search_words and all(w in title_lower for w in search_words):
                        found[0] = hwnd
                        return False
            return True

        cb = WNDENUMPROC(enum_cb)
        user32.EnumWindows(cb, 0)

        if found[0]:
            user32.ShowWindow(found[0], 9)
            user32.SetForegroundWindow(found[0])
        else:
            subprocess.Popen(["code", norm], shell=True)

    elif IS_MAC:
        search = window_title or project_name or ""
        script = f'''
            tell application "System Events"
                set codeProcs to every process whose name is "Code"
                repeat with p in codeProcs
                    set wins to every window of p
                    repeat with w in wins
                        if name of w contains "{search}" then
                            perform action "AXRaise" of w
                            set frontmost of p to true
                            return
                        end if
                    end repeat
                end repeat
            end tell
            do shell script "code {project_path or ""}"
        '''
        subprocess.Popen(["osascript", "-e", script], stderr=subprocess.DEVNULL)


def _extract_project_name(path):
    if not path:
        return "…"
    normalized = path.replace("\\", "/").rstrip("/")
    home = os.path.expanduser("~").replace("\\", "/")
    if normalized.lower() == home.lower():
        return "…"
    parts = normalized.split("/")
    return parts[-1] if parts else "…"


class HookHandler(BaseHTTPRequestHandler):
    bridge = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        session_id = data.get("session", "default")
        status = data.get("status", "idle")
        path = data.get("path", "")
        name = data.get("name", "")

        # capture foreground VS Code window title
        window_title = ""
        if IS_WIN:
            try:
                u32 = ctypes.windll.user32
                hwnd = u32.GetForegroundWindow()
                wlen = u32.GetWindowTextLengthW(hwnd)
                if wlen > 0:
                    buf = ctypes.create_unicode_buffer(wlen + 1)
                    u32.GetWindowTextW(hwnd, buf, wlen + 1)
                    if "Visual Studio Code" in buf.value:
                        window_title = buf.value
            except Exception:
                pass
        elif IS_MAC:
            try:
                out = subprocess.check_output([
                    "osascript", "-e",
                    'tell application "System Events" to get name of front window of (first process whose frontmost is true)'
                ], timeout=2, stderr=subprocess.DEVNULL).decode().strip()
                if "Visual Studio Code" in out or "Code" in out:
                    window_title = out
            except Exception:
                pass

        if status == "closed":
            self.bridge.remove_signal.emit(session_id)
        else:
            self.bridge.update_signal.emit(session_id, status, path, name, window_title)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_server(bridge):
    HookHandler.bridge = bridge
    server = HTTPServer(("127.0.0.1", PORT), HookHandler)
    server.serve_forever()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    bridge = SignalBridge()
    widget = HubWidget(bridge)

    server_thread = threading.Thread(target=run_server, args=(bridge,), daemon=True)
    server_thread.start()

    print(f"Claude Status Hub running on http://127.0.0.1:{PORT}")
    print("Waiting for sessions... (Ctrl+C to quit)")

    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
