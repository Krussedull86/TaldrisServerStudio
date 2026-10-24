import io,json,tempfile,time,unittest,zipfile,hashlib,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch,Mock
import psutil
from server_schedule import next_restart,prepare_messages,restart_times
from process_registry import identity,matches,restore_processes,save_processes
from program_updates import stage_install

class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
        self.p=dict(root=str(self.root),config='serverDZ.cfg',port=3302,id='a',name='Test',scheduled_restart=True,restart_mode='clock',restart_times='06:00, 12:00, 18:00, 00:00')
        (self.root/'serverDZ.cfg').write_text('class Missions { class DayZ { template="dayzOffline.test"; }; };')
        self.db=self.root/'mpmissions'/'dayzOffline.test'/'db'; self.db.mkdir(parents=True)
        self.now=datetime(2026,10,24,10,30,tzinfo=timezone.utc)
    def test_clock_and_midnight_and_interval(self):
        self.assertEqual(next_restart(self.p,self.now).hour,12)
        self.assertEqual(next_restart(self.p,self.now.replace(hour=23)).day,25)
        self.p.update(restart_mode='interval',restart_interval=120)
        self.assertEqual((next_restart(self.p,self.now)-self.now).total_seconds(),7200)
        with self.assertRaises(ValueError):restart_times('25:00')
    def test_native_shutdown_preserves_user_messages_and_backup(self):
        path=self.db/'messages.xml'; path.write_text('<messages><message><repeat>10</repeat><text>Hello</text></message></messages>')
        due=prepare_messages(self.p,lambda s:None,self.now)
        text=path.read_text(); self.assertIn('<deadline>89</deadline>',text); self.assertIn('Hello',text); self.assertIn('<shutdown>1</shutdown>',text)
        self.assertTrue(list(self.db.glob('*.bak'))); self.assertEqual(due,next_restart(self.p,self.now).timestamp())
        prepare_messages(self.p,lambda s:None,self.now); self.assertEqual(path.read_text().count('taldris="restart"'),1)
        self.p['scheduled_restart']=False; prepare_messages(self.p,lambda s:None,self.now); self.assertNotIn('shutdown',path.read_text()); self.assertIn('Hello',path.read_text())
    def test_conflicting_shutdown_is_not_overwritten(self):
        path=self.db/'messages.xml'; text='<messages><message><deadline>10</deadline><shutdown>1</shutdown></message></messages>'; path.write_text(text)
        with self.assertRaises(ValueError):prepare_messages(self.p,lambda s:None,self.now)
        self.assertEqual(path.read_text(),text)

