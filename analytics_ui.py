"""English performance controls and lightweight local game analytics views."""
import copy,math,time
from PySide6.QtCore import Qt,QTimer,QRectF
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QGridLayout,QScrollArea,QComboBox,QSpinBox,QCheckBox,QTableWidget,QTableWidgetItem,QHeaderView,QTabWidget,QMessageBox
from desktop import label,button,card
from performance_policy import policy,PRIORITIES
from telemetry_store import settings

class Trend(QWidget):
    def __init__(self,title,key,color,unit):
        super().__init__();self.title=title;self.key=key;self.color=color;self.unit=unit;self.rows=[];self.setMinimumHeight(150)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),QColor('#141e2e'));p.setPen(QColor('#91a8bd'));p.drawText(16,24,self.title)
        values=[(r['ts'],r.get(self.key)) for r in self.rows];valid=[(t,v) for t,v in values if v is not None]
        if not valid:p.drawText(16,65,'Waiting for history');return
        low=min(t for t,v in valid);high=max(t for t,v in valid);top=max(1,max(v for t,v in valid));area=QRectF(45,40,max(1,self.width()-65),max(1,self.height()-65));path=QPainterPath();open_segment=False
        for t,v in values:
            if v is None:open_segment=False;continue
            x=area.left()+(t-low)/max(1,high-low)*area.width();y=area.bottom()-v/top*area.height()
            if not open_segment:path.moveTo(x,y);open_segment=True
            else:path.lineTo(x,y)
        p.setPen(QPen(QColor('#28394e'),1));p.drawRect(area);p.setPen(QPen(QColor(self.color),2));p.drawPath(path)
        p.setPen(QColor('#e4ebf7'));p.drawText(16,self.height()-8,f'{valid[-1][1]:.1f} {self.unit}  •  peak {top:.1f}')

