# Taldris Server Studio

Et moderne Windows-program for installasjon og administrasjon av DayZ-servere.

- SteamCMD-nedlasting, anonym/konto-innlogging og integrert konsoll.
- DayZ Server-installasjon, konfigurasjon, oppstart og logger.
- Direkte Steam Workshop-søk, modnedlasting og samlingsimport.
- Lokale @mods som lastes direkte fra utviklingsmappene dine.
- Velg per mod: `-mod`, `-serverMod` eller begge.
- Kart med zoom og markører, sikkerhetskopier og automatisering.
- Separate dev/stable-kanaler for programoppdateringer.

## Last ned

Ferdige Windows-pakker publiseres under [Releases](https://github.com/Krussedull86/TaldrisServerStudio/releases) etter vellykket GitHub Actions-bygg. Pakk ut ZIP og kjør TaldrisServerStudio.exe. Ferdig EXE krever ikke Python.

Fra kildekode: installer Python 3.12+, pakk ut/klon repoet og kjør START.bat. Første oppstart installerer PySide6 i et lokalt miljø.

## Utvikling og publisering

Push til **dev** kjører tester, bygger Windows-EXE og publiserer en testutgave. **Stable** publiseres bare manuelt fra en bestemt testet dev-utgave; samme Windows-pakke brukes uten ny bygging. Push til main publiserer ikke stable.

Les [GITHUB_OPPSETT.md](GITHUB_OPPSETT.md) for publisering og [LES_MEG.md](LES_MEG.md) for bruk og begrensninger.

## Tester

```sh
python -m pip install -r requirements.txt
python -m unittest discover -v
```

Windows-kjøring av den ekte DayZ-serveren krever Windows og nødvendig Steam-tilgang. Enkelte prosesstester bruker en Unix-simulering og hoppes over på Windows. RCon, live spillerposisjoner og automatisk erstatning av kjørende program-EXE er foreløpig ikke implementert.
