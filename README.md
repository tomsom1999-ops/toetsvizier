# ToetsAnalyse

ToetsAnalyse is een lokaal desktopprogramma voor een docent. Deze eerste versie
legt het fundament voor vakdatabases, schooljaren, klassen, leerlingen, toetsen
en toetsmatrijzen.

## Simpel of Uitgebreid

Het startscherm biedt bovenaan **Simpel** en onderaan **Uitgebreid**. Uitgebreid
opent de bestaande vakbestanden. Simpel werkt met één losse toets, zonder vak-
of klassenbeheer, in een eigen **`.tviz`-analysebestand**. De twee bestandssoorten
worden niet met elkaar vermengd.

Klik eerst op **Simpel openen**. Pas op het volgende scherm verschijnen
**CITO-analyseformulier uploaden**, **Zelf starten** en **Analyse openen**, elk met uitleg.
Een nieuwe analyse vraagt het aantal vragen en leerlingen. Daarna opent een
handleiding met zeven onderwerpen, gemarkeerde voorbeeldschermen en
Vorige/Volgende. U kunt meteen een onderwerp kiezen, de uitleg overslaan met een
knop of haar bij volgende analyses automatisch overslaan met het aparte vinkje.
De handleiding behandelt maximumscores, namen, 0/N/antwoordletters, beide manieren
van Excel-plakken, de drie invoerrichtingen, optionele instellingen en opslaan.
CITO-import leest de ingevulde vragen, maximumscores en
leerlingenscores uit Referentie en Gegevens; lege leerlingregels worden overgeslagen.

Boven de tabel blijven **Aantal vragen** en **Aantal leerlingen** bewerkbaar.
Verlagen verbergt extra kolommen of rijen zonder de gegevens te wissen. Verhogen
laat eerder ingevulde namen, scores, metadata en antwoordsleutels weer zien.
Normering, analyse en Excel-export gebruiken alleen de zichtbare aantallen.

Voer scores horizontaal per leerling, verticaal per vraag of gecombineerd in.
Ctrl+V plakt vanuit Excel, Ctrl+C kopieert en Ctrl+Z herstelt een invoer of plakactie.
Standaard gebruikt u hele punten. **0** is een echte score; **N** betekent niet
gemaakt en telt als nul; een lege cel moet nog worden ingevuld. Afwezige leerlingen
neemt u niet op. De tabel heeft een kleurenlegenda.

Met **Vragen indelen** koppelt u optionele RTTI-, OBIT- en Bloom-categorieën of eigen
indelingen en categorieën. Met **Meerkeuze instellen** kiest u per vraag een sleutel;
daarna voert u antwoordletters in. Zonder sleutel gebruikt u punten. **Exporteren
naar Excel** bewaart de zichtbare tabel en de vraaginstellingen/metadata.

Na de eerste keer **Opslaan** worden geldige wijzigingen automatisch in het gekozen
bestand bewaard. **Opslaan als** maakt een andere kopie. **Normeren** en **Analyseren**
worden beschikbaar als alle zichtbare maximumscores en scores geldig zijn ingevuld.
Zonder vastgestelde normering is de analyseknop oranje en aanklikbaar: scores en
vragen zijn te analyseren, cijfers en cijferafhankelijke onderdelen volgen na normering.
Groepsniveau gaat over de deelnemers van de toets.
De bestaande dashboards zijn beschikbaar, met technische details achter extra uitleg.
De analyse geeft eerst begrijpelijke conclusies; de oorspronkelijke technische
onderbouwing is opvraagbaar. Bij normering staat uitleg per methode en een
punten-naar-cijfervoorbeeld dat direct meeverandert. Proberen wijzigt geen scores.
Knoppen in de simpele modus zijn Nederlandstalig. De bedieningsknoppen lopen op
kleinere schermen door op een volgende regel en de keuzelijsten passen in hun tabelrijen.

## Beschikbaar in deze versie

### Toetsversies

Ontgrendel **Meerdere versies binnen één toets** bij Geavanceerde instellingen.
Bij een nieuwe toets verschijnt daarna de standaard uitgeschakelde optie
**Deze toets heeft meerdere versies**, met zelf te kiezen versienamen. Bestaande
toetsen kunnen niet achteraf worden omgezet.

