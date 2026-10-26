# Taldris Server Studio 0.7 – drift, Discord og editorer

## Første oppstart fra 0.6 eller eldre

1. Last ned Windows-pakken fra GitHub sin dev-utgave og pakk ut i en ny programmappe.
2. Lukk det gamle kontrollpanelet. Ikke stopp DayZ-serveren bare for å bytte panel.
3. Start den nye EXE-en. Den starter en egen bakgrunnsagent, som gjenbruker bekreftede serverprosesser. Samme EXE/config/profiles/port må kunne bekreftes.
4. Åpne **Discord / tjeneste → Installer / oppdater Windows-tjeneste** hvis driften skal fortsette etter Windows-/RDP-avlogging og starte med Windows. Godta Windows-administratorforespørselen.

En vanlig agentprosess fortsetter når vinduet lukkes. Avlogging kan avslutte brukerprosesser; installer tjenesten for den bruken. Tjenesten heter `TaldrisServerStudioAgent`. Den bruker samme datamappe som panelet, med eget prosessregister, logger, backup og innstillinger. Servere som sist var ønsket kjørende kan startes ved agentoppstart; feilende vedlikehold startes ikke forbi feilen. SCM gjenstarter agenten ved krasj.

Tjenesten kjører som LocalSystem. Eierne og lokale administratorer må derfor være betrodde administratorer av denne maskinen. Bruk fysiske/lokale stier: brukerens mappede nettverksstasjoner er normalt ikke tilgjengelige for en Windows-tjeneste. Agenttilgangen er begrenset til loopback med en tilfeldig nøkkel og Windows-ACL. Discord-token lagres med maskin-DPAPI og samme tilgangsbegrensning. Ingen skyserver kreves.

## Discord-oppsett

Du trenger din egen bot fra https://discord.com/developers/applications .

1. Opprett en applikasjon og en bot. Kopier bot-tokenet til passordfeltet i programmet. Ikke legg det i GitHub eller en Discord-kanal.
2. Inviter boten til Discord-serveren med scopene **bot** og **applications.commands**.
3. Gi boten tilgang til den valgte driftskanalen: View Channel, Send Messages, Read Message History og Attach Files. Administrator er ikke nødvendig. Boten bruker guild-informasjon; Message Content og Members privileged intents er ikke nødvendige.
4. Slå på Developer Mode i Discord og kopier Discord-serverens ID, driftskanalens ID og din egen bruker-ID til oppsettet.
5. Legg inn minst én eier-ID. Bruk komma mellom flere eiere. Eierne får full kontroll innen den konfigurerte Discord-serveren.
6. Roller kan legges inn per rettighet. `read` leser status/spillere/mods/logger, `control` styrer start/stopp/restart/lås, `moderate` styrer meldinger/kick/ban, `maintenance` styrer oppdatering/backup, og `config` styrer modliste/driftsinnstillinger/tilgangslister. Restore, filtilgang, kloning, tvungen stopp og programoppdatering er eierhandlinger.
7. Valgfrie rettigheter per DayZ-server-ID erstatter de globale rollene for den serveren. Manglende rettighet gir avslag. Discord sin generelle Administrator-rolle gir ikke automatisk bot-tilgang.
8. Klikk **Lagre og koble Discord**. Hendelsesstrømmen viser tilkoblingsfeil eller at boten er tilkoblet.

Eksempel på globale roller:

```json
{
  "read": ["ROLLE_ID_FOR_LESING"],
  "control": ["ROLLE_ID_FOR_DRIFT"],
  "moderate": ["ROLLE_ID_FOR_MODERATORER"],
  "maintenance": ["ROLLE_ID_FOR_VEDLIKEHOLD"],
  "config": ["ROLLE_ID_FOR_OPPSETT"]
}
```

Bytt eksempeltekstene med de faktiske numeriske rolle-ID-ene. Bruk en privat driftskanal: hendelsesvarsler er ment for serverstaben.

### Kommandoer

