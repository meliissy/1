#!/usr/bin/env python3
"""ModVC entry point: download Xray, run VLESS+XHTTP on $PORT.

ModVC only exposes the app over HTTPS (its public subdomain goes
through a Cloudflare tunnel), so this is a VLESS+XHTTP node, not
VLESS+REALITY / Hysteria2. XHTTP is used instead of WS per the user's
preference: it is plain HTTP, passes through the tunnel, and
Shadowrocket supports it. The panel is expected to set $PORT; if it
does not, we fall back to 8080 and log the port actually used.

Cloudflared is created directly on this server: if no cloudflared
login certificate is present, `cloudflared tunnel login` is run and
its authorization URL is printed to the logs, then a tunnel named
edge-1021 is created on the server, routed to infrlo.kktv.eu.org,
and run alongside Xray pointing at the local XHTTP port. No token
is used and no credential is written into this file.
"""
import glob
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
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
TUNNEL_NAME = "edge-1021"
HOSTNAME = "infrlo.kktv.eu.org"
CF_DIR = os.path.join(os.path.expanduser("~"), ".cloudflared")


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


def ensure_cloudflared():
    if os.path.exists("cloudflared") and os.access("cloudflared", os.X_OK):
        print("cloudflared binary already present", flush=True)
        return "./cloudflared"
    print("downloading cloudflared...", flush=True)
    urllib.request.urlretrieve(CLOUDFLARED_URL, "cloudflared")
    os.chmod("cloudflared", os.stat("cloudflared").st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print("cloudflared ready", flush=True)
    return "./cloudflared"


def run_streamed(cmd):
    print("running: " + " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        print(line, end="", flush=True)
    code = proc.wait()
    print(f"command finished with exit code {code}", flush=True)
    return code


def setup_cloudflared():
    cloudflared = ensure_cloudflared()
    os.makedirs(CF_DIR, exist_ok=True)
    cert = os.path.join(CF_DIR, "cert.pem")
    if not (os.path.exists(cert) and os.path.getsize(cert) > 0):
        print("cloudflared login required: open the login URL printed next in the logs and authorize the Cloudflare account that owns kktv.eu.org, then this process will continue", flush=True)
        run_streamed([cloudflared, "tunnel", "login"])
    if not (os.path.exists(cert) and os.path.getsize(cert) > 0):
        print("cloudflared login certificate is still missing; cloudflared will not start", flush=True)
        return None
    print("cloudflared login certificate present", flush=True)
    code = run_streamed([cloudflared, "tunnel", "create", TUNNEL_NAME])
    if code != 0:
        print("cloudflared tunnel create did not succeed; the tunnel may already exist", flush=True)
    jsons = glob.glob(os.path.join(CF_DIR, "*.json"))
    if not jsons:
        print("no cloudflared tunnel credentials file found; cloudflared will not start", flush=True)
        return None
    jsons.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    tunnel_json = jsons[0]
    tunnel_id = os.path.splitext(os.path.basename(tunnel_json))[0]
    print(f"cloudflared tunnel credentials file: {tunnel_json}", flush=True)
    config_path = os.path.join(CF_DIR, "config.yml")
    with open(config_path, "w") as f:
        f.write(f"tunnel: {tunnel_id}\n")
        f.write(f"credentials-file: {tunnel_json}\n")
        f.write("ingress:\n")
        f.write(f"  - hostname: {HOSTNAME}\n")
        f.write(f"    service: http://127.0.0.1:{PORT}\n")
        f.write("  - service: http_status:404\n")
    run_streamed([cloudflared, "tunnel", "route", "dns", "--overwrite-dns", TUNNEL_NAME, HOSTNAME])
    print("starting cloudflared named tunnel", flush=True)
    return subprocess.Popen([cloudflared, "tunnel", "--config", config_path, "run"])


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
    cf_proc = setup_cloudflared()
    try:
        code = proc.wait()
    finally:
        if cf_proc is not None and cf_proc.poll() is None:
            cf_proc.terminate()
    sys.exit(code)


if __name__ == "__main__":
    main()
