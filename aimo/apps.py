from pathlib import Path
import os, shutil, socket, subprocess, urllib.parse, codecs, base64, json
from PyQt6.QtCore import Qt,QUrl,QTimer,QProcess,QSaveFile,QIODevice,QRectF
from PyQt6.QtGui import QShortcut,QKeySequence,QPainter,QPen,QFontMetrics,QColor,QFileSystemModel
from PyQt6.QtWidgets import (QWidget,QHBoxLayout,QVBoxLayout,QLabel,QLineEdit,QTreeView,
    QFileIconProvider,QPlainTextEdit,QGridLayout,QStackedWidget,QSlider,QApplication,QAbstractItemView,QScrollArea)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile,QWebEnginePage,QWebEngineSettings
from .window import Window
from .controls import Button,Dialog,Segmented,Switch,Line,label
from .theme import THEME,font
from .icons import icon
from .backend import HOME,calculate,valid_filename,move_to_trash,restore_from_trash,network_info
from .auth import Accounts,account_request


def shortcut(owner,sequence,callback):
    key=QShortcut(QKeySequence(sequence),owner);key.activated.connect(callback);return key


def error_dialog(parent,message):
    dialog=Dialog("暂时无法完成",message,parent=parent);dialog.exec()


class FileModel(QFileSystemModel):
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if orientation==Qt.Orientation.Horizontal and role==Qt.ItemDataRole.DisplayRole:
            return ["名称","大小","类型","修改时间"][section]
        return super().headerData(section,orientation,role)
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if role==Qt.ItemDataRole.DecorationRole and index.column()==0:
            return self.icons["folder" if self.fileInfo(index).isDir() else "file"]
        if role==Qt.ItemDataRole.DisplayRole and index.column()==2:
            info=self.fileInfo(index)
            return "文件夹" if info.isDir() else (info.suffix().upper()+" 文件" if info.suffix() else "文件")
        return super().data(index,role)


