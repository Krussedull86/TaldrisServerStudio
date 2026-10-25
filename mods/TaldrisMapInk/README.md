# Taldris Map Ink (DayZ) - utviklingsversjon

**Status: kildekode / utestet i DayZ-klient og server. Ikke ferdig Workshop-mod.**

Dette prosjektet legger frihåndstegning oppå **vanilla fysisk ItemMap**, og bruker eksisterende `Pen_Black`, `Pen_Blue`, `Pen_Red` og `Pen_Green`. Lesing krever bare kartet. Skriving krever en fungerende penn med tilsvarende farge i spillerens inventar. Fargene lagres på *kartobjektet*, ikke hos spilleren.

## Implementert i kildekoden

- Utvider `ItemMap` og `MapMenu`, uten eget kart-item eller endringer i original-PBO.
- Tegn frihånd over det vanlige kartet, velg farge fra penner du faktisk har.
- Zooming, kartkoordinater og visning via `MapWidget.ScreenToMap` / `MapToScreen`.
- Serverstyrt RPC for å hente tegninger og sende nye segmenter. Serveren sjekker eierskap, at kartet er i hendene, penn/farge, koordinater og antallsgrenser.
- Tegningene serialiseres som tilleggsdata på kartets `OnStoreSave` / `OnStoreLoad`. Skal følge den samme kartinstansen ved overlevering og restart.
- Undo for siste **ulagrede segment**, Save i grupper. Vanilla-kartmarkører bevares.

## Ikke ferdig / testpunkter

- **Ikke** testet kompilert, pakket som PBO eller kjørt på DayZ-server. Etabler først fungerende PBO og sjekk script/RPT.
- Overgang for eksisterende lagrede vanilla-kart må testes med serverbackup. Tilleggsfelt i `OnStoreLoad` kan kreve migrering ved oppgradering/nedgradering.
- RPC-ytelse og pakketstørrelse, samtidige klienter og kartbytte må testes. Grense per kart er 4096 linjesegmenter.
- Tekstbokser, viskelær for lagret blekk, penn-blekkforbruk, egen tusj, drag-and-drop-kombinasjon i inventory, signering og Steam Workshop-publisering er ikke implementert.
- Ved lagring sendes flere RPC-batcher; klientens pending-buffer tømmes før serverbekreftelse. Production-versjon bør ha transaksjons-ID, ACK, retry og rate limiting.
- GUI-oppsett og koordinatplassering må verifiseres på 16:9 og ultrawide. På enkelte skjermer kan root-widgetenes pointer-atferd måtte justeres.

## Bygging på Windows

1. Installer **DayZ Tools** via Steam og sett opp Project Drive (vanligvis `P:\`).
2. Kopier *innholdet i denne mappen* til `P:\TaldrisMapInk\`, så `P:\TaldrisMapInk\config.cpp` og `P:\TaldrisMapInk\scripts\...` finnes.
3. Bruk **Addon Builder** med input `P:\TaldrisMapInk`, prefix `TaldrisMapInk`, output `@TaldrisMapInk\Addons\TaldrisMapInk.pbo`. Pakk alt av .c, .layout og config.
4. Kopier `distribution/mod.cpp` til `@TaldrisMapInk\mod.cpp`.
5. Kjør samme mod på **server og klient** med `-mod=@TaldrisMapInk`. Dette er ikke en server-only mod.
6. Spawn `ChernarusMap` og `Pen_Black` (og de tre andre fargene) på testserver; aktiver loot i types.xml etter eget behov. **Ta backup av persistence**.
7. Verifiser i multiplayer: tegn → SAVE → lukk → åpne → gi kartet til en annen spiller → åpne → restart → åpne. Sjekk `*.RPT` og script logs.

## Forslag til neste iterasjon

Gjør editoren produksjonsklar: ACK/retry, stroke-baserte Undo, tekst-notater, felt for penn-i-hånd/inventory-combine, markerpenner, admin-konfig, migreringstester og ytelsesprofilering. Opprett issue/PR med testlogger før merging.
