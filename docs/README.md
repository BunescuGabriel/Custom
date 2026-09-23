# Text în audio și video

Aplicație locală pentru MP3 și MP4 vertical, cu interfață în română, istoric,
cache audio și subtitrări. Python **3.13** pe Windows sau Linux; pe macOS este
necesar și un font compatibil (vezi secțiunea MP4).

## Instalare și pornire

Din directorul proiectului, în PowerShell:

```powershell
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe main.py
```

Pe Linux/macOS:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

`requirements.txt` este singura listă de instalare și fixează versiunile aplicației,
ale dependențelor tranzitive și ale instrumentelor de testare. `edge-tts==7.2.8`
include parametrul `boundary="WordBoundary"` folosit pentru timpii cuvintelor.
Versiunile se actualizează în acest fișier și se verifică prin testele automate.

Pornirea prin `python main.py` configurează serverul pe **127.0.0.1**, limita
de încărcare la 100 MB și dezactivează statisticile de utilizare. Setările sunt
transmise direct din `main.py`. Aplicația are un singur istoric local și nu
oferă autentificare sau separare între utilizatori; nu schimba adresa de
ascultare pentru a o publica în rețea.

Schema este actualizată automat, cu blocare între fire și procese. Migrarea
păstrează istoricul existent. Fă o copie a directorului `media` înaintea unei
actualizări. Testele folosesc exclusiv baze de date temporare.

## Generare și confidențialitate

- Sinteza nouă trimite textul serviciului Microsoft Edge prin `edge-tts` și
  necesită internet. Detectarea limbii rulează local. Un cache valid poate fi
  reutilizat fără un nou apel de sinteză.
- Sunt disponibile română, rusă, engleză, franceză, germană, italiană și spaniolă.
  Detectarea este o estimare: textul scurt, mixt sau nesuportat cere verificare
  manuală. Recomandările nu blochează editarea limbii, vocii, vitezei sau tonului.
- Limite: 12.000 de caractere, aproximativ 10 minute de narațiune, fundal de
  maximum 100 MB / 4K / 10 minute. Durata reală a MP3 este verificată separat.
- O singură generare grea poate fi activă în același director de stocare,
  inclusiv între procese. Alte cereri primesc un mesaj explicit.
- Lucrarea și parametrii sunt salvați înainte de procesare. Adresa paginii
  conține identificatorul lucrării; reîncărcarea permite recuperarea rezultatului.
  „Lucrări și stocare” permite urmărirea, anularea și reluarea. Lucrările rămase
  active după o oprire sunt marcate „Întrerupt”. Nu sunt reluate automat.
- MP3-ul finalizat este disponibil și în timpul randării MP4. Anularea oprește
  sinteza/procesul FFmpeg și păstrează rezultatele deja finalizate.
- Bugetul TTS este de 180 s pentru cel mult 5 încercări; erorile permanente
  (de exemplu 401) nu sunt repetate. 429/5xx și erorile de rețea folosesc pauze
  crescătoare și `Retry-After`. Bugetul randării este de 900 s.

Textul, parametrii și media rămân pe disc până la ștergere. Șterge rezultatele
din istoric și, dacă este nevoie, parametrii lucrărilor din „Lucrări și stocare”.
Fișierele partajate se șterg numai după ultima referință. Un audio folosit de
videoclipuri poate fi șters după acele videoclipuri. Curățarea manuală elimină
doar fișiere fără referințe, mai vechi de 24 de ore; nu există ștergere automată
a rezultatelor. Jurnalele se rotesc la 10 MiB, cu maximum 100 de copii.

## MP4 vertical

