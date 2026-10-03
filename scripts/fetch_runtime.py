#!/usr/bin/env python3
"""Resolve an entire Ubuntu runtime without installing anything on the host.

An empty dpkg status file makes APT include dependencies already present on the
build host. Package bytes are verified by APT, then extracted into a private
sysroot. This is usable in containers without mount/chroot or hardware KVM.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import shutil
import tarfile

PROJECT = Path(__file__).resolve().parents[1]
PACKAGES = [
    "base-files", "base-passwd", "bash", "coreutils", "dash", "findutils",
    "grep", "sed", "mawk", "gzip", "tar", "util-linux", "login", "passwd",
    "libpam-modules", "libpam-runtime", "sudo", "apt", "ubuntu-keyring",
    "ca-certificates", "locales", "tzdata", "iproute2", "iputils-ping", "curl",
    "busybox-static", "kmod", "e2fsprogs", "dbus", "dbus-x11",
    "xserver-xorg-core", "xserver-xorg-video-fbdev", "xserver-xorg-input-libinput",
    "xserver-xorg-input-evdev", "xvfb", "xauth", "x11-xserver-utils", "x11-utils",
    "openbox", "xcompmgr", "xdotool", "wmctrl", "xterm", "i3lock", "xdg-utils",
    "python3", "python3-pyqt6", "python3-pyqt6.qtwebengine", "python3-xlib",
    "python3-pyte", "libgl1-mesa-dri", "fonts-noto-cjk", "fonts-dejavu-core",
    "qemu-system-x86", "qemu-utils", "seabios", "xorriso", "isolinux",
    "syslinux-common", "cpio", "strace",
    "grub-pc-bin", "grub-common", "grub2-common", "squashfs-tools", "zstd",
    "fdisk", "open-vm-tools", "open-vm-tools-desktop", "xserver-xorg-video-vmware",
    "libreoffice-writer", "libreoffice-calc", "libreoffice-impress",
    "libreoffice-l10n-zh-cn", "libreoffice-gtk3", "fonts-liberation2",
    "fcitx5", "fcitx5-chinese-addons", "fcitx5-frontend-qt6",
    "fcitx5-frontend-gtk3", "pulseaudio", "alsa-utils", "pavucontrol",
    "qpdfview", "ristretto", "procps", "desktop-file-utils", "xdg-user-dirs", "udev",
    "libglib2.0-bin", "qt6-translations-l10n", "qemu-system-gui", "librsvg2-common",
    "language-pack-zh-hans", "language-pack-gnome-zh-hans",
]


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()
    build = Path(os.environ.get("AIMO_BUILD_DIR",str(PROJECT/"build")))
    archives = build / "packages"
    root = build / "sysroot"
    archives.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    status = build / "empty-status"
    status.write_text("")
    dependencies = subprocess.check_output(
        ["apt-cache", "depends", "linux-image-generic"], text=True
    )
    kernel = re.search(r"Depends:\s+(linux-image-\d[^\s]+)", dependencies)
    if not kernel:
        raise SystemExit("Cannot resolve the distribution's Linux kernel")
    requested = PACKAGES + [kernel.group(1), kernel.group(1).replace("linux-image-", "linux-modules-extra-")]
    command = [
        "apt-get", "-o", "APT::Sandbox::User=root",
        "-o", f"Dir::State::status={status}",
        "-o", f"Dir::Cache::archives={archives}",
        "-y", "--download-only", "--no-install-recommends", "install", *requested,
    ]
    if not args.skip_download:
        run(command)
    # Discard only the reproducible extraction tree, never source/user data.
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    # Ubuntu packages target a merged /usr tree. Establish it before extraction.
    for name, target in [("bin", "usr/bin"), ("sbin", "usr/sbin"),
                         ("lib", "usr/lib"), ("lib64", "usr/lib64")]:
        (root / target).mkdir(parents=True, exist_ok=True)
        if not (root / name).exists():
            (root / name).symlink_to(target)
    manifest = []
    for i, deb in enumerate(sorted(archives.glob("*.deb")), 1):
        fields = subprocess.check_output(
            ["dpkg-deb", "--field", str(deb), "Package", "Version", "Architecture"],
            text=True,
        ).strip()
        # Preserve package permissions, but not host user/group ownership: the
        # build container can only represent its own UID/GID. Guest ownership
        # is assigned in the image rather than by chown on the build host.
        unpack = subprocess.Popen(["dpkg-deb", "--fsys-tarfile", str(deb)], stdout=subprocess.PIPE)
        run(["tar", "--no-same-owner", "--keep-directory-symlink", "-xpf", "-", "-C", str(root)], stdin=unpack.stdout)
        unpack.stdout.close()
        if unpack.wait() != 0:
            raise SystemExit(f"Package extraction failed: {deb.name}")
        # Verify regular-file lengths against the signed package archive.
        # Repair interrupted/short writes before this runtime can build an image.
        verify=subprocess.Popen(["dpkg-deb","--fsys-tarfile",str(deb)],stdout=subprocess.PIPE)
        with tarfile.open(fileobj=verify.stdout,mode="r|") as archive:
            for member in archive:
                target=root/member.name.removeprefix("./")
                if member.isfile() and target.exists() and target.stat().st_size!=member.size:
                    with target.open("wb") as output:
                        shutil.copyfileobj(archive.extractfile(member),output)
                    if target.stat().st_size!=member.size:raise RuntimeError("Short package extraction: "+member.name)
        verify.stdout.close()
        if verify.wait()!=0:raise RuntimeError("Package verification failed: "+deb.name)
        with deb.open("rb") as package:
            digest=hashlib.file_digest(package,"sha256").hexdigest()
        manifest.append({"archive": deb.name, "fields": fields,"sha256":digest})
        if i % 25 == 0:
            print(f"Extracted {i} packages", flush=True)
    # qemu-system's usual alternatives links are installed by maintainer scripts.
    for firmware in (root/"usr/share/seabios").glob("*.bin"):
        destination=root/"usr/share/qemu"/firmware.name
        if not destination.exists():destination.symlink_to(Path("../seabios")/firmware.name)
    (build / "packages.lock.json").write_text(
        json.dumps({"kernel_package": kernel.group(1), "requested": requested,
                    "packages": manifest}, ensure_ascii=False, indent=2)
    )
    print(f"Runtime ready: {root}; {len(manifest)} packages", flush=True)


if __name__ == "__main__":
    main()
