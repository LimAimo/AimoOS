#!/usr/bin/env python3
"""Build a writable ext4 guest and initramfs without mount/chroot on the host."""
from pathlib import Path
import argparse,gzip,hashlib,json,os,shutil,stat,struct,subprocess,tempfile,tomllib

PROJECT=Path(__file__).resolve().parents[1]
VERSION=tomllib.loads((PROJECT/"pyproject.toml").read_text())["project"]["version"]
BUILD=Path(os.environ.get("AIMO_BUILD_DIR",str(PROJECT/"build")))
BUILD.mkdir(exist_ok=True)
ROOT=Path(tempfile.mkdtemp(prefix="guest-root-",dir=BUILD))

def write(path,text,mode=0o644):
    target=ROOT/path.lstrip("/");target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text);target.chmod(mode)

def copy(source,target,mode=None):
    dest=ROOT/target.lstrip("/");dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.is_symlink():dest.unlink()
    shutil.copy2(source,dest)
    if mode is not None:dest.chmod(mode)

def newc(entries):
    """Create a root-owned Linux newc archive, including a real console node."""
    data=bytearray()
    for inode,(name,mode,content,major,minor) in enumerate(entries,1):
        name=name.encode()+b"\0"
        fields=[inode,mode,0,0,2 if stat.S_ISDIR(mode) else 1,0,len(content),0,0,major,minor,len(name),0]
        data.extend(b"070701"+b"".join(f"{value:08x}".encode() for value in fields))
        data.extend(name);data.extend(b"\0"*((-len(data))%4))
        data.extend(content);data.extend(b"\0"*((-len(data))%4))
    name=b"TRAILER!!!\0";fields=[0,0,0,0,1,0,0,0,0,0,0,len(name),0]
    data.extend(b"070701"+b"".join(f"{value:08x}".encode() for value in fields)+name)
    data.extend(b"\0"*((-len(data))%512));return bytes(data)

def package_database():
    info=ROOT/"var/lib/dpkg/info";info.mkdir(parents=True,exist_ok=True)
    statuses=[]
    for deb in sorted((BUILD/"packages").glob("*.deb")):
        control=subprocess.check_output(["dpkg-deb","-f",str(deb)],text=True).strip()
        package=next(line.split(": ",1)[1] for line in control.splitlines() if line.startswith("Package: "))
        statuses.append(control+"\nStatus: install ok installed\n")
        paths=subprocess.check_output(["dpkg-deb","--fsys-tarfile",str(deb)])
        # Use tarfile in memory; no package maintainer script is run on the host.
        import tarfile,io
        with tarfile.open(fileobj=io.BytesIO(paths),mode="r:") as archive:
            (info/(package+".list")).write_text("\n".join("/"+m.name.removeprefix("./").rstrip("/") for m in archive.getmembers() if m.name!=".")+"\n")
    write("/var/lib/dpkg/status","\n".join(statuses))
    for name in ["updates","triggers","alternatives"]:(ROOT/"var/lib/dpkg"/name).mkdir(exist_ok=True)

