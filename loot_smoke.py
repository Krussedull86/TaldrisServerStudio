"""Source and frozen smoke test for the actual WebEngine table and WebChannel save."""
def run(report):
    import json,tempfile,types
    from pathlib import Path
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtWidgets import QApplication,QWidget
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    from loot_workspace import LootWorkspace
    app=QApplication.instance() or QApplication([]);temp=tempfile.TemporaryDirectory();studio=QWidget();studio.manager=types.SimpleNamespace(home=Path(temp.name),state={'servers':[]});studio.p={'id':'smoke','name':'Smoke server'};events=[];studio.events=types.SimpleNamespace(put=events.append);studio.guard=lambda fn:fn();workspace=LootWorkspace(studio);workspace.call('map','chernarus');workspace.resize(1400,850);workspace.show();status={'success':False};started=False
    def finish(ok,error=''):
        status.update(success=ok,error=error,events=events);Path(report).write_text(json.dumps(status,indent=2),encoding='utf-8');app.quit()
    def verify():
        nonlocal started
        if workspace.view is None:return
        def ready(value):
            nonlocal started
            if started or not value:return
            started=True
            js="""(async()=>{try{const table=Tabulator.findTable('#tabulator-table')[0];const first=table.getData()[0];const value=first.nominal+1;await table.updateData([{name:first.name,nominal:value}]);document.getElementById('btn_save').click();const result=await window.desktopSaveComplete;if(result?.error)throw Error(result.error);const state=await window.desktopApi.call('state');window.studioSmoke={name:first.name,value,rows:state.rows.length,actual:state.rows.find(r=>r.name===first.name).nominal,rev:state.rev};}catch(e){window.studioSmoke={error:e.message};}})()"""
            workspace.view.page().runJavaScript(js);QTimer.singleShot(2000,check)
        workspace.view.page().runJavaScript("!!(window.Tabulator && document.querySelector('.tabulator-row'))",ready)
    def check():
        def result(raw):
            if not raw:finish(False,'No WebChannel result');return
            value=json.loads(raw);status.update(value);saved=workspace.store.state();finish(not value.get('error') and value.get('actual')==value.get('value') and value.get('rows',0)>2000 and saved['rev']==1,value.get('error',''))
        workspace.view.page().runJavaScript('JSON.stringify(window.studioSmoke)',result)
    timer=QTimer();timer.timeout.connect(verify);timer.start(500);QTimer.singleShot(45000,lambda:finish(False,'WebEngine smoke timed out'));app.exec();timer.stop();workspace.dispose();workspace.close();app.processEvents();temp.cleanup();return 0 if status['success'] else 1