class Files(Window):
    def __init__(self,shell):
        super().__init__("文件","files",(1040,660));self.shell=shell;self.directory=HOME;self.history=[]
        self.layout.addWidget(label("文件","heading"))
        toolbar=QHBoxLayout();toolbar.setSpacing(6)
        for name,tip,callback in [("back","返回",self.back),("home","个人文件",lambda:self.navigate(HOME))]:
            button=Button(icon_name=name);button.setFixedWidth(38);button.setToolTip(tip);button.clicked.connect(callback);toolbar.addWidget(button)
        self.path=QLineEdit(str(HOME));self.path.returnPressed.connect(lambda:self.navigate(Path(self.path.text()).expanduser()));toolbar.addWidget(self.path,1)
        new=Button("新建",icon_name="plus");new.clicked.connect(self.new_menu);toolbar.addWidget(new)
        self.layout.addLayout(toolbar)
        main=QHBoxLayout();main.setSpacing(24)
        sidebar=QVBoxLayout();sidebar.setSpacing(8)
        for title,path in [("个人文件",HOME),("文档",HOME/"文档"),("下载",HOME/"下载"),("回收站",HOME/".local/share/Trash/files")]:
            button=Button(title,icon_name="trash" if title=="回收站" else "folder");button.setFixedWidth(132)
            button.clicked.connect(lambda checked=False,p=path:self.navigate(p));sidebar.addWidget(button)
        sidebar.addStretch();main.addLayout(sidebar)
        self.model=FileModel(self)
        # QFileSystemModel invokes its provider on the filesystem worker.
        # Keep that provider native; paint our cached icons through data() on
        # the GUI thread rather than invoking Python/QPixmap from the worker.
        self.file_icons=QFileIconProvider();self.model.setIconProvider(self.file_icons)
        self.model.icons={name:icon(name) for name in ("folder","file")}
        self.model.setRootPath(str(HOME))
        self.model.setReadOnly(True)
        self.tree=QTreeView();self.tree.setModel(self.model);self.tree.setRootIndex(self.model.index(str(HOME)))
        self.tree.setRootIsDecorated(False);self.tree.setSortingEnabled(True);self.tree.sortByColumn(0,Qt.SortOrder.AscendingOrder)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setColumnWidth(0,310);self.tree.setColumnWidth(1,100);self.tree.setColumnWidth(2,120)
        self.tree.doubleClicked.connect(self.open_index);main.addWidget(self.tree,1);self.layout.addLayout(main,1)
        bottom=QHBoxLayout();self.status=label(str(HOME),"muted");bottom.addWidget(self.status,1)
        for title,callback in [("重命名",self.rename),("移入回收站",self.trash)]:
            button=Button(title);button.clicked.connect(callback);bottom.addWidget(button)
        self.restore_button=Button("还原");self.restore_button.clicked.connect(self.restore);bottom.addWidget(self.restore_button);self.restore_button.hide()
        self.layout.addLayout(bottom)
        shortcut(self,"Ctrl+C",self.copy);shortcut(self,"Ctrl+V",self.paste);shortcut(self,"F2",self.rename);shortcut(self,"Delete",self.trash)
        THEME.changed.connect(self.refresh_icons)

    def refresh_icons(self):
        self.model.icons={name:icon(name) for name in ("folder","file")}
        self.tree.viewport().update()

    def navigate(self,path,remember=True):
        if not path.is_dir():error_dialog(self,"这个文件夹不存在");return
        if remember:self.history.append(self.directory)
        self.directory=path.resolve();self.tree.setRootIndex(self.model.index(str(self.directory)))
        self.path.setText(str(self.directory));self.status.setText(str(self.directory))
        self.restore_button.setVisible(self.directory==(HOME/".local/share/Trash/files").resolve())
    def back(self):
        if self.history:self.navigate(self.history.pop(),False)
    def selected(self):return [Path(self.model.filePath(i)) for i in self.tree.selectionModel().selectedRows(0)]
    def open_index(self,index):
        path=Path(self.model.filePath(index))
        if path.is_dir():self.navigate(path)
        else:self.shell.open_document(path)
    def new_menu(self):
        from PyQt6.QtWidgets import QMenu
        menu=QMenu(self);menu.addAction("新建文件夹",lambda:self.new_item(True));menu.addAction("新建文档",lambda:self.new_item(False))
        menu.exec(self.mapToGlobal(self.rect().topRight())-__import__('PyQt6.QtCore',fromlist=['QPoint']).QPoint(230,-94))
    def new_item(self,directory):
        dialog=Dialog("新建文件夹" if directory else "新建文档",input_value="新建文件夹" if directory else "未命名.txt",parent=self)
        if not dialog.exec():return
        try:
            path=self.directory/valid_filename(dialog.input.text())
            if directory:path.mkdir()
            else:
                with path.open("x",encoding="utf-8"):pass
        except (OSError,ValueError) as exc:error_dialog(self,str(exc))
    def rename(self):
        paths=self.selected()
        if len(paths)!=1:return
        dialog=Dialog("重命名",input_value=paths[0].name,parent=self)
        if not dialog.exec():return
        try:
            target=paths[0].with_name(valid_filename(dialog.input.text()))
            if target.exists():raise ValueError("已经有同名文件了")
            paths[0].rename(target)
        except (OSError,ValueError) as exc:error_dialog(self,str(exc))
    def trash(self):
        paths=self.selected()
        if not paths:return
        dialog=Dialog("移入回收站",f"将选中的 {len(paths)} 项移入回收站？",accept="移入",parent=self)
        if not dialog.exec():return
        try:
            for path in paths:move_to_trash(path)
        except OSError as exc:error_dialog(self,str(exc))
    def copy(self):
        from PyQt6.QtCore import QMimeData
        data=QMimeData();data.setUrls([QUrl.fromLocalFile(str(p)) for p in self.selected()]);QApplication.clipboard().setMimeData(data)
    def restore(self):
        try:
            for path in self.selected():restore_from_trash(path)
        except (OSError,ValueError) as exc:error_dialog(self,str(exc))
    def paste(self):
        try:
            for url in QApplication.clipboard().mimeData().urls():
                path=Path(url.toLocalFile());target=self.directory/path.name
                if target.exists():raise ValueError("目标文件夹已有同名文件")
                if path.is_dir() and target.resolve().is_relative_to(path.resolve()):raise ValueError("不能把文件夹复制到自身内部")
                if path.is_dir():shutil.copytree(path,target)
                else:shutil.copy2(path,target)
        except (OSError,ValueError) as exc:error_dialog(self,str(exc))


