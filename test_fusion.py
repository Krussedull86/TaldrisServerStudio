import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from loot_engine import parse_types,export_types,LootStore
from mission_loot import active_types
from profile_transfer import export_profile,read_profile,import_profile
from core import DEFAULT

XML='''<?xml version="1.0"?><types custom="keep"><!--keep this--><type name="Apple" custom="yes"><nominal>10</nominal><lifetime>100</lifetime><restock>0</restock><min>1</min><quantmin>-1</quantmin><quantmax>100</quantmax><cost>100</cost><flags count_in_cargo="0" count_in_hoarder="0" count_in_map="1" count_in_player="0" crafted="0" deloot="0" extra="keep"/><category name="food" extra="yes"/><usage name="Town"/><custom><unknown>keep me</unknown></custom></type></types>'''
class LootModelTests(unittest.TestCase):
 def test_roundtrip_keeps_custom_nodes_comments_and_attributes(self):
  rows=parse_types(XML);rows[0]['nominal']=25;rows[0]['usage']='Town, Village';text=export_types(XML,rows)
  self.assertIn('keep this',text);self.assertIn('keep me',text);self.assertIn('extra="keep"',text);self.assertIn('extra="yes"',text);self.assertIn('custom="keep"',text);self.assertEqual(parse_types(text)[0]['nominal'],25);self.assertEqual(parse_types(text)[0]['usage'],'Town, Village')
 def test_validation_blocks_entities_duplicate_names_flags_and_ranges(self):
  with self.assertRaises(ValueError):parse_types('<!DOCTYPE types><types/>')
  for field,value in [('quantmax',101),('nominal',-1),('nominal',True)]:
   rows=parse_types(XML);rows[0][field]=value
   with self.assertRaises(ValueError):export_types(XML,rows)
  rows=parse_types(XML);rows[0]['flags']['count_in_map']=2
  with self.assertRaises(ValueError):export_types(XML,rows)
  with self.assertRaises(ValueError):export_types(XML,parse_types(XML)*2)
 def test_saved_revisions_survive_reopen_and_keep_original(self):
  with tempfile.TemporaryDirectory() as home:
   store=LootStore(home);store.create(XML,'Test');identity=store.active['id'];rows=store.state()['rows'];rows[0]['nominal']=77;store.save(rows);self.assertEqual(store.state()['originalRows'][0]['nominal'],10);store.step(-1);self.assertEqual(parse_types(store.xml())[0]['nominal'],10);store.step(1)
   fresh=LootStore(home);self.assertEqual(fresh.active['id'],identity);self.assertEqual(parse_types(fresh.xml())[0]['nominal'],77)
 def test_bundled_map_templates_roundtrip(self):
  for path in Path(__file__).parent.joinpath('loot_maps').rglob('types.xml'):
   rows=parse_types(path.read_text('utf-8'));self.assertGreater(len(rows),100);self.assertEqual(len(parse_types(export_types(path.read_text('utf-8'),rows))),len(rows))

class MissionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.p=dict(id='p',name='Test',root=str(self.root),config='serverDZ.cfg',mission='wrong.cached');(self.root/'serverDZ.cfg').write_text('class Missions { class DayZ { template="dayzOffline.nasdara"; }; };');self.mission=self.root/'mpmissions/dayzOffline.nasdara';(self.mission/'db').mkdir(parents=True);(self.mission/'db/types.xml').write_text(XML)
 def test_cfg_is_authoritative_and_custom_ce_types_are_included(self):
  (self.mission/'custom').mkdir();(self.mission/'custom/items.xml').write_text(XML);(self.mission/'cfgeconomycore.xml').write_text('<economycore><ce folder="custom"><file name="items.xml" type="types"/><file name="events.xml" type="events"/></ce></economycore>');result=active_types(self.p);self.assertEqual(result['mission'],'dayzOffline.nasdara');self.assertEqual(len(result['files']),2)
 def test_ce_cannot_escape_mission(self):
  (self.mission/'cfgeconomycore.xml').write_text('<economycore><ce folder="../../"><file name="outside.xml" type="types"/></ce></economycore>')
  with self.assertRaises(ValueError):active_types(self.p)
 def test_mission_writer_preserves_backup_and_blocks_conflicts(self):
  from PySide6.QtWidgets import QApplication,QWidget,QMessageBox
  from loot_workspace import LootWorkspace
  from core import Manager
  app=QApplication.instance() or QApplication([]);studio=QWidget();studio.manager=Manager(self.root/'data');studio.manager.state['servers']=[self.p];studio.p=self.p;studio.events=Mock();studio.guard=lambda fn:fn();w=LootWorkspace(studio)
  with patch.object(QMessageBox,'question',return_value=QMessageBox.Save):
   w.open_mission();rows=w.store.state()['rows'];rows[0]['nominal']=55;w.store.save(rows);w.save_mission();self.assertEqual(parse_types((self.mission/'db/types.xml').read_text())[0]['nominal'],55);self.assertTrue(list((self.root/'data/config_history').rglob('*.xml')))
   (self.mission/'db/types.xml').write_text(XML)
   with self.assertRaisesRegex(ValueError,'changed on disk'):w.save_mission()
  w.close();w.deleteLater();studio.deleteLater()

class TransferTests(unittest.TestCase):
 def test_export_removes_credentials_and_runtime_import_never_starts(self):
  with tempfile.TemporaryDirectory() as home:
   p=copy.deepcopy(DEFAULT);p.update(id='old',name='Test',root=str(Path(home)/'server'),steam_user='secret-user',password='secret',desired_running=True,autostart=True,programs=[dict(args='--token secret')]);path=Path(home)/'profile.json';export_profile(p,path);text=path.read_text();self.assertNotIn('secret',text);self.assertNotIn('desired_running',text);fields=read_profile(path);manager=Mock();import threading
   manager.lock=threading.RLock();manager.state={'servers':[]};result=import_profile(manager,fields);self.assertNotEqual(result['id'],'old');self.assertFalse(result['autostart']);self.assertFalse(result['desired_running']);manager.start.assert_not_called();self.assertEqual(result['programs'],[])
 def test_invalid_import_does_not_add_partial_profile(self):
  manager=Mock();manager.state={'servers':[]}
  with self.assertRaises(ValueError):import_profile(manager,{'root':'','mods':[]})
  self.assertEqual(manager.state['servers'],[])
