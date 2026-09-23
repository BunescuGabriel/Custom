# Verificarea corecțiilor din todo.md

Data: 23 septembrie 2026. Verificările folosesc stocări temporare; baza și
fișierele media ale utilizatorului nu au fost migrate sau modificate.

Raportul păstrează rezultatele verificării inițiale. Ulterior, la cererea
utilizatorului, au fost eliminate capturile, copia FFmpeg pentru teste, mediul
de validare și directoarele de configurare GitHub/Streamlit. Configurația de
pornire este transmisă din `main.py`; documentația proiectului este în `docs/`.

## Rezultat

- Instalare curată într-un mediu temporar, Python 3.13.7, cu setul de versiuni
  fixate reunit ulterior în singurul fișier `requirements.txt`.
- **65 de teste trecute, zero omise**, inclusiv FFmpeg și browser.
- `pip check`, Ruff 0.16.8, Black 26.5.1 și isort 9.0.1: trecute.
- FFmpeg/FFprobe 9.0.2, distribuția Windows essentials indicată de pagina
  oficială FFmpeg, folosită dintr-o copie temporară.
- Browser Chrome/Edge local: generator și istoric la 360/768/1280 px,
  previzualizare video și rezultat MP4. Capturile inițiale au fost eliminate.

## Acoperire

| Punct | Corecție și verificare |
| --- | --- |
| R01 | Normalizare comună; AppTest schimbă textul/limba și apasă generarea în același ciclu. |
| R02 | UUID, fișiere parțiale, publicare atomică; două sinteze simultane păstrează rezultate distincte. |
| R03 | Versiuni directe/tranzitive fixate, instalare curată, API WordBoundary verificat. |
| R04 | Lingua local, șapte limbi, avertizare pentru text ambiguu/mixt/nesuportat, corecție manuală. |
| R05 | Loopback configurat prin argumentele din main.py; modul local documentat. |
| R06 | Introducere implicită de 3 s, reglabilă; narațiunea și subtitrările pornesc după aceasta. |
| R07 | Împărțire cuvinte lungi și limite de dimensiuni; titlul cu 140 de W încape în cadru. |
| R08 | PNG fix, concatenare cu fundalul de la zero; comparație între cadre reale. |
| R09 | Font configurabil și fallback, verificat înaintea sintezei. |
| R10 | Validare text, resurse, font și capabilități FFmpeg înainte de TTS. |
| R11 | Limite de text/durată/rezoluție/upload, estimare și blocare comună a generărilor grele. |
| R12 | Proces oprit și așteptat; MP4 parțial șters inclusiv la timeout. |
| R13 | Erori de upload capturate, fișiere parțiale curățate, formular păstrat. |
| R14 | Fallback aproximativ explicit, calitate salvată, opțiune de sinteză fără cache. |
| R15 | Tipuri, timpi, ordine, limite și acoperire completă a textului validate. |
| R16 | Previzualizare verticală și alegerea decupării, verificate în browser. |
| R17 | Validare Mutagen, căi controlate, mesaje pentru fișiere indisponibile. |
| R18 | Toate potrivirile sunt parcurse; cache-ul vechi valid rămâne utilizabil. |
| R19 | Înregistrare pending înainte de lucru, compensare la eșec DB, cauză inițială păstrată. |
| R20 | Cache fără copiere MP3, fundaluri deduplicate, ștergere cu referințe și curățare explicită. |
| R21 | Căi relative, rezolvare centrală, migrare și instrucțiuni de mutare media. |
| R22 | Foreign keys pe conexiuni, audit al legăturilor vechi, UI tolerant la relații deteriorate. |
| R23 | Index ORM identic cu migrarea; compare_metadata nu propune diferențe. |
| R24 | Blocare între fire/procese pentru migrații; porniri concurente verificate. |
| R25 | Lucrări persistente, parametri salvați, recuperare după refresh și stare întreruptă după restart. |
| R26 | Etape, timp, retry, anulare și MP3 intermediar; acțiuni incompatibile blocate. |
| R27 | Parametrii rezultatului și avertizare pentru formular schimbat; cache identificat explicit. |
| R28 | Pagini de 25, căutare/stare în DB, selecție păstrată între paginile istoricului. |
| R29 | Datetime și numere în tabel, formatare separată. |
| R30 | Repetare/editare, video din audio existent, reluarea etapei video și afișarea relațiilor. |
| R31 | Mesaje diferențiate cu identificator; detaliile tehnice rămân în jurnal. |
| R32 | Linii unite în interiorul paragrafului; sunt numărate numai paragrafele reale. |
| R33 | Doar pagina activă, polling pentru lucrarea activă, cache UI și limită de 32 MiB. |
| R34 | Providerul, internetul, păstrarea și ștergerea datelor explicate în UI/README. |
| R35 | Texte ale aplicației în română, profiluri/etichete comune centralizate, acțiuni MP3/MP4. |
| R36 | Stiluri restrânse, istoric compact, capturi la trei dimensiuni de ecran. |
| R37 | role=status, aria-live/atomic, reduced-motion și arbore de accesibilitate verificate. |
| R38 | Pas 1 pentru viteză; +2% este reproductibil manual și după restaurare. |
| R39 | UTC explicit, compatibilitate cu datele naive vechi, helper comun. |
| R40 | 401 nu este repetat; 429/5xx/timeout folosesc backoff și Retry-After, în 180 s total. |
| R41 | pytest, AppTest, FFmpeg și Playwright; workflow-ul CI a fost eliminat ulterior la cererea utilizatorului. |
| R42 | Instalare documentată, versiuni hooks/instrumente aliniate; la cererea utilizatorului, instrumentele dev sunt incluse în requirements.txt. |
| R43 | Istoric și formatări comune, callback-uri și stare duplicată eliminate. |

Verificări suplimentare: formular păstrat între pagini, setări MP4 păstrate la
schimbarea formatului, fișiere mari neîncărcate în memoria playerului.

## Limite

Sinteza Microsoft este înlocuită cu un furnizor controlat. Testele nu confirmă
disponibilitatea serviciului extern sau calitatea vorbirii. Cadrul, temporizarea
audio și formatul MP4 sunt verificate cu FFmpeg real, fără textul utilizatorului.

Navigarea cu tastatura și semantica sunt verificate în browser; anunțurile nu
au fost ascultate efectiv cu NVDA/VoiceOver. Workflow-ul Linux nu a fost
executat la distanță și a fost eliminat ulterior. macOS nu a fost testat.

FFmpeg folosit pentru teste nu schimbă PATH global. Pentru MP4 în aplicație,
configurează PATH conform [README](README.md). Migrarea bazei existente are loc la următoarea
pornire; copiază întregul director media înainte de actualizare.