class Notes(Window):
    def __init__(self,shell,path=None):
        super().__init__("记事本","notes",(880,650));self.path=None;self.dirty=False
        row=QHBoxLayout();row.addWidget(label("记事本","heading"));row.addStretch()
        for title,callback in [("打开",self.open_request),("另存为",lambda:self.save(True)),("保存",self.save)]:
            button=Button(title,primary=title=="保存");button.clicked.connect(callback);row.addWidget(button)
        self.layout.addLayout(row)
        self.editor=QPlainTextEdit();self.editor.setFont(font(11));self.editor.setStyleSheet("QPlainTextEdit{border:0;background:transparent;padding:4px;}")
        self.layout.addWidget(self.editor,1);self.status=label("未保存的文档","muted");self.layout.addWidget(self.status)
        self.editor.textChanged.connect(self.changed)
        shortcut(self,"Ctrl+S",self.save);shortcut(self,"Ctrl+O",self.open_request)
        if path:self.load(path)
    def changed(self):
        self.dirty=True;self.status.setText(f"{len(self.editor.toPlainText())} 字符 · 尚未保存")
        self.set_title("记事本 · "+(self.path.name if self.path else "未命名")+" *")
    def load(self,path):
        try:
            if path.stat().st_size>4*1024*1024:raise ValueError("这个文件超过记事本当前支持的 4 MB 大小")
            text=path.read_text(encoding="utf-8",errors="replace")
            self.editor.setPlainText(text);self.path=path;self.dirty=False
            self.set_title("记事本 · "+path.name);self.status.setText(str(path))
        except (OSError,ValueError) as exc:error_dialog(self,str(exc))
    def open_request(self):
        if self.dirty and not self.guard():return
        dialog=Dialog("打开文档",input_value=str(HOME/"文档/欢迎.txt"),parent=self)
        if dialog.exec():self.load(Path(dialog.input.text()).expanduser())
    def save(self,save_as=False):
        if save_as or self.path is None:
            dialog=Dialog("保存文档",input_value=str(self.path or HOME/"文档/未命名.txt"),accept="保存",parent=self)
            if not dialog.exec():return False
            target=Path(dialog.input.text()).expanduser()
            if target.exists() and target!=self.path:
                confirm=Dialog("替换已有文件",f"“{target.name}”已经存在。替换后原内容会被覆盖。",accept="替换",danger=True,parent=self)
                if not confirm.exec():return False
        else:target=self.path
        output=QSaveFile(str(target))
        if not output.open(QIODevice.OpenModeFlag.WriteOnly):error_dialog(self,output.errorString());return False
        output.write(self.editor.toPlainText().encode("utf-8"))
        if not output.commit():error_dialog(self,output.errorString());return False
        self.path=target;self.dirty=False;self.status.setText(str(target));self.set_title("记事本 · "+target.name);return True
    def guard(self):
        dialog=Dialog("保存更改", "这份文档还没有保存。",accept="保存",parent=self)
        discard=Button("不保存");discard.clicked.connect(lambda:dialog.done(2))
        dialog.layout().itemAt(dialog.layout().count()-1).layout().insertWidget(0,discard)
        from PyQt6.QtWidgets import QDialog
        result=dialog.exec()
        if result==QDialog.DialogCode.Accepted:return self.save()
        if result==2:self.dirty=False;return True
        return False
    def closeEvent(self,event):
        if self.dirty and not self._closing and not self.guard():event.ignore();return
        super().closeEvent(event)