- `/taldris servere` viser servere du har lesetilgang til, med ID og prosessstatus.
- `/taldris status server` viser status for valgt server. Serverfeltet har forslag.
- `/taldris panel server` publiserer knapper i den konfigurerte driftskanalen. Status oppdateres omtrent hvert minutt. Knappene fungerer igjen etter bot-omstart.
- `/taldris start server`, `/taldris restart server minutter` og `/taldris stopp server minutter` styrer serveren. Restart/stopp bruker RCon-varsler og en avbrytbar nedtelling.
- `/taldris spillere server` og `/taldris melding server melding` bruker RCon.
- `/taldris handling server handling parametere` dekker øvrige handlinger. Parametere er et JSON-objekt. `/taldris hjelp` viser eksempler.
- `/taldris jobb id` viser et jobbresultat. Raske resultater sendes også privat når jobben fullfører; lange resultater kan komme som tekstvedlegg.
- `/taldris fil server sti` sender en konfigurasjonsfil privat til eieren, med SHA av nåværende innhold.
- `/taldris fillagre server sti sha fil` laster opp endret UTF-8-konfigurasjon. Eierbekreftelse, innholdskontroll, SHA-kontroll og backup skjer før skriving. Filstien må være inne i den valgte servermappen.

Handlinger omfatter `mods`, `backups`, `files`, `logs`, `file_history`, `file_restore`, `schedule_set`, `players`, `bans`, `lock`, `unlock`, `say`, `kick`, `ban`, `unban`, `backup`, `restore`, `rollback_mods`, `maintenance`, `steam`, `check_mods`, `workshop_search`, `mod_add`, `mod_collection`, `mod_remove`, `mod_mode`, `mod_move`, `local_mod_scan`, `local_mod_add`, `list_add`, `clone`, `force_stop`, `cancel_restart` og `program_prepare`.

Eksempler for `parametere`:

```json
{"minutes": 10}
```

```json
{"player": 3, "minutes": 60, "reason": "Regelbrudd"}
```

```json
{"kind": "mods"}
```

```json
{"id": "123456789", "mode": "both"}
```

```json
{"scheduled_restart": true, "restart_mode": "clock", "restart_times": "00:00, 06:00, 12:00, 18:00"}
```

Indekser i modlisten begynner på 0. `client` betyr `-mod`, `server` betyr `-serverMod`, og `both` betyr begge. Modfiler byttes bare mens serveren er stoppet. Lokale utviklermods erstattes ikke med Workshop-nedlastinger.

## RCon og serverstatus

Velg den aktive `BEServer_x64.cfg` under **RCon og spillere**. Filen trenger `RConPort` og `RConPassword`. RCon-porten må være separat fra spill- og query-portene. Passordet leses på servermaskinen ved tilkobling. En tom eller feil port/passord gir en feil; programmet hevder ikke at en kommando er utført uten svar. Timeout på shutdown behandles som ubekreftet: panelet følger prosessen og bruker ikke automatisk tvungen stopp.

RCon gir spillerliste, kick, tidsbestemt/permanent ban, unban, melding til alle, lås og opplås. Spiller-ID-er kan endre seg; hent fersk spillerliste før kick/ban. Ved ban/unban skrives BattlEye-banlisten til disk.

Status skiller mellom en kjørende prosess og svar fra Steam query. Query-svar er en nettverkskontroll, ikke en test av at en spiller faktisk kan fullføre innlogging. Oppetid, RAM, CPU og ledig disk vises i driftsoversikten. CPU kan være over 100 % for prosesser som bruker flere kjerner. Query-svar med splitting/komprimering er foreløpig ikke dekodet; da kan prosessen kjøre selv om status ikke viser query-svar.

## Konfigurasjonssenter

**Konfigurasjon → Finn serverfiler** finner UTF-8 CFG, JSON, XML og TXT inne i servermappen, også missionfiler og genererte modkonfigurasjoner under profiles. Store cache-/spilldata-/@modmapper hoppes over ved søket. Filer over 8 MB er ikke åpnet av editoren.

