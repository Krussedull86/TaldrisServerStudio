(()=>{
 let resolve;const ready=new Promise(r=>resolve=r);window.desktopApi={call:(action,payload=null)=>ready.then(api=>new Promise((done,reject)=>api.call(action,JSON.stringify(payload),raw=>{try{done(JSON.parse(raw));}catch(e){reject(e);}}))),onAction:()=>{}};
 new QWebChannel(qt.webChannelTransport,channel=>resolve(channel.objects.studio));
 window.studioSaveMission=async()=>{try{document.activeElement?.blur();document.getElementById('btn_save').click();const saved=await window.desktopSaveComplete;if(saved?.error)throw Error(saved.error);const result=await window.desktopApi.call('mission_save');if(result?.error)throw Error(result.error);window.showToastSave(result?.data||'Cancelled');}catch(e){window.showToastError(e.message);}};
})();
