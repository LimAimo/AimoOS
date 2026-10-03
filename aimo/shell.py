import os,subprocess,threading,http.server,functools
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import Qt,QRectF,QRect,QTimer,QPoint
from PyQt6.QtGui import QPainter,QPen,QPainterPath,QImage,QPixmap
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLineEdit,QApplication,QScrollArea
from PyQt6.QtNetwork import QLocalServer
from .controls import Button,Dialog,label,animate
from .theme import THEME,font
from .icons import draw_icon,icon
from .backend import HOME,Preferences,external_apps
from .apps import Files,Notes,Terminal,Calculator,Browser,Settings

BUILTINS=[("files","文件","folder",Files),("notes","记事本","note",Notes),
          ("browser","浏览器","browser",Browser),("terminal","终端","terminal",Terminal),
          ("settings","设置","settings",Settings),("calculator","计算器","calculator",Calculator)]


class WindowRegistry:
    def __init__(self):
        from Xlib import display,X,protocol
        self.display=display.Display();self.root=self.display.screen().root;self.X=X;self.protocol=protocol
    def atom(self,name):return self.display.intern_atom(name)
    def property(self,window,name,type_name=None):
        result=window.get_full_property(self.atom(name),self.atom(type_name) if type_name else self.X.AnyPropertyType)
        return result.value if result is not None else None
    def kind(self,widget,name,strut=False):
        wid=int(widget.winId());window=self.display.create_resource_object("window",wid)
        window.change_property(self.atom("_NET_WM_WINDOW_TYPE"),self.atom("ATOM"),32,[self.atom(name)])
        if strut:
            width=widget.screen().geometry().width();height=58
            window.change_property(self.atom("_NET_WM_STRUT_PARTIAL"),self.atom("CARDINAL"),32,[0,0,0,height,0,0,0,0,0,0,0,width-1])
            window.change_property(self.atom("_NET_WM_STRUT"),self.atom("CARDINAL"),32,[0,0,0,height])
        self.display.flush()
    def clients(self):
        result=[]
        for wid in self.property(self.root,"_NET_CLIENT_LIST") or []:
            try:
                window=self.display.create_resource_object("window",int(wid))
                kinds=self.property(window,"_NET_WM_WINDOW_TYPE")
                if kinds is not None and any(x in kinds for x in [self.atom("_NET_WM_WINDOW_TYPE_DOCK"),self.atom("_NET_WM_WINDOW_TYPE_DESKTOP")]):continue
                value=self.property(window,"_NET_WM_NAME","UTF8_STRING")
                name=bytes(value).decode("utf-8","replace") if value is not None else window.get_wm_name()
                if name:result.append({"id":int(wid),"name":name})
            except Exception:continue
        return result
    def active(self):
        data=self.property(self.root,"_NET_ACTIVE_WINDOW")
        return int(data[0]) if data is not None and len(data) else 0
    def activate(self,wid):
        window=self.display.create_resource_object("window",wid)
        event=self.protocol.event.ClientMessage(window=window,client_type=self.atom("_NET_ACTIVE_WINDOW"),data=(32,[2,0,0,0,0]))
        self.root.send_event(event,event_mask=self.X.SubstructureRedirectMask|self.X.SubstructureNotifyMask)
        self.display.flush()


