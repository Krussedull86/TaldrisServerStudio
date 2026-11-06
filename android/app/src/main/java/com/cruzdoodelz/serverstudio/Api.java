package com.cruzdoodelz.serverstudio;

import org.json.JSONObject;
import java.net.URL;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.cert.X509Certificate;
import java.security.cert.CertificateException;
import javax.net.ssl.*;

final class Api {
    static String fingerprint(X509Certificate certificate) throws Exception {
        byte[] bytes=MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded());StringBuilder out=new StringBuilder();for(byte b:bytes)out.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return out.toString();
    }
    static JSONObject call(JSONObject connection,String path,JSONObject body,boolean pair) throws Exception {
        String endpoint=connection.getString("url");URL base=new URL(endpoint);String pin=connection.getString("fingerprint").toLowerCase(java.util.Locale.ROOT).replace(":","");
        if(!base.getProtocol().equals("https")||base.getHost().isEmpty()||base.getUserInfo()!=null||!base.getPath().isEmpty()||base.getQuery()!=null||base.getRef()!=null||!pin.matches("[a-f0-9]{64}"))throw new Exception("Invalid HTTPS endpoint or certificate fingerprint.");
        X509TrustManager trust=new X509TrustManager(){
            public X509Certificate[] getAcceptedIssuers(){return new X509Certificate[0];}
            public void checkClientTrusted(X509Certificate[] chain,String auth) throws CertificateException {throw new CertificateException("Client certificates are not used.");}
            public void checkServerTrusted(X509Certificate[] chain,String auth) throws CertificateException {
                try{if(chain.length==0)throw new Exception("Missing certificate");chain[0].checkValidity();if(!MessageDigest.isEqual(pin.getBytes(StandardCharsets.US_ASCII),fingerprint(chain[0]).getBytes(StandardCharsets.US_ASCII)))throw new Exception("Certificate fingerprint changed. Verify the server in DZSA Tools before pairing again.");}
                catch(Exception error){throw new CertificateException(error);}
            }
        };
        SSLContext tls=SSLContext.getInstance("TLS");tls.init(null,new TrustManager[]{trust},new SecureRandom());
        HttpsURLConnection request=(HttpsURLConnection)new URL(endpoint+path).openConnection();
        // This is explicit certificate identity pinning, including the hostname
        // verifier. It never falls back to accepting arbitrary certificates.
        request.setSSLSocketFactory(tls.getSocketFactory());request.setHostnameVerifier((host,session)->{try{return MessageDigest.isEqual(pin.getBytes(StandardCharsets.US_ASCII),fingerprint((X509Certificate)session.getPeerCertificates()[0]).getBytes(StandardCharsets.US_ASCII));}catch(Exception e){return false;}});
        request.setInstanceFollowRedirects(false);request.setConnectTimeout(10000);request.setReadTimeout(10000);request.setRequestMethod("POST");request.setDoOutput(true);request.setRequestProperty("Content-Type","application/json");
        if(!pair)request.setRequestProperty("Authorization","Bearer "+connection.getString("token"));
        try{
            byte[] data=body.toString().getBytes(StandardCharsets.UTF_8);request.setFixedLengthStreamingMode(data.length);try(java.io.OutputStream out=request.getOutputStream()){out.write(data);}
            int code=request.getResponseCode();InputStream source=code==200?request.getInputStream():request.getErrorStream();if(source==null)throw new Exception("Gateway HTTP "+code+". Check the endpoint and port forwarding.");
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream in=source){byte[] block=new byte[8192];int count;while((count=in.read(block))!=-1){if(bytes.size()+count>2*1024*1024)throw new Exception("Gateway response exceeds limit.");bytes.write(block,0,count);}}
            JSONObject result=new JSONObject(bytes.toString(StandardCharsets.UTF_8.name()));if(code!=200||result.has("error"))throw new Exception(result.optString("error","Gateway HTTP "+code));return result.getJSONObject("result");
        }finally{request.disconnect();}
    }
}
