package com.cruzdoodelz.serverstudio;

import android.content.Context;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import org.json.JSONObject;
import org.json.JSONArray;

public final class MonitorWorker extends Worker {
    public MonitorWorker(@NonNull Context context,@NonNull WorkerParameters params){super(context,params);}
    @NonNull public Result doWork(){
        Context ctx=getApplicationContext();
        try{
            JSONObject root=Vault.read(ctx);if(!root.optBoolean("monitor",false))return Result.success();JSONArray list=root.getJSONArray("connections");
            for(int i=0;i<list.length();i++){
                JSONObject c=list.getJSONObject(i);
                try{
                    JSONObject status=Api.call(c,"/v1/request",new JSONObject().put("method","status"),false);JSONArray servers=status.getJSONArray("servers");JSONObject old=c.optJSONObject("cache");
                    if(old!=null){JSONArray previous=old.optJSONArray("servers");if(previous!=null)for(int n=0;n<servers.length();n++){JSONObject current=servers.getJSONObject(n);for(int j=0;j<previous.length();j++){JSONObject prior=previous.getJSONObject(j);if(prior.optString("id").equals(current.optString("id"))&&prior.optBoolean("running")&&!current.optBoolean("running"))notify(ctx,current.optString("id"),current.optString("name")+" stopped","Open CDS to check server status and command history.");}}}
                    Vault.cache(ctx,c,status);
                }catch(Exception error){/* No command retries and no misleading crash alarm on a failed network request. */}
            }
        }catch(Exception error){return Result.failure();}
        return Result.success();
    }
    private static void notify(Context ctx,String id,String title,String message){
        try{NotificationManager manager=ctx.getSystemService(NotificationManager.class);manager.createNotificationChannel(new NotificationChannel("cds-monitor","CDS server monitoring",NotificationManager.IMPORTANCE_DEFAULT));PendingIntent open=PendingIntent.getActivity(ctx,0,new Intent(ctx,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);manager.notify(id.hashCode(),new android.app.Notification.Builder(ctx,"cds-monitor").setSmallIcon(com.cruzdoodelz.serverstudio.R.drawable.ic_cds).setContentTitle(title).setContentText(message).setContentIntent(open).setAutoCancel(true).build());}catch(SecurityException ignored){}
    }
}
