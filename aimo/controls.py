"""Shared native controls: motion, pointer geometry and focus belong here."""
from PyQt6.QtCore import Qt, QRectF, QPointF, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QKeyEvent
from PyQt6.QtWidgets import QAbstractButton, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit
from .theme import THEME, font, RADII
from .icons import draw_icon


def blend(a, b, t):
    return QColor.fromRgbF(a.redF()*(1-t)+b.redF()*t, a.greenF()*(1-t)+b.greenF()*t,
                          a.blueF()*(1-t)+b.blueF()*t, a.alphaF()*(1-t)+b.alphaF()*t)


def animate(owner, prop, start, end, duration=260):
    previous = getattr(owner, "_animation_"+prop.decode(), None)
    if previous:
        previous.stop()
    animation = QPropertyAnimation(owner, prop, owner)
    animation.setStartValue(start); animation.setEndValue(end)
    animation.setDuration(THEME.duration(duration))
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    setattr(owner, "_animation_"+prop.decode(), animation)
    animation.start()
    return animation


class Button(QAbstractButton):
    def __init__(self, text="", icon_name=None, *, primary=False, danger=False, ink=False, parent=None):
        super().__init__(parent)
        self.setText(text); self.icon_name = icon_name
        self.primary = primary; self.danger = danger; self.ink=ink; self._hover = 0.0; self._key_focus = False
        self.setMinimumHeight(38); self.setMinimumWidth(40 if not text else 76)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @pyqtProperty(float)
    def hover(self): return self._hover
    @hover.setter
    def hover(self, value): self._hover=value; self.update()

    def enterEvent(self, event): animate(self,b"hover",self._hover,1.,140)
    def leaveEvent(self, event): animate(self,b"hover",self._hover,0.,140)
    def focusInEvent(self, event):
        self._key_focus = event.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event); self.update()
    def focusOutEvent(self,event): super().focusOutEvent(event); self.update()
    def mousePressEvent(self,event): self._key_focus=False; super().mousePressEvent(event); self.update()
    def mouseReleaseEvent(self,event): super().mouseReleaseEvent(event); self.update()

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(self.rect()).adjusted(1,1,-1,-1)
        if self.ink:
            bg=blend(THEME.c("text"),THEME.c("secondary"),self._hover);fg=THEME.c("bg")
        elif self.primary:
            bg=blend(THEME.c("accent"),THEME.c("accent_hover"),self._hover)
            fg=THEME.c("accent_text")
        else:
            bg=blend(THEME.c("bg"),THEME.c("sunken"),self._hover)
            fg=THEME.c("danger" if self.danger else "text")
        if self.isDown(): bg=bg.darker(108 if not THEME.dark else 118)
        if not self.isEnabled(): p.setOpacity(.45)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(bg)
        p.drawRoundedRect(rect,RADII["control"],RADII["control"])
        if self.hasFocus() and self._key_focus:
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(THEME.c("accent"),1.5)); p.drawRoundedRect(rect,4,4)
        p.setFont(font(10)); p.setPen(fg)
        if self.icon_name:
            x=12 if self.text() else (self.width()-19)/2
            draw_icon(p,self.icon_name,QRectF(x,(self.height()-19)/2,19,19),fg)
        if self.text():
            p.drawText(QRectF(37 if self.icon_name else 9,0,self.width()-(46 if self.icon_name else 18),self.height()),Qt.AlignmentFlag.AlignCenter,self.text())


class Switch(QAbstractButton):
    def __init__(self,checked=False,parent=None):
        super().__init__(parent); self.setCheckable(True); self.setChecked(checked)
        self.setFixedSize(54,44); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self._position=float(checked)
        self.toggled.connect(lambda on: animate(self,b"position",self._position,float(on),220))

    @pyqtProperty(float)
    def position(self): return self._position
    @position.setter
    def position(self,x): self._position=x; self.update()

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(9,12,36,20); p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(blend(THEME.c("border"),THEME.c("accent"),self._position)); p.drawRoundedRect(rect,10,10)
        p.setBrush(THEME.c("elevated") if not self.isChecked() else THEME.c("accent_text"))
        p.drawEllipse(QRectF(12+16*self._position,15,14,14))