Voer eerst gedeelde vragen in, met een herkenbare titel en per versie een vinkje
en vraagnummer. Een vraag kan ook in slechts enkele versies voorkomen. Voeg daarna
de specifieke vragen toe. Via **Toetsversies beheren** kunt u titels, nummering,
koppelingen en leerlingtoewijzingen beheren. Een overzichtstab toont ontbrekende
titels, vraagkoppelingen, vraagnummers en leerlingtoewijzingen. Met **Alles opslaan**
bewaart u vragen en leerlingtoewijzingen samen; bij een fout wordt geen van beide
gedeeltelijk opgeslagen. Bij sluiten wordt u herinnerd aan niet-opgeslagen
wijzigingen. Toewijzen kan individueel, aan een selectie of aan een hele klas/groep.

Bij het toevoegen kiest u eerst **Gedeelde vraag** of **Versiespecifieke vraag**.
Daarna verschijnen alleen de relevante velden. Een gedeelde vraag krijgt een
herkenbare titel en minstens twee versies; bij een specifieke vraag kiest u één versie.

Bij afwijkende meerkeuzevolgordes koppelt u de inhoudelijk gelijke alternatieven
per versie, met een voorbeeld dat direct laat zien welke letters bij hetzelfde
antwoord horen, zoals **A in versie A = C in versie B**. Per vraag kiest u welke versie leidend is voor de weergegeven
alternatiefletters. Dit staat vermeld in het overzicht en de gezamenlijke
afleideranalyse; de vraagnummers worden hierdoor niet gewijzigd.

Resultateninvoer, Excel-import/export en normering werken per versie. De analyse
kan per versie of gezamenlijk worden geopend. Gedeelde vragen worden samengevoegd
onder hun titel, met het aantal leerlingen met een score. Vragen die niet in een
versie voorkomen tellen niet als nul. Gezamenlijke totaalscores worden uitgedrukt
als percentage van de eigen versie; betrouwbaarheid en meetfout worden per versie
getoond.

Een leerling met scores kan pas van versie wisselen nadat die scores zijn gewist.
Vragen toevoegen aan of verwijderen uit een versie met scores is geblokkeerd;
titels, omschrijvingen en nummering blijven aanpasbaar.

### Overige functies

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

Het updatesysteem controleert een publiek `update.json` op GitHub. Er zijn twee
routes:

- **Updatepakket:** voor kleine patches en gewone appwijzigingen. Dit is een
  ZIP-bestand met alleen appbestanden. ToetsVizier controleert de hash, maakt
  een back-up van bestanden die worden vervangen en vraagt daarna om opnieuw
  starten.
- **Installer:** voor grote releases of wijzigingen aan Python, PySide6,
  Playwright, Qt, Inno Setup of andere runtime-onderdelen.

Gebruik bij een nieuwe release deze volgorde:

1. Verhoog `toetsanalyse\version.py` naar de nieuwe uitgaveversie.
2. Werk `packaging\update_manifest.source.json` bij met de releasenotities en
   wijzigingsregels voor die versie.
3. Kies de publicatieroute.

Voor een kleine update:

```powershell
python packaging\build_update_package.py --version <versie> --dist-dir dist\ToetsVizier
```

Publiceer `releases\ToetsVizier-update-<versie>.zip` op GitHub Releases onder
tag `v<versie>` en genereer daarna `update.json` met de pakketroute en hash:

```powershell
python packaging\build_update_manifest.py --version <versie> --update-type package --package-sha256 <hash>
```

Voor een grote update bouwt u een installer:

```powershell
python packaging\build_installer.py
```

Publiceer daarna de installer op GitHub Releases. De standaardnaam is
   `ToetsVizier-<versie>-windows-installer.exe` onder tag `v<versie>`.
Genereer daarna pas het live manifest:

```powershell
python packaging\build_update_manifest.py
```

Dit schrijft `update.json` in de projectroot. Publiceer dat bestand pas nadat
de installer of het updatepakket echt bestaat; anders zien gebruikers een
update die nog niet kan worden geïnstalleerd.

`build_update_package.py` sluit bewust lokale gebruikersdata uit: `data`,
`backups`, `exports`, `logs`, `config`, databases, Excelbestanden en tijdelijke
bestanden komen niet in het updatepakket. Bij pakketten vanuit `dist\ToetsVizier`
blijven interne runtimebestanden wel behouden.

Let op: voor een geïnstalleerde `.exe` moet het pakket vanuit de PyInstaller-map
`dist\ToetsVizier` worden gebouwd. Dan bevat het pakket de nieuwe `ToetsVizier.exe`
en `_internal`-bestanden. ToetsVizier zet zo'n pakket klaar en laat een kleine
externe toepasser de bestanden vervangen nadat de app is afgesloten.

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
