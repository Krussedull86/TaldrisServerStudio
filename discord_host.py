"""Guild-scoped Discord control. All privileged work runs through HostEngine."""
import asyncio,io,json,threading,time
from pathlib import Path
from host_security import load_secrets

PERMISSIONS={
 'status':'read','players':'read','bans':'moderate','start':'control','stop':'control','restart':'control','cancel_restart':'control','lock':'control','unlock':'control','say':'moderate','kick':'moderate','ban':'moderate','unban':'moderate',
 'mods':'read','backups':'maintenance','files':'owner','file_history':'owner','file_restore':'owner','logs':'read','schedule_set':'config','workshop_search':'read','local_mod_scan':'owner','local_mod_add':'owner','mod_collection':'config','backup':'maintenance','restore':'owner','rollback_mods':'maintenance','maintenance':'maintenance','steam':'maintenance','check_mods':'read','mod_add':'config','mod_remove':'config','mod_mode':'config','mod_move':'config','document_save':'owner','list_add':'config','clone':'owner','force_stop':'owner','program_prepare':'owner','program_status':'read','rotate_logs':'maintenance'}
DANGEROUS={'file_restore','restore','force_stop','rollback_mods','ban','unban','document_save','mod_remove','clone','program_prepare'}


def authorized(settings,guild,user,roles,server,action):
    if str(guild)!=str(settings.get('guild_id','')):return False
    if str(user) in {str(value) for value in settings.get('owners',[])}:return True
    needed=PERMISSIONS.get(action)
    if needed is None or needed=='owner':return False
    permissions=settings.get('server_roles',{}).get(server,settings.get('roles',{}));allowed=permissions.get(needed,[])
    return bool({str(role) for role in roles}&{str(role) for role in allowed})


