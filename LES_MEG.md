# Taldris Server Studio 0.5.1

Windows-program for å installere og administrere en lokal DayZ Dedicated Server eller en Windows-VPS. Nytt: SteamCMD-nedlasting, integrert SteamCMD-konsoll, oppstartsveiviser og direkte Steam Workshop-søk.

## Start programmet

1. Installer Python 3.12 eller nyere fra https://www.python.org/downloads/windows/.
2. Pakk hele ZIP-filen til en egen mappe.
3. Kjør START.bat. Første oppstart oppretter et lokalt Python-miljø og laster ned PySide6. Internett er nødvendig første gang.
4. Programmet åpnes som et eget skrivebordsvindu.

BUILD_EXE.bat bygger en Windows-EXE på maskinen din. Resultatet er `dist\TaldrisServerStudio.exe`. Ingen ferdigbygd Windows-EXE følger med; Windows-bygging kan ikke testes i dette Linux-miljøet.

## GitHub og programoppdateringer (nytt i 0.5)

Dev/stable-arbeidsflyter er klargjort, og Programoppdatering lar deg velge kanal, sjekke nye versjoner og laste ned en kontrollert Windows-pakke. Repo: https://github.com/Krussedull86/TaldrisServerStudio. Les GITHUB_OPPSETT.md for detaljer. Automatisk installasjon av selve programmet er ikke implementert.

## Lasting: mod, servermod eller begge

Velg en mod i Modbibliotek → Endre valgt mod / mod, servermod eller begge. Tre valg: **Mod (-mod)**, **Servermod (-serverMod)** eller **Begge (-mod + -serverMod)**. Dette støttes for lokale mods og Workshop-mods. Begge bruker samme mappesti i begge oppstartsargumentene; modden lastes bare ned/installert én gang. Lastrekkefølgen beholdes innenfor hver liste. Gamle profiler beholder sin tidligere lastetype.

## Lokale mods og egne utviklermods (nytt i 0.4)

1. Åpne **Modbibliotek → Bla gjennom lokale @mods**.
2. Velg mappen som inneholder moddene, for eksempel `DayZ/!Workshop`, en servermappe eller din egen byggmappe. Du kan også velge én @mod direkte.
3. Trykk **Finn @mods**. Kryss av for **Søk også i undermapper** hvis du har flere prosjekter under en overordnet mappe.
4. Velg moddene som skal brukes, og velg **Klient + server** eller **Kun server** for importen. **Begge** legger modden i både `-mod` og `-serverMod`.
5. Trykk **Importer valgte**. Endre rekkefølge og aktivering i modbiblioteket. Lastetype kan endres per mod med knappen for klient-/server-only.

Programmet finner bare mapper med `@` først i navnet. Filer med @navn og andre vanlige mapper importeres ikke. Listen viser full lokal sti og antall PBO-filer og offentlige signeringsnøkler. Samme fysiske mappe legges ikke til flere ganger. Mappekoblinger under Steam !Workshop støttes også.

**Last direkte fra utviklingsmappen:** Lokale importerte mods får tom Workshop-ID og en absolutt lokal sti i oppstartskommandoen. PBO-filene kopieres eller endres ikke av panelet. Workshop-oppdateringer berører ikke disse moddene, selv om de inneholder meta.cpp fra en tidligere publisering. Bygg PBO-filene til den samme mappen og start serveren på nytt for å bruke den nye versjonen. Dette er ikke hot reload og omfatter ikke kjøring av upakkede kildeskript.

Mapper uten en pakket PBO i Addons vises også. Du kan velge dem, men de legges inn som inaktive. Bygg modden til `@DinMod/Addons`, aktiver den i modbiblioteket og start på nytt. Oppstarten stoppes med en forklaring hvis en aktiv lokal mod mangler eller ikke har PBO-filer.

Offentlige `.bikey`-filer i moddens Keys-mappe oppdateres i serverens keys-mappe ved oppstart. Signaturkrav endres ikke automatisk. Mods som brukes av både server og klient må også være lastet på klienten. **Åpne valgt modmappe** åpner mappen i Utforsker. Fjerner du modden fra listen, slettes ingen kildefiler.

## Fra tom mappe til server

Åpne **Kom i gang**:

