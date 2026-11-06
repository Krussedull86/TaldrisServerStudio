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
    private LinearLayout root,cards;private TextView status;private JSONObject connection,lastStatus;private boolean busy=false,foreground=false;private EditText invitation;
    private final Runnable refreshLoop=new Runnable(){public void run(){if(foreground){refresh();ui.postDelayed(this,15000);}}};
    @Override public void onCreate(Bundle state){super.onCreate(state);getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);home();}
    @Override public void onResume(){super.onResume();foreground=true;ui.removeCallbacks(refreshLoop);ui.postDelayed(refreshLoop,500);}
    @Override public void onPause(){super.onPause();foreground=false;ui.removeCallbacks(refreshLoop);}
    @Override public void onDestroy(){super.onDestroy();network.shutdownNow();}
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private TextView text(String value,int size,int color){TextView view=new TextView(this);view.setText(value);view.setTextSize(size);view.setTextColor(color);view.setPadding(0,dp(4),0,dp(4));return view;}
    private Button button(String title,Runnable action){Button b=new Button(this);b.setText(title);b.setTextColor(BG);b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(ACCENT));b.setAllCaps(false);b.setOnClickListener(v->action.run());return b;}
    private LinearLayout column(){LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);return layout;}
    private EditText input(String hint){EditText edit=new EditText(this);edit.setTextColor(TEXT);edit.setHintTextColor(MUTED);edit.setHint(hint);return edit;}
    private void error(Exception e){if(!isFinishing())new AlertDialog.Builder(this).setTitle("CDS connection").setMessage(e.getMessage()==null?"The request could not be completed.":e.getMessage()).setPositiveButton("OK",null).show();}
    private void base(){
        root=column();root.setBackgroundColor(BG);root.setPadding(dp(18),dp(18),dp(18),dp(18));
        root.setOnApplyWindowInsetsListener((v,insets)->{int top=insets.getSystemWindowInsetTop(),bottom=insets.getSystemWindowInsetBottom();v.setPadding(dp(18),dp(12)+top,dp(18),dp(12)+bottom);return insets;});
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.addView(root);setContentView(scroll);root.addView(text("CRUZDOODELZ",24,ACCENT));root.addView(text("SERVER STUDIO · ANDROID",12,MUTED));
    }
    private void home(){
        try{
            JSONObject vault=Vault.read(this);JSONArray connections=vault.getJSONArray("connections");int active=Math.max(0,Math.min(vault.optInt("active",0),connections.length()-1));connection=connections.length()==0?null:connections.getJSONObject(active);
            if(connection==null){pairScreen();return;}
            base();root.addView(text(connection.optString("name","Server host"),20,TEXT));root.addView(text(connection.getString("url"),12,MUTED));
            LinearLayout row=new LinearLayout(this);row.addView(button("Hosts",this::hosts),new LinearLayout.LayoutParams(0,-2,1));row.addView(button("Refresh",this::refresh),new LinearLayout.LayoutParams(0,-2,1));root.addView(row);
            status=text("Connecting…",14,MUTED);root.addView(status);
            LinearLayout tools=new LinearLayout(this);tools.addView(button("History",this::history),new LinearLayout.LayoutParams(0,-2,1));tools.addView(button("Monitoring",this::monitoring),new LinearLayout.LayoutParams(0,-2,1));root.addView(tools);
            cards=column();root.addView(cards);lastStatus=connection.optJSONObject("cache");if(lastStatus!=null)render(lastStatus,false);refresh();
        }catch(Exception e){error(e);}
    }
    private void hosts(){
        try{JSONObject vault=Vault.read(this);JSONArray all=vault.getJSONArray("connections");String[] names=new String[all.length()+2];for(int i=0;i<all.length();i++)names[i]=all.getJSONObject(i).optString("name","Host")+" · "+all.getJSONObject(i).optString("url");names[all.length()]="Pair another host";names[all.length()+1]="Forget current host";
            new AlertDialog.Builder(this).setTitle("Connections").setItems(names,(dialog,index)->{
                try{if(index==all.length()){pairScreen();return;}if(index==all.length()+1){new AlertDialog.Builder(this).setTitle("Forget this host?").setMessage("Credentials and cached status are removed from this phone. Revoke the phone in Windows to remove server-side access too.").setPositiveButton("Forget",(d,w)->{try{synchronized(Vault.class){JSONObject latest=Vault.read(this);JSONArray list=latest.getJSONArray("connections");for(int j=list.length()-1;j>=0;j--)if(list.getJSONObject(j).getString("token").equals(connection.getString("token")))list.remove(j);latest.put("active",0);Vault.write(this,latest);}home();}catch(Exception e){error(e);}}).setNegativeButton("Cancel",null).show();return;}
                    synchronized(Vault.class){JSONObject latest=Vault.read(this);latest.put("active",index);Vault.write(this,latest);}home();
                }catch(Exception e){error(e);}
            }).setNegativeButton("Close",null).show();
        }catch(Exception e){error(e);}
    }
    private void pairScreen(){
        connection=null;lastStatus=null;base();root.addView(text("Pair your server host",24,TEXT));root.addView(text("In Windows: Android access → enable HTTPS → choose permissions → Create pairing QR code.",15,MUTED));
        invitation=input("Paste pairing invitation JSON");invitation.setMinLines(4);invitation.setMaxLines(7);invitation.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);root.addView(invitation);EditText name=input("Phone name");name.setText(Build.MODEL);root.addView(name);
        root.addView(button("Scan pairing QR",()->new IntentIntegrator(this).setDesiredBarcodeFormats(IntentIntegrator.QR_CODE_TYPES).setPrompt("Scan the QR code shown in CDS on your Windows host").setBeepEnabled(false).initiateScan()));
        root.addView(button("Review and pair",()->{
            try{JSONObject setup=new JSONObject(invitation.getText().toString());String url=setup.getString("url"),pin=setup.getString("fingerprint");if(setup.optInt("protocol")!=1)throw new Exception("Unsupported pairing protocol.");
                new AlertDialog.Builder(this).setTitle("Verify server identity").setMessage("Address:\n"+url+"\n\nCertificate SHA-256:\n"+pin+"\n\nCompare this fingerprint with the Windows application. Pair only if it matches.").setPositiveButton("Pair",(dialog,which)->{
                    if(busy)return;String phoneName=name.getText().toString();busy=true;network.execute(()->{try{JSONObject result=Api.call(setup,"/v1/pair",new JSONObject().put("code",setup.getString("code")).put("name",phoneName),true);JSONObject item=new JSONObject().put("url",url).put("fingerprint",pin).put("token",result.getString("token")).put("name",phoneName).put("expires",result.getDouble("expires"));
                        synchronized(Vault.class){JSONObject vault=Vault.read(this);JSONArray list=vault.getJSONArray("connections");list.put(item);vault.put("active",list.length()-1);Vault.write(this,vault);}ui.post(()->{busy=false;home();});
                    }catch(Exception e){ui.post(()->{busy=false;error(e);});}});
                }).setNegativeButton("Cancel",null).show();
            }catch(Exception e){error(e);}
        }));root.addView(button("Back to hosts",this::home));root.addView(text("Invitations are one-use and expire after five minutes. Existing RCon and local owner API ports are not used by this app.",13,MUTED));
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){IntentResult result=IntentIntegrator.parseActivityResult(requestCode,resultCode,data);if(result!=null){if(result.getContents()!=null&&invitation!=null)invitation.setText(result.getContents());return;}super.onActivityResult(requestCode,resultCode,data);}
    private void refresh(){
        if(connection==null||busy)return;JSONObject selected=connection;busy=true;
        network.execute(()->{try{JSONObject result=Api.call(selected,"/v1/request",new JSONObject().put("method","status"),false);Vault.cache(this,selected,result);ui.post(()->{busy=false;if(connection==selected){lastStatus=result;render(result,true);}});}
            catch(Exception e){ui.post(()->{busy=false;if(connection!=selected)return;if(lastStatus!=null)render(lastStatus,false);status.setText("OFFLINE / NOT CONFIRMED · "+e.getMessage()+"\nCached data is not live. Commands are never queued offline.");});}});
    }
    private String value(JSONObject o,String key,String unit){return o.isNull(key)||!o.has(key)?"—":o.optString(key)+unit;}
    private String timestamp(double seconds){return android.text.format.DateFormat.format("dd MMM HH:mm:ss",new java.util.Date((long)(seconds*1000))).toString();}
    private void render(JSONObject result,boolean live){
        if(cards==null)return;cards.removeAllViews();status.setText((live?"LIVE":"CACHED · NOT LIVE")+" · "+timestamp(result.optDouble("at",0))+"\nAgent "+result.optString("version")+" b"+result.optInt("build"));
        JSONArray servers=result.optJSONArray("servers"),scopes=result.optJSONArray("scopes");boolean control=contains(scopes,"control"),message=contains(scopes,"message");
        if(servers==null||servers.length()==0){cards.addView(text("No server profiles are available to this phone.",16,MUTED));return;}
        for(int i=0;i<servers.length();i++){
            JSONObject server=servers.optJSONObject(i);if(server==null)continue;LinearLayout card=column();card.setBackgroundColor(PANEL);card.setPadding(dp(14),dp(12),dp(14),dp(12));LinearLayout.LayoutParams margin=new LinearLayout.LayoutParams(-1,-2);margin.setMargins(0,dp(12),0,0);cards.addView(card,margin);
            card.addView(text(server.optString("name"),21,TEXT));card.addView(text((server.optBoolean("running")?"● RUNNING":"○ STOPPED")+(server.optBoolean("busy")?" · BUSY":""),13,ACCENT));card.addView(text("Players "+value(server,"players","")+"     FPS "+value(server,"fps","")+"\nCPU "+value(server,"cpu","%")+"     RAM "+value(server,"ram"," MB"),17,TEXT));card.addView(text("CPU 100% = one logical core",11,MUTED));
            if(!server.isNull("restart_at")&&server.optDouble("restart_at")>0)card.addView(text("Next restart/countdown: "+timestamp(server.optDouble("restart_at")),13,MUTED));if(!server.optString("warning").isEmpty())card.addView(text(server.optString("warning"),13,Color.rgb(255,193,107)));
            String id=server.optString("id");LinearLayout actions=new LinearLayout(this);Button start=button("Start",()->confirm(id,"start"));Button restart=button("Restart",()->confirm(id,"restart"));Button stop=button("Stop",()->confirm(id,"stop"));actions.addView(start,new LinearLayout.LayoutParams(0,-2,1));actions.addView(restart,new LinearLayout.LayoutParams(0,-2,1));actions.addView(stop,new LinearLayout.LayoutParams(0,-2,1));card.addView(actions);start.setEnabled(live&&control&&!server.optBoolean("running")&&!server.optBoolean("busy"));restart.setEnabled(live&&control&&server.optBoolean("running"));stop.setEnabled(live&&control&&server.optBoolean("running"));
            LinearLayout extra=new LinearLayout(this);Button say=button("Message",()->message(id));Button cancel=button("Cancel countdown",()->confirm(id,"cancel_restart"));extra.addView(say,new LinearLayout.LayoutParams(0,-2,1));extra.addView(cancel,new LinearLayout.LayoutParams(0,-2,1));card.addView(extra);say.setEnabled(live&&message&&server.optBoolean("running"));cancel.setEnabled(live&&control&&server.optBoolean("running"));Button history=button("Performance history",()->analytics(id));history.setEnabled(live);card.addView(history);
        }
    }
    private boolean contains(JSONArray list,String key){if(list!=null)for(int i=0;i<list.length();i++)if(key.equals(list.optString(i)))return true;return false;}
    private void confirm(String server,String action){
        LinearLayout content=column();content.setPadding(dp(20),dp(8),dp(20),0);EditText minutes=input("Countdown in minutes (1–60)");minutes.setInputType(InputType.TYPE_CLASS_NUMBER);minutes.setText("10");if(action.equals("restart")||action.equals("stop")){content.addView(text("Players receive a countdown. A working RCon connection is required.",14,TEXT));content.addView(minutes);}else content.addView(text("Send this action to the selected server?",15,TEXT));
        new AlertDialog.Builder(this).setTitle(action.replace('_',' ')).setView(content).setPositiveButton("Send",(dialog,which)->{try{JSONObject body=new JSONObject().put("method","action").put("server",server).put("action",action);if(action.equals("restart")||action.equals("stop"))body.put("minutes",Integer.parseInt(minutes.getText().toString()));send(body);}catch(Exception e){error(e);}}).setNegativeButton("Cancel",null).show();
    }
    private void message(String server){EditText field=input("Message to all players (max. 240 characters)");new AlertDialog.Builder(this).setTitle("Server message").setView(field).setPositiveButton("Send",(dialog,which)->{try{send(new JSONObject().put("method","action").put("server",server).put("action","say").put("message",field.getText().toString()));}catch(Exception e){error(e);}}).setNegativeButton("Cancel",null).show();}
    private void send(JSONObject body){
        if(busy||connection==null)return;JSONObject selected=connection;
        try{body.put("request",UUID.randomUUID().toString().replace("-","")).put("expires",System.currentTimeMillis()/1000.0+60);}catch(Exception e){error(e);return;}
        busy=true;status.setText("Sending command…");network.execute(()->{try{Api.call(selected,"/v1/request",body,false);ui.post(()->{busy=false;if(connection==selected){status.setText("Command accepted. Check history for the result.");ui.postDelayed(this::refresh,1200);}});}catch(Exception e){ui.post(()->{busy=false;new AlertDialog.Builder(this).setTitle("Command not confirmed").setMessage(e.getMessage()+"\n\nRefresh status and history before trying again. No automatic retry was sent.").setPositiveButton("Refresh",(d,w)->refresh()).show();});}});
    }
    private void history(){
        if(lastStatus==null)return;JSONArray jobs=lastStatus.optJSONArray("jobs");StringBuilder out=new StringBuilder();if(jobs!=null)for(int i=0;i<jobs.length();i++){JSONObject j=jobs.optJSONObject(i);out.append(timestamp(j.optDouble("created"))).append(" · ").append(j.optString("action")).append(" · ").append(j.optString("status")).append("\n").append(j.optString("result")).append("\n\n");}TextView text=text(out.length()==0?"No commands from this phone yet.":out.toString(),14,TEXT);text.setTextIsSelectable(true);ScrollView scroll=new ScrollView(this);scroll.setPadding(dp(16),0,dp(16),0);scroll.addView(text);new AlertDialog.Builder(this).setTitle("Command history · this phone").setView(scroll).setPositiveButton("Close",null).show();
    }
    private void analytics(String server){
        if(connection==null||busy)return;JSONObject selected=connection;busy=true;network.execute(()->{try{JSONObject result=Api.call(selected,"/v1/request",new JSONObject().put("method","analytics").put("server",server),false);ui.post(()->{busy=false;LinearLayout graphs=column();JSONArray rows=result.optJSONArray("history");for(String[] spec:new String[][]{{"Engine FPS","engine"},{"CPU % · 100% = one core","cpu"},{"RAM MB","ram"}})graphs.addView(new Trend(spec[0],spec[1],rows),new LinearLayout.LayoutParams(-1,dp(170)));ScrollView scroll=new ScrollView(this);scroll.addView(graphs);new AlertDialog.Builder(this).setTitle("Last hour").setView(scroll).setPositiveButton("Close",null).show();});}catch(Exception e){ui.post(()->{busy=false;error(e);});}});
    }
    private void monitoring(){
        try{JSONObject v=Vault.read(this);boolean enabled=v.optBoolean("monitor",false);new AlertDialog.Builder(this).setTitle("Background status checks").setMessage("Optional checks run roughly every 15 minutes when Android allows network work. They can be delayed by battery saving. A detected running-to-stopped transition produces a notification; this is not instant push monitoring.").setPositiveButton(enabled?"Disable":"Enable",(d,w)->{try{synchronized(Vault.class){JSONObject root=Vault.read(this);root.put("monitor",!enabled);Vault.write(this,root);}if(enabled)WorkManager.getInstance(this).cancelUniqueWork("cds-monitor");else{if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},44);Constraints network=new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build();PeriodicWorkRequest task=new PeriodicWorkRequest.Builder(MonitorWorker.class,15,TimeUnit.MINUTES).setConstraints(network).build();WorkManager.getInstance(this).enqueueUniquePeriodicWork("cds-monitor",ExistingPeriodicWorkPolicy.UPDATE,task);}}catch(Exception e){error(e);}}).setNegativeButton("Close",null).show();}catch(Exception e){error(e);}
    }
    private final class Trend extends View {
        private final String title,key;private final JSONArray rows;private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        Trend(String title,String key,JSONArray rows){super(MainActivity.this);this.title=title;this.key=key;this.rows=rows;}
        @Override protected void onDraw(Canvas canvas){super.onDraw(canvas);canvas.drawColor(PANEL);paint.setColor(MUTED);paint.setTextSize(dp(14));canvas.drawText(title,dp(16),dp(25),paint);double max=1;int count=0;if(rows!=null)for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&!row.isNull(key)){max=Math.max(max,row.optDouble(key));count++;}}
            if(count==0){canvas.drawText("No measurements yet",dp(16),dp(65),paint);return;}Path path=new Path();boolean segment=false;for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row==null||row.isNull(key)){segment=false;continue;}float x=dp(16)+(getWidth()-dp(32))*i/(float)Math.max(1,rows.length()-1);float y=getHeight()-dp(20)-(float)(row.optDouble(key)/max)*(getHeight()-dp(60));if(segment)path.lineTo(x,y);else{path.moveTo(x,y);segment=true;}}paint.setColor(ACCENT);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(dp(2));canvas.drawPath(path,paint);paint.setStyle(Paint.Style.FILL);}
    }
}
