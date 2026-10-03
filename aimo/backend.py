"""Real filesystem/preferences/application services, independent of rendering."""
from pathlib import Path
import ast
import configparser
import json
import operator
import os
import shlex
import shutil
import socket
import subprocess
import tempfile
import urllib.parse
from datetime import datetime

HOME=Path(os.environ.get("AIMO_USER_HOME",str(Path.home())))


def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix=".aimo-")
    try:
        with os.fdopen(fd,"w") as handle:
            json.dump(data,handle,ensure_ascii=False,indent=2);handle.flush();os.fsync(handle.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


class Preferences:
    def __init__(self):
        self.path=HOME/".config/aimoos/preferences.json"
        self.values=dict(dark=False,reduced_motion=False,text_scale=1.0,wallpaper=True,wallpaper_path="",clock24=True)
        try:self.values.update(json.loads(self.path.read_text()))
        except (OSError,ValueError):pass

    def set(self,key,value):
        updated={**self.values,key:value};atomic_json(self.path,updated);self.values=updated


def valid_filename(name):
    if not name or name in (".","..") or "/" in name or "\0" in name:
        raise ValueError("请输入有效的文件名")
    return name


def move_to_trash(path):
    path=Path(path);valid_filename(path.name)
    base=HOME/".local/share/Trash";files=base/"files";info=base/"info"
    files.mkdir(parents=True,exist_ok=True);info.mkdir(exist_ok=True)
    name=path.name;count=1
    while (files/name).exists() or (files/name).is_symlink() or (info/(name+".trashinfo")).exists():
        name=f"{path.name}.{count}";count+=1
    metadata="[Trash Info]\nPath="+urllib.parse.quote(str(path.absolute()))+"\nDeletionDate="+datetime.now().strftime("%Y-%m-%dT%H:%M:%S")+"\n"
    temp=info/(name+".trashinfo")
    temp.write_text(metadata)
    try:shutil.move(str(path),str(files/name))
    except Exception:temp.unlink(missing_ok=True);raise
    return files/name


def restore_from_trash(path):
    path=Path(path);base=HOME/".local/share/Trash"
    if path.parent.resolve()!=(base/"files").resolve():raise ValueError("请选择回收站中的项目")
    metadata=base/"info"/(path.name+".trashinfo")
    parser=configparser.ConfigParser(interpolation=None);parser.read(metadata)
    try:target=Path(urllib.parse.unquote(parser["Trash Info"]["Path"]))
    except KeyError:raise ValueError("这个项目没有原位置记录") from None
    if not target.is_absolute():raise ValueError("原位置记录无效")
    if target.exists() or target.is_symlink():raise ValueError("原位置已经有同名文件")
    if not target.parent.is_dir():raise ValueError("原文件夹不存在，请先还原文件夹")
    shutil.move(str(path),str(target));metadata.unlink();return target


OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,
     ast.Div:operator.truediv,ast.Mod:operator.mod,ast.USub:operator.neg,ast.UAdd:operator.pos}


def calculate(expression):
    if len(expression)>160:raise ValueError("算式太长了")
    tree=ast.parse(expression.replace("×","*").replace("÷","/"),mode="eval")
    def evaluate(node,depth=0):
        if depth>32:raise ValueError("算式太复杂了")
        if isinstance(node,ast.Expression):return evaluate(node.body,depth+1)
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            if abs(node.value)>1e100:raise ValueError("数字超出范围")
            return node.value
        if isinstance(node,ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](evaluate(node.left,depth+1),evaluate(node.right,depth+1))
        if isinstance(node,ast.UnaryOp) and type(node.op) in OPS:return OPS[type(node.op)](evaluate(node.operand,depth+1))
        raise ValueError("暂不支持这个算式")
    return evaluate(tree)


def external_apps():
    roots=[Path(os.environ.get("AIMO_APPLICATION_DIR","/usr/share/applications")),HOME/".local/share/applications"]
    result=[];seen=set()
    for root in roots:
        for path in sorted(root.glob("*.desktop")):
            try:
                parser=configparser.ConfigParser(interpolation=None,strict=False)
                parser.read(path);entry=parser["Desktop Entry"]
                if entry.get("Type")!="Application" or entry.get("NoDisplay")=="true" or entry.get("Hidden")=="true" or entry.get("Terminal")=="true":continue
                argv=[x for x in shlex.split(entry.get("Exec","")) if not x.startswith("%")]
                if not argv or not shutil.which(argv[0]) or path.name in seen:continue
                seen.add(path.name)
                result.append(dict(id=path.stem,name=entry.get("Name[zh_CN]",entry.get("Name",path.stem)),argv=argv,icon="application"))
            except (OSError,KeyError,ValueError,configparser.Error):continue
    return result


def network_info():
    addresses=[]
    try:
        output=subprocess.check_output(["ip","-j","address"],text=True,stderr=subprocess.DEVNULL)
        for interface in json.loads(output):
            if interface.get("ifname")=="lo":continue
            for entry in interface.get("addr_info",[]):
                if entry.get("family")=="inet":addresses.append((interface["ifname"],entry["local"]))
    except (OSError,ValueError,subprocess.SubprocessError):pass
    return addresses