1. Oppgi servernavn, en egen servermappe og SteamCMD-mappe. Standardforslag er klare i programmet.
2. Velg **Anonym** eller **Steam-konto**. Anonym er standard for nye profiler.
3. Klikk **Last ned SteamCMD**, eller gå rett til installasjon: manglende SteamCMD lastes da ned automatisk fra Valves offisielle HTTPS-adresse.
4. Velg spillerplasser og mission. Chernarus er standard. Enoch/Sakhal og andre missions må faktisk finnes i servermappen og kan kreve ekstra tilgang/data.
5. Klikk **Installer og klargjør**. Programmet installerer/validerer DayZ Server (Steam App 223350), laster ned aktive Workshop-mods, installerer bekreftede modnedlastinger, kopierer bikey-filer og oppretter en konfigurasjon hvis den mangler.
6. Hvis **Start serveren etter vellykket installasjon** er valgt, starter programmet serverprosessen etter at alle nødvendige trinn har lykkes.
7. Se **Logger → Nyeste RPT** for å kontrollere at serveren er klar. «Prosess kjører» er ikke en nettverkstest.

Eksisterende serverkonfigurasjon overskrives ikke av veiviseren. Navn, spillerplasser og kart i veiviseren brukes ved opprettelse av en ny konfigurasjon. Bruk konfigurasjonseditoren for å endre en eksisterende server. Knappen «Start eksisterende server» bruker sist lagrede profil.

## Viktig om anonym Steam-tilgang

Anonym innlogging i SteamCMD gir ikke automatisk rettigheter til DayZ Server eller Workshop-filer. Steam/Bohemia bestemmer tilgangen. Bohemias veiledning bruker en Steam-konto ved installasjon av DayZ Server.

Programmet lar deg forsøke anonymt. Hvis Steam avviser tilgang, viser det feilmeldingen og starter ikke serveren. Velg deretter **Steam-konto**, oppgi brukernavn og prøv igjen. Workshop krever ofte en konto med nødvendig DayZ-tilgang. Programmet omgår ikke tilgangskrav.

**Test innlogging** tester bare innloggingen i den SteamCMD-økten. Det bekrefter ikke nedlastingsrettigheter. Hver jobb starter en ny SteamCMD-prosess med den lagrede innloggingsmetoden; SteamCMD kan gjenbruke sine egne bufrede innloggingsdata.

## Rettet i 0.5.1: SteamCMD som bare viste startteksten

Windows kjører nå SteamCMD i en ekte pseudoterminal (ConPTY) i stedet for bare å lese vanlig stdout. Dette fanger konsollmeldinger, innloggingsspørsmål og nedlastingsstatus som ellers kan bli borte. En egen statuslinje viser gjeldende fase, medgått tid og hvor lenge det er siden siste melding. Prosent leses også fra Steams format uten prosenttegn. Den bevegelige linjen alene betyr bare at jobben fortsatt er aktiv; den er ikke bevis på nedlasting.

**Følg siste melding** kan slås av for å lese tidligere meldinger. **Åpne SteamCMD-loggmappe** åpner Steams egne logger, blant annet content_log.txt. Eldre programutgaver viser ikke automatisk utdata fra en SteamCMD-jobb startet av en ny utgave; avslutt/avbryt den gamle jobben før du starter installasjonen igjen etter programbytte.

## SteamCMD-konsoll i programmet

Fanen **Kom i gang → SteamCMD-konsoll** viser sanntidsutdata og fremdrift når Steam rapporterer en prosent.

Når Steam ber om passord eller Steam Guard, skriv i det skjulte inputfeltet og trykk **Send til SteamCMD**. Programmet legger ikke passord/Guard-koder i profilfilen eller aktivitetsloggen, og skjuler innsendte verdier i terminalvisningen. SteamCMD kan selv lagre innloggingsdata i SteamCMD-mappen. Konsollen er input til SteamCMD, ikke en PowerShell-terminal.

**Avbryt jobb** stopper SteamCMD. Ufullstendige filer blir liggende og kan lastes ned på nytt. Ingen automatisk serverstart eller modinstallasjon utføres ved avbrutt jobb eller manglende bekreftelse på at hele nedlastingsjobben lyktes.

## Steam Workshop

Åpne **Steam Workshop**:

- Søk direkte på Steam med navn. Bruk Forrige/Neste for flere resultater. Søk bruker Steams offentlige nettside og detalj-API, uten tredjeparts serverkatalog og uten API-nøkkel.
- Se navn, Workshop-ID, størrelse, sist oppdatert og beskrivelse.
- Legg valgt mod til serverprofilen med en knapp eller dobbeltklikk.
- Lim inn Workshop-ID eller en steamcommunity.com-lenke for å hente en bestemt mod.
- Importer en offentlig Workshop-samling. Programmet viser innholdet før import. Høyst 100 direkte elementer; undersamlinger støttes ikke.
- **Last ned og installer aktive mods** henter filene med SteamCMD, finner den bekreftede nedlastingsmappen og installerer dem i servermappen.
- **Sjekk modoppdateringer** sammenligner Steams oppdateringstid med sist registrerte installasjon. Mods som ikke er installert gjennom 0.3 har ukjent lokal versjon.

