# ToetsAnalyse

ToetsAnalyse is een lokaal desktopprogramma voor een docent. Deze eerste versie
legt het fundament voor vakdatabases, schooljaren, klassen, leerlingen, toetsen
en toetsmatrijzen.

## Beschikbaar in deze versie

- Een afzonderlijke SQLite-database per vak.
- Startscherm voor nieuw vak, bestaand vak, laatst geopend vak en herstel uit
  back-up.
- Dashboard per gekozen schooljaar.
- Beheer en bewerken van klassen/groepen en leerlingen.
- Leerlingenimport uit een Magister Excel-export met de kolommen `Stamnummer`,
  `Roepnaam`, `Tussenvoegsel` en `Achternaam`, ook als de kopregel niet op de
  eerste rij staat; import vindt plaats naar een vooraf gekozen cluster/groep
  en negeert de Magister-kolom `Klas`.
- Filteren van leerlingen op cluster/groep, niveau en leerjaar, verwijderen uit
  een schooljaar en toevoegen van eigen leerlingkenmerken.
- Bewerken en bevestigd verwijderen van toetsen; klassen/groepen kunnen worden
  verwijderd wanneer er geen leerlingen of toetsen meer aan gekoppeld zijn.
- Bij een toets van het type `Herkansing` wordt verplicht vastgelegd van welke
  oorspronkelijke toets dit de herkansing is.
- Toetsbeheer met een duidelijke vinklijst voor koppeling aan een of meer
  klassen/groepen.
- Toetsmatrijs-editor met puntentotaal, optionele tijdindicatie, een of meer
  toetsbrede taxonomieen en zelf toe te voegen vraageigenschappen.
- Standaardtaxonomieen RTTI, OBIT en Bloom in iedere nieuwe vakdatabase, met
  de mogelijkheid eigen taxonomieen en waarden toe te voegen.
- Een menu `Vraagclassificaties` waarin de docent keuzewaarden voor velden
  zoals `Vraagtype` instelt, bijvoorbeeld `Leg uit`, `Bereken`, `Bepaal` en
  `Teken`.
- Classificaties kunnen worden bewerkt; bij een keuzelijst kunnen opties los
  worden toegevoegd, hernoemd of verwijderd zolang ze niet meer in gebruik zijn.
- Bij het aanmaken of bewerken van een toets kiest de docent via vinklijsten
  welke taxonomieen en extra vraagvelden gebruikt worden. Bij elke vraag is
  vervolgens binnen iedere gekozen taxonomie een waarde verplicht.
- Voor `Vraagtype` kan per toets een selectie worden aangevinkt, zodat alleen
  de gewenste opties, bijvoorbeeld `Bereken` en `Teken`, bij die toetsvragen
  beschikbaar zijn.
- `Vraagtype` staat zelf ook in `Velden toevoegen aan vragen`; na aanvinken kies je
  daaronder welke vraagtype-opties voor de toets mogen worden gebruikt. Bij het
  aanvinken van `Vraagtype` verschijnt de optielijst en worden standaard alle
  ingestelde opties geselecteerd.
- Na het toevoegen of wijzigen van vraagclassificaties kan een bestaande toets
  via `Toetsen` > `Bewerken` alsnog van die velden of vraagtypen worden voorzien.
- Het scherm `Resultateninvoer` toont de leerlingen uit de aan een toets
  gekoppelde groepen en laat scores per vraag invoeren. De docent kiest of de
  invoer na Enter horizontaal per leerling of verticaal per vraag doorgaat.
  Scoregrenzen, numerieke invoer, totaalscores en leerlingstatussen worden
  direct gecontroleerd en opgeslagen. Met de optie `Halve punten mogelijk`
  bepaalt de docent of alleen hele punten of ook `x,5`-scores zijn toegestaan.
  Staat deze optie op `nee` en hebben alle vragen maximaal 9 punten, dan springt
  de invoer direct door zonder Enter.
- Vanuit `Toetsmatrijs` genereert de knop `Toetsmatrijs genereren` een preview
  in dashboardstijl met algemene toetsgegevens, een matrix met
  classificatiechips en grafische puntverdelingen per taxonomie, domein en
  vraagtype. De preview gebruikt een ingebedde browserweergave; de PDF-export
  wordt met Playwright Chromium gerenderd, zodat moderne HTML/CSS, kleuren,
  grafieken en pagina-afbrekingen behouden blijven in liggend A4-formaat.
