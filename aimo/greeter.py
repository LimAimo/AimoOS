from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter,QPen
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QLabel,QStackedWidget
from .auth import Accounts
from .controls import Button,label,Segmented
from .theme import THEME,font


class Greeter(QWidget):
    authenticated=pyqtSignal(dict)

    def __init__(self,preview=False):
        super().__init__();self.accounts=Accounts(preview);self.first_run=self.accounts.profile() is None
        self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("AimoOS · 登录")
        self.fields={}
        layout=QHBoxLayout(self);layout.setContentsMargins(110,80,110,80);layout.setSpacing(110)
        left=QVBoxLayout();left.addStretch()
        brand=label("AimoOS");brand.setFont(font(39,serif=True));left.addWidget(brand)
        caption=label("从这里开始。" if self.first_run else "欢迎回来。")
        caption.setFont(font(19,serif=True));left.addSpacing(20);left.addWidget(caption)
        left.addSpacing(20);line=label("你的文件、应用与日常。","muted");left.addWidget(line);left.addStretch()
        footer=label("利姆艾莫","muted");left.addWidget(footer)
        layout.addLayout(left,1)
        form_widget=QWidget();form_widget.setFixedWidth(370)
        form=QVBoxLayout(form_widget);form.setContentsMargins(0,0,0,0);form.setSpacing(10)
        form.addStretch()
        self.profile=self.accounts.profile()
        self.account_title=label("设置你的账户" if self.first_run else self.profile["display_name"],"heading")
        form.addWidget(self.account_title)
        if not self.first_run and len(self.accounts.all())>1:
            choose=Button("切换账户",icon_name="user");choose.clicked.connect(self.choose_account);form.addWidget(choose)
        form.addSpacing(20)
        fields=[("display_name","显示名称","利姆艾莫",False),("username","用户名","aimo",False),
                ("password","密码","",True),("confirm","确认密码","",True)] if self.first_run else [("password","密码","",True)]
        for key,title,value,password in fields:
            form.addWidget(label(title,"section"));entry=QLineEdit(value);entry.setMinimumHeight(43)
            if password:entry.setEchoMode(QLineEdit.EchoMode.Password)
            if key=="username":entry.setPlaceholderText("小写字母、数字或下划线")
            self.fields[key]=entry;form.addWidget(entry);form.addSpacing(9)
        self.error=label("","muted");self.error.setWordWrap(True);self.error.setMinimumHeight(32);form.addWidget(self.error)
        submit=Button("创建账户" if self.first_run else "登录",ink=True);submit.setMinimumHeight(43)
        submit.clicked.connect(self.submit);form.addWidget(submit)
        if self.first_run:
            skip=Button("跳过此步骤");skip.setMinimumHeight(43)
            skip.clicked.connect(self.skip_setup);form.addWidget(skip)
            hint=label("跳过后使用无密码的本地账户，可在设置中添加密码。","muted")
            hint.setWordWrap(True);form.addWidget(hint)
            self.fields["password"].setPlaceholderText("6 至 256 个字符")
        self.fields[fields[-1][0]].returnPressed.connect(self.submit)
        form.addSpacing(20)
        self.theme_control=Segmented([("浅色","light"),("深色","dark")])
        self.theme_control.selected.connect(lambda value:THEME.apply(dark=value=="dark"));form.addWidget(self.theme_control)
        form.addStretch();layout.addWidget(form_widget)
        THEME.changed.connect(self.update)

    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),THEME.c("bg"));p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(THEME.c("soft"),1));x=self.width()-520
        p.drawLine(x,80,x,self.height()-80)
        p.setPen(QPen(THEME.c("border"),1));p.drawArc(QRectF(-180,self.height()-320,570,570),0,180*16)
        p.drawLine(75,self.height()-136,420,self.height()-136)

    def submit(self):
        password=self.fields["password"].text()
        try:
            if self.first_run:
                if password!=self.fields["confirm"].text():raise ValueError("两次输入的密码不一致")
                profile=self.accounts.create(self.fields["username"].text().strip(),self.fields["display_name"].text().strip(),password)
            else:
                if not self.accounts.verify(password,self.profile["username"]):raise ValueError("密码不正确，请再试一次")
                profile=self.profile
            for field in self.fields.values():
                if field.echoMode()==QLineEdit.EchoMode.Password:field.clear()
            self.authenticated.emit(profile)
        except Exception as exc:
            # Never include subprocess stdin, shadow hashes or credentials in UI/logs.
            message=str(exc) if isinstance(exc,ValueError) else "暂时无法完成，请检查后重试"
            self.error.setText(message)

    def skip_setup(self):
        if not self.first_run:return
        try:
            username="aimo"
            if not self.accounts.preview:
                import pwd
                index=0
                while True:
                    try:pwd.getpwnam(username)
                    except KeyError:break
                    index+=1;username=f"aimo{index}"
            profile=self.accounts.create(username,"本地用户","",skip_password=True)
            for field in self.fields.values():field.clear()
            self.authenticated.emit(profile)
        except Exception as exc:
            self.error.setText(str(exc) if isinstance(exc,ValueError) else "无法创建本地账户，请重试")

    def choose_account(self):
        from PyQt6.QtWidgets import QMenu
        menu=QMenu(self)
        for profile in self.accounts.all():
            menu.addAction(profile["display_name"],lambda checked=False,p=profile:self.select_account(p))
        menu.exec(self.account_title.mapToGlobal(self.account_title.rect().bottomLeft()))

    def select_account(self,profile):
        self.profile=profile;self.account_title.setText(profile["display_name"])
        self.fields["password"].clear();self.fields["password"].setFocus();self.error.clear()