- **Visuell editor** viser scalar CFG-felt, hele JSON-strukturen og XML-elementer/attributter. Kjente brytere har avhuking. Passord maskeres i den visuelle visningen; rå tekst viser originalfilen.
- Høyreklikk et XML-element for nytt barneelement/attributt, duplisering eller sletting. Endringene er fortsatt bare i editoren til du lagrer.
- **Types / loot** har søk/filter, nominal/min/lifetime/restock/quantmin/quantmax/cost og category/usage/value/tag. Flere navn skilles med semikolon. Kategorier har redigerbare forslag; du kan skrive egne modverdier.
- **Importer types** lar deg beholde eller erstatte eksisterende klasser med samme navn. Ukjente XML-felt, attributter og kommentarer beholdes ved strukturerte types-endringer. Masseendring bruker valgte rader og en multiplikator. Mengde -1 beholdes ved skalering.
- Flagg og øvrige types-detaljer er tilgjengelige i den visuelle XML-strukturen. Nye eller sjeldne modinnstillinger kan alltid redigeres i rå tekst.
- **Rå tekst** gir tilgang til hele filen. XML/JSON/CFG kontrolleres før lagring; det er ingen komplett DayZ-/modspesifikk schema-validator for alle mulige filer.
- **Endringer** viser forskjellen fra originalen. **Kontroller og lagre** viser en gjennomgang før det skrives.
- **Historikk** åpner en tidligere versjon i editoren; gjenopprettingen skrives først ved eksplisitt lagring.
- Filer lagres gjennom agenten mens serveren er stoppet. Endringer fra en annen klient avvises, slik at de ikke overskrives stille. En backup av opprinnelige bytes lagres først.

Dette dekker blant annet serverDZ.cfg, cfggameplay.json, types.xml, events.xml, globals.xml, economy.xml, cfgeconomycore.xml, cfgspawnabletypes.xml, cfgrandompresets.xml, messages.xml, spawn-/territoriefiler, BattlEye-konfigurasjon og støttede modfiler. Generiske felt er ikke et løfte om at enhver modinnstilling kan forklares automatisk.

## Kartverksted

Velg kartbilde og korrekt kartstørrelse per server. Bildet strekkes til kartets fulle X/Z-utstrekning, med nord øverst, X mot høyre og Z oppover.

**+ XML-lag** åpner mission-/spawn-/territoriefiler som har elementer med `x` og `z`. Flere lag kan vises/skjules samtidig. Velg aktivt lag og gruppe. Dra punkter for å flytte dem, dobbeltklikk for å legge til fra samme punktmal, eller skriv inn nøyaktige koordinater. Y, rotasjon og andre attributter beholdes. Radius som allerede ligger i `r` eller `radius` kan vises som sirkler.

**Rediger valgt punkt** lar deg endre X/Z og eksisterende radius i meter. Radiussirkelen følger punktet ved flytting. **Angre** og **Gjør om** holder inntil 50 endringer per lag i den åpne økten, også når du bytter server. Endringene skrives først til serverfilen når du lagrer.

**Kontroller og lagre lag** viser filforskjell og lager backup. Kartet beregner ikke terrenghøyde og endrer ikke Y automatisk. Det viser konfigurerte punkter, ikke faktiske loot-spawns eller live spillerposisjoner. Vilkårlige JSON-koordinater, polygonsoneverktøy, automatisk uthenting av kartbilder og live posisjoner fra en egen servermod er videre arbeid.

## Backup, rollback og testserver

- Gjenoppretting velger arkiv fra serverens egen backupmappe, tar en ny backup først og bytter lagringsmapper som hele mapper. En journal gjør avbrutte bytter reparerbare ved neste agentoppstart. Serveren startes ikke automatisk etter manuell gjenoppretting.
- Modinstallasjon beholder én `.previous`-versjon. Tilbakerulling bytter til denne versjonen mens serveren er stoppet. Dette kan ikke rulle tilbake Workshop-klienten hos spillerne, og en eldre mod kan være uforenlig med nyere persistence.
- Kloning til testserver bruker en ny mappe og foreslår egne spill-/query-porter. Standard `storage_*`, logger og tidligere modversjoner hoppes over. Kopierte BattlEye-filer får ny RCon-port og nytt tilfeldig passord. Lokale modstier kan fortsatt peke til samme utviklerkilde; de kopieres ikke om til Workshop-mods.