class Desktop(QWidget):
    def __init__(self,shell):
        super().__init__();self.shell=shell
        self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("桌面");self.setGeometry(QApplication.primaryScreen().geometry())
        for i,(title,name,app) in enumerate([("个人文件","folder","files"),("浏览器","browser","browser")]):
            button=Button(title,icon_name=name,parent=self);button.setGeometry(28,28+i*52,132,42)
            button.clicked.connect(lambda checked=False,key=app:shell.launch(key))
        THEME.changed.connect(self.update)
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),THEME.c("bg"))
        if not THEME.wallpaper:return
        if THEME.wallpaper_path:
            picture=QPixmap(THEME.wallpaper_path)
            if not picture.isNull():
                scaled=picture.scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap((self.width()-scaled.width())//2,(self.height()-scaled.height())//2,scaled);return
        p.setRenderHint(QPainter.RenderHint.Antialiasing);w,h=self.width(),self.height()
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(THEME.c("panel"))
        p.drawRect(QRectF(w*.49,h*.16,w*.40,h*.60))
        p.setPen(QPen(THEME.c("border"),1));p.setBrush(Qt.BrushStyle.NoBrush)
        for shift in [0,32,64]:
            path=QPainterPath();x=w*.59+shift;y=h*.26+shift;r=w*.20
            path.moveTo(x,y+r*.55);path.cubicTo(x,y-r*.20,x+r,y-r*.20,x+r,y+r*.55)
            path.lineTo(x+r,h*.83);path.lineTo(x,h*.83);path.closeSubpath();p.drawPath(path)
        p.setPen(QPen(THEME.c("soft"),1));p.drawLine(int(w*.26),int(h*.69),int(w*.92),int(h*.69))
        p.drawLine(int(w*.40),int(h*.12),int(w*.40),int(h*.84))
        p.setPen(THEME.c("secondary"));p.setFont(font(22,serif=True));p.drawText(QRectF(w*.55,h*.85,w*.35,55),Qt.AlignmentFlag.AlignRight,"AimoOS")


class TaskButton(Button):
    def __init__(self,shell,app_id,icon_name):
        super().__init__(icon_name=icon_name);self.shell=shell;self.app_id=app_id;self.running=False;self.active=False
    def paintEvent(self,event):
        super().paintEvent(event)
        if self.running:
            p=QPainter(self);p.setPen(QPen(THEME.c("accent" if self.active else "tertiary"),2.5))
            length=14 if self.active else 5;p.drawLine((self.width()-length)//2,self.height()-3,(self.width()+length)//2,self.height()-3)


class Taskbar(QWidget):
    def __init__(self,shell):
        super().__init__();self.shell=shell;self.buttons={}
        self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setWindowTitle("任务栏");screen=QApplication.primaryScreen().geometry();self.setGeometry(0,screen.height()-58,screen.width(),58)
        self.account=Button(icon_name="user",parent=self);self.account.setToolTip(shell.display_name);self.account.setGeometry(20,8,42,42);self.account.clicked.connect(self.account_menu)
        self.start=TaskButton(shell,"start","start");self.start.setParent(self);self.start.setToolTip("开始");self.start.clicked.connect(shell.toggle_start)
        self.clock=label("","muted")
        self.clock.setParent(self);self.clock.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.clock.setGeometry(self.width()-144,7,120,44)
        self.lock_button=Button(icon_name="lock",parent=self);self.lock_button.setGeometry(self.width()-192,8,38,42)
        self.lock_button.setToolTip("锁定屏幕");self.lock_button.clicked.connect(shell.lock)
        for app_id,title,name,_ in BUILTINS:
            button=TaskButton(shell,app_id,name);button.setParent(self);button.setToolTip(title)
            button.clicked.connect(lambda checked=False,key=app_id:shell.launch(key));self.buttons[app_id]=button
        self.arrange();THEME.changed.connect(self.update)
    def arrange(self):
        all_buttons=[self.start,*self.buttons.values()];width=len(all_buttons)*46+(len(all_buttons)-1)*4;x=(self.width()-width)//2
        for button in all_buttons:button.setGeometry(x,7,46,44);button.show();x+=50
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),THEME.c("panel"));p.setPen(THEME.c("soft"));p.drawLine(0,0,self.width(),0)
    def refresh(self,clients,active):
        own={int(window.winId()):window.app_id for window in self.shell.windows if not window._closing}
        external={str(client["id"]):client for client in clients if client["id"] not in own}
        for key in list(self.buttons):
            if key.isdigit() and key not in external:self.buttons.pop(key).deleteLater()
        for key,client in external.items():
            if key not in self.buttons:
                button=TaskButton(self.shell,key,"terminal" if "term" in client["name"].lower() else "application")
                button.setParent(self);button.clicked.connect(lambda checked=False,wid=client["id"]:self.shell.registry.activate(wid));self.buttons[key]=button
            self.buttons[key].setToolTip(client["name"])
        for key,button in self.buttons.items():
            button.running=(key in external) if key.isdigit() else key in own.values()
            button.active=(int(key)==active) if key.isdigit() else own.get(active)==key;button.update()
        self.arrange()
        now=datetime.now();self.clock.setText(now.strftime("%H:%M" if self.shell.preferences.values.get("clock24",True) else "%I:%M %p")+"\n"+f"{now.month} 月 {now.day} 日")
    def account_menu(self):
        from PyQt6.QtWidgets import QMenu
        menu=QMenu(self);menu.addAction(self.shell.display_name,lambda:self.shell.launch("settings"));menu.addSeparator()
        menu.addAction("锁定",self.shell.lock);menu.addAction("退出登录",self.shell.logout);menu.addSeparator()
        menu.addAction("重新启动",lambda:self.shell.power("reboot"));menu.addAction("关机",lambda:self.shell.power("poweroff"))
        menu.exec(self.mapToGlobal(QPoint(20,-menu.sizeHint().height()-8)))