class Calculator(Window):
    def __init__(self,shell):
        super().__init__("计算器","calculator",(400,590));self.setMinimumSize(360,500)
        self.layout.addWidget(label("计算器","heading"));self.history=label("","muted");self.layout.addWidget(self.history)
        self.expression=QLineEdit("0");self.expression.setAlignment(Qt.AlignmentFlag.AlignRight);self.expression.setMinimumHeight(68)
        self.expression.setStyleSheet("QLineEdit{font-size:32px;border:0;background:transparent;}");self.layout.addWidget(self.expression)
        grid=QGridLayout();grid.setSpacing(6)
        for row,items in enumerate([["C","(",")","÷"],["7","8","9","×"],["4","5","6","−"],["1","2","3","+"],["⌫","0",".","="]]):
            for column,text in enumerate(items):
                button=Button(text,primary=text=="=");button.setMinimumHeight(55)
                button.clicked.connect(lambda checked=False,value=text:self.press(value));grid.addWidget(button,row,column)
        self.layout.addLayout(grid,1);self.expression.returnPressed.connect(lambda:self.press("="))
    def press(self,value):
        text=self.expression.text()
        if value=="C":self.expression.setText("0");self.history.clear()
        elif value=="⌫":self.expression.setText(text[:-1] or "0")
        elif value=="=":
            try:
                answer=calculate(text.replace("−","-"));self.history.setText(text+" =")
                self.expression.setText(format(answer,".12g"))
            except (ValueError,SyntaxError,ZeroDivisionError,OverflowError):self.history.setText("请检查算式")
        else:self.expression.setText(("" if text=="0" and value not in [".","÷","×","+","−"] else text)+value)


class Browser(Window):
    def __init__(self,shell,url=None):
        super().__init__("浏览器","browser",(1110,710));self.layout.setContentsMargins(10,10,10,10);self.layout.setSpacing(8)
        row=QHBoxLayout();row.setSpacing(4)
        self.view=QWebEngineView()
        # The profile must outlive the page, which is owned by the view/body.
        self.profile=QWebEngineProfile("aimo-browser",self)
        self.profile.setPersistentStoragePath(str(HOME/".local/share/aimoos/browser"))
        self.profile.setCachePath(str(HOME/".cache/aimoos/browser"))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        self.view.setPage(QWebEnginePage(self.profile,self.view))
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled,True)
        self.view.page().fullScreenRequested.connect(self.fullscreen_request)
        for name,tip,callback in [("back","返回",self.view.back),("forward","前进",self.view.forward),("refresh","刷新",self.view.reload),("home","首页",self.home)]:
            button=Button(icon_name=name);button.setFixedWidth(36);button.setToolTip(tip);button.clicked.connect(callback);row.addWidget(button)
        self.address=QLineEdit();self.address.setPlaceholderText("搜索或输入网址");self.address.returnPressed.connect(self.navigate);row.addWidget(self.address,1)
        self.layout.addLayout(row);self.layout.addWidget(self.view,1)
        self.status=label("","muted");self.layout.addWidget(self.status)
        self.view.urlChanged.connect(lambda url:self.address.setText(url.toString()))
        self.view.titleChanged.connect(lambda title:self.set_title("浏览器 · "+title[:60]))
        self.view.loadProgress.connect(lambda p:self.status.setText("正在打开网页" if p<100 else ""))
        self.view.loadFinished.connect(lambda ok:self.status.setText("" if ok else "网页未能打开，请检查地址或连接后重试"))
        self.view.page().profile().downloadRequested.connect(self.download)
        shortcut(self,"Ctrl+L",lambda:(self.address.setFocus(),self.address.selectAll()))
        if url:self.view.load(QUrl(str(url)))
        else:self.home()
    def home(self):self.view.load(QUrl("http://127.0.0.1:8765/"))
    def navigate(self):
        value=self.address.text().strip()
        if not value:return
        if "://" not in value:
            value="https://"+value if "." in value and " " not in value else "https://duckduckgo.com/?q="+urllib.parse.quote(value)
        url=QUrl(value)
        if url.scheme() not in ("http","https","file","about"):
            self.status.setText("暂不支持这个地址类型");return
        self.view.load(url)
    def download(self,item):
        destination=HOME/"下载";destination.mkdir(exist_ok=True)
        item.setDownloadDirectory(str(destination));item.accept()
        self.status.setText("正在下载 · "+item.downloadFileName())
        item.isFinishedChanged.connect(lambda:self.status.setText("下载完成 · "+item.downloadFileName() if item.isFinished() else self.status.text()))
    def fullscreen_request(self,request):
        request.accept()
        if request.toggleOn():self.showFullScreen()
        else:self.showNormal()


