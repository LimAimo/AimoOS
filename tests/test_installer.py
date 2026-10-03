"""The installer must never choose a populated or mounted disk."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.install_disk import disks,install

class InstallerSafety(unittest.TestCase):
    def test_only_blank_unmounted_large_disks_are_candidates(self):
        base={'type':'disk','size':20*1024**3,'fstype':None,'mountpoints':[None]}
        values=[dict(base,path='/dev/sda'),dict(base,path='/dev/sdb',children=[{'path':'/dev/sdb1'}]),
                dict(base,path='/dev/sdc',fstype='ext4'),dict(base,path='/dev/sdd',mountpoints=['/']),
                dict(base,path='/dev/sde',size=8*1024**3),dict(base,path='/dev/sr0',type='rom')]
        with patch('scripts.install_disk.subprocess.check_output',return_value=json.dumps({'blockdevices':values})):
            self.assertEqual([d['path'] for d in disks()],['/dev/sda'])
    def test_changed_disk_is_rejected_before_writes(self):
        with patch('scripts.install_disk.os.geteuid',return_value=0),patch('scripts.install_disk.disks',return_value=[]),patch('scripts.install_disk.run') as write:
            with self.assertRaises(RuntimeError):install('/dev/sda','/missing.iso')
            write.assert_not_called()
    def test_signatures_are_checked_before_partitioning(self):
        with patch('scripts.install_disk.os.geteuid',return_value=0),patch('scripts.install_disk.disks',return_value=[{'path':'/dev/sda'}]),patch('scripts.install_disk.subprocess.check_output',return_value='{"signatures":[{"type":"ext4"}]}'),patch('scripts.install_disk.run') as write:
            with self.assertRaises(RuntimeError):install('/dev/sda','/missing.iso')
            write.assert_not_called()