class PerformancePage(QWidget):
    def __init__(self,studio):
        super().__init__();self.studio=studio;self.identity=None
        outer=QVBoxLayout(self);scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();layout=QVBoxLayout(content);scroll.setWidget(content);outer.addWidget(scroll)
        hero,h=card('PROCESS PERFORMANCE','Per-server Windows scheduling. These controls do not overclock the CPU or reserve dedicated physical cores.');layout.addWidget(hero)
        self.hardware=studio.manager.client.call('hardware');hw=self.hardware
        h.addWidget(label(f"{hw['logical']} logical CPUs • {hw.get('physical') or '?'} physical cores • {hw['total_ram_mb']/1024:.1f} GB installed RAM",'muted'))
        self.message=label('Saved settings are applied to the selected server only.','eyebrow');h.addWidget(self.message)
        form=QFormLayout();self.priority=QComboBox();self.priority.addItems(PRIORITIES);form.addRow('Process priority',self.priority)
        self.workers=self.spin(0,len(hw['allowed']));self.workers.setSpecialValueText('Automatic');form.addRow('DayZ parallel worker count (restart)',self.workers)
        self.fps=self.spin(0,200);self.fps.setSpecialValueText('Engine default');form.addRow('Server FPS ceiling (restart)',self.fps)
        self.budget=self.spin(0,100);self.budget.setSpecialValueText('Unlimited');self.budget.setSuffix(' % of system CPU');form.addRow('Windows CPU budget',self.budget)
        self.warning=self.spin(0,hw['total_ram_mb']);self.warning.setSpecialValueText('Disabled');self.warning.setSuffix(' MB working set');form.addRow('RAM warning threshold',self.warning)
        self.cap=self.spin(0,hw['total_ram_mb']);self.cap.setSpecialValueText('Unlimited');self.cap.setSuffix(' MB private commit');form.addRow('Hard memory ceiling',self.cap);h.addLayout(form)
        h.addWidget(label('A hard memory ceiling rejects new memory allocations. It does not reserve RAM and can make DayZ fail or crash. Prefer warnings until you know the server\'s normal peak. CPU budgets can reduce server update FPS.','muted'))
        box,c=card('LOGICAL CPU SELECTION','Select specific CPUs, or leave all unchecked to allow every CPU available to the agent.');grid=QGridLayout();self.cores={}
        for i,cpu in enumerate(hw['allowed']):
            check=QCheckBox('CPU '+str(cpu));grid.addWidget(check,i//8,i%8);self.cores[cpu]=check
        c.addLayout(grid);r=QHBoxLayout();r.addWidget(button('Allow all CPUs',lambda:[b.setChecked(False) for b in self.cores.values()]));c.addLayout(r);layout.addWidget(box)
        actions=QHBoxLayout();actions.addWidget(button('Save performance settings',lambda:studio.guard(self.save),'primary'));actions.addWidget(button('Apply live process controls',lambda:studio.guard(self.apply)));actions.addStretch();layout.addLayout(actions)
        layout.addWidget(label('Worker count and FPS ceiling take effect after server restart. Priority, affinity, CPU budget and memory ceiling can be applied while the server is running. A budget is a share of system scheduling time, not CPU clock speed.','muted'))
        self.current=label('No managed server process.','muted');layout.addWidget(self.current);layout.addStretch()
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh_metrics);self.timer.start(3000);self.load()
    @staticmethod
    def spin(low,high):
        s=QSpinBox();s.setRange(low,high);return s
    def load(self):
        p=policy(self.studio.p);self.identity=self.studio.p['id'];self.priority.setCurrentText(p['priority']);self.workers.setValue(p['worker_count']);self.fps.setValue(p['fps_limit']);self.budget.setValue(p['cpu_budget']);self.warning.setValue(p['ram_warning_mb']);self.cap.setValue(p['ram_limit_mb'])
        for cpu,box in self.cores.items():box.setChecked(cpu in p['affinity'])
        self.message.setText('Performance profile: '+self.studio.p['name']);self.refresh_metrics()
    def read(self):return dict(priority=self.priority.currentText(),affinity=[cpu for cpu,b in self.cores.items() if b.isChecked()],worker_count=self.workers.value(),fps_limit=self.fps.value(),cpu_budget=self.budget.value(),ram_warning_mb=self.warning.value(),ram_limit_mb=self.cap.value())
    def save(self):
        candidate=self.read();policy({'performance':candidate})
        from performance_policy import launch_arguments
        launch_arguments({'performance':candidate},self.studio.p.get('extra_args',[]))
        previous=policy(self.studio.p)
        if candidate['ram_limit_mb'] and candidate['ram_limit_mb']!=previous['ram_limit_mb']:
            if QMessageBox.warning(self,'Hard memory ceiling','Windows will reject allocations above this private committed-memory ceiling. DayZ may crash or stop. Save this ceiling?',QMessageBox.Save|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Save:return False
        self.studio.p['performance']=candidate;self.studio.manager.save();self.message.setText('Saved. Live process changes require Apply; worker/FPS changes require a restart.');return True
    def apply(self):
        if self.read()!=policy(self.studio.p):
            if not self.save():return
        job=self.studio.manager.enqueue('performance_apply',self.studio.p);key=self.studio.p['id']
        def done(result):
            if self.studio.p['id']==key:self.message.setText(str(result));self.studio.manager.refresh();self.refresh_metrics()
        self.studio.run_task(lambda:self.studio.manager.wait_job(job),done,description='Performance controls')
    def refresh_metrics(self):
        if not hasattr(self.studio,'p'):return
        runtime=self.studio.manager.runtime.get(self.studio.p['id'],{});p=runtime.get('performance',{});s=runtime.get('telemetry',{}).get('sample')
        text=f"PID {runtime.get('pid','—')} • CPU {runtime.get('cpu_percent','—')}% (100% = one core) • RAM working set {runtime.get('ram_mb','—')} MB"
        if p.get('applied'):text+='\nApplied: '+p.get('priority','Normal')+' • CPUs '+str(p.get('affinity','all'))+' • CPU budget '+str(p.get('cpu_budget',0) or 'unlimited')+' • commit ceiling '+str(p.get('ram_limit_mb',0) or 'unlimited')
        if s:text+=f"\nEngine FPS {s.get('engine_fps',0):.1f} • server updates/s {s['fps']:.1f} • mean frame {s['frame_ms']:.2f} ms • peak {s['peak_ms']:.2f} ms"
        if runtime.get('resource_warning'):text+='\n'+runtime['resource_warning']
        self.current.setText(text)

class AnalyticsPage(QWidget):
    def __init__(self,studio):
        super().__init__();self.studio=studio;self.busy=False;self.identity=None;studio.analytics_cache={}
        layout=QVBoxLayout(self);self.status=label('No game telemetry connected.','eyebrow');layout.addWidget(self.status)
        top=QHBoxLayout();self.window=QComboBox();self.window.addItems(['Last hour','Last 6 hours','Last 24 hours']);top.addWidget(self.window);top.addWidget(button('Refresh',self.poll));top.addWidget(button('Install / update server-only bridge',lambda:studio.guard(self.install),'primary'));layout.addLayout(top)
        tabs=QTabWidget();layout.addWidget(tabs,1)
        dashboard=QWidget();dash=QVBoxLayout(dashboard);self.values=label('Update FPS —   Frame —   Players —','title');dash.addWidget(self.values)
        self.detail=label('Engine FPS: native GetAvgFPS(64). Script update frequency/frame times: MissionServer.OnUpdate. Network tick rate is not inferred from FPS.','muted');dash.addWidget(self.detail)
        self.fps_chart=Trend('Engine FPS (64-frame average)','engine','#65dfc5','FPS');self.ram_chart=Trend('RAM working set','ram','#9d9aff','MB');self.cpu_chart=Trend('CPU (100% = one logical core)','cpu','#f4bf72','%');charts=QHBoxLayout()
        for chart in (self.fps_chart,self.ram_chart,self.cpu_chart):charts.addWidget(chart)
        dash.addLayout(charts);self.players=QTableWidget(0,5);self.players.setHorizontalHeaderLabels(['Player','X','Z','Health','Ping ms']);self.players.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.players.setEditTriggers(QTableWidget.NoEditTriggers);dash.addWidget(self.players,1);tabs.addTab(dashboard,'Overview & players')
        loot=QWidget();ll=QVBoxLayout(loot);self.loot_note=label('Optional local ground-loot sampling. This is not a full-map item count.','muted');ll.addWidget(self.loot_note);self.loot_table=QTableWidget(0,2);self.loot_table.setHorizontalHeaderLabels(['Sampled item type','Count in current sample']);self.loot_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.loot_table.setEditTriggers(QTableWidget.NoEditTriggers);ll.addWidget(self.loot_table);tabs.addTab(loot,'Loot samples')
        config=QWidget();cl=QVBoxLayout(config);form=QFormLayout();self.enabled=QCheckBox('Read snapshots from the DayZ server mod');form.addRow('Telemetry',self.enabled)
        self.collect=QCheckBox('Collect live positions and occupancy heatmap');form.addRow('Player positions',self.collect);self.names=QCheckBox('Include player display names (no Steam IDs)');form.addRow('Player names',self.names)
        self.scan=QCheckBox('Sample one player area every 15 seconds');form.addRow('Ground loot / nearby infected / vehicles',self.scan)
        self.interval=PerformancePage.spin(2,60);form.addRow('Snapshot interval, seconds',self.interval);self.radius=PerformancePage.spin(25,200);form.addRow('Loot sample radius, meters',self.radius);self.retention=PerformancePage.spin(1,30);form.addRow('History retention, days',self.retention);self.low=PerformancePage.spin(1,200);form.addRow('Low update-FPS warning threshold',self.low);cl.addLayout(form)
        cl.addWidget(label('Save and install/update while the server is stopped, then restart it. The bridge is loaded only with -serverMod; clients do not need it. Snapshots stay on the server machine. Each profile has its own bridge ID and history. Collection does not change loot, players or the economy.','muted'))
        cl.addWidget(button('Save collection settings',lambda:studio.guard(self.save)));cl.addStretch();tabs.addTab(config,'Collection settings')
        layout.addWidget(label('Open Map & markers for Live players, Player heatmap and Sampled loot overlays. Heatmaps show accumulated player-seconds in 100 m cells.','muted'))
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(5000);self.load()
    def load(self):
        s=settings(self.studio.p);self.identity=self.studio.p['id'];self.enabled.setChecked(s['enabled']);self.collect.setChecked(s['collect_players']);self.names.setChecked(s['collect_names']);self.scan.setChecked(s['scan_loot']);self.interval.setValue(s['interval']);self.radius.setValue(s['loot_radius']);self.retention.setValue(s['retention_days']);self.low.setValue(s['low_fps']);self.show_data(self.studio.analytics_cache.get(self.identity,{}))
    def save(self):
        s=dict(enabled=self.enabled.isChecked(),interval=self.interval.value(),collect_players=self.collect.isChecked(),collect_names=self.names.isChecked(),scan_loot=self.scan.isChecked(),loot_radius=self.radius.value(),retention_days=self.retention.value(),low_fps=self.low.value());settings({'telemetry':s});self.studio.p['telemetry']=s;self.studio.manager.save();self.status.setText('Saved. Install/update the bridge while stopped and restart the server.')
    def install(self):
        self.enabled.setChecked(True);self.save();job=self.studio.manager.enqueue('telemetry_install',self.studio.p)
        self.studio.run_task(lambda:self.studio.manager.wait_job(job),lambda result:self.status.setText(result['message']),description='Telemetry bridge')
    def poll(self):
        if self.busy or not hasattr(self.studio,'p'):return
        if self.studio.stack.currentWidget() is not self and self.studio.stack.currentIndex()!=1:return
        self.busy=True;key=self.studio.p['id'];hours=[1,6,24][self.window.currentIndex()]
        def ready(data):
            self.busy=False;self.studio.analytics_cache[key]=data
            if self.studio.p['id']!=key:return
            self.show_data(data)
            if hasattr(self.studio,'workbench'):self.studio.workbench.draw_live(data)
        before=set(self.studio.tasks);self.studio.run_task(lambda:self.studio.manager.client.call('analytics',{'server':key,'hours':hours}),ready,description='Analytics')
        for task in self.studio.tasks-before:task.finished.connect(lambda:setattr(self,'busy',False))
    def show_data(self,data):
        status=data.get('status',{});s=status.get('sample') if status.get('connected') else None
        self.status.setText(self.studio.p['name']+' • '+status.get('message','Waiting for telemetry')+(f" • age {status['age']:.1f} s" if status.get('age') is not None else ''))
        self.values.setText(f"{s.get('engine_fps',0):.1f} engine FPS  •  {s['fps']:.1f} updates/s  •  {s['player_count']} players" if s else 'Update FPS —   Frame —   Players —')
        self.detail.setText((f"Mean / peak update frame: {s['frame_ms']:.2f} / {s['peak_ms']:.2f} ms • frames over 50 ms: {s['slow_frames']}\nEngine FPS range (64 frames): {s.get('engine_min',0):.1f}–{s.get('engine_max',0):.1f} • network tick rate is not inferred from FPS." if s else 'Engine FPS uses native engine sampling. Update frequency and frame times use MissionServer.OnUpdate.'))

        for chart in (self.fps_chart,self.ram_chart,self.cpu_chart):chart.rows=data.get('history',[]);chart.update()
        players=s.get('players',[]) if s else [];self.players.setRowCount(len(players))
        for row,v in enumerate(players):
            for col,k in enumerate(('name','x','z','health','ping')):self.players.setItem(row,col,QTableWidgetItem(str(round(v[k],1)) if isinstance(v[k],float) else str(v[k])))
        counts={}
        if s:
            for item in s['loot']:counts[item['type']]=counts.get(item['type'],0)+1
            self.loot_note.setText(f"Sample radius {s['loot_radius']:.0f} m near X {s['loot_x']:.0f}, Z {s['loot_z']:.0f} • age {s['loot_age']:.1f} s • infected {s['sampled_infected']} • vehicles {s['sampled_vehicles']}"+(' • sample truncated' if s['loot_truncated'] else '')+'\nGround items only; sampled areas are not a whole-server census.')
        else:self.loot_note.setText('Waiting for optional ground-loot samples. This is not a full-map item count.')
        self.loot_table.setRowCount(len(counts))
        for row,(name,count) in enumerate(sorted(counts.items())):self.loot_table.setItem(row,0,QTableWidgetItem(name));self.loot_table.setItem(row,1,QTableWidgetItem(str(count)))
