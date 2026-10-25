# Kleine Windows-updates

Maak eerst een actuele programmabuild. Gebruik een vorige build als basis om
alleen gewijzigde bestanden op te nemen (inclusief assets en runtimebestanden):

```powershell
python packaging/build_update_package.py --version 1.1.5 --dist-dir dist/ToetsVizier --baseline-dir previous/ToetsVizier --output-dir releases
python packaging/build_patch_exe.py releases/ToetsVizier-update-1.1.5.zip --output-dir releases
```

De tweede opdracht vereist PyInstaller en maakt één zelfstandig updateprogramma.
De normale `ToetsVizier.spec` bouwt daarnaast `ToetsVizier-updater.exe` en neemt
die op in de programmamap. De knop Bijwerken downloadt het ZIP-pakket, start een
tijdelijke kopie van die helper en gebruikt de normale afsluitroute van de app.
De helper toont een eigen venster en wacht maximaal twee minuten op het stoppen
van het app-proces. Bij annuleren van afsluiten of een verstreken wachttijd wordt
geen update toegepast. Deze integratie vereist een eerste programmabuild met de
helper; bestaande installaties zonder helper krijgen een duidelijke foutmelding.
De gebruiker heeft geen Python nodig. Publiceer pas na controle op een kopie van
de oudste ondersteunde installatie. Een baseline moet overeenkomen met die
ondersteunde installatie. De updater controleert de basisbestanden en weigert een
afwijkende of oudere installatie voordat hij bestanden vervangt.
Laat `--baseline-dir` weg om alle programmabestanden mee te nemen.

De updater zoekt de bestaande installatie via het register en de standaardmap.
Bij een andere locatie kan de gebruiker de map kiezen. ToetsVizier moet vooraf
worden gesloten. Bestanden worden met SHA-256 gecontroleerd, vóór overschrijven
gekopieerd naar `%LOCALAPPDATA%/ToetsVizier/backups/updates`, en na kopiëren opnieuw
gecontroleerd. Bij een schrijffout herstelt hij de vorige bestanden en verwijdert
hij nieuwe patchbestanden. Bij een herstelfout toont hij de back-uplocatie.
Gebruikersdata en instellingen worden geweigerd als patchinhoud.

Dit bouwt geen volledige installer en publiceert niets. Een nieuwe appversie
vereist nog steeds een programmabuild; alleen broncode vervangen werkt niet bij
een verpakte Windows-app. Verwijderde bestanden blijven voorlopig aanwezig.