class Segmented(QWidget):
    selected = pyqtSignal(str)

    def __init__(self,items,value=None,parent=None):
        super().__init__(parent)
        self.items=items; self.value=value or items[0][1]; self._marker=QRectF()
        self._press=None; self._dragging=False; self._press_center=0
        self.setFont(font(9.5));self.setFixedHeight(38); self.setMinimumWidth(sum(self.fontMetrics().horizontalAdvance(x[0])+30 for x in items)+6)
        self.setCursor(Qt.CursorShape.PointingHandCursor); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        THEME.changed.connect(self.reflow)

    def reflow(self):
        self.setFont(font(9.5))
        self.setMinimumWidth(sum(self.fontMetrics().horizontalAdvance(x[0])+30 for x in self.items)+6)
        animation=getattr(self,"_animation_marker",None)
        if not animation or animation.endValue()!=self.target():self.setValue(self.value)
        self.update()

    def rectangles(self):
        widths=[self.fontMetrics().horizontalAdvance(label)+30 for label,_ in self.items]
        total=sum(widths); extra=max(0,self.width()-6-total)/len(widths)
        x=3.; result=[]
        for width in widths:
            result.append(QRectF(x,3,width+extra,32)); x+=width+extra
        return result

    @pyqtProperty(QRectF)
    def marker(self): return self._marker
    @marker.setter
    def marker(self,rect): self._marker=rect; self.update()

    def target(self):
        return self.rectangles()[next((i for i,x in enumerate(self.items) if x[1]==self.value),0)]

    def setValue(self,value,emit=False):
        self.value=value; target=self.target()
        if self._marker.isEmpty(): self._marker=target
        else: animate(self,b"marker",self._marker,target,260)
        self.update()
        if emit:self.selected.emit(value)

    def resizeEvent(self,event):
        anim=getattr(self,"_animation_marker",None)
        if anim:anim.stop()
        self._marker=self.target(); self.update()

    def paintEvent(self,event):
        if self._marker.isEmpty():self._marker=self.target()
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(THEME.c("soft"),1));p.setBrush(THEME.c("panel"));p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),5,5)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(THEME.c("text"));p.drawRoundedRect(self._marker,4,4)
        p.setFont(font(9.5))
        for rect,(label,_) in zip(self.rectangles(),self.items):
            p.setPen(THEME.c("secondary"));p.drawText(rect,Qt.AlignmentFlag.AlignCenter,label)
            # Only covered glyph pixels invert. Icons and surrounding UI never do.
            p.save();p.setClipRect(self._marker);p.setPen(THEME.c("bg"))
            p.drawText(rect,Qt.AlignmentFlag.AlignCenter,label);p.restore()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        self._press=event.position();self._dragging=False;self._press_center=self._marker.center().x()

    def mouseMoveEvent(self,event):
        if self._press is None:return
        dx=event.position().x()-self._press.x()
        if not self._dragging and abs(dx)<6:return
        if not self._dragging:
            self._dragging=True;self.grabMouse()
            animation=getattr(self,"_animation_marker",None)
            if animation:animation.stop()
        rects=self.rectangles();x=max(rects[0].center().x(),min(rects[-1].center().x(),self._press_center+dx))
        for left,right in zip(rects,rects[1:]):
            if left.center().x()<=x<=right.center().x():
                t=(x-left.center().x())/(right.center().x()-left.center().x())
                self.marker=QRectF(left.x()+(right.x()-left.x())*t,3,left.width()+(right.width()-left.width())*t,32);break
        else:self.marker=rects[0] if x<=rects[0].center().x() else rects[-1]

    def mouseReleaseEvent(self,event):
        if self._press is None:return
        rects=self.rectangles()
        x=self._marker.center().x() if self._dragging else event.position().x()
        if self._dragging:self.releaseMouse()
        index=min(range(len(rects)),key=lambda i:abs(rects[i].center().x()-x))
        self._press=None;self._dragging=False;self.setValue(self.items[index][1],True)

    def keyPressEvent(self,event):
        index=next(i for i,x in enumerate(self.items) if x[1]==self.value)
        if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right):
            index=(index+(-1 if event.key()==Qt.Key.Key_Left else 1))%len(self.items)
            self.setValue(self.items[index][1],True)
        else:super().keyPressEvent(event)


class Dialog(QDialog):
    def __init__(self,title,message="",*,input_value=None,accept="确定",danger=False,parent=None):
        super().__init__(parent)
        self.setWindowTitle(title);self.setWindowFlags(Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(420);self.setMaximumWidth(520)
        layout=QVBoxLayout(self);layout.setContentsMargins(28,24,28,24);layout.setSpacing(18)
        heading=QLabel(title);heading.setFont(font(18,serif=True));layout.addWidget(heading)
        if message:
            label=QLabel(message);label.setWordWrap(True);label.setObjectName("muted");layout.addWidget(label)
        self.input=None
        if input_value is not None:
            self.input=QLineEdit(input_value);layout.addWidget(self.input)
        row=QHBoxLayout();row.addStretch()
        cancel=Button("取消");ok=Button(accept,primary=not danger,danger=danger)
        cancel.clicked.connect(self.reject);ok.clicked.connect(self.accept)
        row.addWidget(cancel);row.addWidget(ok);layout.addLayout(row)
        if danger:cancel.setFocus()
        elif self.input:self.input.setFocus();self.input.selectAll();self.input.returnPressed.connect(self.accept)
        else:ok.setFocus()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(THEME.c("soft"),1));p.setBrush(THEME.c("bg"))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),12,12)

    def showEvent(self,event):
        super().showEvent(event)
        self.setWindowOpacity(0.);animate(self,b"windowOpacity",0.,1.,180)


class Line(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedHeight(1);THEME.changed.connect(self.update)
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),THEME.c("soft"))


def label(text,kind=None):
    result=QLabel(text)
    if kind:result.setObjectName(kind)
    return result
