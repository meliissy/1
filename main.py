#!/usr/bin/env python3
"""ModVC entry point: download Xray, run VLESS+XHTTP on $PORT.

ModVC only exposes the app over HTTPS (its public subdomain goes
through a Cloudflare tunnel), so this is a VLESS+XHTTP node, not
VLESS+REALITY / Hysteria2. XHTTP is used instead of WS per the user's
preference: it is plain HTTP, passes through the tunnel, and
Shadowrocket supports it. The panel is expected to set $PORT; if it
does not, we fall back to 8080 and log the port actually used.
"""
import json
import os
import stat
import subprocess
import sys
import urllib.request
import zipfile

UUID = "031f5d30-4a92-4b44-bf4f-64ac6483bb49"
WSPATH = "/ZEj5QoInC5udYjOw"
PORT = int(os.environ.get("PORT", "8080"))
XRAY_URL = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"


def ensure_xray():
    if os.path.exists("xray") and os.access("xray", os.X_OK):
        print("xray binary already present", flush=True)
        return "./xray"
    print("downloading xray...", flush=True)
    urllib.request.urlretrieve(XRAY_URL, "xray.zip")
    with zipfile.ZipFile("xray.zip") as z:
        z.extract("xray")
    os.chmod("xray", os.stat("xray").st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print("xray ready", flush=True)
    return "./xray"


def main():
    xray = ensure_xray()
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "port": PORT,
                "protocol": "vless",
                "settings": {"clients": [{"id": UUID}], "decryption": "none"},
                "streamSettings": {
                    "network": "xhttp",
                    "xhttpSettings": {"path": WSPATH, "mode": "auto"},
                },
            }
        ],
        "outbounds": [{"protocol": "freedom"}],
    }
    with open("config.json", "w") as f:
        json.dump(config, f)
    print(f"starting xray vless+xhttp on port {PORT} path {WSPATH}", flush=True)
    proc = subprocess.Popen([xray, "-config", "config.json"])
    sys.exit(proc.wait())


if __name__ == "__main__":
    main()
