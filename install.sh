#!/usr/bin/env bash
# OpenDoor — Setup-Script für Raspberry Pi
# Ausführen mit: bash install.sh

set -euo pipefail
cd "$(dirname "$0")"

echo "=== OpenDoor Setup ==="

# Python-Abhängigkeiten
echo ">> Virtuelle Umgebung erstellen..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "   OK"

# .env anlegen
if [ ! -f .env ]; then
  echo ""
  echo ">> .env konfigurieren"
  read -rp "   Tailscale-Hostname des Pi (z.B. pi.tail12345.ts.net): " rp_id
  secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed \
    -e "s|dein-pi.tail12345.ts.net|${rp_id}|g" \
    -e "s|HIER_ZUFAELLIGEN_STRING_EINSETZEN|${secret}|g" \
    .env.example > .env
  echo "   .env erstellt (SESSION_SECRET automatisch generiert)"
else
  echo ">> .env bereits vorhanden, übersprungen"
fi

# Systemd-Service
SERVICE_FILE="/etc/systemd/system/opendoor.service"
WORK_DIR="$(pwd)"
VENV_PYTHON="${WORK_DIR}/.venv/bin/python"

echo ""
echo ">> Systemd-Service installieren (benötigt sudo)..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=OpenDoor — Raspberry Pi Türöffner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${WORK_DIR}
ExecStart=${VENV_PYTHON} -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
EnvironmentFile=${WORK_DIR}/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable opendoor
sudo systemctl restart opendoor
echo "   Service gestartet"

echo ""
echo "=== Fertig! ==="
echo ""
echo "Nächste Schritte:"
echo "  1. Tailscale Serve aktivieren:"
echo "     tailscale serve --bg http://localhost:8000"
echo "     (damit bekommst du HTTPS auf https://$(hostname).your-tailnet.ts.net)"
echo ""
echo "  2. Im Browser öffnen und erstes Gerät registrieren"
echo ""
echo "  Logs ansehen:  journalctl -u opendoor -f"
echo "  Service-Status: systemctl status opendoor"