class TerminalView(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        import pyte
        self.screen_data=pyte.Screen(100,30);self.stream=pyte.Stream(self.screen_data)
        self.decoder=codecs.getincrementaldecoder("utf-8")("replace")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);self.setMinimumSize(300,200)
        self.process=QProcess(self);self.process.setProgram(__import__('sys').executable)
        self.process.setArguments([str(Path(__file__).with_name("pty_worker.py"))]);self.process.setWorkingDirectory(str(HOME))
        self.process.readyReadStandardOutput.connect(self.read);self.process.start()
        self.blink=True;self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(550)
    def tick(self):
        self.blink=True if THEME.reduced_motion else not self.blink;self.update()
    def read(self):
        data=bytes(self.process.readAllStandardOutput());self.stream.feed(self.decoder.decode(data));self.update()
    def send(self,data):self.process.write((json.dumps({"data":base64.b64encode(data.encode()).decode()})+"\n").encode())
    def resizeEvent(self,event):
        metrics=QFontMetrics(font(10,mono=True));self.cell_width=metrics.horizontalAdvance("M");self.cell_height=metrics.height()+3
        columns=max(10,(self.width()-20)//self.cell_width);rows=max(4,(self.height()-12)//self.cell_height)
        self.screen_data.resize(rows,columns)
        self.process.write((json.dumps({"resize":[columns,rows]})+"\n").encode())
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),THEME.c("bg"));p.setFont(font(10,mono=True))
        metrics=p.fontMetrics();width=metrics.horizontalAdvance("M");height=metrics.height()+3
        colors={"red":"#C27666","green":"#6C967B","yellow":"#B79B65","blue":"#7E9BAB","magenta":"#AB869C","cyan":"#6B9B9D","black":THEME.value("text"),"white":THEME.value("text"),"default":THEME.value("text")}
        for y in range(self.screen_data.lines):
            for x,char in self.screen_data.buffer[y].items():
                if char.data in (""," "):continue
                p.setPen(QColor(colors.get(char.fg,THEME.value("text"))))
                p.drawText(10+x*width,6+y*height+metrics.ascent(),char.data)
        if self.hasFocus() and self.blink:
            p.setPen(QPen(THEME.c("accent"),2));cursor=self.screen_data.cursor
            p.drawLine(10+cursor.x*width,6+(cursor.y+1)*height-2,10+(cursor.x+1)*width-1,6+(cursor.y+1)*height-2)
    def keyPressEvent(self,event):
        if event.modifiers()&Qt.KeyboardModifier.ControlModifier:
            if event.modifiers()&Qt.KeyboardModifier.ShiftModifier and event.key()==Qt.Key.Key_V:self.send(QApplication.clipboard().text());return
            if Qt.Key.Key_A<=event.key()<=Qt.Key.Key_Z:self.send(chr(event.key()-Qt.Key.Key_A+1));return
        codes={Qt.Key.Key_Return:"\r",Qt.Key.Key_Enter:"\r",Qt.Key.Key_Backspace:"\x7f",Qt.Key.Key_Tab:"\t",Qt.Key.Key_Escape:"\x1b",Qt.Key.Key_Up:"\x1b[A",Qt.Key.Key_Down:"\x1b[B",Qt.Key.Key_Right:"\x1b[C",Qt.Key.Key_Left:"\x1b[D",Qt.Key.Key_Home:"\x1b[H",Qt.Key.Key_End:"\x1b[F",Qt.Key.Key_Delete:"\x1b[3~"}
        text=codes.get(event.key(),event.text())
        if text:self.send(text)
    def stop(self):self.process.terminate();self.process.waitForFinished(500)


