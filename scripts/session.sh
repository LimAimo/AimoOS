#!/bin/sh
# This script is invoked only after runuser has dropped root privileges.
set -eu
cd /opt/aimoos
export PYTHONPATH=/opt/aimoos
export LANG=zh_CN.UTF-8 LC_ALL=zh_CN.UTF-8 TZ=Asia/Shanghai
export QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=softpipe SAL_DISABLEGL=1 SAL_DISABLESKIA=1
export QT_IM_MODULE=fcitx GTK_IM_MODULE=fcitx XMODIFIERS=@im=fcitx
export XDG_CURRENT_DESKTOP=AimoOS XDG_SESSION_TYPE=x11
export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --disable-dev-shm-usage"
unset QTWEBENGINE_DISABLE_SANDBOX
mkdir -p "$HOME/.config/openbox" "$HOME/.config/gtk-3.0" "$HOME/.config/fcitx5" "$HOME/.cache/aimoos" "$HOME/文档" "$HOME/下载" "$HOME/图片"
chmod 700 "$HOME"
cp /opt/aimoos/config/openbox/rc.xml "$HOME/.config/openbox/rc.xml"
if [ ! -f "$HOME/.config/fcitx5/profile" ]; then
  cp /opt/aimoos/config/fcitx5/profile "$HOME/.config/fcitx5/profile"
fi
if [ ! -f "$HOME/.config/gtk-3.0/settings.ini" ]; then
  cp /opt/aimoos/config/gtk-settings.ini "$HOME/.config/gtk-3.0/settings.ini"
fi
pulseaudio --start --exit-idle-time=-1 2>"$HOME/.cache/aimoos/audio.log" || true
openbox --config-file "$HOME/.config/openbox/rc.xml" >"$HOME/.cache/aimoos/window-manager.log" 2>&1 &
aimo_wm_pid=$!
xcompmgr -n >"$HOME/.cache/aimoos/compositor.log" 2>&1 &
aimo_compositor_pid=$!
trap 'kill "$aimo_compositor_pid" "$aimo_wm_pid" 2>/dev/null || true; pulseaudio --kill 2>/dev/null || true' EXIT HUP INT TERM
fcitx5 -d >"$HOME/.cache/aimoos/input-method.log" 2>&1 || true
python3 -m aimo.main --desktop
