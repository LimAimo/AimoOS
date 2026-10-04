import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from aimo.auth import Accounts


class AccountSetup(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.accounts=Accounts(preview=True)
        self.accounts.path=Path(self.temp.name)/"accounts.json"

    def tearDown(self):
        self.temp.cleanup()

    def test_skip_creates_local_account_and_can_set_password_later(self):
        profile=self.accounts.create("aimo","本地用户","",skip_password=True)
        self.assertTrue(profile["administrator"])
        self.assertTrue(self.accounts.verify("","aimo"))
        self.assertFalse(self.accounts.verify("wrong","aimo"))
        with self.assertRaises(ValueError):
            self.accounts.create("second","另一用户","",skip_password=True)

    def test_native_first_account_prepares_missing_groups(self):
        self.accounts.preview=False
        calls=[]
        def run(args,**kwargs):
            calls.append((args,kwargs))
        with patch.object(self.accounts,"privileged"),patch("aimo.auth.grp.getgrnam",side_effect=KeyError),patch("aimo.auth.subprocess.run",side_effect=run):
            profile=self.accounts.create("alice","爱丽丝","abc:中文 123")
        self.assertTrue(profile["administrator"])
        self.assertEqual([args for args,_ in calls[:3]],[["groupadd","--system",name] for name in ("sudo","video","audio")])
        password_call=next(kwargs for args,kwargs in calls if args==["chpasswd"])
        self.assertEqual(password_call["input"],"alice:abc:中文 123\n")
        self.assertEqual(self.accounts.profile("alice")["display_name"],"爱丽丝")

    def test_matching_password_validation_is_explicit(self):
        for password in ("123456","中文密码足够长"," leading and trailing "):
            Accounts.validate("alice","爱丽丝",password)
        with self.assertRaisesRegex(ValueError,"6 至 256"):
            Accounts.validate("alice","爱丽丝","12345")
