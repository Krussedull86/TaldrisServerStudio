package com.cruzdoodelz.serverstudio;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import org.json.JSONObject;
import org.json.JSONArray;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

final class Vault {
    private static final String ALIAS="cds.mobile.credentials.v1";
    private static SecretKey key() throws Exception {
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(!ks.containsAlias(ALIAS)) {
            KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());generator.generateKey();
        }
        return (SecretKey)ks.getKey(ALIAS,null);
    }
    static synchronized JSONObject read(Context context) throws Exception {
        String text=context.getSharedPreferences("vault",Context.MODE_PRIVATE).getString("data",null);
        if(text==null)return new JSONObject().put("connections",new JSONArray()).put("active",0);
        JSONObject encoded=new JSONObject(text);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(encoded.getString("iv"),Base64.NO_WRAP)));
        return new JSONObject(new String(cipher.doFinal(Base64.decode(encoded.getString("ciphertext"),Base64.NO_WRAP)),java.nio.charset.StandardCharsets.UTF_8));
    }
    static synchronized void write(Context context,JSONObject value) throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());
        JSONObject data=new JSONObject().put("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)).put("ciphertext",Base64.encodeToString(cipher.doFinal(value.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)),Base64.NO_WRAP));
        if(!context.getSharedPreferences("vault",Context.MODE_PRIVATE).edit().putString("data",data.toString()).commit())throw new Exception("Could not store device credentials.");
    }
    static synchronized void cache(Context context,JSONObject connection,JSONObject status) throws Exception {
        JSONObject root=read(context);JSONArray list=root.getJSONArray("connections");
        for(int i=0;i<list.length();i++){JSONObject c=list.getJSONObject(i);if(c.getString("token").equals(connection.getString("token"))){c.put("cache",status);c.put("cached_at",System.currentTimeMillis());}}
        write(context,root);
    }
}
