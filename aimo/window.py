"""Native top-level windows; Openbox handles external clients and global keys."""
from PyQt6.QtCore import Qt, QRect, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter,QPen,QFont
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QApplication,QLayout
from .controls import Button,animate
from .theme import THEME,font,RADII


class TitleBar(QWidget):
    def __init__(self,window,title):
        super().__init__(window);self.owner=window;self.setFixedHeight(46)
        row=QHBoxLayout(self);row.setContentsMargins(16,4,6,4);row.setSpacing(2)
        self.title=QLabel(title);self.title.setFont(font(10,weight=QFont.Weight.Medium))
        row.addWidget(self.title);row.addStretch()
        for name,callback,tip in [("minimize",window.minimize,"最小化"),("maximize",window.maximize,"最大化"),("close",window.close,"关闭")]:
            button=Button(icon_name=name,danger=name=="close");button.setFixedSize(38,34)
            button.setToolTip(tip);button.clicked.connect(callback);row.addWidget(button)
            if name=="maximize":self.max_button=button

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            if self.owner.expanded:self.owner.restore_geometry()
            handle=self.owner.windowHandle()
            if handle:handle.startSystemMove()

    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.owner.maximize()


class Window(QWidget):
    minimized=pyqtSignal(object)

    def __init__(self,title,app_id,size=(940,610)):
        super().__init__()
        self.app_id=app_id;self.expanded=False;self.normal_rect=None;self._closing=False
        self.setWindowTitle(title);self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(520,340);self.resize(*size);self.setMouseTracking(True)
        outer=QVBoxLayout(self);self.outer_layout=outer;outer.setContentsMargins(6,6,6,6);outer.setSpacing(0)
        self.titlebar=TitleBar(self,title);outer.addWidget(self.titlebar)
        self.body=QWidget();self.layout=QVBoxLayout(self.body)
        self.layout.setContentsMargins(24,16,24,20);self.layout.setSpacing(16);outer.addWidget(self.body,1)
        THEME.changed.connect(self.update)

    def set_title(self,title):self.setWindowTitle(title);self.titlebar.title.setText(title)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(THEME.c("border"),1));p.setBrush(THEME.c("bg"))
        radius=0 if self.expanded or self.isMaximized() else RADII["surface"]
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),radius,radius)
        p.setPen(QPen(THEME.c("soft"),1));p.drawLine(16,52,self.width()-16,52)

    def mouseMoveEvent(self,event):
        x,y=event.position().x(),event.position().y();edge=7
        horizontal=(x<edge or x>self.width()-edge);vertical=(y<edge or y>self.height()-edge)
        if horizontal and vertical:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor if (x<edge)==(y<edge) else Qt.CursorShape.SizeBDiagCursor)
        elif horizontal:self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif vertical:self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:self.unsetCursor()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or self.expanded:return
        x,y=event.position().x(),event.position().y();edges=Qt.Edge(0)
        if x<7:edges|=Qt.Edge.LeftEdge
        if x>self.width()-7:edges|=Qt.Edge.RightEdge
        if y<7:edges|=Qt.Edge.TopEdge
        if y>self.height()-7:edges|=Qt.Edge.BottomEdge
        if edges and self.windowHandle():self.windowHandle().startSystemResize(edges)

    def maximize(self):
        if self.expanded:self.restore_geometry();return
        self.normal_rect=self.geometry();self.expanded=True
        screen=self.screen().availableGeometry();self.titlebar.max_button.icon_name="restore"
        animate(self,b"geometry",self.geometry(),screen,280)

    def restore_geometry(self):
        if not self.expanded:return
        self.expanded=False;self.titlebar.max_button.icon_name="maximize"
        animate(self,b"geometry",self.geometry(),self.normal_rect or QRect(160,100,900,600),260)

    def minimize(self):
        rect=self.geometry();target=QRect(rect.center().x()-60,self.screen().geometry().bottom()-48,120,32)
        self.minimize_rect=rect;minimum=self.minimumSize()
        self.setMinimumSize(1,1);self.outer_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        animation=animate(self,b"geometry",rect,target,220)
        def finish():
            self.showMinimized();self.setMinimumSize(minimum);self.setGeometry(rect)
            self.minimized.emit(self)
        if THEME.duration(220):animation.finished.connect(finish)
        else:finish()

    def reveal(self):
        if self.isMinimized():
            target=getattr(self,"minimize_rect",self.geometry());minimum=self.minimumSize();self.setMinimumSize(1,1)
            start=QRect(target.center().x()-60,self.screen().geometry().bottom()-48,120,32)
            self.setGeometry(start);self.showNormal();animation=animate(self,b"geometry",start,target,220)
            if THEME.duration(220):animation.finished.connect(lambda:self.setMinimumSize(minimum))
            else:self.setMinimumSize(minimum)
        else:self.show()
        self.raise_();self.activateWindow()

    def closeEvent(self,event):
        if self._closing:event.accept();return
        event.ignore();self._closing=True
        animation=animate(self,b"windowOpacity",self.windowOpacity(),0.,150)
        if THEME.duration(150):animation.finished.connect(self._finish_close)
        else:self._finish_close()

    def _finish_close(self):self.hide();self.deleteLater()

    def enter(self):
        screen=self.screen().availableGeometry()
        self.resize(min(self.width(),screen.width()-32),min(self.height(),screen.height()-32))
        self.move(max(screen.x()+16,min(self.x(),screen.right()-self.width()-15)),max(screen.y()+16,min(self.y(),screen.bottom()-self.height()-15)))
        self.show();self.setWindowOpacity(0.);animate(self,b"windowOpacity",0.,1.,180)
