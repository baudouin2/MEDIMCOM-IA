#!/usr/bin/env bash
# Installs OBS Studio (free screen recorder) on Ubuntu, prepares a folder for the recordings, and opens it.
#   bash docs/video/installer_obs.sh
set -euo pipefail

if ! command -v obs >/dev/null; then
  echo "→ Installing OBS Studio (your password will be asked once)…"
  sudo apt-get update -y
  sudo apt-get install -y software-properties-common
  # Official OBS repository (latest version); if it is not available, Ubuntu's own package
  if sudo add-apt-repository -y ppa:obsproject/obs-studio; then
    sudo apt-get update -y
  fi
  sudo apt-get install -y obs-studio ffmpeg
fi

mkdir -p "$HOME/Videos/MEDIMCOM_demo"
echo
echo "✓ OBS Studio is installed. Recordings will go to: $HOME/Videos/MEDIMCOM_demo"
echo
echo "First time in OBS (2 minutes):"
echo "  1. The auto-configuration wizard opens: choose 'Optimize just for recording', 1920x1080, 30 FPS."
echo "  2. Settings → Output → Recording Path: $HOME/Videos/MEDIMCOM_demo ; Recording Format: mp4."
echo "  3. Sources (bottom) → +  → 'Screen Capture (PipeWire)' on Ubuntu 22.04/24.04 (Wayland),"
echo "     or 'Screen Capture (XSHM)' on Xorg → choose your screen → OK."
echo "  4. Sources → +  → 'Audio Input Capture' → your microphone (for the narration)."
echo "  5. Start Recording / Stop Recording (bottom right)."
echo
nohup obs >/dev/null 2>&1 &
echo "→ OBS is opening…"
