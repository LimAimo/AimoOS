import argparse,os,subprocess,sys,pwd,signal,shutil,time,faulthandler
from pathlib import Path

def main():
    faulthandler.enable()
    parser=argparse.ArgumentParser();parser.add_argument("--greeter",action="store_true");parser.add_argument("--desktop",action="store_true");parser.add_argument("--preview",action="store_true")
    args=parser.parse_args()
    if args.preview:
        os.environ.setdefault("AIMO_USER_HOME",str(Path.cwd()/"build/preview-home"))
        os.environ["QTWEBENGINE_DISABLE_SANDBOX"]="1"
    elif args.desktop and os.geteuid()==0:
        raise SystemExit("The desktop must run as an ordinary signed-in user")
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS","--disable-gpu --disable-dev-shm-usage")
    from PyQt6.QtCore import Qt,QLocale,QTranslator,QLibraryInfo
    from PyQt6.QtWidgets import QApplication
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    QLocale.setDefault(QLocale("zh_CN"))
    app=QApplication(sys.argv);app.setApplicationName("AimoOS");app.setQuitOnLastWindowClosed(False);app.setStyle("Fusion")
    translator=QTranslator(app)
    if translator.load("qtbase_zh_CN",QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):app.installTranslator(translator)
    from .theme import THEME,load_fonts
    load_fonts();THEME.apply()
    if args.greeter:
        from .greeter import Greeter
        greeter=Greeter(args.preview);greeter.setGeometry(app.primaryScreen().geometry());greeter.show();authenticated=[]
        greeter.authenticated.connect(lambda profile:(authenticated.append(profile),app.quit()))
        result=app.exec();greeter.close()
        if authenticated:
            profile=authenticated[0]
            if args.preview:
                from .shell import Shell
                shell=Shell(profile,True);return app.exec()
            account=pwd.getpwnam(profile["username"]);runtime=Path(f"/run/user/{account.pw_uid}")
            runtime.mkdir(parents=True,exist_ok=True);os.chown(runtime,account.pw_uid,account.pw_gid);os.chmod(runtime,0o700)
            authority=Path(account.pw_dir)/".Xauthority"
            if os.environ.get("XAUTHORITY"):
                shutil.copyfile(os.environ["XAUTHORITY"],authority)
                os.chown(authority,account.pw_uid,account.pw_gid);authority.chmod(0o600)
            env={**os.environ,"HOME":account.pw_dir,"USER":account.pw_name,"LOGNAME":account.pw_name,
                 "XDG_RUNTIME_DIR":str(runtime),"XAUTHORITY":str(authority),"AIMO_SOCKET_PATH":f"/tmp/aimoos-{account.pw_uid}.sock"}
            child=subprocess.Popen(["runuser","-u",account.pw_name,"--","dbus-run-session","--","/opt/aimoos/scripts/session.sh"],env=env,start_new_session=True)
            child.wait()
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            # Detached input-method/office processes must not survive logout.
            for sig in (signal.SIGTERM,signal.SIGKILL):
                for entry in Path("/proc").iterdir():
                    if not entry.name.isdigit():continue
                    try:
                        status=(entry/"status").read_text()
                        uid=int(next(line for line in status.splitlines() if line.startswith("Uid:")).split()[1])
                        if uid==account.pw_uid:os.kill(int(entry.name),sig)
                    except (OSError,ValueError,StopIteration):pass
                if sig==signal.SIGTERM:time.sleep(.6)
            authority.unlink(missing_ok=True)
        return result
    from .auth import Accounts
    from .shell import Shell
    profile=Accounts(args.preview).profile() or {"display_name":"LimAimo"}
    shell=Shell(profile,args.preview);return app.exec()

if __name__=="__main__":sys.exit(main())
