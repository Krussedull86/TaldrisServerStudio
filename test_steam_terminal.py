"""Actual Windows console regression: WriteConsoleW bypasses ordinary stdout pipes."""
import os,sys,time,tempfile,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from steam_status import plain_terminal,progress_percent,stage

class TerminalStatusTests(unittest.TestCase):
    def test_native_progress_without_percent_sign(self):
        self.assertEqual(progress_percent('Update state (0x61) downloading, progress: 23.87 (1234 / 5678)'),23)
        self.assertEqual(progress_percent('[ 7%] Checking for updates …'),7)
        self.assertIsNone(progress_percent('Steam Console Client'))
    def test_terminal_codes_and_carriage_returns(self):
        text='\x1b[?25l\x1b[32mUpdate\x1b[0m\rDownloading\r\nPassword:'
        self.assertEqual(plain_terminal(text),'Update\nDownloading\nPassword:')
        self.assertIn('Venter på Steam-passord',stage(text))
    def test_start_banner_does_not_claim_download(self):
        self.assertIn('venter',stage('Steam Console Client\n-- type quit to exit --'))
        self.assertIn('Laster ned',stage('Update state downloading, progress: 12.0 (10 / 100)'))
        self.assertIn('Steam melder en feil',stage('ERROR! Failed to install: No subscription'))

@unittest.skipUnless(sys.platform=='win32','Requires an actual Windows console')
class WindowsConsoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_captures_console_only_output_and_accepts_input(self):
        from steam_terminal import WindowsConsoleProcess
        with tempfile.TemporaryDirectory() as temp:
            script=Path(temp)/'console test.py'
            script.write_text('''import ctypes,sys,time
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetStdHandle.restype=ctypes.c_void_p
kernel.WriteConsoleW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint),ctypes.c_void_p]
handle=kernel.GetStdHandle(-11)
def console(text):
 written=ctypes.c_uint()
 if not kernel.WriteConsoleW(handle,text,len(text),ctypes.byref(written),None):raise ctypes.WinError(ctypes.get_last_error())
console('CONSOLE-ONLY READY\\r\\n')
reply=sys.stdin.readline().strip()
console('INPUT-RECEIVED '+reply+'\\r\\n')
console('Update state downloading, progress: 42.7 (427 / 1000)\\r\\n')
''',encoding='utf-8')
            process=WindowsConsoleProcess(); process.setProgram(sys.executable); process.setArguments(['-u',str(script)]); process.setWorkingDirectory(temp)
            output=[]; exits=[]; errors=[]
            def read():output.append(bytes(process.readAllStandardOutput()).decode('utf-8'))
            process.readyReadStandardOutput.connect(read); process.finished.connect(lambda code,status:exits.append(code)); process.errorOccurred.connect(lambda e:errors.append(process.errorString()))
            process.start(); end=time.monotonic()+20; sent=False
            while time.monotonic()<end and not exits and not errors:
                self.app.processEvents(); text=plain_terminal(''.join(output))
                if 'CONSOLE-ONLY READY' in text and not sent:process.write(b'test-input\n'); sent=True
                time.sleep(.01)
            if not exits and not errors:
                process.kill(); cleanup=time.monotonic()+5
                while process.worker is not None and time.monotonic()<cleanup:self.app.processEvents(); time.sleep(.01)
            self.assertFalse(errors,errors); self.assertEqual(exits,[0]); text=plain_terminal(''.join(output))
            self.assertIn('CONSOLE-ONLY READY',text); self.assertIn('INPUT-RECEIVED test-input',text); self.assertEqual(progress_percent(text),42)
