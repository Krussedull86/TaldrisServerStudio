(()=>{
 const esc=s=>String(s).replace(/[<>&"']/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]));
 const response=x=>new Response(typeof x==='string'?x:JSON.stringify(x),{headers:{'Content-Type':'application/json'}});
 const api=(action,payload)=>window.desktopApi.call(action,payload);
 const nativeFetch=window.fetch.bind(window);
 let active;window.fetch=async(input,opts={})=>{
 const u=new URL(input,location.href);if(!u.pathname.includes('/backend/'))return nativeFetch(input,opts);
 const endpoint=u.pathname.split('/').pop();
 switch(endpoint){
 case 'tutorial.php':return response({status:'no'});
 case 'getFileName.php':{active=await api('state');return response(`<span class="dz_editorTitle">File:</span> <strong>${esc(active.title)} · revision ${active.rev}</strong> <span class="dz_editorTitle">${active.rows.length} items · Saved on this PC</span> <a href="backend/download.php?id=${active.id}&rev=${active.rev}" class="dz_editorTitle">Export XML…</a>`);}
 case 'save.php':return response(await api('save',JSON.parse(opts.body)));
 case 'osf.php':return response(await api(u.searchParams.has('undo')?'undo':'redo'));
 case 'listFiles.php':{const versions=u.searchParams.has('listVersions');const projects=await api('list',versions?'versions':'all');if(projects.error)return response(projects);return response(projects.map(p=>({file_id:p.id,file_title:p.title,revision:p.rev,modified_date:p.modified.replace('T',' ').slice(0,19),xml_downloaded:'—',linkED:`backend/load.php?id=${p.id}&rev=${p.rev}`,linkDL:`backend/download.php?id=${p.id}&rev=${p.rev}`,linkRMV:`backend/delete.php?id=${p.id}&rev=${p.rev}`,linkRMF:`backend/delete.php?id=${p.id}&rmf`,status:p.id===active.id&&p.rev===active.rev?'active':'inactive'})));}
 default:return response({error:'Unsupported action.'});
 }};
 async function show(action,payload){const r=await api(action,payload);if(r?.error)window.showToastError(r.error);return r;}
 // Saving a project revision precedes export, including an uncommitted cell edit.
 async function exportCurrent(){try{document.activeElement?.blur();document.getElementById('btn_save').click();const saved=await window.desktopSaveComplete;if(saved?.error)throw Error(saved.error);await show('export');}catch(e){window.showToastError(e.message);}}
 document.addEventListener('click',async e=>{const a=e.target.closest('a');if(!a)return;const u=new URL(a.href);if(!u.pathname.includes('/backend/'))return;e.preventDefault();const payload={id:u.searchParams.get('id'),rev:Number(u.searchParams.get('rev'))};if(u.pathname.endsWith('/download.php')){if(payload.id===active.id&&payload.rev===active.rev)await exportCurrent();else await show('export',payload);}else if(u.pathname.endsWith('/load.php'))await show('load',payload);else if(u.pathname.endsWith('/delete.php'))await show(u.searchParams.has('rmf')?'delete':'deleteRevision',payload);});
 window.startDesktop=async()=>{
 active=await api('state');if(active?.error)throw Error(active.error);document.querySelector('.desktop-brand small').textContent='SERVER STUDIO '+(active.appVersion||'1.2.0');window.jsonDataMod=JSON.stringify(active.rows);window.jsonDataOrg=JSON.stringify(active.originalRows);
 document.getElementById('dz_listVersions').textContent='Saved versions · '+active.title;
 document.getElementById('desktop-channel').hidden=true;document.getElementById('desktop-updates').hidden=true;
 document.getElementById('desktop-open').addEventListener('click',()=>show('open'));
 document.getElementById('desktop-export').addEventListener('click',exportCurrent);
 document.getElementById('desktop-validate').addEventListener('click',async()=>{const result=await show('validate');if(result?.data)window.showToastTools(result.data);});
 const mapSelect=document.getElementById('desktop-map');if(Array.isArray(active.maps)){mapSelect.replaceChildren(new Option('New from map…',''),...active.maps.map(m=>new Option(m.name,m.id)));}
 document.getElementById('desktop-map').addEventListener('change',e=>{const value=e.target.value;e.target.value='';if(value)show('map',value);});
 window.desktopApi.onAction(action=>{if(action==='export')exportCurrent();else document.getElementById('btn_'+action)?.click();});
 await window.initEditorJS();window.initTierMapsJS();
 };
 // State is written to disk by the main process, never localStorage.
 const oldFetch=window.fetch;window.fetch=(input,opts)=>{const promise=oldFetch(input,opts);if(String(input).includes('backend/save.php'))window.desktopSaveComplete=promise.then(async r=>{const data=await r.clone().json();return data;});return promise;};
 window.desktopDirty=()=>api('dirty');
 window.desktopFileAction=(action,item)=>show(action,{id:item.file_id,rev:Number(item.revision)});
})();

