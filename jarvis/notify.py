"""Cross-platform desktop notifications, best-effort."""
import shutil
import subprocess
import sys
from subprocess import DEVNULL


def send_notification(title: str, message: str) -> None:
    if shutil.which("osascript"):
        argv = ["osascript", "-e", f'display notification "{message}" with title "{title}"']
    elif shutil.which("notify-send"):
        argv = ["notify-send", title, message]
    else:
        sys.stderr.write("\a")
        sys.stderr.flush()
        return

    try:
        subprocess.run(argv, timeout=5, stdout=DEVNULL, stderr=DEVNULL)
    except Exception:
        pass
