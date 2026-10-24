"""Read a real Windows console, including programs that bypass redirected stdout.

Qt remains on the GUI thread; blocking ConPTY reads run on a separate thread.
Linux uses QProcess for tests. No shell intermediary is used on either platform.
"""
import sys,threading,time
from PySide6.QtCore import QObject,QThread,Signal,QProcess

class ConsoleWorker(QThread):
    received=Signal(str); exited=Signal(int); failed=Signal(str)
    def __init__(self,program,args,cwd,parent=None):
        super().__init__(parent); self.program=program; self.args=list(args); self.cwd=cwd; self.proc=None; self.cancelled=threading.Event(); self.input_lock=threading.Lock()
    def run(self):
        proc=None
        try:
            from winpty import PtyProcess
            proc=PtyProcess.spawn([self.program,*self.args],cwd=self.cwd,dimensions=(40,180))
            with self.input_lock:self.proc=proc
            if self.cancelled.is_set():proc.terminate(force=True)
            while True:
                try:
                    text=proc.read(8192)
                    if text:self.received.emit(text)
                except EOFError:break
            code=proc.exitstatus
            # Some console backends deliver EOF shortly before exit status is ready.
            deadline=time.monotonic()+2
            while code is None and time.monotonic()<deadline:
                time.sleep(.02); code=proc.exitstatus
            self.exited.emit(int(code) if code is not None else 1)
        except Exception as e:
            if proc is None:self.failed.emit(str(e))
            else:self.received.emit('\n[Terminalfeil: '+str(e)+']\n'); self.exited.emit(1)
        finally:
            with self.input_lock:self.proc=None
            if proc is not None:
                try:proc.close(force=True)
                except Exception:pass
    def write(self,data):
        with self.input_lock:
            if self.proc is None:raise ValueError('Terminalen starter fortsatt. Vent på SteamCMD-spørsmålet før du sender input.')
            return self.proc.write(data)
    def stop(self):
        self.cancelled.set()
        with self.input_lock:
            if self.proc is not None:
                try:self.proc.terminate(force=True)
                except Exception:pass

class WindowsConsoleProcess(QObject):
    """Small QProcess-compatible surface used by SteamSession."""
    readyReadStandardOutput=Signal(); finished=Signal(int,object); errorOccurred=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent); self.program=''; self.args=[]; self.cwd=None; self.worker=None; self.buffer=bytearray(); self.error_text=''
    def setProcessChannelMode(self,mode):pass  # ConPTY already combines both console streams.
    def setProgram(self,value):self.program=value
    def setArguments(self,args):self.args=list(args)
    def setWorkingDirectory(self,path):self.cwd=path
    def start(self):
        if self.worker is not None and self.worker.isRunning():raise ValueError('Terminalprosessen kjører allerede.')
        self.buffer.clear(); self.error_text=''; worker=ConsoleWorker(self.program,self.args,self.cwd,self); self.worker=worker
        worker.received.connect(self._received); worker.failed.connect(self._failed)
        # Emit process completion only after the worker has released all terminal resources.
        self.exit_code=1; worker.exited.connect(self._exit_status); worker.finished.connect(self._finished); worker.start()
    def _received(self,text):self.buffer.extend(text.encode('utf-8')); self.readyReadStandardOutput.emit()
    def _failed(self,message):self.error_text=message; self.failed_start=True
    def _exit_status(self,code):self.exit_code=code
    def _finished(self):
        worker=self.worker; self.worker=None
        if worker:worker.deleteLater()
        if self.error_text:self.errorOccurred.emit(QProcess.FailedToStart)
        else:self.finished.emit(self.exit_code,QProcess.NormalExit)
    def readAllStandardOutput(self):data=bytes(self.buffer); self.buffer.clear(); return data
    def write(self,data):
        if self.worker is None:raise ValueError('SteamCMD-terminalen kjører ikke.')
        text=bytes(data).decode('utf-8').replace('\r\n','\n').replace('\n','\r\n'); return self.worker.write(text)
    def kill(self):
        if self.worker is not None:self.worker.stop()
    def errorString(self):return self.error_text

def terminal_process(parent=None):
    return WindowsConsoleProcess(parent) if sys.platform=='win32' else QProcess(parent)
