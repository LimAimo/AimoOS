#!/usr/bin/env python3
"""Build a BIOS installer ISO and pristine VMware VM without host mounts.

A temporary QEMU guest installs the very same ISO onto a new SATA disk. All
privileged partition/mount/GRUB operations happen inside that disposable guest.
"""
from pathlib import Path
import argparse,gzip,json,os,shutil,stat,subprocess,sys,tomllib,zipfile,hashlib
import build_image as base
P=base.PROJECT; B=base.BUILD; R=base.ROOT
V=base.VERSION
ENV={**os.environ,'AIMO_BUILD_DIR':str(B)}

def native(argv,**kwargs):
    return subprocess.run(['bash',str(P/'scripts/native_env.sh'),*[str(a) for a in argv]],check=True,env=ENV,**kwargs)

def initrd(output):
    """Include a dependency-closed set of actual Ubuntu storage modules."""
    sysroot=B/'sysroot';version=next((sysroot/'usr/lib/modules').iterdir()).name
    native([sysroot/'usr/sbin/depmod','-b',sysroot,version])
    paths={}
    def add_file(source,dest):paths[dest]=(stat.S_IFREG|0o755,Path(source).read_bytes())
    add_file(sysroot/'usr/bin/busybox','bin/busybox')
    add_file(sysroot/'usr/bin/kmod','bin/kmod')
    add_file(P/'config/initramfs-init','init')
    # Resolve dependencies for both kmod and the real util-linux blkid.
    import re
    add_file(sysroot/'usr/sbin/blkid','bin/blkid')
    for executable in ('usr/bin/kmod','usr/sbin/blkid'):
        result=native(['ldd',sysroot/executable],capture_output=True,text=True).stdout
        for item in re.findall(r'(?:=>\s+)?(/[^\s()]+)',result):
            path=Path(item)
            if path.is_file():
                dest=str(path.relative_to(sysroot)) if path.is_relative_to(sysroot) else str(path).lstrip('/')
                if dest.startswith("lib/"):dest="usr/"+dest
                add_file(path,dest)
    loader=sysroot/'usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'
    add_file(loader,'lib64/ld-linux-x86-64.so.2')
    for name in ('ahci','ata_piix','sd_mod','sr_mod','virtio_pci','virtio_blk','virtio_scsi','mptspi','vmw_pvscsi','isofs','squashfs','overlay','loop'):
        result=native([sysroot/'usr/sbin/modprobe','-d',sysroot,'-S',version,'--show-depends',name],capture_output=True,text=True).stdout
        for line in result.splitlines():
            if not line.startswith('insmod '):continue
            source=Path(line.split()[1]).resolve();dest=str(source.relative_to(sysroot))
            dest=dest.removesuffix('.zst')
            data=native([sysroot/'usr/bin/zstd','-dc',source],capture_output=True).stdout if source.suffix=='.zst' else source.read_bytes()
            paths[dest]=(stat.S_IFREG|0o644,data)
    for name in ('modules.dep','modules.alias','modules.softdep','modules.builtin','modules.builtin.modinfo','modules.builtin.bin','modules.dep.bin','modules.alias.bin'):
        source=sysroot/'usr/lib/modules'/version/name
        if source.exists():paths[str(source.relative_to(sysroot))]=(stat.S_IFREG|0o644,source.read_bytes())
    paths['lib']=(stat.S_IFLNK|0o777,b'usr/lib')
    paths['bin/modprobe']=(stat.S_IFLNK|0o777,b'kmod')
    for name in ('sh','mount','mkdir','sleep','switch_root','cat','losetup'):
        paths['bin/'+name]=(stat.S_IFLNK|0o777,b'busybox')
    # Re-index the uncompressed dependency closure rather than shipping indexes
    # pointing at .ko.zst files. This avoids early-kernel compression mismatches.
    module_stage=B/'initrd-modules'
    shutil.rmtree(module_stage,ignore_errors=True)
    (module_stage/'usr/lib/modules'/version).mkdir(parents=True)
    (module_stage/'lib').symlink_to('usr/lib')
    for name,(mode,data) in paths.items():
        if name.startswith('usr/lib/modules/') and stat.S_ISREG(mode):
            file=module_stage/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
    native([sysroot/'usr/sbin/depmod','-b',module_stage,version])
    for file in (module_stage/'usr/lib/modules'/version).glob('modules.*'):
        paths[str(file.relative_to(module_stage))]=(stat.S_IFREG|0o644,file.read_bytes())
    dirs={'bin','dev','proc','sys','newroot','usr','usr/lib','lib64','aimo'}
    for name in paths:
        dirs.update(str(parent) for parent in Path(name).parents if str(parent)!='.')
    entries=[(d,stat.S_IFDIR|0o755,b'',0,0) for d in sorted(dirs) if d not in paths]
    entries.extend((name,mode,data,0,0) for name,(mode,data) in paths.items())
    entries.append(('dev/console',stat.S_IFCHR|0o600,b'',5,1))
    with gzip.open(output,'wb',compresslevel=6) as archive:archive.write(base.newc(entries))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--size-gib',type=int,default=20);ap.add_argument('--stage-root',type=Path,help='Reuse a pristine staging tree after a failed build')
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if args.size_gib<16:ap.error('VM disk must be at least 16 GiB')
    iso=out/f'AimoOS-{V}-amd64.iso';disk=out/'aimoos-vmware.raw'
    if iso.exists() or disk.exists():raise SystemExit('Output exists; choose another folder to protect user data.')
    if args.stage_root:
        global R
        R=args.stage_root.resolve();base.ROOT=R
        if not (R/'usr/bin/python3.12').is_file() or list((R/'home').iterdir()):
            raise SystemExit('Only an empty-account build staging tree can be reused.')
        for source in P.rglob('*'):
            relative=source.relative_to(P)
            if any(part in ('build','out','screenshots','.git','__pycache__','release') for part in relative.parts):continue
            if source.is_file() and source.suffix not in ('.log','.zip','.vmdk','.img','.iso','.pyc'):
                dest=R/'opt/aimoos'/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        base.copy(P/'scripts/aimo-init','/sbin/aimo-init',0o755)
    else:
        base.prepare_root()
    kernel=next((B/'sysroot/boot').glob('vmlinuz-*'));base.copy(kernel,'/boot/vmlinuz',0o644)
    initrd(R/'boot/initrd.gz')
    base.write('/boot/grub/grub.cfg','set timeout=3\nset default=0\nmenuentry "AimoOS" {\n search --no-floppy --label AimoOS --set=root\n linux /boot/vmlinuz root=LABEL=AimoOS rw quiet loglevel=3\n initrd /boot/initrd.gz\n}\n')
    stage=B/'iso-stage';shutil.rmtree(stage,ignore_errors=True);(stage/'aimo').mkdir(parents=True);(stage/'isolinux').mkdir()
    print('Compressing install filesystem…',flush=True)
    native([B/'sysroot/usr/bin/mksquashfs',R,stage/'aimo/root.squashfs','-noappend','-comp','zstd','-Xcompression-level','3','-processors','2','-no-progress'])
    shutil.copy2(R/'boot/vmlinuz',stage/'aimo/vmlinuz');shutil.copy2(R/'boot/initrd.gz',stage/'aimo/initrd.gz')
    shutil.copy2(B/'sysroot/usr/lib/ISOLINUX/isolinux.bin',stage/'isolinux/isolinux.bin')
    shutil.copy2(B/'sysroot/usr/lib/syslinux/modules/bios/ldlinux.c32',stage/'isolinux/ldlinux.c32')
    (stage/'isolinux/isolinux.cfg').write_text('DEFAULT aimo\nPROMPT 0\nTIMEOUT 30\nLABEL aimo\n KERNEL /aimo/vmlinuz\n APPEND initrd=/aimo/initrd.gz aimo.install=1 quiet loglevel=3\n')
    native([B/'sysroot/usr/bin/xorriso','-as','mkisofs','-o',iso,'-V','AIMOOS_INSTALL','-b','isolinux/isolinux.bin','-c','isolinux/boot.cat','-no-emul-boot','-boot-load-size','4','-boot-info-table','-isohybrid-mbr',B/'sysroot/usr/lib/ISOLINUX/isohdpfx.bin',stage])
    # A disposable bootstrap root, with external kernel, exists only at build time.
    bootstrap=B/'vmware-bootstrap.img'
    if bootstrap.exists():bootstrap.unlink(missing_ok=True)
    with bootstrap.open('wb') as f:f.truncate(12*1024**3)
    subprocess.run(['mke2fs','-q','-t','ext4','-F','-m','1','-L','AimoOS','-d',str(R),str(bootstrap)],check=True)
    with disk.open('wb') as f:f.truncate(args.size_gib*1024**3)
    print('Installing the ISO onto the new virtual SATA disk…',flush=True)
    log=out/'build-boot.log'
    command=[B/'sysroot/usr/bin/qemu-system-x86_64','-L',B/'sysroot/usr/share/qemu','-accel','tcg,thread=multi','-cpu','max','-smp','4','-m','4096','-display','none','-nic','none','-snapshot','-kernel',R/'boot/vmlinuz','-initrd',R/'boot/initrd.gz','-append','root=LABEL=AimoOS rw console=ttyS0 loglevel=4 aimo.build=1','-drive',f'file={bootstrap},format=raw,if=virtio','-device','ich9-ahci,id=sata','-drive',f'file={disk},format=raw,if=none,id=target,snapshot=off','-device','ide-hd,drive=target,bus=sata.0','-drive',f'file={iso},media=cdrom,readonly=on','-serial',f'file:{log}','-no-reboot']
    native(command,timeout=1200)
    if 'AIMO_INSTALL_SUCCESS' not in log.read_text(errors='replace'):raise RuntimeError('Guest installer failed; inspect '+str(log))
    folder=out/f'AimoOS-{V}-VMware';folder.mkdir()
    native([B/'sysroot/usr/bin/qemu-img','convert','-p','-f','raw','-O','vmdk','-o','subformat=monolithicSparse,adapter_type=ide',disk,folder/'AimoOS.vmdk'])
    (folder/'AimoOS.vmx').write_text('''.encoding = "UTF-8"
config.version = "8"
virtualHW.version = "19"
displayName = "AimoOS 0.2.0"
guestOS = "ubuntu-64"
firmware = "bios"
memsize = "4096"
numvcpus = "4"
cpuid.coresPerSocket = "2"
sata0.present = "TRUE"
sata0:0.present = "TRUE"
sata0:0.fileName = "AimoOS.vmdk"
sata0:0.deviceType = "disk"
ethernet0.present = "TRUE"
ethernet0.connectionType = "nat"
ethernet0.virtualDev = "e1000"
ethernet0.startConnected = "TRUE"
usb.present = "TRUE"
ehci.present = "TRUE"
sound.present = "TRUE"
sound.virtualDev = "hdaudio"
mks.enable3d = "FALSE"
svga.autodetect = "TRUE"
svga.vramSize = "134217728"
tools.syncTime = "TRUE"
''')
    guide=P/'docs/VMWARE.md'
    if guide.exists():shutil.copy2(guide,folder/'VMware-Guide.md')
    archive=out/f'AimoOS-{V}-VMware.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(folder.iterdir()):z.write(file,file.relative_to(out))
    sums=out/'SHA256SUMS.txt'
    sums.write_text(''.join(f'{hashlib.file_digest(f.open("rb"),"sha256").hexdigest()}  {f.name}\n' for f in (iso,archive)))
    bootstrap.unlink(missing_ok=True)
    if not args.stage_root:shutil.rmtree(R)
    shutil.copy2(B/'packages.lock.json',out/'packages.lock.json')
    print(json.dumps({'iso':str(iso),'vmware':str(archive),'checksums':str(sums)},indent=2),flush=True)
if __name__=='__main__':main()
