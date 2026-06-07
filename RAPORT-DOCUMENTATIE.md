# Simularea Paralela a Furnicii lui Langton cu MPI

## Raport de Proiect - Algoritmi Paraleli

**Autor:** Iulian Cocriș

**Data:** Iunie 2026
**Versiune:** 1.0

---

## 1. Introducere

Acest proiect implementează o simulare a automatonului celular Langton's Ant în două variante: una secvențială și una paralelizată folosind MPI (Message Passing Interface). Scopul este să demonstreze cum un algoritm local simplu poate fi scalat pe mai multe nuclee/procese și să evidențieze compromisurile dintre calcul, comunicare și I/O.

Obiective:

- implementarea unui simulator secvențial robust în C++
- dezvoltarea unei versiuni MPI cu partiționare 1D pe rânduri
- includerea unui front-end GUI Python pentru vizualizare
- evaluarea performanței cu benchmark-uri strong și weak scaling
- documentarea arhitecturii și rezultatelor experimentale

---

## 2. Descrierea Proiectului

Proiectul conține următoarele componente principale:

- `src/main.cpp` — simulator secvențial C++
- `src/mpi_main.cpp` — simulator distribuit MPI C++
- `build.bat` — script de compilare secvențială pe Windows
- `build-mpi.bat` — script de compilare MPI pe Windows
- `benchmark.py` — suită de benchmark pentru compararea performanței
- `plot_results.py` — generator de grafice pentru datele benchmark
- `gui.py` — aplicație Tkinter pentru vizualizare interactivă
- `RAPORT-DOCUMENTATIE.md` — documentație tehnică a proiectului

### 2.1 Comportament și output

Simularea produce imagini PPM ale stării finale și ale snapshot-urilor la pași regulați. Fiecare celulă are o stare binară: albă sau neagră, iar furnicile sunt reprezentate în roșu în output-ul vizual.

Snapshot-urile PPM sunt opționale și se activează prin parametrul `-k`. Aceste fișiere permit urmărirea evoluției simulării la intervale de timp prestabilite.

Imagine finală secvențială:

![Imagine finală secvențială](output_final.ppm)

Imagine finală MPI:

![Imagine finală MPI](output_final_mpi.ppm)

---

## 3. Fundamentele Langton's Ant

Langton's Ant este un model de automat celular cu reguli simple, dar cu comportament emergent complex:

1. Citește culoarea celulei curente: alb sau negru
2. Dacă celula este albă, întoarce 90° la dreapta; dacă este neagră, întoarce 90° la stânga
3. Inversează culoarea celulei curente
4. Avansează un pas înainte

Direcțiile sunt codificate astfel:

- `0` = Nord
- `1` = Est
- `2` = Sud
- `3` = Vest

Pe termen lung, chiar și o singură furnică poate genera structuri complexe, inclusiv un "highway" periodic care apare după câteva mii de pași.

Acest comportament emergent este motivul pentru care modelul este interesant: reacții locale simple pot conduce la o dinamică globală neanticipată, iar simularea pe mulți pași devine necesară pentru a observa structurile care apar.

---

## 4. Arhitectura tehnică

### 4.1 Simulatorul secvențial

`src/main.cpp` construiește o grilă `N × N` stocată ca un `vector<uint8_t>` și o listă de structuri `Ant`.

Structura `Ant` conține:

- `id` — identificator unic
- `x, y` — coordonate curente
- `dir` — direcția curentă
- `steps_matching` și istoricul de mișcare pentru detectarea highway-ului

La fiecare pas, simularea actualizează culoarea celulei, rotirea furnicii și mișcarea acesteia. Dacă opțiunea `-k` este setată, se salvează un snapshot PPM la intervale regulate.

### 4.2 Simulatorul MPI

`src/mpi_main.cpp` extinde modelul secvențial cu:

- partiționare 1D pe rânduri
- ghost rows pentru a gestiona frontierele locale
- schimb de mesaje `MPI_Sendrecv`
- migrare de ant între procese
- export PPM la rank 0 pentru output global

Fiecare proces prelucrează un subset de rânduri ale grilei și comunică doar două rânduri per pas către procesele vecine. Aceasta înseamnă că, în loc să sincronizeze întreaga grilă la fiecare pas, comunicarea se limitează la marginile necesare pentru a calcula starea celulelor de frontieră.

### 4.3 Partiționarea domeniului

Partiționarea folosește o distribuție egală a rândurilor:

```cpp
int base = N / world_size;
int remainder = N % world_size;
for (int rank = 0; rank < world_size; ++rank) {
  row_start[rank] = offset;
  row_count[rank] = base + (rank < remainder ? 1 : 0);
  offset += row_count[rank];
}
```

Această strategie menține sarcina de lucru echilibrată pentru P procese. Dacă `N` nu se împarte exact la `world_size`, primele procese primesc câte un rând în plus, ceea ce evită ca un proces să aibă semnificativ mai puțin de calculat.

Rândurile alocate sunt izolate astfel încât fiecare proces să poată actualiza intern celulele fără a avea nevoie de acces direct la toată grila globală. Singurele informații externe necesare sunt ghost rows și migrările de furnică.

### 4.4 Migrarea furnicilor

În versiunea MPI, fiecare proces deține doar un sub-set de rânduri din grila globală. Când o furnică se deplasează, este posibil să părăsească domeniul local și să ajungă în rândurile unui proces vecin. Pentru a trata această situație fără a transfera instantaneu întreaga structură de date a furnicii, se folosește un mecanism de migrare bazat pe intenții.

Conceptul de `Intent` reprezintă o notificare mică și eficientă:

- `Intent` conține poziția finală a furnicii după pas, procesul țintă și direcția actualizată după rotație.
- El reprezintă faptul că o furnică a „intenționat” să traverseze frontiera și trebuie preluată de procesul vecin.

Fluxul este următorul:

1. Procesul local actualizează starea tuturor furnicilor care rămân în domeniul său.
2. Dacă o furnică iese în afara blocului de rânduri gestionat de proces, se generează un `Intent` în loc să se modifice imediat lista globală.
3. Toate intenturile către procese vecine sunt schimbate prin mesaje MPI între rank-uri.
4. Procesele primitoare recepționează intenturile și recreează furnicile în lista locală, folosind poziția și direcția transmise.
5. La pasul următor, aceste furnici noi sunt tratate ca membri obișnuiți ai sub-domeniului local.

Această abordare reduce costul de comunicație, deoarece se transmit doar date esențiale pentru fiecare furnică care traversează frontiera. De asemenea, separă clar calculul local de gestiunea migrării, ceea ce simplifică sincronizarea între procese.

Mai precis, intenturile permit ca traseul unei furnici să fie finalizat local până la frontieră, iar apoi noul proprietar primește doar informațiile necesare pentru a continua simularea în secțiunea sa de grilă.

---

## 5. Build și rulare

### 5.1 Build secvențial

```powershell
cd "c:\Users\Iulian\Desktop\AgPA\Proiect-EXAMEN"
.\build.bat
```

Executabilul rezultat:

- `build\langton.exe`

### 5.2 Build MPI

```powershell
cd "c:\Users\Iulian\Desktop\AgPA\Proiect-EXAMEN"
.\build-mpi.bat
```

Executabilul rezultat:

- `build-mpi\langton_mpi.exe`

### 5.3 Rulare secvențială

```powershell
build\langton.exe -n 500 -t 10000 -a 5 -k 100
```

### 5.4 Rulare MPI

```powershell
mpiexec -n 4 build-mpi\langton_mpi.exe -n 1000 -t 10000 -a 20 -k 100
```

### 5.5 Interfața GUI

```powershell
python gui.py
```

---

## 6. Benchmark și performanță

