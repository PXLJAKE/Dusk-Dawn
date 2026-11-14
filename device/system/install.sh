#!/usr/bin/env bash
# Installs SleepGenerator on Raspberry Pi OS Lite (Bookworm, 64-bit) on a Pi Zero 2 W.
# Run from the repo:  sudo ./device/system/install.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEVICE_DIR="$(dirname "$HERE")"
CONFIG_TXT=/boot/firmware/config.txt

echo "==> packages"
apt-get update
apt-get install -y python3-venv python3-numpy python3-scipy python3-yaml \
  python3-gpiozero python3-lgpio python3-spidev libportaudio2 alsa-utils squeezelite

echo "==> boot config (DigiAMP+, SPI for the LEDs)"
add_line() { grep -qxF "$1" "$CONFIG_TXT" || echo "$1" >> "$CONFIG_TXT"; }
sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$CONFIG_TXT"
add_line "dtoverlay=iqaudio-dacplus,unmute_amp"
add_line "dtparam=spi=on"
add_line "core_freq=250"   # stable SPI clock for the SK6812 LEDs

echo "==> user + app"
id sleepgen >/dev/null 2>&1 || useradd --system --groups audio,gpio,spi --home /opt/sleepgen sleepgen
mkdir -p /opt/sleepgen /etc/sleepgen
python3 -m venv --system-site-packages /opt/sleepgen/venv
/opt/sleepgen/venv/bin/pip install --upgrade "$DEVICE_DIR"
[ -f /etc/sleepgen/config.yaml ] || cp "$DEVICE_DIR/config.example.yaml" /etc/sleepgen/config.yaml

echo "==> audio mixing + music player"
cp "$HERE/asound.conf" /etc/asound.conf
cat > /etc/default/squeezelite <<'SQ'
SL_NAME="Soundlampe"
SL_SOUNDCARD="default"
SB_EXTRA_ARGS="-a 160:4:: -C 5"
SQ

echo "==> services"
cp "$HERE/sleepgen.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable sleepgen squeezelite

echo
echo "Done. Edit /etc/sleepgen/config.yaml (MQTT host, user, password) and reboot."