Instalează FFmpeg și FFprobe cu `libass`, `libx264` și AAC și pune executabilele
în `PATH`. Folosește [distribuțiile indicate de FFmpeg](https://ffmpeg.org/download.html).
Pe Ubuntu: `sudo apt-get install ffmpeg fonts-dejavu-core`. Pe Windows,
redeschide terminalul după modificarea `PATH`.

Fontul este ales dintre Arial Bold (Windows/macOS) și DejaVu/Liberation Sans
(Linux). Poți seta `VIDEO_TITLE_FONT_PATH` la un fișier TTF cu diacritice și
caractere chirilice. Lipsa fontului/codecurilor este detectată înainte de TTS.

Ieșirea este 1080 × 1920, 30 FPS, H.264/AAC. Sunetul original al fundalului
este eliminat. Alege decuparea la stânga, centru sau dreapta și folosește
previzualizarea pentru a verifica încadrarea și poziția textului.

Introducerea are implicit **3 secunde**, reglabilă între 0 și 10 secunde.
Se folosește un cadru fix de la secunda 1, sau de la mijlocul unui fundal mai
scurt de 2 secunde. După introducere, fundalul și narațiunea încep de la secunda
0; subtitrările sunt deplasate cu exact durata introducerii. Valoarea 0 elimină
introducerea. Fundalul se repetă până la sfârșitul narațiunii.

Subtitrările folosesc timpii verificați ai cuvintelor când aceștia sunt compleți.
Metadatele lipsă/corupte blochează videoclipul dacă nu ai bifat explicit acceptarea
subtitrărilor aproximative. Calitatea este salvată în istoric. Pentru un MP3 vechi
poți folosi „Ignoră cache-ul și sintetizează din nou” pentru a reface metadatele.

## Istoric și fișiere

Istoricul are căutare, filtre, pagini de 25 de rezultate, selecție compactă și
tabel opțional cu date/numerice sortabile. Datele sunt afișate explicit în UTC.
Poți reîncărca setările sau crea/reîncerca un video folosind audio-ul existent.
Un fișier mai mare de 32 MiB se deschide din calea locală afișată, pentru a
limita memoria consumată de player și descărcări. Cache-ul UI păstrează cel mult
4 fișiere mici, maximum 5 minute.

- `media/data/app.db`: istoric și lucrări persistente.
- `media/data/app.log`: diagnostic cu identificatori de eroare și timp UTC.
- `media/audio`: MP3 și metadate JSONL.
- `media/backgrounds`: fundaluri deduplicate după conținut.
- `media/videos`: MP4, subtitrări și fișiere temporare.

Căile din bază sunt relative la `media`; migrarea convertește căile vechi care
conțin acel director. Pentru backup sau mutare, oprește aplicația și copiază
**întregul director `media`**, inclusiv baza și fișierele dependente. Setează
`APP_MEDIA_DIR` dacă vrei altă locație de stocare. Căile externe nevalide nu sunt
deschise din istoric.

`LOG_LEVEL` controlează nivelul jurnalului; `LOG_FORMAT=json` scrie numai în
consolă; `NO_COLOR` dezactivează culorile consolei. Detaliile FFmpeg și traceback-urile
rămân în jurnal, iar interfața afișează un mesaj și un cod de eroare.

## Dezvoltare și verificare

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pre_commit install
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m black --check .
.venv/Scripts/python.exe -X utf8 -m isort --check-only src tests migrations main.py
.venv/Scripts/python.exe -m pytest -q
```

Testele de browser folosesc Chrome/Edge local pe Windows sau Chromium instalat
cu `python -m playwright install chromium`. FFmpeg și FFprobe sunt necesare
pentru testele marcate `integration` și pentru partea audio/video a testului
de browser. Pentru unități: `python -m pytest -m "not integration and not browser"`.
Testele înlocuiesc serviciul extern TTS și generează local media sintetică.

Testele locale verifică migrațiile, regresiile, MP4 prin FFprobe și browserul
la 360/768/1280 px. Capturile sunt salvate în directorul temporar al testului.
Rezultatele verificării inițiale sunt în [raport](verification.md), iar lista
corecțiilor este în [todo.md](todo.md).
Verificarea manuală cu un cititor de ecran și un apel TTS real rămân recomandate
în mediul în care folosești aplicația.
