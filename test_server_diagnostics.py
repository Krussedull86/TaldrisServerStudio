import tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import Mock,patch
from core import Manager
from server_diagnostics import current_logs,exit_label,describe
class ServerDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.base=Path(self.temp.name); self.messages=[]; self.m=Manager(self.base/'data',self.messages.append); self.p=self.m.state['servers'][0]; self.p['auto_firewall']=False
        self.root=self.base/'server with spaces'; self.root.mkdir(); self.p['root']=str(self.root); (self.root/'DayZServer_x64.exe').touch(); (self.root/'serverDZ.cfg').write_text('hostname="Test";')
        self.proc=Mock(pid=4242); self.proc.poll.return_value=None
    def start(self):
        with patch('core.subprocess.Popen',return_value=self.proc) as spawn:self.m.start(self.p); return spawn.call_args
    def test_direct_exe_with_explicit_windows_console_and_absolute_paths(self):
        call=self.start(); args=call.args[0]
        self.assertEqual(args[0],str((self.root/'DayZServer_x64.exe').resolve())); self.assertTrue(all(not arg.lower().endswith('.bat') for arg in args)); self.assertIn('-config='+str((self.root/'serverDZ.cfg').resolve()),args); self.assertIn('-profiles='+str((self.root/'profiles').resolve()),args)
        self.assertEqual(call.kwargs['creationflags'],getattr(subprocess,'CREATE_NEW_CONSOLE',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)); self.assertEqual(self.m.launches[self.p['id']]['pid'],4242)
    def test_exit_is_reported_once_with_new_rpt_and_error_excerpt(self):
        self.start(); profile=self.root/'profiles'; (profile/'new.RPT').write_text("Can't compile World script module\nMissing addon test\n")
        self.proc.poll.return_value=1; events=self.m.poll_processes(); self.assertEqual(len(events),1); self.assertEqual(events[0]['code'],1); self.assertIn('new.RPT',events[0]['logs'][0]); self.assertIn('SERVERPROSESSEN AVSLUTTET','\n'.join(self.messages)); self.assertIn("Can't compile",'\n'.join(self.messages)); self.assertEqual(self.m.poll_processes(),[])
    def test_stale_log_not_presented_as_new_failure(self):
        profile=self.root/'profiles'; profile.mkdir(); (profile/'old.RPT').write_text('OLD error')
        self.start(); self.proc.poll.return_value=-1073741515; event=self.m.poll_processes()[0]; self.assertEqual(event['logs'],[]); self.assertIn('nødvendig DLL','\n'.join(self.messages)); self.assertNotIn('OLD error','\n'.join(self.messages))
    def test_user_stop_is_identified_separately(self):
        self.start(); self.m.force_stop(self.p); self.proc.poll.return_value=0; events=self.m.poll_processes(); self.assertTrue(events[0]['expected_stop']); self.assertNotIn('SERVERPROSESSEN AVSLUTTET','\n'.join(self.messages))
    def test_restarting_does_not_lose_previous_exit(self):
        self.start(); self.proc.poll.return_value=1
        second=Mock(pid=4343); second.poll.return_value=None
        with patch('core.subprocess.Popen',return_value=second):self.m.start(self.p)
        self.assertEqual(self.m.launches[self.p['id']]['pid'],4343); self.assertIn('SERVERPROSESSEN AVSLUTTET','\n'.join(self.messages))
    def test_windows_exit_code_label(self):
        label,hint=exit_label(-1073741515); self.assertIn('0xC0000135',label); self.assertIn('DLL',hint)
if __name__=='__main__':unittest.main()