## Programoppdatering

Manuell oppdateringssjekk i Windows-panelet klargjør en nyere utgave med SHA-256-kontroll. Panelet starter på nytt; DayZ beholdes. Agenten oppgraderes separat og overtar bekreftede prosesser. Pågående jobber og ulagrede editorendringer må være ferdige før panelbytte. Discord-handlingen `program_prepare` klargjør og oppgraderer agenten når jobbene er ferdig, også uten åpent Windows-panel. Et tilkoblet panel bytter utgave, og neste paneloppstart bruker den aktive installerte utgaven. Windows-tjenesten beholder DayZ-prosessene når agenten byttes. Eierbekreftelse kreves i Discord.

## Verifisering og begrensninger

Automatiske tester bruker midlertidige serverfiler, en lokal RCon-testserver, den lokale agent-API-en og Discord-kommandoregistrering uten ekte bot-tilkobling. GitHub bygger Windows-EXE og starter/stopper den ferdige agenten i en tom testmappe. Ekte Discord-rolleoppsett, Steam Guard, SCM-installasjon på din Windows-maskin og DayZ-spillerinnlogging må fortsatt testes med ditt oppsett. Stable publiseres ikke automatisk.

Primærkilder brukt i implementasjonen:
- https://www.battleye.com/downloads/BERConProtocol.txt
- https://www.battleye.com/support/documentation/
- https://discord.com/developers/docs/interactions/receiving-and-responding
- https://community.bistudio.com/wiki/DayZ:Central_Economy_Configuration
- https://community.bistudio.com/wiki/DayZ:Central_Economy_mission_files_modding
- https://mhammond.github.io/pywin32/servicemanager.html
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html


## Installasjon og oppgradering (0.7.1)

Last ned **TaldrisServerStudio-Setup.exe** fra en GitHub-utgave og kjør den. Installasjonen gjelder Windows-brukeren og trenger ikke administrator. Den lager snarveier på skrivebordet og i Start-menyen, og en oppføring under Windows sine installerte apper. Vanlig EXE fra ZIP tilbyr installasjon eller portabel kjøring ved første start. Du kan også velge **Programoppdatering → Installer programmet på denne PC-en** senere.

Programstarteren ligger i `%LOCALAPPDATA%/Programs/TaldrisServerStudio`. Innstillinger og egne programversjoner ligger fortsatt i datamappen `%LOCALAPPDATA%/TaldrisServerStudio` (eller din valgte `--home`). Servermappene flyttes ikke. Snarveien følger aktiv versjon etter oppgradering. Velg dev/stable og **Lagre og sjekk** for å laste ned, kontrollere og installere en nyere utgave. Programvinduet byttes; DayZ-prosessene stoppes ikke. Windows-tjenesten installeres fortsatt separat fra Discord/tjeneste-siden.

Avinstallasjon fjerner programstarter, snarveier og Windows-oppføringen. Den stopper ikke agent, tjeneste eller DayZ og beholder datamappen, versjonsfiler og alle serverdata. Vil du avslutte driften, stopp serverne og fjern tjenesten separat før du sletter data.

## Lokal test uten krav om Steam Query

Stopp valgt server. Åpne **Innstillinger**, huk av **Lokal test – start uten krav om Steam Query**, og lagre. Programmet tillater da at `steamQueryPort` mangler, sender ingen A2S-query og viser prosessstatus i stedet for query-status. Automatisk brannmurregel inkluderer ikke en ekstra query-port i denne modusen. Koble direkte til `127.0.0.1:<spillport>` fra samme maskin.

