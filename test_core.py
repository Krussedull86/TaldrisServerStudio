import tempfile, unittest, zipfile, sys, subprocess
from pathlib import Path
from core import Manager, command, local_path
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.base=Path(self.tmp.name)
        self.m=Manager(self.base/'data'); self.p=self.m.state['servers'][0]; self.root=self.base/'server'; self.root.mkdir(); self.p['root']=str(self.root)
    def test_escape(self):
        with self.assertRaises(ValueError):local_path(self.root,'../outside')
    def test_mod_arguments(self):
        self.p['mods']=[dict(folder='@CF',id='1559212036',server=False,enabled=True),dict(folder='@Private',id='',server=True,enabled=True)]
        args=command(self.p); self.assertIn('-mod=@CF',args); self.assertIn('-serverMod=@Private',args)
        self.p['mods'][0]['folder']='@a;@b'
        with self.assertRaises(ValueError):command(self.p)
    def test_mod_servermod_and_both_preserve_order(self):
        self.p['mods']=[dict(folder='@Client',id='',server=False,enabled=True),dict(folder='@Both',id='',server=False,load_mode='both',enabled=True),dict(folder='@Server',id='',server=True,enabled=True),dict(folder='@Off',id='',load_mode='both',enabled=False)]
        args=command(self.p); self.assertIn('-mod=@Client;@Both',args); self.assertIn('-serverMod=@Both;@Server',args)
        self.m.save(); self.assertEqual(Manager(self.base/'data').state['servers'][0]['mods'][1]['load_mode'],'both')
    def test_backup_and_persist(self):
        (self.root/'serverDZ.cfg').write_text('hostname="test";'); (self.root/'mpmissions').mkdir(); (self.root/'mpmissions'/'state.bin').write_bytes(b'abc')
        self.m.backup(self.p)
        archive=next((self.base/'data'/'backups').rglob('*.zip'))
        with zipfile.ZipFile(archive) as z:self.assertEqual(z.read('mpmissions/state.bin'),b'abc'); self.assertIsNone(z.testzip())
        self.m.save(); self.assertEqual(Manager(self.base/'data').state['servers'][0]['root'],str(self.root))
    def test_deploy(self):
        src=self.base/'workshop'/'123'/'addons'; src.mkdir(parents=True); (src/'test.pbo').write_bytes(b'pbo')
        keys=src.parent/'keys'; keys.mkdir(); (keys/'test.bikey').write_bytes(b'key')
        self.p['workshop']=str(self.base/'workshop'); self.p['mods']=[dict(folder='@Test',id='123',enabled=True,server=False)]
        self.m.deploy(self.p); self.assertEqual((self.root/'@Test'/'addons'/'test.pbo').read_bytes(),b'pbo'); self.assertTrue((self.root/'keys'/'test.bikey').exists())
        (self.root/'@Test'/'stale.pbo').touch(); self.m.deploy(self.p); self.assertFalse((self.root/'@Test'/'stale.pbo').exists())
    def test_missing_executable(self):
        with self.assertRaises(ValueError):self.m.start(self.p)
    def test_active_job_blocked(self):
        process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']); self.m.procs[self.p['id']]=process
        try:
            with self.assertRaises(ValueError):self.m.job(self.p,self.m.backup)
        finally:process.terminate(); process.wait()
if __name__=='__main__':unittest.main()
