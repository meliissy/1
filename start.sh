#!/bin/bash
# Fallback entry point if the ModVC panel lets you set a custom start command.
set -e
if [ ! -x ./xray ]; then
  curl -L https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip -o xray.zip
  unzip -o xray.zip xray
  chmod +x xray
fi
python3 main.py
