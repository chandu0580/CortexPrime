"""Hold a stable URL for the governed API, and put it back when it drops.

    python scripts/demo_api_url.py
    ->  http://127.0.0.1:18120

Why this exists rather than a NodePort: the governed service is ClusterIP by
design -- the product exposes a cluster-internal address and an operator chooses
how to reach it -- and the single host port this k3d cluster maps is already
held by a live worker from an earlier phase. Recreating the cluster's load
balancer to add another would risk the environment every phase's evidence lives
in, for a convenience.

What it does instead is the thing that was actually broken: ``kubectl
port-forward`` drops under load on this machine, and it drops *quietly* -- the
process can stay alive while its tunnel is dead. This supervises it, checks the
far end rather than the socket, and rebuilds it when it stops answering. Stop
with Ctrl-C.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

NS = os.environ.get("DEMO_NAMESPACE", "cortexprime")
PORT = int(os.environ.get("DEMO_PORT", "18120"))
SERVICE = os.environ.get("DEMO_SERVICE", "svc/cortexprime-governed")
TARGET_PORT = int(os.environ.get("DEMO_TARGET_PORT", "8110"))
URL = f"http://127.0.0.1:{PORT}"


def answering() -> bool:
    """Ask the far end, not the socket.

    A dead tunnel still accepts a local connection, which is how a forward that
    had stopped working kept reporting itself healthy for most of an afternoon.
    """
    try:
        with urllib.request.urlopen(f"{URL}/healthz", timeout=3) as answer:
            return answer.status == 200
    except (urllib.error.URLError, OSError):
        return False


def start():
    return subprocess.Popen(
        ["kubectl", "-n", NS, "port-forward", SERVICE, f"{PORT}:{TARGET_PORT}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    forward = None
    restarts = 0
    print(f"holding {URL} -> {NS}/{SERVICE}:{TARGET_PORT}")
    print("  /docs     the API browser")
    print("  /healthz  liveness")
    print("  Ctrl-C to stop\n")
    try:
        while True:
            if not answering():
                if forward is not None:
                    forward.terminate()
                    restarts += 1
                    print(f"  [{time.strftime('%H:%M:%S')}] tunnel stopped "
                          f"answering; rebuilding (restart #{restarts})")
                forward = start()
                for _ in range(30):
                    if answering():
                        print(f"  [{time.strftime('%H:%M:%S')}] up at {URL}")
                        break
                    time.sleep(1)
                else:
                    print("  could not reach the runtime; is the cluster up?")
            time.sleep(3)
    except KeyboardInterrupt:
        print("\nstopped")
        return 0
    finally:
        if forward is not None:
            forward.terminate()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.default_int_handler)
    sys.exit(main())
