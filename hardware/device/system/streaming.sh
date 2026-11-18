#!/usr/bin/env bash
# AirPlay 2 (shairport-sync + nqptp) and Spotify Connect (raspotify) for the Soundlampe.
# Called by install.sh; can also be run on its own:  sudo ./hardware/device/system/streaming.sh
# Skip a part with AIRPLAY=0 or SPOTIFY=0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
AIRPLAY="${AIRPLAY:-1}"
SPOTIFY="${SPOTIFY:-1}"
NQPTP_TAG=1.2.9
SHAIRPORT_TAG=5.6.3

if [ "$AIRPLAY" = 1 ]; then
  echo "==> AirPlay 2 (builds from source, about 15 min on a Pi 3 A+)"
  apt-get install -y --no-install-recommends build-essential git autoconf automake libtool \
    pkg-config libpopt-dev libconfig-dev libasound2-dev avahi-daemon libavahi-client-dev \
    libssl-dev libsoxr-dev libplist-dev libplist-utils libsodium-dev libavutil-dev libavcodec-dev \
    libavformat-dev uuid-dev libgcrypt20-dev xxd
  # Debian 13 (Trixie) and later need systemd-dev for the service files
  . /etc/os-release
  [ "${VERSION_ID%%.*}" -ge 13 ] 2>/dev/null && apt-get install -y --no-install-recommends systemd-dev
  # the Debian package is AirPlay 1 only; remove it so it can't clash
  apt-get remove -y shairport-sync >/dev/null 2>&1 || true
  BUILD="$(mktemp -d)"
  git clone --depth 1 --branch "$NQPTP_TAG" https://github.com/mikebrady/nqptp.git "$BUILD/nqptp"
  (cd "$BUILD/nqptp" && autoreconf -fi && ./configure --with-systemd-startup && make -j2 && make install)
  git clone --depth 1 --branch "$SHAIRPORT_TAG" https://github.com/mikebrady/shairport-sync.git "$BUILD/shairport-sync"
  (cd "$BUILD/shairport-sync" && autoreconf -fi && \
    ./configure --sysconfdir=/etc --with-alsa --with-soxr --with-avahi --with-ssl=openssl \
      --with-systemd-startup --with-airplay-2 && make -j2 && make install)
  rm -rf "$BUILD"
  cp "$HERE/shairport-sync.conf" /etc/shairport-sync.conf
  id shairport-sync >/dev/null 2>&1 && usermod -aG audio shairport-sync
  systemctl daemon-reload
  systemctl enable nqptp shairport-sync
fi

if [ "$SPOTIFY" = 1 ]; then
  echo "==> Spotify Connect (raspotify)"
  apt-get install -y curl gpg
  curl -fsSL https://dtcooper.github.io/raspotify/key.asc -o /usr/share/keyrings/raspotify_key.asc
  echo "deb [signed-by=/usr/share/keyrings/raspotify_key.asc] https://dtcooper.github.io/raspotify raspotify main" \
    > /etc/apt/sources.list.d/raspotify.list
  apt-get update
  apt-get install -y raspotify
  conf=/etc/raspotify/conf
  set_opt() { sed -i "/^#\?$1=/d" "$conf"; echo "$1=$2" >> "$conf"; }
  set_opt LIBRESPOT_NAME '"Soundlampe"'
  set_opt LIBRESPOT_BACKEND alsa
  set_opt LIBRESPOT_DEVICE default
  set_opt LIBRESPOT_BITRATE 320
  set_opt LIBRESPOT_INITIAL_VOLUME 60
  systemctl enable raspotify
fi