class Terminal(Window):
    def __init__(self,shell):
        super().__init__("终端","terminal",(900,570));self.layout.addWidget(label("终端","heading"))
        self.terminal=TerminalView();self.layout.addWidget(self.terminal,1);self.terminal.setFocus()
    def closeEvent(self,event):
        self.terminal.stop();super().closeEvent(event)


class Settings(Window):
    def __init__(self,shell):
        super().__init__("设置","settings",(1020,680));self.shell=shell
        main=QHBoxLayout();main.setSpacing(60)
        left=QVBoxLayout();left.addWidget(label("设置","heading"));left.addWidget(label(shell.display_name,"muted"));left.addStretch();main.addLayout(left,1)
        right=QVBoxLayout();right.setSpacing(20)
        sections=Segmented([("外观","appearance"),("系统","system"),("账户","account"),("关于","about")])
        right.addWidget(sections);self.pages=QStackedWidget();right.addWidget(self.pages,1);main.addLayout(right,3);self.layout.addLayout(main,1)
        def page(title):
            widget=QWidget();box=QVBoxLayout(widget);box.setContentsMargins(0,10,0,0);box.setSpacing(20)
            box.addWidget(label(title,"heading"));scroll=QScrollArea();scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame);scroll.setWidget(widget);self.pages.addWidget(scroll);return box
        appearance=page("外观")
        mode=Segmented([("浅色","light"),("深色","dark")],"dark" if THEME.dark else "light")
        mode.selected.connect(lambda value:self.set_pref("dark",value=="dark"));self.row(appearance,"主题",mode)
        wallpaper=Switch(THEME.wallpaper);wallpaper.toggled.connect(lambda on:self.set_pref("wallpaper",on));self.row(appearance,"显示壁纸",wallpaper)
        pictures=QHBoxLayout();choose=Button("选择图片");choose.clicked.connect(self.choose_wallpaper);pictures.addWidget(choose)
        original=Button("恢复纸面");original.clicked.connect(lambda:self.set_pref("wallpaper_path",""));pictures.addWidget(original)
        picture_widget=QWidget();picture_widget.setLayout(pictures);self.row(appearance,"壁纸",picture_widget)
        motion=Switch(THEME.reduced_motion);motion.toggled.connect(lambda on:self.set_pref("reduced_motion",on));self.row(appearance,"减少动态效果",motion)
        scale=Segmented([("标准","1.0"),("较大","1.15")],str(THEME.text_scale))
        scale.selected.connect(lambda value:self.set_pref("text_scale",float(value)));self.row(appearance,"文字大小",scale)
        appearance.addStretch()
        system=page("系统")
        self.row(system,"网络",label("已连接" if network_info() else "尚未连接"))
        for name,address in network_info():self.row(system,name,label(address,"muted"))
        self.row(system,"主机名",label(socket.gethostname(),"muted"))
        self.row(system,"处理器",label(os.uname().machine,"muted"))
        usage=shutil.disk_usage(HOME);self.row(system,"可用空间",label(f"{usage.free/1024**3:.1f} GB","muted"))
        clock=Switch(shell.preferences.values.get("clock24",True));clock.toggled.connect(lambda on:self.set_pref("clock24",on));self.row(system,"24 小时时间",clock);system.addStretch()
        account=page("账户");self.row(account,"显示名称",label(shell.display_name));self.row(account,"用户名",label(os.environ.get("USER","aimo"),"muted"))
        self.row(account,"个人文件",label(str(HOME),"muted"))
        self.row(account,"账户类型",label("管理员" if Accounts().profile() and Accounts().profile().get("administrator") else "标准用户","muted"))
        password=Button("修改密码");password.clicked.connect(self.password_request);self.row(account,"密码",password)
        profiles=Accounts().all()
        if profiles:self.row(account,"系统账户",label("、".join(p["display_name"] for p in profiles),"muted"))
        if Accounts().profile() and Accounts().profile().get("administrator"):
            add=Button("添加账户",icon_name="plus");add.clicked.connect(self.create_account);self.row(account,"其他用户",add)
        lock=Button("锁定屏幕",icon_name="lock");lock.clicked.connect(shell.lock);self.row(account,"锁屏",lock)
        logout=Button("退出登录");logout.clicked.connect(shell.logout);self.row(account,"登录",logout);account.addStretch()
        about=page("AimoOS");about.addWidget(label("纸、墨与日常。"));about.addWidget(label("为利姆艾莫制作。","muted"))
        about.addSpacing(12);self.row(about,"内核",label(os.uname().release,"muted"));self.row(about,"系统底座",label("Ubuntu 24.04 LTS","muted"))
        about.addStretch()
        sections.selected.connect(lambda value:self.pages.setCurrentIndex(["appearance","system","account","about"].index(value)))
    def row(self,layout,title,control):
        if getattr(layout,"_has_rows",False):layout.addWidget(Line())
        layout._has_rows=True;control.setAccessibleName(title)
        row=QHBoxLayout();row.addWidget(label(title));row.addStretch();row.addWidget(control);layout.addLayout(row)
    def set_pref(self,key,value):
        try:
            self.shell.preferences.set(key,value)
            if key!="clock24":THEME.apply(**{key:value})
        except OSError:error_dialog(self,"偏好暂时没有保存，请稍后重试")

    def choose_wallpaper(self):
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtGui import QImageReader
        path,_=QFileDialog.getOpenFileName(self,"选择壁纸",str(HOME/"图片"),"图片 (*.png *.jpg *.jpeg *.webp)")
        if not path:return
        if not QImageReader(path).canRead():error_dialog(self,"这个图片暂时无法打开");return
        self.set_pref("wallpaper_path",path);self.set_pref("wallpaper",True)

    def account_dialog(self,title,fields,action):
        dialog=Dialog(title,accept="保存",parent=self);form=QVBoxLayout();inputs={}
        for key,caption,password in fields:
            form.addWidget(label(caption,"section"));entry=QLineEdit()
            if password:entry.setEchoMode(QLineEdit.EchoMode.Password)
            form.addWidget(entry);inputs[key]=entry
        status=label("","muted");status.setWordWrap(True);form.addWidget(status)
        dialog.layout().insertLayout(1,form)
        while dialog.exec():
            values={key:entry.text() for key,entry in inputs.items()}
            if values["password"]!=values.pop("confirm"):
                status.setText("两次输入的密码不一致");continue
            try:
                account_request(action,**values)
                for entry in inputs.values():entry.clear()
                return
            except (ValueError,OSError,subprocess.SubprocessError) as exc:status.setText(str(exc))
        for entry in inputs.values():entry.clear()
    def password_request(self):
        self.account_dialog("修改密码",[("old_password","当前密码",True),("password","新密码",True),("confirm","确认新密码",True)],"password")
    def create_account(self):
        self.account_dialog("添加账户",[("display_name","显示名称",False),("username","用户名",False),("password","密码",True),("confirm","确认密码",True)],"create")
