import argparse
import os
from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication,QMessageBox
from desktop import STYLE
from operations_ui import OperationsStudio
from panel_handoff import wait_panel,active_exe,mark_active

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--home'); parser.add_argument('--wait-panel',nargs=2)
    args=parser.parse_args()
    home=Path(args.home) if args.home else Path(os.getenv('LOCALAPPDATA',Path.home()))/'TaldrisServerStudio'
    home.mkdir(parents=True,exist_ok=True)
    if args.wait_panel:wait_panel(int(args.wait_panel[0]),float(args.wait_panel[1]))
    if getattr(sys,'frozen',False) and not args.wait_panel:
        target=active_exe(home)
        if target and target!=Path(sys.executable).resolve():
            subprocess.Popen([str(target),'--home',str(home)],cwd=str(target.parent)); sys.exit(0)
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    lock=QLockFile(str(home/'panel.lock')); lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None,'Taldris','Kontrollpanelet kjører allerede for denne datamappen.'); sys.exit(1)
    window=OperationsStudio(home); window.show(); mark_active(home); sys.exit(app.exec())
