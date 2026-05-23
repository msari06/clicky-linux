#!/usr/bin/env bash
# Checks the Linux system dependencies Clicky needs.
# If anything is missing, prints the apt command to install them.

set -u

ok()    { printf "  \033[32m✓\033[0m %s\n" "$1"; }
miss()  { printf "  \033[31m✗\033[0m %s\n" "$1"; }
warn()  { printf "  \033[33m!\033[0m %s\n" "$1"; }
header(){ printf "\n\033[1m%s\033[0m\n" "$1"; }

missing_packages=()

require_pkg() {
  local pkg="$1"
  local description="$2"
  if dpkg -s "$pkg" >/dev/null 2>&1; then
    ok "$pkg ($description)"
  else
    miss "$pkg ($description)"
    missing_packages+=("$pkg")
  fi
}

header "Display server"
echo "  XDG_SESSION_TYPE = ${XDG_SESSION_TYPE:-unknown}"
echo "  XDG_CURRENT_DESKTOP = ${XDG_CURRENT_DESKTOP:-unknown}"
if [[ "${XDG_SESSION_TYPE:-}" != "x11" ]]; then
  warn "You're not on X11. The MVP is tuned for X11 — global hotkey and overlay support are limited on Wayland."
fi

header "Python packages"
require_pkg python3        "Python 3 interpreter"
require_pkg python3-venv   "venv module"
require_pkg python3-dev    "Python headers"

header "Qt runtime libraries (PyQt6)"
require_pkg libxcb-cursor0 "Qt 6 xcb cursor plugin"
require_pkg libxkbcommon0  "Qt keyboard handling"
require_pkg libegl1        "EGL runtime"
require_pkg libgl1         "OpenGL runtime"
require_pkg libfontconfig1 "Font configuration"
require_pkg libdbus-1-3    "D-Bus"

header "GNOME tray (if you're on GNOME 45+)"
if command -v gnome-shell >/dev/null 2>&1; then
  if gnome-extensions list 2>/dev/null | grep -q "appindicatorsupport"; then
    ok "AppIndicator and KStatusNotifierItem Support extension is installed"
  else
    warn "AppIndicator extension is missing — the tray icon may not show up."
    echo "       Install: https://extensions.gnome.org/extension/615/appindicator-support/"
  fi
else
  ok "Not on GNOME, skipping tray check"
fi

header "Result"
if [ ${#missing_packages[@]} -eq 0 ]; then
  ok "All dependencies are ready."
  exit 0
else
  miss "${#missing_packages[@]} package(s) missing. To install:"
  echo ""
  echo "    sudo apt update && sudo apt install -y ${missing_packages[*]}"
  echo ""
  exit 1
fi
