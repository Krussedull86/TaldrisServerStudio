package com.cruzdoodelz.serverstudio;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Build;
import android.graphics.Color;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.view.View;
import android.graphics.drawable.GradientDrawable;
import android.graphics.Typeface;
import android.os.SystemClock;
import android.text.TextWatcher;
import android.text.Editable;
import android.widget.*;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.text.InputType;
import androidx.work.*;
import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;
import org.json.JSONObject;
import org.json.JSONArray;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;

public final class MainActivity extends Activity {
    private final int BG=Color.rgb(12,18,29),PANEL=Color.rgb(22,32,47),ACCENT=Color.rgb(103,223,198),TEXT=Color.rgb(231,238,247),MUTED=Color.rgb(148,169,190);
    private final ExecutorService network=Executors.newSingleThreadExecutor();private final Handler ui=new Handler(Looper.getMainLooper());
    private LinearLayout root,cards,connectionPanel;private TextView status,connectionDetail,summary;private ScrollView scroll;private String filter="",lastFailure="";private boolean connected=false,fetching=false;private long lastContact=0,latency=0;private EditText search;private final java.util.Set<String> expanded=new java.util.HashSet<>();private JSONObject connection,lastStatus;private boolean busy=false,foreground=false;private EditText invitation;
    private final Runnable refreshLoop=new Runnable(){public void run(){if(foreground){refresh();updateConnection();ui.postDelayed(this,10000);}}};
    @Override public void onCreate(Bundle state){super.onCreate(state);getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);home();}
    @Override public void onResume(){super.onResume();foreground=true;ui.removeCallbacks(refreshLoop);ui.postDelayed(refreshLoop,500);}
    @Override public void onPause(){super.onPause();foreground=false;ui.removeCallbacks(refreshLoop);}
    @Override public void onDestroy(){super.onDestroy();network.shutdownNow();}
    private void post(Runnable action){ui.post(()->{if(!isFinishing()&&!isDestroyed())action.run();});}
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private TextView text(String value,int size,int color){TextView view=new TextView(this);view.setText(value);view.setTextSize(size);if(size>=20)view.setTypeface(Typeface.DEFAULT,Typeface.BOLD);view.setTextColor(color);view.setPadding(0,dp(4),0,dp(4));return view;}
    private GradientDrawable surface(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));d.setStroke(dp(1),Color.rgb(38,53,72));return d;}
    private Button button(String title,Runnable action){Button b=new Button(this);b.setText(title);b.setTextSize(13);b.setTextColor(TEXT);b.setBackground(surface(Color.rgb(31,46,63),12));b.setAllCaps(false);b.setMinHeight(dp(48));b.setMinimumHeight(dp(48));b.setPadding(dp(10),dp(6),dp(10),dp(6));b.setOnClickListener(v->action.run());return b;}
    private LinearLayout panel(){LinearLayout box=column();box.setPadding(dp(16),dp(14),dp(16),dp(14));box.setBackground(surface(PANEL,20));return box;}
    private void spaced(LinearLayout parent,View view){LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,dp(12),0,0);parent.addView(view,lp);}
    private void rowButton(LinearLayout row,String title,Runnable action){LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(48),1);lp.setMargins(dp(3),dp(5),dp(3),dp(5));row.addView(button(title,action),lp);}
    private LinearLayout column(){LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);return layout;}
    private LinearLayout metric(String title,String value){LinearLayout tile=column();tile.setPadding(dp(10),dp(6),dp(10),dp(6));tile.setBackground(surface(Color.rgb(14,24,37),12));tile.addView(text(title,11,MUTED));tile.addView(text(value,20,TEXT));return tile;}
    private void metrics(LinearLayout card,JSONObject server){
        for(String[][] pair:new String[][][]{{{"PLAYERS","players",""},{"ENGINE FPS","fps",""}},{{"CPU · ONE CORE = 100%","cpu","%"},{"RAM WORKING SET","ram"," MB"}}}){
            LinearLayout row=new LinearLayout(this);for(String[] m:pair){LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-2,1);lp.setMargins(dp(3),dp(3),dp(3),dp(3));row.addView(metric(m[0],value(server,m[1],m[2])),lp);}card.addView(row);
        }
    }
    private String uptime(long seconds){long hours=seconds/3600;return (hours/24>0?hours/24+"d ":"")+(hours%24)+"h "+(seconds%3600/60)+"m";}
    private EditText input(String hint){EditText edit=new EditText(this);edit.setTextColor(TEXT);edit.setHintTextColor(MUTED);edit.setHint(hint);return edit;}
    private void error(Exception e){if(!isFinishing()&&!isDestroyed())new AlertDialog.Builder(this).setTitle("DZSA Tools connection").setMessage(e.getMessage()==null?"The request could not be completed.":e.getMessage()).setPositiveButton("OK",null).show();}
    private void base(){
        root=column();root.setBackgroundColor(BG);root.setPadding(dp(18),dp(18),dp(18),dp(18));
        root.setOnApplyWindowInsetsListener((v,insets)->{int top=insets.getSystemWindowInsetTop(),bottom=insets.getSystemWindowInsetBottom();v.setPadding(dp(18),dp(12)+top,dp(18),dp(12)+bottom);return insets;});
        scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.addView(root);setContentView(scroll);root.addView(text("DZSA TOOLS",26,ACCENT));root.addView(text("YOUR SERVERS. ONE WORKSPACE.",11,MUTED));
    }
    private void home(){
        try{
            JSONObject vault=Vault.read(this);JSONArray connections=vault.getJSONArray("connections");int active=Math.max(0,Math.min(vault.optInt("active",0),connections.length()-1));connection=connections.length()==0?null:connections.getJSONObject(active);
            if(connection==null){pairScreen();return;}
            connected=false;fetching=false;lastContact=0;lastFailure="";filter="";base();
            LinearLayout top=new LinearLayout(this);rowButton(top,"Switch host",this::hosts);rowButton(top,"Refresh",this::refresh);root.addView(top);
            connectionPanel=panel();status=text("CONNECTING",15,ACCENT);connectionDetail=text("Establishing a secure connection…",13,MUTED);connectionPanel.addView(text(connection.optString("name","Server host"),19,TEXT));connectionPanel.addView(status);connectionPanel.addView(text(connection.getString("url"),12,MUTED));connectionPanel.addView(connectionDetail);connectionPanel.addView(button("Connection details & diagnostics",this::connectionDetails));spaced(root,connectionPanel);
            summary=text("Waiting for server overview",17,TEXT);spaced(root,summary);
            LinearLayout tools=new LinearLayout(this);rowButton(tools,"Activity",this::history);rowButton(tools,"Alerts",this::monitoring);root.addView(tools);
            search=input("Search servers…");search.setSingleLine(true);search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence t,int a,int c,int f){}public void onTextChanged(CharSequence t,int a,int before,int count){filter=t.toString().toLowerCase(java.util.Locale.ROOT);if(lastStatus!=null)render(lastStatus,connected&&!fetching);}public void afterTextChanged(Editable e){}});root.addView(search);
            cards=column();root.addView(cards);lastStatus=connection.optJSONObject("cache");if(lastStatus!=null)render(lastStatus,false);updateConnection();refresh();
        }catch(Exception e){error(e);}
    }
    private void hosts(){
        try{JSONObject vault=Vault.read(this);JSONArray all=vault.getJSONArray("connections");String[] names=new String[all.length()+3];for(int i=0;i<all.length();i++)names[i]=all.getJSONObject(i).optString("name","Host")+" · "+all.getJSONObject(i).optString("url");names[all.length()]="Pair another host";names[all.length()+1]="Forget current host";names[all.length()+2]="Rename current host";
            new AlertDialog.Builder(this).setTitle("Connections").setItems(names,(dialog,index)->{
                try{if(index==all.length()+2){renameHost();return;}if(index==all.length()){pairScreen();return;}if(index==all.length()+1){new AlertDialog.Builder(this).setTitle("Forget this host?").setMessage("Credentials and cached status are removed from this phone. Revoke the phone in Windows to remove server-side access too.").setPositiveButton("Forget",(d,w)->{try{synchronized(Vault.class){JSONObject latest=Vault.read(this);JSONArray list=latest.getJSONArray("connections");for(int j=list.length()-1;j>=0;j--)if(list.getJSONObject(j).getString("token").equals(connection.getString("token")))list.remove(j);latest.put("active",0);Vault.write(this,latest);}home();}catch(Exception e){error(e);}}).setNegativeButton("Cancel",null).show();return;}
                    synchronized(Vault.class){JSONObject latest=Vault.read(this);latest.put("active",index);Vault.write(this,latest);}home();
                }catch(Exception e){error(e);}
            }).setNegativeButton("Close",null).show();
        }catch(Exception e){error(e);}
    }
    private void renameHost(){
        if(connection==null)return;JSONObject selected=connection;EditText name=input("Host display name");name.setText(connection.optString("name"));new AlertDialog.Builder(this).setTitle("Name this connection").setView(name).setPositiveButton("Save",(d,w)->{try{String value=name.getText().toString().trim();if(value.isEmpty()||value.length()>60)throw new Exception("Choose a name of 1–60 characters.");synchronized(Vault.class){JSONObject v=Vault.read(this);JSONArray all=v.getJSONArray("connections");for(int i=0;i<all.length();i++)if(all.getJSONObject(i).getString("token").equals(selected.getString("token")))all.getJSONObject(i).put("name",value);Vault.write(this,v);}home();}catch(Exception e){error(e);}}).setNegativeButton("Cancel",null).show();
    }
    private void pairScreen(){
        connection=null;connected=false;fetching=false;lastStatus=null;base();root.addView(text("Welcome to your control room",26,TEXT));root.addView(text("1  Enable Android access on Windows\n2  Scan the pairing code\n3  Review and connect",16,ACCENT));root.addView(text("In Windows: Android access → enable HTTPS → choose permissions → Create pairing QR code.",15,MUTED));
        invitation=input("Paste pairing invitation JSON");invitation.setMinLines(4);invitation.setMaxLines(7);invitation.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);root.addView(invitation);EditText name=input("Phone name");name.setText(Build.MODEL);root.addView(name);
        root.addView(button("Scan pairing QR",()->new IntentIntegrator(this).setDesiredBarcodeFormats(java.util.Collections.singletonList("QR_CODE")).setPrompt("Scan the QR code shown in DZSA Tools on your Windows host").setBeepEnabled(false).initiateScan()));
        root.addView(button("Review and pair",()->{
            try{JSONObject setup=new JSONObject(invitation.getText().toString());String url=setup.getString("url"),pin=setup.getString("fingerprint");if(setup.optInt("protocol")!=1)throw new Exception("Unsupported pairing protocol.");
                new AlertDialog.Builder(this).setTitle("Verify server identity").setMessage("Address:\n"+url+"\n\nCertificate SHA-256:\n"+pin+"\n\nCompare this fingerprint with the Windows application. Pair only if it matches.").setPositiveButton("Pair",(dialog,which)->{
                    if(busy)return;String phoneName=name.getText().toString();busy=true;network.execute(()->{try{JSONObject result=Api.call(setup,"/v1/pair",new JSONObject().put("code",setup.getString("code")).put("name",phoneName),true);JSONObject item=new JSONObject().put("url",url).put("fingerprint",pin).put("token",result.getString("token")).put("name",phoneName).put("expires",result.getDouble("expires"));
                        synchronized(Vault.class){JSONObject vault=Vault.read(this);JSONArray list=vault.getJSONArray("connections");list.put(item);vault.put("active",list.length()-1);Vault.write(this,vault);}post(()->{busy=false;home();});
                    }catch(Exception e){post(()->{busy=false;error(e);});}});
                }).setNegativeButton("Cancel",null).show();
            }catch(Exception e){error(e);}
        }));root.addView(button("Back to hosts",this::home));root.addView(text("Invitations are one-use and expire after five minutes. Existing RCon and local owner API ports are not used by this app.",13,MUTED));
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){IntentResult result=IntentIntegrator.parseActivityResult(requestCode,resultCode,data);if(result!=null){if(result.getContents()!=null&&invitation!=null)invitation.setText(result.getContents());return;}super.onActivityResult(requestCode,resultCode,data);}
    private void refresh(){
        if(isDestroyed()||isFinishing()||connection==null||busy)return;JSONObject selected=connection;busy=true;fetching=true;long began=SystemClock.elapsedRealtime();updateConnection();
        network.execute(()->{try{JSONObject result=Api.call(selected,"/v1/request",new JSONObject().put("method","status"),false);Vault.cache(this,selected,result);post(()->{busy=false;if(connection==selected){fetching=false;connected=true;lastFailure="";lastContact=System.currentTimeMillis();latency=SystemClock.elapsedRealtime()-began;lastStatus=result;render(result,true);updateConnection();}});}
            catch(Exception e){post(()->{busy=false;if(connection!=selected)return;fetching=false;connected=false;lastFailure=diagnose(e);if(lastStatus!=null)render(lastStatus,false);else if(cards!=null){cards.removeAllViews();cards.addView(text("No live data yet. Check the connection details below and try again.",16,MUTED));}updateConnection();});}});
    }
    private String diagnose(Exception error){
        String raw=String.valueOf(error.getMessage());String low=raw.toLowerCase(java.util.Locale.ROOT);
        if(error instanceof java.net.UnknownHostException)return "ADDRESS NOT FOUND · Check the hostname, DNS and phone internet connection.";
        if(error instanceof javax.net.ssl.SSLException||low.contains("certificate")||low.contains("fingerprint"))return "CERTIFICATE CHECK FAILED · Verify the fingerprint in Windows. Do not bypass verification; create a new pairing invitation if the certificate was replaced.";
        if(error instanceof java.net.SocketTimeoutException)return "CONNECTION TIMED OUT · Check the host is online, HTTPS gateway is enabled and the TCP port is forwarded/allowed.";
        if(error instanceof java.net.ConnectException)return "CONNECTION REFUSED · Check the address/port and that Android access says Listening on Windows.";
        if(low.contains("revoked")||low.contains("expired")||low.contains("access denied"))return "ACCESS NEEDS ATTENTION · The pairing may have expired or been revoked. Check this phone in Windows Android access.";
        return raw;
    }
    private void updateConnection(){
        if(connection==null||status==null)return;
        long age=lastContact==0?Long.MAX_VALUE:(System.currentTimeMillis()-lastContact)/1000;
        boolean fresh=connected&&age<35;
        String title=fetching?(fresh?"● CONNECTED · SYNCING":"◌ CONNECTING"):(fresh?"● CONNECTED TO AGENT":(lastFailure.isEmpty()?"○ WAITING FOR CONNECTION":"○ DISCONNECTED"));status.setText(title);status.setTextColor(fresh?ACCENT:Color.rgb(255,193,107));
        String detail=fresh?"Secure HTTPS · "+latency+" ms round trip · updated "+age+"s ago":"Server controls need a fresh authenticated response.";
        if(!lastFailure.isEmpty())detail+="\n"+lastFailure;
        if(!fresh&&lastStatus!=null)detail+="\nShowing cached data from "+timestamp(lastStatus.optDouble("at",0));
        connectionDetail.setText(detail);
    }
    private void connectionDetails(){
        if(connection==null)return;
        String detail="Gateway: "+connection.optString("url")+"\n\nCertificate SHA-256:\n"+connection.optString("fingerprint")+"\n\nLast successful response: "+(lastContact==0?"Not connected during this session":timestamp(lastContact/1000.0))+"\nRound-trip time: "+(lastContact==0?"—":latency+" ms")+"\n\n"+(lastFailure.isEmpty()?"No connection error recorded.":lastFailure)+"\n\nCHECKLIST\n• Windows agent is running\n• Android access is enabled and Listening\n• Address and TCP port are correct\n• Windows Firewall allows the port\n• For mobile data: router forwarding reaches the host\n• A LAN address is reachable only on your LAN/VPN\n\nThis connection is to the background agent. The Windows program window may be closed while the agent remains online.";
        TextView info=text(detail,14,TEXT);info.setTextIsSelectable(true);ScrollView view=new ScrollView(this);view.setPadding(dp(20),dp(8),dp(20),dp(8));view.addView(info);new AlertDialog.Builder(this).setTitle("Connection to Windows host").setView(view).setPositiveButton("Retry",(d,w)->refresh()).setNeutralButton("Hosts",(d,w)->hosts()).setNegativeButton("Close",null).show();
    }
    private String value(JSONObject o,String key,String unit){return o.isNull(key)||!o.has(key)?"—":o.optString(key)+unit;}
    private String timestamp(double seconds){return android.text.format.DateFormat.format("dd MMM HH:mm:ss",new java.util.Date((long)(seconds*1000))).toString();}
    private void render(JSONObject result,boolean live){
        if(cards==null)return;int scrollY=scroll==null?0:scroll.getScrollY();cards.removeAllViews();status.setText((live?"LIVE":"CACHED · NOT LIVE")+" · "+timestamp(result.optDouble("at",0))+"\nAgent "+result.optString("version")+" b"+result.optInt("build"));
        JSONArray servers=result.optJSONArray("servers"),scopes=result.optJSONArray("scopes");boolean control=contains(scopes,"control"),message=contains(scopes,"message");
        if(servers==null||servers.length()==0){cards.addView(text("No server profiles are available to this phone.",16,MUTED));return;}
        int runningCount=0,totalPlayers=0,knownPlayers=0;for(int n=0;n<servers.length();n++){JSONObject v=servers.optJSONObject(n);if(v!=null){if(v.optBoolean("running"))runningCount++;if(!v.isNull("players")){totalPlayers+=v.optInt("players",0);knownPlayers++;}}}summary.setText(runningCount+" / "+servers.length()+" servers running\n"+(knownPlayers==0?"Player telemetry unavailable":totalPlayers+" players"+(knownPlayers<servers.length()?" · partial telemetry":"")));
        for(int i=0;i<servers.length();i++){
            JSONObject server=servers.optJSONObject(i);if(server==null||!server.optString("name").toLowerCase(java.util.Locale.ROOT).contains(filter))continue;LinearLayout card=panel();LinearLayout.LayoutParams margin=new LinearLayout.LayoutParams(-1,-2);margin.setMargins(0,dp(12),0,0);cards.addView(card,margin);
            card.addView(text(server.optString("name"),21,TEXT));card.addView(text((server.optBoolean("running")?"● RUNNING":"○ STOPPED")+(server.optBoolean("busy")?" · BUSY":""),13,ACCENT));metrics(card,server);if(server.optBoolean("running"))card.addView(text("Uptime "+uptime(server.optLong("uptime",0)),12,MUTED));if(server.isNull("fps"))card.addView(text("Engine telemetry unavailable · process status is separate",12,MUTED));
            if(!server.isNull("restart_at")&&server.optDouble("restart_at")>0)card.addView(text("Next restart/countdown: "+timestamp(server.optDouble("restart_at")),13,MUTED));if(!server.optString("warning").isEmpty())card.addView(text(server.optString("warning"),13,Color.rgb(255,193,107)));
            String id=server.optString("id");LinearLayout controls=column();controls.setVisibility(expanded.contains(id)?View.VISIBLE:View.GONE);Button expand=button("Manage server  ▾",()->{boolean show=controls.getVisibility()!=View.VISIBLE;controls.setVisibility(show?View.VISIBLE:View.GONE);if(show)expanded.add(id);else expanded.remove(id);});card.addView(expand);card.addView(controls);LinearLayout actions=new LinearLayout(this);Button start=button("Start",()->confirm(id,"start"));Button restart=button("Restart",()->confirm(id,"restart"));Button stop=button("Stop",()->confirm(id,"stop"));stop.setTextColor(Color.rgb(255,143,153));start.setTextColor(ACCENT);restart.setTextColor(ACCENT);actions.addView(start,new LinearLayout.LayoutParams(0,-2,1));actions.addView(restart,new LinearLayout.LayoutParams(0,-2,1));actions.addView(stop,new LinearLayout.LayoutParams(0,-2,1));controls.addView(actions);start.setEnabled(live&&control&&!server.optBoolean("running")&&!server.optBoolean("busy"));restart.setEnabled(live&&control&&server.optBoolean("running"));stop.setEnabled(live&&control&&server.optBoolean("running"));
            LinearLayout extra=new LinearLayout(this);Button say=button("Message",()->message(id));Button cancel=button("Cancel countdown",()->confirm(id,"cancel_restart"));extra.addView(say,new LinearLayout.LayoutParams(0,-2,1));extra.addView(cancel,new LinearLayout.LayoutParams(0,-2,1));controls.addView(extra);say.setEnabled(live&&message&&server.optBoolean("running"));cancel.setEnabled(live&&control&&server.optBoolean("running"));Button history=button("Performance history",()->analytics(id));history.setEnabled(live);controls.addView(history);
        }
        if(cards.getChildCount()==0)cards.addView(text("No servers match your search.",16,MUTED));
        if(scroll!=null)scroll.post(()->scroll.scrollTo(0,scrollY));updateConnection();
    }
    private boolean contains(JSONArray list,String key){if(list!=null)for(int i=0;i<list.length();i++)if(key.equals(list.optString(i)))return true;return false;}
    private void confirm(String server,String action){
        LinearLayout content=column();content.setPadding(dp(20),dp(8),dp(20),0);EditText minutes=input("Countdown in minutes (1–60)");minutes.setInputType(InputType.TYPE_CLASS_NUMBER);minutes.setText("10");if(action.equals("restart")||action.equals("stop")){content.addView(text("Players receive a countdown. A working RCon connection is required.",14,TEXT));content.addView(minutes);}else content.addView(text("Send this action to the selected server?",15,TEXT));
        new AlertDialog.Builder(this).setTitle(action.replace('_',' ')).setView(content).setPositiveButton("Send",(dialog,which)->{try{JSONObject body=new JSONObject().put("method","action").put("server",server).put("action",action);if(action.equals("restart")||action.equals("stop"))body.put("minutes",Integer.parseInt(minutes.getText().toString()));send(body);}catch(Exception e){error(e);}}).setNegativeButton("Cancel",null).show();
    }
    private void message(String server){EditText field=input("Message to all players (max. 240 characters)");new AlertDialog.Builder(this).setTitle("Server message").setView(field).setPositiveButton("Send",(dialog,which)->{try{send(new JSONObject().put("method","action").put("server",server).put("action","say").put("message",field.getText().toString()));}catch(Exception e){error(e);}}).setNegativeButton("Cancel",null).show();}
    private void send(JSONObject body){
        if(busy||connection==null)return;if(!connected||System.currentTimeMillis()-lastContact>35000){error(new Exception("Connection is not fresh. Refresh status before sending commands."));return;}JSONObject selected=connection;
        try{body.put("request",UUID.randomUUID().toString().replace("-","")).put("expires",System.currentTimeMillis()/1000.0+60);}catch(Exception e){error(e);return;}
        busy=true;Toast.makeText(this,"Sending command…",Toast.LENGTH_SHORT).show();network.execute(()->{try{Api.call(selected,"/v1/request",body,false);post(()->{busy=false;if(connection==selected){Toast.makeText(this,"Command accepted. Check Activity for the result.",Toast.LENGTH_LONG).show();ui.postDelayed(this::refresh,1200);}});}catch(Exception e){post(()->{busy=false;new AlertDialog.Builder(this).setTitle("Command not confirmed").setMessage(e.getMessage()+"\n\nRefresh status and history before trying again. No automatic retry was sent.").setPositiveButton("Refresh",(d,w)->refresh()).show();});}});
    }
    private void history(){
        if(lastStatus==null)return;JSONArray jobs=lastStatus.optJSONArray("jobs");StringBuilder out=new StringBuilder();if(jobs!=null)for(int i=0;i<jobs.length();i++){JSONObject j=jobs.optJSONObject(i);out.append(timestamp(j.optDouble("created"))).append(" · ").append(j.optString("action")).append(" · ").append(j.optString("status")).append("\n").append(j.optString("result")).append("\n\n");}TextView text=text(out.length()==0?"No commands from this phone yet.":out.toString(),14,TEXT);text.setTextIsSelectable(true);ScrollView scroll=new ScrollView(this);scroll.setPadding(dp(16),0,dp(16),0);scroll.addView(text);new AlertDialog.Builder(this).setTitle("Command history · this phone").setView(scroll).setPositiveButton("Close",null).show();
    }
    private void analytics(String server){
        if(isDestroyed()||isFinishing()||connection==null||busy)return;JSONObject selected=connection;busy=true;network.execute(()->{try{JSONObject result=Api.call(selected,"/v1/request",new JSONObject().put("method","analytics").put("server",server),false);post(()->{busy=false;LinearLayout graphs=column();JSONArray rows=result.optJSONArray("history");for(String[] spec:new String[][]{{"Engine FPS","engine"},{"CPU % · 100% = one core","cpu"},{"RAM MB","ram"}})graphs.addView(new Trend(spec[0],spec[1],rows),new LinearLayout.LayoutParams(-1,dp(170)));ScrollView scroll=new ScrollView(this);scroll.addView(graphs);new AlertDialog.Builder(this).setTitle("Last hour").setView(scroll).setPositiveButton("Close",null).show();});}catch(Exception e){post(()->{busy=false;error(e);});}});
    }
    private void monitoring(){
        try{JSONObject v=Vault.read(this);boolean enabled=v.optBoolean("monitor",false);new AlertDialog.Builder(this).setTitle("Background status checks").setMessage("Optional checks run roughly every 15 minutes when Android allows network work. They can be delayed by battery saving. A detected running-to-stopped transition or two consecutive access failures produce a notification; this is not instant push monitoring.").setPositiveButton(enabled?"Disable":"Enable",(d,w)->{try{synchronized(Vault.class){JSONObject root=Vault.read(this);root.put("monitor",!enabled);Vault.write(this,root);}if(enabled)WorkManager.getInstance(this).cancelUniqueWork("cds-monitor");else{if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},44);Constraints network=new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build();PeriodicWorkRequest task=new PeriodicWorkRequest.Builder(MonitorWorker.class,15,TimeUnit.MINUTES).setConstraints(network).build();WorkManager.getInstance(this).enqueueUniquePeriodicWork("cds-monitor",ExistingPeriodicWorkPolicy.UPDATE,task);}}catch(Exception e){error(e);}}).setNegativeButton("Close",null).show();}catch(Exception e){error(e);}
    }
    private final class Trend extends View {
        private final String title,key;private final JSONArray rows;private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        Trend(String title,String key,JSONArray rows){super(MainActivity.this);this.title=title;this.key=key;this.rows=rows;}
        @Override protected void onDraw(Canvas canvas){super.onDraw(canvas);canvas.drawColor(PANEL);paint.setColor(MUTED);paint.setTextSize(dp(14));canvas.drawText(title,dp(16),dp(25),paint);double max=1;int count=0;if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&!row.isNull(key)){max=Math.max(max,row.optDouble(key));count++;}}
            if(count==0){canvas.drawText("No measurements yet",dp(16),dp(65),paint);return;}Path path=new Path();boolean segment=false;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row==null||row.isNull(key)){segment=false;continue;}float x=dp(16)+(getWidth()-dp(32))*i/(float)Math.max(1,rows.length()-1);float y=getHeight()-dp(20)-(float)(row.optDouble(key)/max)*(getHeight()-dp(60));if(segment)path.lineTo(x,y);else{path.moveTo(x,y);segment=true;}}paint.setColor(ACCENT);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(dp(2));canvas.drawPath(path,paint);paint.setStyle(Paint.Style.FILL);}
    }
}
