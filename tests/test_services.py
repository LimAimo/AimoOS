"""Behavioral checks for data safety and calculator execution boundaries."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from aimo import backend
from aimo.auth import Accounts

class Services(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.home=Path(self.directory.name)
        self.change=patch.object(backend,'HOME',self.home);self.change.start()
    def tearDown(self):self.change.stop();self.directory.cleanup()
    def test_calculator_precedence_and_nonexecution(self):
        self.assertEqual(backend.calculate('(12+8)×3÷2'),30)
        for value in ["__import__('os').system('true')",'x+1','2**99999','[1][0]']:
            with self.subTest(value=value),self.assertRaises(ValueError):backend.calculate(value)
    def test_preferences_survive_new_session(self):
        first=backend.Preferences();first.set('dark',True);first.set('text_scale',1.15)
        second=backend.Preferences();self.assertTrue(second.values['dark']);self.assertEqual(second.values['text_scale'],1.15)
        self.assertEqual(first.path.stat().st_mode&0o777,0o600)
    def test_trash_preserves_collisions_and_original_locations(self):
        source=self.home/'计划.txt';source.write_text('第一份',encoding='utf-8')
        first=backend.move_to_trash(source);source.write_text('第二份',encoding='utf-8')
        second=backend.move_to_trash(source)
        self.assertNotEqual(first,second);self.assertEqual(first.read_text(),'第一份');self.assertEqual(second.read_text(),'第二份')
        restored=backend.restore_from_trash(first);self.assertEqual(restored,source)
        with self.assertRaises(ValueError):backend.restore_from_trash(second)
        self.assertTrue(second.exists())
    def test_filenames_do_not_escape_directory(self):
        for name in ['', '.', '..', '../outside','/etc/passwd','null\0name']:
            with self.subTest(name=name),self.assertRaises(ValueError):backend.valid_filename(name)
        self.assertEqual(backend.valid_filename('工作计划.txt'),'工作计划.txt')
    def test_multiple_accounts_verify_independently(self):
        with patch.dict(os.environ,{'AIMO_PREVIEW_ACCOUNT':str(self.home/'accounts.json')}):
            accounts=Accounts(preview=True)
            first=accounts.create('alice','甲用户','fixture-alpha')
            second=accounts.create('bob','乙用户','fixture-beta')
            self.assertTrue(first['administrator']);self.assertFalse(second['administrator'])
            self.assertTrue(accounts.verify('fixture-alpha','alice'))
            self.assertFalse(accounts.verify('fixture-alpha','bob'))
            self.assertFalse(accounts.verify('wrong-password','alice'))
            with self.assertRaises(ValueError):accounts.create('alice','同名','fixture-alpha')
            self.assertNotIn('fixture-alpha',accounts.path.read_text())

if __name__=='__main__':unittest.main()
