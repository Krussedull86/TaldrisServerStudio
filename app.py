import argparse,os,subprocess,sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--home');parser.add_argument('--install',action='store_true');parser.add_argument('--install-only',action='store_true');parser.add_argument('--portable',action='store_true');parser.add_argument('--wait-panel',nargs=2);parser.add_argument('--wait-agent',nargs=2);parser.add_argument('--agent',action='store_true');parser.add_argument('--windows-service',action='store_true');parser.add_argument('--upgrade-service',action='store_true')
    args=parser.parse_args();home=Path(args.home) if args.home else Path(os.getenv('LOCALAPPDATA',Path.home()))/'TaldrisServerStudio';home.mkdir(parents=True,exist_ok=True)
    if args.install_only:
        from self_install import install
        install(home);return 0
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
        from self_install import launcher_target
        target=launcher_target(home) or active_exe(home)
        if target and target!=Path(sys.executable).resolve():subprocess.Popen([str(target),'--home',str(home)],cwd=str(target.parent),env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'});return 0
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setStyleSheet(STYLE)
    if getattr(sys,'frozen',False) and sys.platform=='win32' and not args.wait_panel:
        from self_install import read_install,install
        choice=args.install or Path(sys.executable).name=='TaldrisServerStudio-Setup.exe'
        if not choice and not args.portable and not read_install(home) and not (home/'portable_mode.json').exists():
            box=QMessageBox();box.setWindowTitle('Installer Taldris Server Studio');box.setText('Installer programmet med snarveier og støtte for oppgraderinger, eller kjør portabelt. Serverdata beholdes ved oppgradering og avinstallasjon.');yes=box.addButton('Installer',QMessageBox.AcceptRole);portable=box.addButton('Kjør portabelt',QMessageBox.ActionRole);box.addButton(QMessageBox.Cancel);box.exec()
            if box.clickedButton()==yes:choice=True
            elif box.clickedButton()==portable:(home/'portable_mode.json').write_text('{}')
            else:return 0
        if choice:
            try:target=Path(install(home))
            except Exception as error:QMessageBox.critical(None,'Installasjon',str(error));return 1
            if target.resolve()!=Path(sys.executable).resolve():
                probe=QLockFile(str(home/'panel.lock'));probe.setStaleLockTime(0)
                if not probe.tryLock(0):QMessageBox.information(None,'Installert','Programmet er installert. Lukk det åpne programvinduet og bruk den nye snarveien. DayZ-serverne fortsetter.');return 0
                probe.unlock();subprocess.Popen([str(target),'--home',str(home)],cwd=str(target.parent),env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'});return 0
    lock=QLockFile(str(home/'panel.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(0):QMessageBox.information(None,'Taldris','Kontrollpanelet kjører allerede for denne datamappen.');return 1
    try:window=SuiteStudio(home)
    except Exception as error:QMessageBox.critical(None,'Taldris – oppstart',str(error));return 1
    window.show();mark_active(home);return app.exec()

if __name__=='__main__':sys.exit(main())
