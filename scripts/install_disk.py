#!/usr/bin/env python3
"""Install only on a checked, empty virtual disk. Run in the installer guest."""
import argparse,json,os,subprocess,time
from pathlib import Path

def run(argv, **kwargs):
    return subprocess.run(argv,check=True,**kwargs)

def disks():
    data=json.loads(subprocess.check_output(['lsblk','-b','-J','-o','PATH,TYPE,SIZE,FSTYPE,MOUNTPOINTS,MODEL'],text=True))
    return [d for d in data['blockdevices'] if d['type']=='disk' and int(d['size'])>=16*1024**3
            and not d.get('children') and not d.get('fstype') and not any(d.get('mountpoints') or [])]

def install(device, source, notify=print):
    if os.geteuid()!=0:raise RuntimeError('安装程序需要系统权限')
    candidates={d['path'] for d in disks()}
    if device not in candidates:raise RuntimeError('只能安装到至少 16 GB、没有分区的空白虚拟磁盘')
    # Independently reject signatures not reported by lsblk.
    signatures=json.loads(subprocess.check_output(['wipefs','-J',device],text=True))
    if signatures.get('signatures'):raise RuntimeError('磁盘上已有数据，请新建空白虚拟磁盘')
    source=Path(source)
    if not source.is_file():raise RuntimeError('找不到安装光盘内容')
    notify('正在创建磁盘分区…')
    run(['sfdisk','--wipe','never',device],input='label: dos\nunit: sectors\n\nstart=2048, type=83, bootable\n',text=True)
    run(['blockdev','--rereadpt',device]);time.sleep(1)
    partition=device+('p1' if device[-1].isdigit() else '1')
    for _ in range(30):
        if Path(partition).exists():break
        time.sleep(.2)
    target=Path('/run/aimo-install-target');target.mkdir(exist_ok=True)
    mounted=False
    try:
        run(['mkfs.ext4','-q','-F','-m','1','-L','AimoOS',partition])
        run(['mount',partition,str(target)]);mounted=True
        notify('正在复制系统、办公软件和中文字体…')
        run(['unsquashfs','-no-progress','-f','-d',str(target),str(source)])
        notify('正在安装启动程序…')
        (target/'boot/grub').mkdir(parents=True,exist_ok=True)
        (target/'boot/grub/grub.cfg').write_text('set timeout=3\nset default=0\nmenuentry "AimoOS" {\n search --no-floppy --label AimoOS --set=root\n linux /boot/vmlinuz root=LABEL=AimoOS rw quiet loglevel=3\n initrd /boot/initrd.gz\n}\n')
        for name in ('dev','proc','sys'):
            run(['mount','--bind','/'+name,str(target/name)])
        try:
            run(['chroot',str(target),'grub-install','--target=i386-pc','--recheck',device])
        finally:
            for name in ('sys','proc','dev'):run(['umount',str(target/name)])
        run(['sync']);notify('安装完成。关闭虚拟机，断开 ISO，再开机创建账户。')
    finally:
        if mounted:run(['umount',str(target)])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('device');parser.add_argument('--source',default='/aimo/media/aimo/root.squashfs')
    args=parser.parse_args();install(args.device,args.source)
