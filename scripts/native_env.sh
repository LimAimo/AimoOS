#!/usr/bin/env bash
# Run the extracted runtime without host-level package installation.
set -euo pipefail
aimo_project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
aimo_runtime_root="${AIMO_BUILD_DIR:-$aimo_project_root/build}/sysroot"
export LD_LIBRARY_PATH="$aimo_runtime_root/usr/lib/x86_64-linux-gnu:$aimo_runtime_root/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$aimo_runtime_root/usr/bin:$aimo_runtime_root/usr/sbin:$PATH"
export PYTHONPATH="$aimo_project_root:$aimo_runtime_root/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
export QT_PLUGIN_PATH="$aimo_runtime_root/usr/lib/x86_64-linux-gnu/qt6/plugins"
export QTWEBENGINE_RESOURCES_PATH="$aimo_runtime_root/usr/share/qt6/resources"
export QTWEBENGINE_LOCALES_PATH="$aimo_runtime_root/usr/share/qt6/translations/qtwebengine_locales"
export QTWEBENGINEPROCESS_PATH="$aimo_runtime_root/usr/lib/qt6/libexec/QtWebEngineProcess"
export AIMO_FONT_DIR="$aimo_runtime_root/usr/share/fonts/opentype/noto"
export LIBGL_DRIVERS_PATH="$aimo_runtime_root/usr/lib/x86_64-linux-gnu/dri"
export LIBGL_ALWAYS_SOFTWARE=1
export QEMU_MODULE_DIR="$aimo_runtime_root/usr/lib/x86_64-linux-gnu/qemu"
exec "$@"
