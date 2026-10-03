"""Linux accounts. Privileged entry points are confined to the guest."""
from pathlib import Path
import hashlib
import hmac
import json
import os
import pwd
import re
import subprocess
from .backend import atomic_json

ACCOUNT=Path("/etc/aimo/accounts.json")


class Accounts:
    def __init__(self,preview=False):
        self.preview=preview
        self.path=Path(os.environ.get("AIMO_PREVIEW_ACCOUNT","build/preview-accounts.json")) if preview else ACCOUNT

    def all(self):
        try:
            value=json.loads(self.path.read_text())
            return value if isinstance(value,list) else [value]
        except (OSError,ValueError):return []

    def profile(self,username=None):
        profiles=self.all()
        if username is None and os.geteuid()!=0:username=pwd.getpwuid(os.getuid()).pw_name
        return next((p for p in profiles if p["username"]==username),None) if username else (profiles[0] if profiles else None)

    def privileged(self):
        if self.preview:return
        if os.geteuid()!=0 or not Path("/etc/aimo-release").exists():
            raise PermissionError("账户操作只能由 AimoOS 登录服务处理")

    @staticmethod
    def validate(username,display_name,password):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,23}",username):raise ValueError("用户名请使用小写字母、数字或下划线，以字母开头")
        if not display_name or len(display_name)>48 or any(x in display_name for x in ":\n\r\0"):raise ValueError("请输入有效的显示名称")
        if len(password)<6 or len(password)>256 or any(x in password for x in "\n\r\0"):raise ValueError("密码需要 6 至 256 个字符")

    def create(self,username,display_name,password):
        self.privileged();self.validate(username,display_name,password)
        profiles=self.all()
        if any(p["username"]==username for p in profiles):raise ValueError("这个用户名已经存在")
        profile={"username":username,"display_name":display_name,"administrator":not profiles}
        if self.preview:
            salt=os.urandom(16)
            profile.update(salt=salt.hex(),digest=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex())
        else:
            subprocess.run(["useradd","--create-home","--shell","/bin/bash","--user-group","--comment",display_name,username],check=True,capture_output=True)
            try:
                subprocess.run(["chpasswd"],input=f"{username}:{password}\n",text=True,check=True,capture_output=True)
                groups="sudo,video,audio" if profile["administrator"] else "video,audio"
                subprocess.run(["usermod","-aG",groups,username],check=True,capture_output=True)
            except subprocess.SubprocessError:
                subprocess.run(["userdel","--remove",username],capture_output=True)
                raise RuntimeError("账户创建未完成，请重试") from None
        atomic_json(self.path,[*profiles,profile])
        if not self.preview:os.chmod(self.path,0o644)
        return profile

    def verify(self,password,username=None):
        profile=self.profile(username)
        if not profile:return False
        if self.preview:
            digest=hashlib.scrypt(password.encode(),salt=bytes.fromhex(profile["salt"]),n=16384,r=8,p=1).hex()
            return hmac.compare_digest(digest,profile["digest"])
        self.privileged()
        import crypt,spwd
        try:digest=spwd.getspnam(profile["username"]).sp_pwdp
        except KeyError:return False
        if not digest or digest.startswith(("!","*")):return False
        return hmac.compare_digest(crypt.crypt(password,digest) or "",digest)

    def change_password(self,username,old_password,new_password):
        self.privileged()
        profile=self.profile(username)
        if not profile or not self.verify(old_password,username):raise ValueError("当前密码不正确")
        self.validate(username,profile["display_name"],new_password)
        subprocess.run(["chpasswd"],input=f"{username}:{new_password}\n",text=True,check=True,capture_output=True)


def account_request(action,**values):
    """Passwords travel over stdin, never command-line arguments or logs."""
    result=subprocess.run(["sudo","-n","/opt/aimoos/scripts/account-helper"],
        input=json.dumps({"action":action,**values}),text=True,capture_output=True,timeout=15)
    try:reply=json.loads(result.stdout)
    except ValueError:raise ValueError("账户服务暂时不可用") from None
    if not reply.get("ok"):raise ValueError(reply.get("message","账户操作未完成"))
    return reply
