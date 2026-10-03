"""Exercise filesystem workers, themed icons and repeated window destruction."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PyQt6.QtCore import Qt,QTimer
    from PyQt6.QtWidgets import QApplication,QWidget
    from PyQt6.QtTest import QTest
except ImportError:
    QApplication=None

_APP=None
def application():
    global _APP
    if _APP is None:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        _APP=QApplication.instance() or QApplication([])
    return _APP

@unittest.skipIf(QApplication is None,'Run with the extracted Qt runtime for native checks')
class NativeFiles(unittest.TestCase):
    def test_worker_loading_theme_changes_and_reopen(self):
        app=application()
        from aimo import apps
        from aimo.theme import THEME
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory)
            for i in range(120):(home/f'文档-{i:03d}.txt').write_text(str(i))
            with patch.object(apps,'HOME',home):
                THEME.apply(reduced_motion=True)
                for cycle in range(3):
                    window=apps.Files(SimpleNamespace())
                    window.show();root=window.model.index(str(home))
                    for _ in range(50):
                        QTest.qWait(20)
                        if window.model.rowCount(root)==120:break
                    self.assertEqual(window.model.rowCount(root),120)
                    for dark in (True,False):
                        THEME.apply(dark=dark);app.processEvents()
                        for row in range(120):
                            index=window.model.index(row,0,root)
                            self.assertFalse(window.model.data(index,Qt.ItemDataRole.DecorationRole).isNull())
                    window.close();app.processEvents();QTest.qWait(40)
                THEME.apply(dark=False,reduced_motion=False)


@unittest.skipIf(QApplication is None,'Run with the extracted Qt runtime for native checks')
class NativeSession(unittest.TestCase):
    def test_logout_exits_with_animated_windows_open(self):
        app=application()
        app.setQuitOnLastWindowClosed(False)
        from aimo.controls import Dialog
        from aimo.shell import Shell
        from aimo.window import Window
        from aimo.theme import THEME
        THEME.apply(reduced_motion=False)
        taskbar=QWidget();taskbar.show()
        window=Window('Session document','notes');window.show()
        shell=Shell.__new__(Shell);shell.taskbar=taskbar;shell.windows=[]
        expired=[]
        watchdog=QTimer();watchdog.setSingleShot(True)
        watchdog.timeout.connect(lambda:(expired.append(True),app.exit(1)))
        def confirm():
            dialog=app.activeModalWidget()
            if isinstance(dialog,Dialog):dialog.accept()
            else:QTimer.singleShot(10,confirm)
        QTimer.singleShot(30,confirm)
        QTimer.singleShot(0,shell.logout)
        watchdog.start(1500)
        try:
            self.assertEqual(app.exec(),0)
            self.assertFalse(expired,'Animated close events prevented the session from exiting')
        finally:
            watchdog.stop();taskbar.close()
            if not window._closing:window._finish_close()
            app.processEvents();QTest.qWait(40)

if __name__=='__main__':unittest.main()