def prepare_root():
    sysroot=BUILD/"sysroot"
    if not (sysroot/"usr/bin/python3.12").exists():raise SystemExit("Run scripts/fetch_runtime.py first")
    if ROOT.exists():shutil.rmtree(ROOT)
    print("Staging guest filesystem…",flush=True)
    shutil.copytree(sysroot,ROOT,symlinks=True)
    # Ubuntu installs these ucf-managed defaults from package postinst. The
    # runtime extractor deliberately does not execute scripts on the host.
    office_registry=ROOT/"usr/lib/libreoffice/share/.registry"
    if office_registry.is_dir():
        shutil.copytree(office_registry,ROOT/"etc/libreoffice/registry",dirs_exist_ok=True)
    for name in ["dev","proc","sys","run","tmp","home","root","etc/aimo","etc/sudoers.d","var/log","etc/xdg"]:
        (ROOT/name).mkdir(parents=True,exist_ok=True)
    (ROOT/"tmp").chmod(0o1777);(ROOT/"root").chmod(0o700)
    source=ROOT/"opt/aimoos"
    shutil.copytree(PROJECT,source,ignore=shutil.ignore_patterns("build","out","screenshots",".git","__pycache__","*.pyc"))
    for script in (source/"scripts").iterdir():
        if script.is_file():script.chmod(0o755)
    copy(PROJECT/"scripts/aimo-init","/sbin/aimo-init",0o755)
    copy(PROJECT/"scripts/open-url","/usr/bin/aimo-open",0o755)
    copy(PROJECT/"config/applications/aimo-browser.desktop","/usr/share/applications/aimo-browser.desktop")
    copy(PROJECT/"config/mimeapps.list","/etc/xdg/mimeapps.list")
    shutil.copytree(PROJECT/"config/theme/Aimo",ROOT/"usr/share/themes/Aimo",dirs_exist_ok=True)
    # base-passwd ships templates; package maintainer scripts normally copy these.
    passwd=(ROOT/"usr/share/base-passwd/passwd.master").read_text()
    group=(ROOT/"usr/share/base-passwd/group.master").read_text()
    if not any(line.startswith("messagebus:") for line in passwd.splitlines()):passwd+="messagebus:x:102:102::/nonexistent:/usr/sbin/nologin\n"
    if not any(line.startswith("messagebus:") for line in group.splitlines()):group+="messagebus:x:102:\n"
    write("/etc/passwd",passwd);write("/etc/group",group)
    write("/etc/shadow","\n".join(line.split(":")[0]+":!:20000:0:99999:7:::" for line in passwd.splitlines())+"\n",0o600)
    write("/etc/gshadow","\n".join(line.split(":")[0]+":!::" for line in group.splitlines())+"\n",0o600)
    write("/etc/hostname","aimoos\n");write("/etc/hosts","127.0.0.1 localhost\n127.0.1.1 aimoos\n::1 localhost\n")
    write("/etc/resolv.conf","nameserver 10.0.2.3\n")
    write("/etc/aimo-release",f"AimoOS {VERSION}\n")
    write("/etc/os-release",f'NAME="AimoOS"\nPRETTY_NAME="AimoOS {VERSION}"\nID=aimoos\nID_LIKE=ubuntu\nVERSION_ID="{VERSION}"\nUBUNTU_CODENAME=noble\n')
    write("/etc/fstab","/dev/vda / ext4 defaults,noatime 0 1\n")
    write("/etc/nsswitch.conf","passwd: files\ngroup: files\nshadow: files\nhosts: files dns\nnetworks: files\nservices: files\nprotocols: files\n")
    write("/etc/default/locale","LANG=zh_CN.UTF-8\n")
    write("/etc/pam.d/common-auth","auth required pam_unix.so\n")
    write("/etc/pam.d/common-account","account required pam_unix.so\n")
    write("/etc/pam.d/common-password","password required pam_unix.so yescrypt\n")
    write("/etc/pam.d/common-session","session required pam_unix.so\n")
    write("/etc/pam.d/common-session-noninteractive","session required pam_unix.so\n")
    write("/etc/pam.d/i3lock","auth include common-auth\n")
    write("/etc/sudoers","Defaults env_reset\nDefaults secure_path=\"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"\nroot ALL=(ALL:ALL) ALL\n%sudo ALL=(ALL:ALL) ALL\n@includedir /etc/sudoers.d\n",0o440)
    write("/etc/sudoers.d/aimoos","ALL ALL=(root) NOPASSWD: /opt/aimoos/scripts/power-helper reboot, /opt/aimoos/scripts/power-helper poweroff, /opt/aimoos/scripts/account-helper\n",0o440)
    login=ROOT/"etc/login.defs"
    with login.open("a") as file:file.write("\nUMASK 077\nHOME_MODE 0700\n")
    for name in ["usr/bin/sudo","usr/bin/passwd","usr/sbin/unix_chkpwd"]:
        if (ROOT/name).exists():(ROOT/name).chmod(0o4755)
    write("/etc/X11/xorg.conf.d/20-aimo.conf",'Section "Device"\n Identifier "QEMU display"\n Driver "modesetting"\n Option "AccelMethod" "none"\nEndSection\n')
    # Firmware symlinks and font/GL caches are initialized inside the guest.
    package_database()
    write("/etc/apt/sources.list","deb http://archive.ubuntu.com/ubuntu noble main universe restricted multiverse\ndeb http://archive.ubuntu.com/ubuntu noble-updates main universe restricted multiverse\ndeb http://security.ubuntu.com/ubuntu noble-security main universe restricted multiverse\n")
    # Packages include stale intermediate depmod tables until their postinst runs.
    # Generate the complete index after both main and extra modules are staged.
    version=next((ROOT/"usr/lib/modules").iterdir()).name
    subprocess.run(["bash",str(PROJECT/"scripts/native_env.sh"),str(sysroot/"usr/sbin/depmod"),"-b",str(ROOT),version],check=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--size-gib",type=int,default=12)
    args=parser.parse_args();out=Path(os.environ.get("AIMO_OUT_DIR",str(PROJECT/"out")));out.mkdir(exist_ok=True)
    if os.geteuid()!=0:raise SystemExit("Build as root so all system files in the image have the correct ownership.")
    if args.size_gib<8:raise SystemExit("The office image requires at least 8 GiB.")
    image=out/"aimoos.img"
    if image.exists():raise SystemExit("out/aimoos.img already exists. Move it before rebuilding; it may contain user data.")
    prepare_root()
    kernel=next((BUILD/"sysroot/boot").glob("vmlinuz-*"));shutil.copy2(kernel,out/"vmlinuz")
    busybox=(BUILD/"sysroot/usr/bin/busybox").read_bytes()
    entries=[(name,stat.S_IFDIR|0o755,b"",0,0) for name in ["bin","dev","proc","sys","newroot"]]
    entries+=[("bin/busybox",stat.S_IFREG|0o755,busybox,0,0),("init",stat.S_IFREG|0o755,(PROJECT/"config/initramfs-init").read_bytes(),0,0),("dev/console",stat.S_IFCHR|0o600,b"",5,1)]
    entries += [("bin/"+name,stat.S_IFLNK|0o777,b"busybox",0,0) for name in ["sh","mount","mkdir","sleep","switch_root"]]
    with gzip.open(out/"initrd.gz","wb",compresslevel=6) as file:file.write(newc(entries))
    with image.open("wb") as file:file.truncate(args.size_gib*1024**3)
    subprocess.run(["mke2fs","-q","-t","ext4","-L","AimoOS","-F","-m","1","-d",str(ROOT),str(image)],check=True)
    shutil.copy2(BUILD/"packages.lock.json",out/"packages.lock.json")
    shutil.rmtree(ROOT)
    print(f"Built {image} ({args.size_gib} GiB, sparse); kernel {kernel.name}",flush=True)

if __name__=="__main__":main()
