"""Chinese installation screen for the BIOS VMware installer ISO."""
import subprocess,sys
from PyQt6.QtCore import Qt,QThread,pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QLineEdit
from .controls import Button,label
from .theme import THEME,font,load_fonts
from scripts.install_disk import disks,install

class Worker(QThread):
    progress=pyqtSignal(str);finished_install=pyqtSignal(bool,str)
    def __init__(self,device):super().__init__();self.device=device
    def run(self):
        try:
            install(self.device,'/aimo/media/aimo/root.squashfs',self.progress.emit)
            self.finished_install.emit(True,'安装完成。先关闭虚拟机并断开 ISO，再开机创建账户。')
        except Exception as exc:self.finished_install.emit(False,'安装失败：'+str(exc))

class Installer(QWidget):
    def __init__(self):
        super().__init__();self.setWindowFlags(Qt.WindowType.FramelessWindowHint);self.setWindowTitle('AimoOS · 安装')
        outer=QHBoxLayout(self);outer.setContentsMargins(80,64,80,64);outer.addStretch()
        body=QVBoxLayout();body.setSpacing(16);body.addStretch()
        title=label('安装 AimoOS');title.setFont(font(32,serif=True));body.addWidget(title)
        body.addWidget(label('选择新建的空白虚拟磁盘。系统和文件会保存在这里。','muted'))
        self.choose=QComboBox();self.choose.setMinimumHeight(44);body.addWidget(self.choose)
        self.notice=label('仅支持 BIOS 启动，磁盘至少 16 GB。已有数据的磁盘不会出现在列表中。','muted');self.notice.setWordWrap(True);body.addWidget(self.notice)
        self.confirm=QLineEdit();self.confirm.setPlaceholderText('输入 INSTALL 确认安装到所选空白磁盘');self.confirm.setMinimumHeight(44);body.addWidget(self.confirm)
        self.status=label('','muted');self.status.setWordWrap(True);self.status.setMinimumHeight(64);body.addWidget(self.status)
        self.start=Button('开始安装',ink=True);self.start.clicked.connect(self.begin);body.addWidget(self.start)
        self.refresh=Button('重新检查磁盘');self.refresh.clicked.connect(self.scan);body.addWidget(self.refresh)
        self.power=Button('关闭虚拟机');self.power.clicked.connect(lambda:subprocess.Popen(['/usr/bin/busybox','poweroff','-f']));body.addWidget(self.power)
        body.addStretch();container=QWidget();container.setFixedWidth(600);container.setLayout(body);outer.addWidget(container);outer.addStretch();self.scan()
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),THEME.c('bg'))
    def scan(self):
        self.choose.clear()
        for d in disks():self.choose.addItem(f"{d['path']} · {int(d['size'])/1024**3:.0f} GB · {(d.get('model') or '').strip()}",d['path'])
        self.start.setEnabled(self.choose.count()>0)
        self.status.setText('' if self.choose.count() else '没有可用的空白磁盘。请关机后在 VMware 中添加至少 20 GB 的新 SATA 磁盘。')
    def begin(self):
        if self.confirm.text()!='INSTALL':self.status.setText('请输入 INSTALL 确认所选磁盘。');return
        for widget in (self.start,self.refresh,self.choose,self.confirm,self.power):widget.setEnabled(False)
        self.worker=Worker(self.choose.currentData());self.worker.progress.connect(self.status.setText);self.worker.finished_install.connect(self.done);self.worker.start()
    def done(self,ok,message):
        self.status.setText(message);self.power.setEnabled(True)
        if not ok:self.refresh.setEnabled(True)

def main():
    app=QApplication(sys.argv);app.setStyle('Fusion');load_fonts();THEME.apply()
    window=Installer();window.setGeometry(app.primaryScreen().geometry());window.show();return app.exec()
if __name__=='__main__':sys.exit(main())