class StartMenu(QWidget):
    def __init__(self,shell):
        super().__init__();self.shell=shell
        self.setWindowFlags(Qt.WindowType.Popup|Qt.WindowType.FramelessWindowHint);self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(550,470);self.setWindowTitle("开始")
        box=QVBoxLayout(self);box.setContentsMargins(26,24,26,20);box.setSpacing(20)
        self.query=QLineEdit();self.query.setPlaceholderText("搜索应用");self.query.textChanged.connect(self.populate);box.addWidget(self.query)
        box.addWidget(label("应用","heading"));content=QWidget();self.grid=QGridLayout(content);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(7)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.Shape.NoFrame);scroll.setWidget(content);box.addWidget(scroll,1)
        bottom=QHBoxLayout();bottom.addWidget(label(shell.display_name,"muted"));bottom.addStretch()
        lock=Button(icon_name="lock");lock.setFixedWidth(38);lock.clicked.connect(lambda:(self.hide(),shell.lock()));bottom.addWidget(lock)
        power=Button(icon_name="power");power.setFixedWidth(38);power.clicked.connect(lambda:(self.hide(),shell.power("poweroff")));bottom.addWidget(power);box.addLayout(bottom)
        self.populate()
    def populate(self):
        while self.grid.count():
            item=self.grid.takeAt(0)
            if item.widget():item.widget().deleteLater()
        query=self.query.text().strip().lower();items=[]
        for app_id,title,name,_ in BUILTINS:
            items.append((title,name,lambda key=app_id:self.open_builtin(key)))
        for entry in self.shell.external:
            items.append((entry["name"],"terminal" if "term" in entry["id"].lower() else "application",lambda e=entry:self.open_external(e)))
        items=[x for x in items if query in x[0].lower()]
        for i,(title,name,callback) in enumerate(items):
            button=Button(title,icon_name=name);button.setMinimumHeight(44)
            button.clicked.connect(lambda checked=False,cb=callback:cb());self.grid.addWidget(button,i//2,i%2)
        if not items:self.grid.addWidget(label("没有找到应用","muted"),0,0)
    def open_builtin(self,key):self.hide();self.shell.launch(key)
    def open_external(self,entry):self.hide();subprocess.Popen(entry["argv"],cwd=HOME)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(THEME.c("soft"),1));p.setBrush(THEME.c("bg"))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),8,8)
    def present(self):
        screen=QApplication.primaryScreen().geometry();self.move((screen.width()-self.width())//2,screen.height()-58-self.height()-12)
        self.show();self.query.setFocus();self.setWindowOpacity(0.);animate(self,b"windowOpacity",0.,1.,180)


class Shell:
    def __init__(self,profile,preview=False):
        self.preview=preview;self.display_name=profile.get("display_name","LimAimo");self.windows=[]
        HOME.mkdir(parents=True,exist_ok=True)
        for directory in ["文档","下载","图片"]:(HOME/directory).mkdir(exist_ok=True)
        welcome=HOME/"文档/欢迎.txt"
        if not welcome.exists():welcome.write_text("欢迎来到 AimoOS。\n\n这是你的个人文档。\n桌面上的窗口可以拖动、缩放、最小化和分屏。\n\n文件、记事本、终端、浏览器和设置已就位。\n你在这里保存的内容，会在下次登录时继续保留。\n",encoding="utf-8")
        self.preferences=Preferences();THEME.apply(**{k:v for k,v in self.preferences.values.items() if k in ("dark","reduced_motion","text_scale","wallpaper","wallpaper_path")})
        self.external=[entry for entry in external_apps() if entry["argv"][0] not in ("openbox","xcompmgr","i3lock") and not entry["id"].startswith("aimo-")]
        self.registry=WindowRegistry();self.desktop=Desktop(self);self.registry.kind(self.desktop,"_NET_WM_WINDOW_TYPE_DESKTOP");self.desktop.show();self.desktop.lower()
        self.taskbar=Taskbar(self);self.registry.kind(self.taskbar,"_NET_WM_WINDOW_TYPE_DOCK",True);self.taskbar.show()
        self.start_menu=StartMenu(self)
        self.timer=QTimer();self.timer.timeout.connect(self.refresh);self.timer.start(350);self.dragging=False
        self.control=QLocalServer();path=os.environ.get("AIMO_SOCKET_PATH",f"/tmp/aimoos-{os.getuid()}.sock")
        QLocalServer.removeServer(path);self.control.listen(path);os.chmod(path,0o600)
        self.control.newConnection.connect(self.command)
        handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(Path(__file__).parents[1]/"assets/web"))
        try:
            server=http.server.ThreadingHTTPServer(("127.0.0.1",8765),handler)
            threading.Thread(target=server.serve_forever,daemon=True).start();self.web_server=server
        except OSError:self.web_server=None
        self.refresh()
    def launch(self,app_id):
        for window in self.windows:
            if window.app_id==app_id and not window._closing:window.reveal();return window
        match=next((item for item in BUILTINS if item[0]==app_id),None)
        if not match:return
        window=match[3](self);window.setWindowIcon(icon(match[2]));self.windows.append(window)
        window.destroyed.connect(lambda _,w=window:self.windows.remove(w) if w in self.windows else None)
        offset=(len(self.windows)-1)%4;window.move(150+offset*48,82+offset*35);window.enter();return window
    def open_document(self,path):
        if path.suffix.lower() in (".txt",".md",".py",".json",".log",".sh",".css",".html",""):
            window=Notes(self,path);window.setWindowIcon(icon("note"));self.windows.append(window)
            window.destroyed.connect(lambda _,w=window:self.windows.remove(w) if w in self.windows else None);window.move(330,120);window.enter()
        else:subprocess.Popen(["xdg-open",str(path)],cwd=HOME)
    def toggle_start(self):
        if self.start_menu.isVisible():self.start_menu.hide()
        else:self.start_menu.present()
    def refresh(self):
        try:
            clients=self.registry.clients();active=self.registry.active();self.taskbar.refresh(clients,active)
            pointer=self.registry.root.query_pointer();pressed=bool(pointer.mask&self.registry.X.Button1Mask)
            if self.dragging and not pressed:
                for window in self.windows:
                    if int(window.winId())!=active or window.expanded:continue
                    geometry=window.geometry();screen=window.screen().availableGeometry()
                    if geometry.x()<=8:self.snap(window,"left")
                    elif geometry.right()>=screen.right()-8:self.snap(window,"right")
                    elif geometry.y()<=8:window.maximize()
            self.dragging=pressed
        except Exception:pass
    def snap(self,window,direction):
        screen=window.screen().availableGeometry();window.normal_rect=window.geometry();window.expanded=False
        width=screen.width()//2;x=screen.x() if direction=="left" else screen.x()+width
        animate(window,b"geometry",window.geometry(),QRect(x,screen.y(),width,screen.height()),260)
    def command(self):
        connection=self.control.nextPendingConnection()
        def read():
            value=bytes(connection.readAll()).decode("utf-8","replace").strip()
            if value=="toggle-start":self.toggle_start()
            elif value.startswith("launch:"):self.launch(value.split(":",1)[1])
            elif value.startswith("browser:"):
                from PyQt6.QtCore import QUrl
                window=self.launch("browser");window.view.load(QUrl.fromUserInput(value.split(":",1)[1]))
            elif value=="lock":self.lock()
            elif value=="logout":self.logout()
            elif value.startswith("snap-"):
                active=self.registry.active();window=next((w for w in self.windows if int(w.winId())==active),None)
                if window:self.snap(window,value[5:])
                else:
                    screen=QApplication.primaryScreen().availableGeometry();half=screen.width()//2;x=0 if value.endswith("left") else half
                    subprocess.run(["wmctrl","-ir",hex(active),"-b","remove,maximized_vert,maximized_horz"])
                    subprocess.run(["wmctrl","-ir",hex(active),"-e",f"0,{x},0,{half},{screen.height()-25}"])
            connection.disconnectFromServer()
        connection.readyRead.connect(read)
        if connection.bytesAvailable():read()
    def lock(self):
        if self.preview:return
        screen=QApplication.primaryScreen().geometry();image=QImage(screen.size(),QImage.Format.Format_RGB32)
        image.fill(THEME.c("bg"));p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(THEME.c("text"));p.setFont(font(34,serif=True))
        p.drawText(QRectF(0,screen.height()*.20,screen.width(),80),Qt.AlignmentFlag.AlignCenter,self.display_name)
        p.setPen(THEME.c("secondary"));p.setFont(font(12))
        p.drawText(QRectF(0,screen.height()*.31,screen.width(),45),Qt.AlignmentFlag.AlignCenter,"屏幕已锁定")
        p.drawText(QRectF(0,screen.height()*.70,screen.width(),45),Qt.AlignmentFlag.AlignCenter,"输入密码，按 Enter 解锁。")
        p.setPen(QPen(THEME.c("soft"),1));p.drawLine(80,screen.height()-100,screen.width()-80,screen.height()-100);p.end()
        path=HOME/".cache/aimoos/lock.png";path.parent.mkdir(parents=True,exist_ok=True);image.save(str(path))
        subprocess.Popen(["i3lock","--image",str(path),"--color",THEME.value("bg").lstrip("#")])
    def can_leave(self):
        for window in self.windows:
            if isinstance(window,Notes) and window.dirty and not window.guard():return False
        return True
    def logout(self):
        dialog=Dialog("退出登录","请先保存其他应用中尚未保存的内容。",accept="退出登录",parent=self.taskbar)
        # quit() sends close events, which our animated windows deliberately
        # defer. After the save guards succeed, exit the session event loop so
        # those animations cannot veto logout and leave a hidden desktop alive.
        if dialog.exec() and self.can_leave():QApplication.instance().exit(0)
    def power(self,action):
        title="重新启动" if action=="reboot" else "关机"
        dialog=Dialog(title,"请先保存其他应用中尚未保存的内容。",accept=title,parent=self.taskbar)
        if not dialog.exec() or not self.can_leave():return
        if self.preview:return
        subprocess.Popen(["sudo","-n","/opt/aimoos/scripts/power-helper",action])