Benchmark-ul compară rularea secvențială cu execuția MPI și salvează rezultatele în `benchmark_results.json`.

### 6.1 Generare grafice

```powershell
python plot_results.py
```

Graficul generat:

![Benchmark plots](benchmark_plots.png)

### 6.2 Rezultate observate

- Strong scaling: creștere de performanță cu P, dar cu eficiență descrescătoare
- Weak scaling: timp aproape constant pentru date proporționale per proces
- Costul principal este comunicarea ghost rows și exportul PPM periodic

Interpretare:

- `Strong scaling` măsoară cum scade timpul total când păstrăm fix mărimea problemei și creștem numărul de procese. Ideal, timpul scade invers proporțional cu P.
- `Weak scaling` măsoară cum se comportă sistemul când mărimea problemei crește proporțional cu numărul de procese, astfel încât fiecare proces are aceeași cantitate de lucru. Ideal, timpul rămâne constant.

Explicare termeni:

- `ghost rows`
  - Fiecare proces deține doar un bloc de rânduri din grila globală.
  - Pentru a calcula starea celulelor de frontieră, procesul trebuie să cunoască valorile rândurilor adiacente de la procesul vecin.
  - Aceste rânduri adiacente se numesc `ghost rows` și sunt schimbate în mod repetat între procese cu `MPI_Sendrecv`.
  - Comunicarea acestor rânduri introduce latență și overhead de bandă, mai ales când procesele sunt multe.

- `exportul PPM periodic`
  - Dacă aplicația scrie imagini PPM la intervale regulate (`-k`), atunci procesul MPI trebuie să colecteze sau să combine datele din toate procesele și să scrie un fișier global.
  - Scrierea PPM este o operație de I/O costisitoare și poate bloca execuția dacă se face frecvent.
  - Sincronizarea necesară pentru a produce o imagine coerentă din date parțiale crește overhead-ul în MPI.

Din aceste motive, chiar dacă fiecare proces face calcul local eficient, performanța totală depinde și de comunicarea de frontieră și de I/O-ul de vizualizare.

### 6.3 Interpretare

- Linia ideală de speedup arată un comportament linear.
- Valorile măsurate pot fi sub ideal datorită overhead-ului de comunicare și sincronizare.
- Graficele din `benchmark_plots.png` oferă o evaluare clară a eficienței MPI la P=2 și P=4.

---

## 7. Concluzii

Proiectul oferă o demonstrație practică a paralelizării unei simulări de automat celular. Arhitectura MPI este eficientă pentru grile mari și un număr moderat de procese, iar structura proiectului permite extindere către partiționare 2D, load balancing dinamic și accelerare hardware.

### 7.1 Puncte forte

- implementare completă secvențială și MPI
- bază de cod clară și modulară
- suport pentru vizualizare și benchmark
- informații de proiectare documentate

### 7.2 Direcții viitoare

- reducerea frecvenței snapshot-urilor pentru a scădea costul I/O
- implementarea unui algoritm ring-pass în loc de Allgather pentru anumite tranzacții
- load balancing dinamic atunci când agenții se concentrează într-o regiune
- accelerare GPU/CUDA pentru calcul local
- extindere la partiționare 2D pentru grile foarte mari

---

## 8. Bibliografie

1. **Langton, C. G.** (1986). "Studying artificial life with cellular automata." *Physica D: Nonlinear Phenomena*, 22(1–3), 120–149.
2. **Wolfram, S.** (2002). *A New Kind of Science*. Wolfram Media.
3. **Bunimovich, L. A., & Troubetzkoy, S. E.** (1992). "Recurrence properties of Lorentz lattice gas cellular automata." *Journal of Statistical Physics*, 67(1–2), 289–302.
4. **MPI Forum.** (2021). *MPI: A Message-Passing Interface Standard, Version 4.0*.
5. **Open MPI Development Team.** (2024). *Open MPI Documentation, Version 5.0*.