Dette slår av programmets query-krav og overvåking. Det deaktiverer ikke Steam-autentisering, BattlEye eller DayZ-motorens eventuelle interne standardport, og gjør ikke serveren privat eller bundet til localhost. Bruk brannmur/nettverksoppsett hvis tilgangen må begrenses. Konfigurasjonsfilen endres ikke av avhukingen. Fjern avhukingen for vanlig serverdrift med kontrollert query-port.


## Importer en eksisterende server fra BAT / CMD (0.7.2)

Velg **Kom i gang** eller **Innstillinger → Importer eksisterende server fra BAT / CMD**. Velg startskriptet, og velg riktig serverstart hvis filen inneholder flere. Forhåndsvisningen lar deg rette servermappe, konfigurasjon, profiles, spillport, ekstra startvalg og lokale modstier. Du kan velge `mod`, `serverMod` eller begge for hver mod, og deaktivere mods som mangler. Velg ny profil eller en eksisterende profil som skal oppdateres, og bekreft importen.

Filen leses uten å kjøres. Vanlige `set`-variabler, `%~dp0`, `%cd%`, `cd /d`, `start` med tittel og `/D`, direkte EXE-start, `call` direkte til EXE og fortsettelse med `^` støttes. Uløste variabler, ukjente startvalg og skript som krever dynamisk tolkning vises som merknader. Betingelser, eksterne skript, pipe/omdirigering, `&&`, forsinket `!variabel!`-utvidelse og batchens stopp-/restartløkker overtas ikke. Bruk Automatisering til planlagt drift etter import.

Alle mods fra BAT registreres som **lokale kilder**, også mapper med Workshop-ID i navnet. Dermed lastes de ikke ned eller overskrives automatisk. En mod i begge lastelistene importeres én gang med lastemåten begge. Importen flytter ikke filer, endrer ikke CFG eller verdensdata og starter ikke serveren. EXE og konfigurasjon må finnes i valgt servermappe; profiles/CFG utenfor servermappen må tilpasses manuelt. Stopp serveren og vent til jobber er ferdige før en eksisterende profil oppdateres.

Ekstra startvalg finnes også under Innstillinger. Støttede valg er `-name`, `-cpuCount`, `-maxMem`, `-limitFPS`, `-BEpath`, `-filePatching`, `-netlog`, `-doSimulate`, `-noSound`, `-noSplash`, `-noPause` og `-scrAllowFileWrite`. Øvrige valg rapporteres i forhåndsvisningen i stedet for å legges til ubemerket. Mods, konfigurasjon, port og profiles styres av egne felt. Standardvalgene `-dologs`, `-adminlog` og `-freezecheck` legges fortsatt til av programmet.


## Flere servere fra samme servermappe (0.7.3)

Profiler kan dele DayZServer_x64.exe og modfiler. Samtidige instanser må ha forskjellige spill-/query-porter og separate profiles-mapper. De må også bruke ulike missionmapper eller ulike `instanceId` i hver sin CFG, slik at de ikke skriver til samme `storage_<instanceId>`. Programmet gir nå en konkret konfliktmelding i stedet for å avvise selve servermappen. Én kjørende prosess registreres bare på én profil.

Native restartplaner skriver til missionens `db/messages.xml`, så uavhengige native planer krever separate missionmapper. Filoppdateringer og backup av den delte servermappen utsettes mens en annen server bruker den. En vanlig restart kan starte serveren igjen uten slikt filvedlikehold. Ingen annen server stoppes automatisk.

**Kom i gang → Mission / kart → Lagre kartvalg til CFG** skriver valgt navn direkte til den eksisterende CFG-filen med backup. Listen henter kart fra `mpmissions` og gjeldende CFG; egne navn kan fortsatt skrives inn. `dayzOffline.nasdara` er også med i standardlisten. BAT-importen leser mission fra CFG i stedet for å lagre et standardkart. Kartvalg kan lagres til en egen CFG i rotmappen mens en annen server bruker samme installasjon, men aldri til en CFG som brukes av en aktiv profil. Spillport og profiles endres under Innstillinger; `instanceId` endres i konfigurasjonseditoren. Ingen verdier endres automatisk til en ny verden.
