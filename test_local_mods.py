import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from core import Manager,command,validate_mod
from local_mods import scan_mods,import_mods
from steam_services import steam_arguments
class LocalModTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.base=Path(self.tmp.name); self.m=Manager(self.base/'data'); self.p=self.m.state['servers'][0]; self.p['root']=str(self.base/'server'); Path(self.p['root']).mkdir()
    def make_mod(self,name,parent=None):
        p=(parent or self.base)/name; (p/'Addons').mkdir(parents=True); (p/'Addons'/'mod.Pbo').write_bytes(b'packed test'); return p
    def test_scan_only_at_folders_and_direct_selection(self):
        mod=self.make_mod('@Developer (test)'); self.make_mod('OrdinaryMod'); (self.base/'@not-a-directory').touch()
        rows=scan_mods(self.base)['mods']; self.assertEqual([r['name'] for r in rows],['@Developer (test)']); self.assertEqual(rows[0]['pbo_count'],1)
        self.assertEqual(scan_mods(mod,True)['mods'][0]['name'],mod.name)
    def test_recursive_scan_does_not_descend_into_mods(self):
        outer=self.make_mod('@Outer'); self.make_mod('@Embedded',outer); self.make_mod('@Nested',self.base/'build')
        self.assertEqual(len(scan_mods(self.base)['mods']),1)
        self.assertEqual([m['name'] for m in scan_mods(self.base,True)['mods']],['@Nested','@Outer'])
    def test_duplicate_import_and_workshop_isolation(self):
        local=self.make_mod('@Weather'); rows=scan_mods(self.base)['mods']; added,skipped=import_mods(self.p,rows)
        self.assertEqual((len(added),skipped),(1,0)); self.assertEqual(added[0]['id'],''); self.assertEqual(added[0]['source'],'local')
        again,skipped=import_mods(self.p,rows); self.assertEqual((len(again),skipped),(0,1))
        args=steam_arguments(self.p,'all'); self.assertNotIn('+workshop_download_item',args)
        self.assertIn('-mod='+str(local),command(self.p))
        self.m.save(); reload=Manager(self.base/'data'); self.assertEqual(reload.state['servers'][0]['mods'][0]['path'],str(local))
    def test_local_mod_can_load_in_both_lists(self):
        local=self.make_mod('@Both'); added,_=import_mods(self.p,scan_mods(local)['mods'],load_mode='both'); args=command(self.p)
        self.assertEqual(added[0]['load_mode'],'both'); self.assertIn('-mod='+str(local),args); self.assertIn('-serverMod='+str(local),args)
    def test_existing_server_mod_not_duplicated(self):
        p=self.make_mod('@Existing',Path(self.p['root'])); self.p['mods']=[dict(folder=p.name,id='',enabled=True,server=False)]
        added,skipped=import_mods(self.p,scan_mods(p)['mods']); self.assertEqual((len(added),skipped),(0,1))
    def test_unbuilt_mod_imports_inactive(self):
        (self.base/'@Unbuilt').mkdir(); added,_=import_mods(self.p,scan_mods(self.base)['mods']); self.assertFalse(added[0]['enabled'])
        self.assertFalse(any(a.startswith('-mod=') for a in command(self.p)))
    def test_mixed_order_serveronly_and_source_untouched(self):
        a=self.make_mod('@A',self.base/'dev mods'); b=self.make_mod('@B',self.base/'dev mods')
        rows=scan_mods(a)['mods']; import_mods(self.p,rows); self.p['mods'].append(dict(folder='@CF',id='1559212036',enabled=True,server=False)); import_mods(self.p,scan_mods(b)['mods'],server_only=True)
        args=command(self.p); self.assertIn('-mod='+str(a)+';@CF',args); self.assertIn('-serverMod='+str(b),args); self.assertEqual((a/'Addons'/'mod.Pbo').read_bytes(),b'packed test')
    def test_start_uses_local_source_and_refreshes_bikey(self):
        local=self.make_mod('@Local'); (local/'Keys').mkdir(); (local/'Keys'/'dev.bikey').write_bytes(b'public key')
        import_mods(self.p,scan_mods(local)['mods']); root=Path(self.p['root']); (root/'DayZServer_x64.exe').touch(); (root/'serverDZ.cfg').write_text('hostname="test";')
        with patch('core.subprocess.Popen') as start:self.m.start(self.p); args=start.call_args[0][0]
        self.assertIn('-mod='+str(local),args); self.assertEqual((root/'keys'/'dev.bikey').read_bytes(),b'public key'); self.assertFalse((root/'@Local').exists())
    def test_invalid_path_and_missing_source_do_not_start(self):
        m=dict(folder='@bad',id='',source='local',path=str(self.base/'@bad;other'),enabled=True,server=False)
        with self.assertRaises(ValueError):validate_mod(m)
        local=self.make_mod('@Removed'); import_mods(self.p,scan_mods(local)['mods']); (local/'Addons'/'mod.Pbo').unlink(); root=Path(self.p['root']); (root/'DayZServer_x64.exe').touch(); (root/'serverDZ.cfg').touch()
        with patch('core.subprocess.Popen') as start:
            with self.assertRaises(ValueError):self.m.start(self.p)
            start.assert_not_called()
if __name__=='__main__':unittest.main()