- Vanuit `Toetsanalyse` > `Leerlingniveau` kan een leerlingvriendelijk
  PDF-rapport worden gegenereerd voor een gekozen leerling of als batch van
  losse PDF's voor alle leerlingen. Een samenstelvenster bepaalt welke
  profielgrafieken, vraaganalyse, aandachtspunten en geanonimiseerde
  positiekaart worden opgenomen; RTTI, OBIT en Bloom krijgen automatisch een
  korte toelichting. Optioneel kan een tweede positiekaart worden opgenomen.
  Bij export voor een individuele leerling kan de docent daarnaast persoonlijke
  feedback toevoegen als aparte kaart in het rapport.
  Bij batch-export toont het programma de voortgang per leerling en kan de
  docent de resterende export annuleren.
- Bij een herkansing bevat dit toetsmatrijsrapport onderaan automatisch een
  vergelijking met de originele toets, met per verdeling een tabel en twee
  taartdiagrammen met legenda voor origineel en herkansing.
- Niveaukeuzes voor groepen en toetsen zijn: `vmbo basis kader`, `vmbo kader`,
  `mavo`, `havo`, `vwo`, `basis/kader`, `kader/mavo`, `mavo/havo` en `havo/vwo`.
- Automatische back-up bij het sluiten van een vak of de toepassing, plus een
  handmatige back-upknop.

De database bevat al de hoofdtabellen voor latere normering, resultaten,
vraagbankvragen en rapportage-exports. Deze functies krijgen in volgende
bouwfasen hun schermen en berekeningen.

## Starten

Installeer Python 3.12 of nieuwer en voer in deze map uit:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

Voor de PDF-export wordt de browser van Playwright gebruikt. Daardoor is het
programma niet afhankelijk van Microsoft Edge of een andere browser die al op
de computer staat. Als Chromium nog niet is geinstalleerd, geeft de exportknop
een duidelijke melding met bovenstaande eenmalige installatieopdracht.

Voor distributie zijn er nu twee smaken:

- **Portable build:** PyInstaller-map met `ToetsVizier.exe`, `_internal` en
  `ms-playwright`.
- **Installer:** Inno Setup-installer die de app in
  `%LOCALAPPDATA%\Programs\ToetsVizier` plaatst.

Een geinstalleerde versie bewaart gebruikersdata niet in de programmamap, maar
in `%LOCALAPPDATA%\ToetsVizier\` (`data`, `backups`, `exports`, `logs`,
`config`). Alleen in portable modus blijft data naast `ToetsVizier.exe`
staan.

## Releases en updates publiceren

Het updatesysteem controleert een publiek `update.json` op GitHub. Als daarin
een nieuwere versie staat, downloadt ToetsVizier de installer, sluit de app af
en start daarna de update.

Gebruik bij een nieuwe release deze volgorde:

1. Verhoog `toetsanalyse\version.py` naar de nieuwe uitgaveversie.
2. Werk `packaging\update_manifest.source.json` bij met de releasenotities en
   wijzigingsregels voor die versie.
3. Bouw eerst de installer:

```powershell
python packaging\build_installer.py
```

4. Publiceer daarna de installer op GitHub Releases. De standaardnaam is
   `ToetsVizier-<versie>-windows-installer.exe` onder tag `v<versie>`.
5. Genereer daarna pas het live manifest:

```powershell
python packaging\build_update_manifest.py
```

Dit schrijft `update.json` in de projectroot. Publiceer dat bestand pas nadat
de installer echt bestaat; anders zien gebruikers een update die nog niet
kan worden geïnstalleerd.

U kunt ook controleren of `update.json` nog overeenkomt met het sjabloon en de
huidige versie:

```powershell
python packaging\build_update_manifest.py --check
```

## Opslag

Nieuwe vakken worden standaard voorgesteld in `data/`. Back-ups verschijnen in
`backups/` en worden voorzien van datum en tijd. Herstellen maakt bewust een
nieuwe databasekopie, zodat een bestaande vakdatabase niet stilzwijgend wordt
overschreven.
