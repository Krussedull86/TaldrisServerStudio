# GitHub: dev og stable

Repo: https://github.com/Krussedull86/TaldrisServerStudio

Utvikling skjer på dev. Main inneholder publiseringsoppsettet. Stable publiseres bare etter uttrykkelig godkjenning.

## Samme hovedregel som YSK

- Push til `dev`: Linux-tester, Windows-tester og Windows-EXE bygges med GitHub Actions.
- Vellykket dev-bygg publiseres automatisk som en GitHub prerelease, med navn som `dev-v0.5.0.b12`.
- Stable endres aldri ved en vanlig dev-push.
- Når en dev-versjon er testet og godkjent, publiseres den manuelt til stable.
- Stable-publiseringen laster ned den bestemte testede dev-pakken, kontrollerer SHA-256 og publiserer de samme filene uten ny bygging. Stable-taggen blir for eksempel `v0.5.0.b12`.
- Stable ligger som GitHubs Latest-utgave. Dev-utgaver får eksplisitt `latest=false`.

YSK-oppsettet publiserer gjennom Supabase. Dette prosjektet bruker direkte, offentlige GitHub Releases og krever ikke Supabase eller API-nøkkel i klienten. Det støtter ikke private release-repoer i denne versjonen.

## Første tilkobling

Dette prosjektet bruker det offentlige repoet `Krussedull86/TaldrisServerStudio`. Adressen er konfigurert i release_info.py og stemples automatisk under GitHub-bygging.

1. Legg INNHOLDET av `TaldrisServerStudio`-mappen på repoets rot. `app.py`, `requirements.txt` og `.github/` skal ligge direkte i repoet.
2. Legg samme oppsett på `main`, som skal være standardbranch. Dette gjør den manuelle stable-jobben synlig i GitHub Actions.
3. Opprett `dev` fra `main`. Push utviklingsendringer til `dev`.
4. GitHub Actions → **Taldris dev** starter automatisk ved kodeendringer på dev. Den kan også kjøres manuelt på dev.
5. Ved vellykket bygg ligger Windows-pakken under Releases. Den ferdige EXE-en krever ikke Python hos brukeren.

Arbeidsflytene bruker GitHubs innebygde GITHUB_TOKEN med innholdsskrivetilgang kun i publiseringsjobben. Ingen personlige tokens skal legges i kildekoden. Repo-/organisasjonspolicy må tillate GitHub Actions og innholdsskriving for publiseringsjobben.

Det skal bare pushes programkode. Egne servermapper, SteamCMD, personlige innstillinger, passord, private modnøkler og PBO-er er utelatt fra programutgivelsene og oppført i .gitignore. Se gjennom første commit før den pushes.

## Publiser stable etter testing

1. Finn eksakt dev-tag for utgaven du har testet, for eksempel `dev-v0.5.0.b12`.
2. GitHub Actions → **Promote tested dev to stable** → Run workflow.
3. Velg `main` og lim inn dev-taggen.
4. Skriv `STABLE` i bekreftelsesfeltet og kjør arbeidsflyten.

Det er denne manuelle handlingen som publiserer stable. Vanlige push til main gjør det ikke. Publiseringstaggen er unik; en eksisterende release overskrives ikke. Main-kildekoden kan oppdateres med vanlig PR/merge uavhengig av release-promoteringen.

## Programoppdatering

I programmet: **Programoppdatering**.

- Velg repo og kanal, `stable` eller `dev`.
- Velg automatisk sjekk ved oppstart, eller trykk **Lagre og sjekk**.
- GitHub-bygde EXE-er får repo-adressen innebygd automatisk. Første kanal er stable; testere kan velge dev.
- Ny utgave varsles i statusfelt og aktivitetslogg.
- **Last ned Windows-pakke** henter ZIP og kontrollerer størrelse og SHA-256 før filen tilbys.
- Pakk ut til egen mappe, avslutt gammel programutgave og start ny EXE. Serverdata og lokale modmapper ligger separat og blir ikke byttet ut av nedlastingen.

Dette er oppdateringssjekk og kontrollert nedlasting, ikke automatisk erstatning av en kjørende EXE. Direkte automatisk installasjon og omstart av panelet er ikke implementert. Programmet stopper heller ikke en DayZ-server for å installere en programoppdatering. Kjør derfor programbyttet når serverdriften tillater det, slik at du beholder prosesskontrollen i gjeldende økt.

Build-nummer settes fra GitHub Actions run_number. `VERSION` i release_info.py økes når en ny programversjon skal gis et annet versjonsnummer. Både semantisk versjon og byggnummer brukes ved sammenligning.

## Teststatus

Arbeidsflytene er klargjort og YAML er kontrollert lokalt. Tester og bygge-/pakkeverktøy kan kjøres lokalt. Ingen ekte GitHub Actions-kjøring, publisering eller Windows-EXE-bygg er utført for dette prosjektet ennå, før første vellykkede arbeidsflytkjøring. Ingen Windows-kodesigneringssertifikater er konfigurert; EXE-bygg er derfor usignerte.
