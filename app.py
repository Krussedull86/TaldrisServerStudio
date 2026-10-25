import argparse,os,subprocess,sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--home');parser.add_argument('--wait-panel',nargs=2);parser.add_argument('--wait-agent',nargs=2);parser.add_argument('--agent',action='store_true');parser.add_argument('--windows-service',action='store_true');parser.add_argument('--upgrade-service',action='store_true')
    args=parser.parse_args();home=Path(args.home) if args.home else Path(os.getenv('LOCALAPPDATA',Path.home()))/'TaldrisServerStudio';home.mkdir(parents=True,exist_ok=True)
    if args.windows_service:
        from windows_service import run_service
        run_service(home);return 0
    if args.upgrade_service:
        from windows_service import replace_running_service
        replace_running_service(home,sys.executable);return 0
    if args.wait_agent:
        from panel_handoff import wait_panel
        wait_panel(int(args.wait_agent[0]),float(args.wait_agent[1]))
    if args.agent:
        from host_api import serve
        serve(home);return 0
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication,QMessageBox
    from desktop import STYLE
    from suite_ui import SuiteStudio
    from panel_handoff import wait_panel,active_exe,mark_active
    if args.wait_panel:wait_panel(int(args.wait_panel[0]),float(args.wait_panel[1]))
    if getattr(sys,'frozen',False) and not args.wait_panel:
        target=active_exe(home)
        if target and target!=Path(sys.executable).resolve():subprocess.Popen([str(target),'--home',str(home)],cwd=str(target.parent),env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'});return 0
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setStyleSheet(STYLE);lock=QLockFile(str(home/'panel.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(0):QMessageBox.information(None,'Taldris','Kontrollpanelet kjører allerede for denne datamappen.');return 1
    try:window=SuiteStudio(home)
    except Exception as error:QMessageBox.critical(None,'Taldris – oppstart',str(error));return 1
    window.show();mark_active(home);return app.exec()

if __name__=='__main__':sys.exit(main())
