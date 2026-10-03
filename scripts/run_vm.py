#!/usr/bin/env python3
"""Boot the persistent disk with QEMU; no laboratory backdoor is enabled."""
from pathlib import Path
import argparse,os,shlex,shutil

PROJECT=Path(__file__).resolve().parents[1]

def command(args):
    build=Path(os.environ.get("AIMO_BUILD_DIR",str(PROJECT/"build")))
    out=Path(os.environ.get("AIMO_OUT_DIR",str(PROJECT/"out")))
    bundled=build/"sysroot/usr/bin/qemu-system-x86_64"
    qemu=args.qemu or (str(bundled) if bundled.exists() else shutil.which("qemu-system-x86_64"))
    if not qemu:raise SystemExit("QEMU is missing. Run fetch_runtime.py or install qemu-system-x86.")
    disk=Path(args.disk) if args.disk else out/"aimoos.img"
    for path in (disk,out/"vmlinuz",out/"initrd.gz"):
        if not path.is_file():raise SystemExit(f"Missing {path}; build the image first.")
    accel=args.accel
    if accel=="auto":accel="kvm" if os.access("/dev/kvm",os.R_OK|os.W_OK) else "tcg"
    argv=[qemu,"-name","AimoOS","-accel",accel if accel=="kvm" else "tcg,thread=multi",
          "-cpu","host" if accel=="kvm" else "max","-smp",str(args.cpus),"-m",str(args.memory),
          "-usb","-device","usb-tablet","-vga","none","-device","VGA,xres=1600,yres=900",
          "-device","virtio-rng-pci","-netdev","user,id=net0","-device","e1000,netdev=net0,romfile=",
          "-kernel",str(out/"vmlinuz"),"-initrd",str(out/"initrd.gz"),
          "-append","root=/dev/vda rw console=ttyS0 loglevel=4",
          "-drive",f"file={disk},format=raw,if=virtio","-serial",f"file:{out/'boot.log'}"]
    if qemu==str(bundled):argv += ["-L",str(build/"sysroot/usr/share/qemu")]
    if args.headless:argv += ["-display","none","-audiodev","none,id=audio"]
    else:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise SystemExit("A graphical host session is required; use --headless for diagnostics.")
        argv += ["-display",args.display,"-audiodev","pa,id=audio" if os.environ.get("PULSE_SERVER") or os.environ.get("XDG_RUNTIME_DIR") else "none,id=audio"]
    argv += ["-device","intel-hda","-device","hda-duplex,audiodev=audio"]
    return ["bash",str(PROJECT/"scripts/native_env.sh"),*argv] if qemu==str(bundled) else argv

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accel",choices=("auto","kvm","tcg"),default="auto")
    parser.add_argument("--memory",type=int,default=4096,help="RAM in MiB")
    parser.add_argument("--cpus",type=int,default=4)
    parser.add_argument("--display",choices=("gtk","sdl"),default="gtk")
    parser.add_argument("--headless",action="store_true")
    parser.add_argument("--disk");parser.add_argument("--qemu")
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    if args.memory<2048 or args.cpus<1:parser.error("Use at least 2048 MiB and one vCPU")
    argv=command(args)
    if args.dry_run:print(shlex.join(argv));return
    os.execvp(argv[0],argv)

if __name__=="__main__":main()