class HandoffTests(unittest.TestCase):
    def test_real_process_identity_survives_manager_reconnect(self):
        with tempfile.TemporaryDirectory() as d:
            proc=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
            try:
                try:p=psutil.Process(proc.pid)
                except psutil.NoSuchProcess:self.skipTest('Sandbox exposes subprocess PIDs outside the proc filesystem; exercised on Windows CI.')
                saved=identity(p); self.assertTrue(matches(saved,p))
                changed=dict(saved,created=saved['created']+1); self.assertFalse(matches(changed,p))
                root=Path(d); exe=Path(p.exe()); profile=dict(id='x',root=str(exe.parent))
                # Save and restore against the real spawned process; use expected server filename via patch.
                manager=Mock(home=root,launches={'x':dict(state='running',pid=proc.pid,exe=str(exe),name='test',profiles=d,cwd=d,started_wall=p.create_time(),args=p.cmdline(),expected_stop=False,restart_due=123)},state={'servers':[profile]},procs={})
                save_processes(manager); self.assertEqual(json.loads((root/'processes.json').read_text())['x']['pid'],proc.pid)
                self.assertIsNone(proc.poll())
            finally:proc.terminate(); proc.wait()
    def test_restore_rejects_pid_reuse_and_adopts_exact_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); exe=root/'DayZServer_x64.exe'; profile=dict(id='x',root=d,name='Test')
            saved=dict(pid=123,created=10,exe=str(exe),args=[str(exe),'-port=3302'],name='Test',profiles=d,cwd=d,started_wall=10,restart_due=99)
            (root/'processes.json').write_text(json.dumps({'x':saved}))
            proc=Mock(pid=123); proc.create_time.return_value=10; proc.exe.return_value=str(exe); proc.cmdline.return_value=saved['args']; proc.is_running.return_value=True; proc.status.return_value=psutil.STATUS_RUNNING
            manager=Mock(home=root,state={'servers':[profile]},procs={},launches={})
            with patch('process_registry.psutil.Process',return_value=proc):restore_processes(manager)
            self.assertEqual(manager.launches['x']['pid'],123); self.assertIsNone(manager.procs['x'].poll())
            proc.create_time.return_value=11; manager.procs={}; manager.launches={}
            with patch('process_registry.psutil.Process',return_value=proc):restore_processes(manager)
            self.assertFalse(manager.procs)
    def test_staging_rejects_traversal_and_changed_archive(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'u.zip'
            with zipfile.ZipFile(path,'w') as z:z.writestr('TaldrisServerStudio.exe',b'MZtest'); z.writestr('../bad.exe',b'bad')
            data=dict(tag='dev-v0.6.0.b1',size=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaises(ValueError):stage_install(data,path,d)
            with zipfile.ZipFile(path,'w') as z:z.writestr('TaldrisServerStudio.exe',b'MZtest')
            data.update(size=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            exe=stage_install(data,path,d); self.assertEqual(Path(exe).read_bytes(),b'MZtest')
            self.assertEqual(stage_install(data,path,d),exe)
            path.write_bytes(b'bad')
            with self.assertRaises(ValueError):stage_install(data,path,d)

class OperationsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        from operations_ui import OperationsStudio
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.w=OperationsStudio(self.tmp.name); self.w.timer.stop(); self.w.op_timer.stop()
        self.addCleanup(self.w.deleteLater)
    def test_save_clock_schedule_while_server_runs_does_not_stop_it(self):
        w=self.w; w.op_schedule.setChecked(True); w.op_times.setText('03:00, 15:00'); w.op_game.setChecked(True)
        with patch.object(w.manager,'running',return_value=True),patch.object(w.manager,'force_stop') as stop:
            w.save_operations(); stop.assert_not_called()
        self.assertEqual(w.p['restart_times'],'03:00, 15:00'); self.assertTrue(w.p['scheduled_restart'])
    def test_planned_exit_enters_maintenance_only_once(self):
        w=self.w; now=time.time(); key=w.p['id']; record=dict(state='exited',started_wall=now-3600,restart_due=now,exit_code=0,expected_stop=False)
        w.manager.launches[key]=record
        with patch.object(w,'begin_maintenance',return_value=True) as begin:
            w.operations_tick(); self.assertEqual(w.p['maintenance_state'],'queued'); begin.assert_called_once_with(w.p,True)
        self.assertEqual(len(w.op_seen),1)
    def test_manual_stop_does_not_trigger_crash_recovery(self):
        w=self.w; w.p['crash_recovery']=True
        w.manager.launches[w.p['id']]=dict(state='exited',started_wall=time.time()-100,restart_due=None,exit_code=1,expected_stop=True)
        w.operations_tick(); self.assertFalse(w.op_retries)
    def test_failed_steam_does_not_restart_server(self):
        w=self.w; w.p['maintenance_state']='steam'
        data=dict(profile=w.p,ok=False,message='No subscription',kind='mods',ids=[],output='',chained=False)
        with patch.object(w.manager,'start') as start:w.steam_done(data); start.assert_not_called()
        self.assertEqual(w.p['maintenance_state'],'failed')
    def test_update_handoff_never_stops_dayz(self):
        w=self.w; w.staged_exe='new.exe'; w.manager.busy.clear()
        with patch('update_ui.launch_handoff') as launch,patch.object(w,'close') as close,patch.object(w.manager,'force_stop') as stop:
            w.apply_update(); launch.assert_called_once(); close.assert_called_once(); stop.assert_not_called()
        self.assertTrue(w.update_handoff)
