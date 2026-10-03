"""Exercise filesystem workers, themed icons and repeated window destruction."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtTest import QTest
except ImportError:
    QApplication=None

@unittest.skipIf(QApplication is None,'Run with the extracted Qt runtime for native checks')
class NativeFiles(unittest.TestCase):
    def test_worker_loading_theme_changes_and_reopen(self):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        app=QApplication.instance() or QApplication([])
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

if __name__=='__main__':unittest.main()