class DiscordHost:
    def __init__(self,engine):self.engine=engine;self.client=None;self.loop=None;self.thread=None
    def start(self):
        settings=self.engine.manager.state.get('discord',{})
        if not settings.get('enabled'):return
        token=load_secrets(self.engine.home).get('discord_token')
        if not token:self.engine.log('Discord er aktivert, men bot-token mangler.');return
        self.engine.secrets.append(token)
        self.thread=threading.Thread(target=self.run,args=(token,),daemon=True);self.thread.start()
    def stop(self):
        if self.loop and self.client:
            try:asyncio.run_coroutine_threadsafe(self.client.close(),self.loop)
            except RuntimeError:pass
    def run(self,token):
        try:asyncio.run(self.main(token))
        except Exception as error:self.engine.log('Discord-tilkobling feilet: '+str(error))
    async def main(self,token):
        import discord,aiohttp
        from discord import app_commands
        from network_tls import tls_context
        host=self;engine=self.engine;settings=engine.manager.state['discord'];guild=discord.Object(id=int(settings['guild_id']));self.loop=asyncio.get_running_loop()
        class Client(discord.Client):
            async def setup_hook(self):
                self.tree=app_commands.CommandTree(self)
                self.tree.add_command(group,guild=guild);await self.tree.sync(guild=guild)
                self.add_view(ControlView())
            async def on_ready(self):
                engine.log('Discord-boten er tilkoblet.')
                if not hasattr(self,'notice_task') or self.notice_task.done():self.notice_task=asyncio.create_task(notifications())
        def check(interaction,server,action):
            if not interaction.guild_id or not authorized(settings,interaction.guild_id,interaction.user.id,[r.id for r in getattr(interaction.user,'roles',[])],server,action):raise ValueError('Du har ikke tilgang til denne handlingen på denne serveren.')
        async def dispatch(interaction,server,action,data=None,confirmed=False):
            try:
                p=engine.profile(server);check(interaction,p['id'],action)
                if action=='status':
                    snap=engine.snapshot();runtime=snap['runtime'][p['id']];record=runtime.get('launch',{});text=f"**{p['name']}**\n{'Prosess kjører' if runtime['running'] else 'Stoppet'} • port {p['port']}\nRAM: {runtime.get('ram_mb','—')} MB\nVedlikehold: {p.get('maintenance_state','idle')}"
                    if record.get('restart_due'):
                        import datetime
                        text+='\nNeste restart: <t:'+str(int(record['restart_due']))+':R>'
                    await interaction.response.send_message(text,ephemeral=True,allowed_mentions=discord.AllowedMentions.none());return
                if action in DANGEROUS and not confirmed:
                    view=ConfirmView(interaction.user.id,p['id'],action,data or {});await interaction.response.send_message('Bekreft **'+action+'** på **'+p['name']+'**. Kontroller server og parametere: `'+str(data or {})[:700]+'`',view=view,ephemeral=True,allowed_mentions=discord.AllowedMentions.none());return
                await interaction.response.defer(ephemeral=True)
                job=engine.enqueue(action,p['id'],data or {},actor='Discord '+str(interaction.user.id));await interaction.followup.send('Jobb mottatt: `'+job['id']+'`. Bruk `/taldris jobb` for resultat.',ephemeral=True)
                async def report_result():
                    for _ in range(60):
                        await asyncio.sleep(.5);current=engine.jobs.get(job['id'],{})
                        if current.get('status') in ('completed','failed'):
                            try:
                                check(interaction,p['id'],action);value=current.get('error',current.get('result','Fullført.'));text=engine.redact(json.dumps(value,indent=2,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value))
                                if isinstance(value,dict) and value.get('artifact'):
                                    path=engine.home/'job_results'/value['artifact'];await interaction.followup.send('Jobbresultat:',file=discord.File(path),ephemeral=True)
                                elif len(text)>1900:await interaction.followup.send('Jobbresultat:',file=discord.File(io.BytesIO(text.encode()),filename='resultat.txt'),ephemeral=True)
                                else:await interaction.followup.send(text,ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
                            except Exception:pass
                            return
                asyncio.create_task(report_result())
            except Exception as error:
                message=engine.redact(error)
                if interaction.response.is_done():await interaction.followup.send(message,ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
                else:await interaction.response.send_message(message,ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
        class ConfirmView(discord.ui.View):
            def __init__(self,user,server,action,data):super().__init__(timeout=60);self.user=user;self.server=server;self.action=action;self.data=data;self.used=False
            @discord.ui.button(label='Bekreft',style=discord.ButtonStyle.danger)
            async def confirm(self,interaction:discord.Interaction,button:discord.ui.Button):
                if interaction.user.id!=self.user or self.used:await interaction.response.send_message('Bekreftelsen er ikke gyldig for deg eller er allerede brukt.',ephemeral=True);return
                self.used=True;button.disabled=True;await dispatch(interaction,self.server,self.action,self.data,True);self.stop()
            @discord.ui.button(label='Avbryt',style=discord.ButtonStyle.secondary)
            async def cancel(self,interaction:discord.Interaction,button:discord.ui.Button):
                if interaction.user.id!=self.user:await interaction.response.send_message('Dette er ikke din bekreftelse.',ephemeral=True);return
                self.used=True;self.stop();await interaction.response.edit_message(content='Avbrutt.',view=None)
        class ControlView(discord.ui.View):
            def __init__(self):super().__init__(timeout=None)
            async def server(self,interaction):
                configured=settings.get('panels',{}).get(str(interaction.message.id))
                if not configured:raise ValueError('Panelet er ikke registrert. Opprett det på nytt med /taldris panel.')
                return configured
            @discord.ui.button(label='Status',custom_id='taldris:status',style=discord.ButtonStyle.secondary)
            async def status(self,i:discord.Interaction,b:discord.ui.Button):await dispatch(i,await self.server(i),'status')
            @discord.ui.button(label='Start',custom_id='taldris:start',style=discord.ButtonStyle.success)
            async def start(self,i:discord.Interaction,b:discord.ui.Button):await dispatch(i,await self.server(i),'start')
            @discord.ui.button(label='Restart om 10 min',custom_id='taldris:restart',style=discord.ButtonStyle.primary)
            async def restart(self,i:discord.Interaction,b:discord.ui.Button):await dispatch(i,await self.server(i),'restart',{'minutes':10})
            @discord.ui.button(label='Avbryt restart',custom_id='taldris:cancel',style=discord.ButtonStyle.secondary)
            async def cancel(self,i:discord.Interaction,b:discord.ui.Button):await dispatch(i,await self.server(i),'cancel_restart')
            @discord.ui.button(label='Backup',custom_id='taldris:backup',style=discord.ButtonStyle.secondary)
            async def backup(self,i:discord.Interaction,b:discord.ui.Button):await dispatch(i,await self.server(i),'backup')
        group=app_commands.Group(name='taldris',description='Taldris Server Studio – drift og administrasjon')
        @group.command(name='servere',description='Vis servere du har lesetilgang til')
        async def servers(interaction:discord.Interaction):
            rows=[]
            for p in engine.manager.state['servers']:
                try:check(interaction,p['id'],'status');rows.append(p['name']+' • `'+p['id']+'` • '+('kjører' if engine.manager.running(p) else 'stoppet'))
                except ValueError:pass
            await interaction.response.send_message('\n'.join(rows)[:1900] or 'Ingen servertilgang.',ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
        @group.command(name='status',description='Status for en server')
        async def status(interaction:discord.Interaction,server:str):await dispatch(interaction,server,'status')
        @group.command(name='start',description='Start en server')
        async def start(interaction:discord.Interaction,server:str):await dispatch(interaction,server,'start')
        @group.command(name='restart',description='Restart med spillervarsel og nedtelling')
        async def restart(interaction:discord.Interaction,server:str,minutter:app_commands.Range[int,1,1440]=10):await dispatch(interaction,server,'restart',{'minutes':minutter})
        @group.command(name='stopp',description='Stopp med spillervarsel og nedtelling')
        async def stop(interaction:discord.Interaction,server:str,minutter:app_commands.Range[int,1,1440]=10):await dispatch(interaction,server,'stop',{'minutes':minutter})
        @group.command(name='spillere',description='Hent spillerliste fra RCon')
        async def players(interaction:discord.Interaction,server:str):await dispatch(interaction,server,'players')
        @group.command(name='melding',description='Send melding til alle spillere')
        async def say(interaction:discord.Interaction,server:str,melding:str):await dispatch(interaction,server,'say',{'message':melding})
        @group.command(name='handling',description='Andre serverhandlinger. Parametere er JSON; se hjelp')
        async def action(interaction:discord.Interaction,server:str,handling:str,parametere:str='{}'):
            try:
                if handling not in PERMISSIONS:raise ValueError('Ukjent handling. Bruk /taldris hjelp.')
                data=json.loads(parametere)
                if not isinstance(data,dict):raise ValueError('Parametere må være et JSON-objekt.')
                await dispatch(interaction,server,handling,data)
            except Exception as error:await interaction.response.send_message(engine.redact(error),ephemeral=True)
        @group.command(name='jobb',description='Se resultat for en jobb på en server du har tilgang til')
        async def job(interaction:discord.Interaction,id:str):
            try:
                job=engine.jobs[id];check(interaction,job['server'],job['action']);text=job.get('error',job.get('result',job['status']));await interaction.response.send_message(str(text)[:1900],ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
            except Exception:await interaction.response.send_message('Jobben finnes ikke eller du mangler tilgang.',ephemeral=True)
        @group.command(name='panel',description='Publiser et kontrollpanel i konfigurert driftskanal')
        async def panel(interaction:discord.Interaction,server:str):
            try:
                p=engine.profile(server);check(interaction,p['id'],'start')
                if str(interaction.channel_id)!=str(settings.get('channel_id','')):raise ValueError('Bruk den konfigurerte driftskanalen.')
                await interaction.response.send_message('Oppretter kontrollpanel.',ephemeral=True);message=await interaction.channel.send('**'+p['name']+'**\n'+('Prosess kjører' if engine.manager.running(p) else 'Stoppet'),view=ControlView(),allowed_mentions=discord.AllowedMentions.none());settings.setdefault('panels',{})[str(message.id)]=p['id'];engine.manager.save()
            except Exception as error:
                if not interaction.response.is_done():await interaction.response.send_message(engine.redact(error),ephemeral=True)
        @group.command(name='fil',description='Hent konfigurasjonsfil privat (kun eier)')
        async def file(interaction:discord.Interaction,server:str,sti:str):
            try:
                p=engine.profile(server);check(interaction,p['id'],'document_save');await interaction.response.defer(ephemeral=True)
                from config_documents import Document,digest
                doc=Document(p,sti,engine.home);await interaction.followup.send('Fil: '+sti+'\nSHA: `'+digest(doc.original)+'`',file=discord.File(io.BytesIO(doc.text.encode()),filename=Path(sti).name),ephemeral=True)
            except Exception as error:
                if interaction.response.is_done():await interaction.followup.send(engine.redact(error),ephemeral=True)
                else:await interaction.response.send_message(engine.redact(error),ephemeral=True)
        @group.command(name='fillagre',description='Last opp redigert konfigurasjon med SHA og bekreftelse (kun eier)')
        async def file_save(interaction:discord.Interaction,server:str,sti:str,sha:str,fil:discord.Attachment):
            try:
                p=engine.profile(server);check(interaction,p['id'],'document_save')
                if fil.size>8*1024**2:raise ValueError('Maks 8 MB.')
                await interaction.response.defer(ephemeral=True)
                raw=await fil.read();data=dict(file=sti,base=sha,text=raw.decode('utf-8-sig'))
                # Do not echo secret file contents into the confirmation message.
                view=ConfirmView(interaction.user.id,p['id'],'document_save',data);await interaction.followup.send('Bekreft lagring av **'+sti+'** med backup. Eksisterende SHA kontrolleres før skriving.',view=view,ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
            except Exception as error:
                if interaction.response.is_done():await interaction.followup.send(engine.redact(error),ephemeral=True)
                else:await interaction.response.send_message(engine.redact(error),ephemeral=True)
        @group.command(name='hjelp',description='Vis støttede handlinger og parameter-eksempler')
        async def help_command(interaction:discord.Interaction):
            if str(interaction.guild_id)!=str(settings['guild_id']):await interaction.response.send_message('Ingen tilgang.',ephemeral=True);return
            await interaction.response.send_message('Handlinger: '+', '.join(PERMISSIONS)+'\nEksempler:\n`kick`: {"player":3,"reason":"Regelbrudd"}\n`ban`: {"player":3,"minutes":60,"reason":"Regelbrudd"}\n`steam`: {"kind":"mods"}\n`mod_add`: {"id":"123456789","mode":"client"}\n`mod_mode`: {"index":0,"mode":"both"}\n`restore`: {"archive":"fil.zip"}\n`clone`: {"root":"D:/DayZTest","name":"Test"}\n`list_add`: {"list":"whitelist.txt","uid":"SPILLER-ID"}\nAlle indekser begynner på 0. Eier styrer rettighetene i Windows-panelet.',ephemeral=True)
        async def notifications():
            cursor=0;last_panels=0
            while not self.client.is_closed():
                await asyncio.sleep(10)
                try:
                    channel=self.client.get_channel(int(settings.get('channel_id') or 0))
                    if not channel or str(getattr(channel.guild,'id',''))!=str(settings['guild_id']):continue
                    events=engine.snapshot(cursor)['events'];cursor=engine.event_id
                    important=[e['text'] for e in events if any(word in e['text'].casefold() for word in ('feil','krasj','avsluttet','fullført','gjenstart','restart','startet'))]
                    if important:await channel.send('\n'.join(important[-8:])[:1900],allowed_mentions=discord.AllowedMentions.none())
                    if time.time()-last_panels>60:
                        last_panels=time.time()
                        for message_id,server in list(settings.get('panels',{}).items()):
                            p=engine.profile(server);message=await channel.fetch_message(int(message_id));await message.edit(content='**'+p['name']+'**\n'+('Prosess kjører' if engine.manager.running(p) else 'Stoppet')+' • vedlikehold: '+p.get('maintenance_state','idle'),view=ControlView())
                except Exception as error:engine.log('Discord-varsling: '+str(error))
        async def server_autocomplete(interaction:discord.Interaction,current:str):
            result=[]
            for p in engine.manager.state['servers']:
                try:
                    check(interaction,p['id'],'status')
                    if current.casefold() in (p['name']+' '+p['id']).casefold():result.append(app_commands.Choice(name=p['name'][:100],value=p['id']))
                except ValueError:pass
            return result[:25]
        for command in group.commands:
            if any(parameter.name=='server' for parameter in command.parameters):command.autocomplete('server')(server_autocomplete)
        intents=discord.Intents.none();intents.guilds=True
        async with aiohttp.TCPConnector(ssl=tls_context()) as connector:
            self.client=Client(intents=intents,connector=connector,allowed_mentions=discord.AllowedMentions.none())
            await self.client.start(token)