Importerte modmapper heter `@WorkshopID` for å unngå navnekollisjoner. Modnavnet vises i modbiblioteket. Egendefinerte mappenavn kan legges til manuelt via Modbibliotek. Eksisterende samme Workshop-ID legges ikke til to ganger.

Kontroller avhengigheter, lastrekkefølge og eventuelle lisens-/server-only-regler på moddens Workshop-side. Disse løses ikke automatisk. CF må plasseres før mods som trenger CF. Alle nye Workshop-importer settes til klient + server; bruk «Endre valgt modmappe / klient- eller server-only» hvis modforfatteren krever server-only. Import til profilen er ikke et abonnement på Steam-kontoen din.

Modmapper erstattes via staging og bikey-filer kopieres til keys. Ta kopi av lokale modendringer først. Gamle bikey-filer slettes ikke automatisk. Nedlasting og installasjon er ikke én atomisk transaksjon for alle mods: ved feil kan noen tidligere mods være installert, men serveren starter ikke automatisk.

Offentlig Workshop-søk er avhengig av Steams nettsideformat. Hvis Steam endrer formatet eller blokkerer forespørselen, viser programmet dette; innlegging via ID/lenke kan fortsatt fungere.

## Automatisk oppdatering

Velg intervall under **Automatisering**. Panelet må være åpent. Jobben kjører bare mens profilen er stoppet. Den oppdaterer serveren, laster ned aktive Workshop-mods og installerer dem etter bekreftet nedlasting. Ingen automatisk tvangsstopp eller omstart av en kjørende server. Serveren startes ikke automatisk etter denne vedlikeholdsjobben. Steam Guard kan kreve innspill i konsollen.

## Nettverk og serverdrift

Dette programmet leier ikke en VPS og endrer ikke router eller brannmur automatisk. For offentlig tilgang må maskinen ha riktig nettverkstilgang og porter konfigurert etter DayZ-dokumentasjonen. Oppstartsveiviseren velger ikke query-port automatisk; ved flere servere må konfigurasjon, spill-/query-porter og mapper være forskjellige.

Panelet administrerer kun prosesser det selv startet i gjeldende økt. Eksternt startede servere oppdages ikke. Kontroller at ingen eksterne prosesser bruker samme mapper før oppdatering eller backup. Panelet sperrer samme aktive mappe og spillport mellom sine egne profiler. Lukkes panelet mens serveren kjører, fortsetter serverprosessen, men den kan ikke tas over automatisk neste gang.

Tvungen stopp kan miste ulagrede data. Bruk DayZ sin graceful shutdown når mulig. RCon/graceful restart er ikke implementert i denne versjonen.

## Kart, logger og backup

- Eget kvadratisk kartbilde med nord opp. Scroll for zoom, dra for panorering, dobbeltklikk for markør. Eksporter markører som JSON. Ingen live spillerposisjoner.
- Loggleser viser siste 100 KB av valgt fil og oppdateres når filen endres.
- Backup tar med serverkonfigurasjon, profiles, mpmissions og battleye. Krever at serveren er stoppet. Arkivene kan inneholde passord og spillerdata; oppbevar dem privat.
- Gjenoppretting er manuell: stopp serveren, pakk ut arkivet i en tom mappe, kontroller innholdet og kopier til servermappen.
- Oppsett og backup lagres i `%LOCALAPPDATA%\TaldrisServerStudio`. Ingen automatisk sletting av backup.

## Testet og ikke testet

Automatiserte tester dekker lokal @skanning, direkte modstier, kildebeskyttelse, nøkkelkopiering, duplikater og ubygde mods, samt backend, nedlastingsarkiv, beskyttelse mot overskriving, anonym/konto-kommandoer, feiltolking, samlingsrekkefølge, Workshop-søkformat, GUI, passordskjuling og hele klargjøringsflyten med en simulert SteamCMD-prosess.

Direkte nettverkstester har bekreftet nedlasting av offisiell SteamCMD-bootstrap fra Valve, CF-metadata fra Steam API og faktisk Workshop-søk. Windows-SteamCMD-innlogging, nedlasting av hele DayZ Server, Steam Guard og faktisk spillbar serverdrift er ikke testet her. De krever Windows og eventuell Steam-tilgang.

Ikke implementert: BattlEye RCon, kick/ban, live spillerposisjoner, CFTools API, Discord, Windows-tjeneste, eksternt hostingpanel, varslet omstart eller automatisk oppdatering av selve kontrollpanelet.

Dokumentasjon:
- https://developer.valvesoftware.com/wiki/SteamCMD
- https://community.bistudio.com/wiki/DayZ:Hosting_a_Linux_Server
- https://community.bistudio.com/wiki/DayZ:Server_Configuration
- https://partner.steamgames.com/doc/webapi/ISteamRemoteStorage
