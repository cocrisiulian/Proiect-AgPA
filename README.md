# Langton's Ant Simulator

Acest proiect conține o implementare C++ a automatonului celular Langton's Ant, cu:

- simulator secvențial (`src/main.cpp`)
- simulator distribuit MPI (`src/mpi_main.cpp`)
- interfață GUI Python (`gui.py`)
- scripturi de build pentru Windows
- benchmark și analiză de performanță
- raport tehnic detaliat în `REPORT.md`

## Ce face proiectul

Simularea rulează pe o grilă bidimensională N×N. Fiecare "furnică" alternează culorile celulelor și își schimbă direcția în funcție de culoarea curentă.

Funcționalități principale:

- secvențial și MPI distribuit
- suport pentru mai multe furnici
- torus (wrap-around) implicit, cu opțiune `--no-wrap`
- export PPM al stării finale și al snapshot-urilor periodice
- vizualizare opțională cu interfață Tkinter

## Structură proiect

- `src/main.cpp` — simulator secvențial
- `src/mpi_main.cpp` — simulator MPI cu decompoziție pe rânduri și schimb de ghost rows
- `gui.py` — interfață Tkinter pentru rulare și vizualizare
- `build.bat` — build secvențial cu MSVC
- `build-mpi.bat` — build MPI cu Microsoft MPI sau wrapper MPI din PATH
- `benchmark.py` — suită benchmark și test de validare
- `plot_results.py` — generare grafice de performanță
- `REPORT.md` — documentație tehnică și analiză
- `benchmark_results.json` — rezultate benchmark generate
- `output_final.ppm` / `output_final_mpi.ppm` — fișiere de ieșire PPM

## Cerințe

- Windows
- Visual Studio Build Tools / MSVC pentru `build.bat`
- Microsoft MPI sau Open MPI / MPICH pentru `build-mpi.bat`
- Python 3 pentru `benchmark.py`, `plot_results.py` și `gui.py`
- `matplotlib`, `numpy` pentru `plot_results.py`

## Build

### 1. Build secvențial

```powershell
.build.bat
```

Executabilul rezultat este:

- `build\langton.exe`

### 2. Build MPI

```powershell
.build-mpi.bat
```

Acest script detectează fie Microsoft MPI (`MSMPI_INC` / `MSMPI_LIB64`), fie un wrapper MPI disponibil în `PATH` (`mpicxx`, `mpic++`, `mpicc`). Executabilul rezultat este:

- `build-mpi\langton_mpi.exe`

## Rulare

### Secvențial

```powershell
build\langton.exe -n 500 -t 10000 -a 5 -k 1000
```

### MPI

```powershell
mpiexec -n 4 build-mpi\langton_mpi.exe -n 1000 -t 10000 -a 20 -k 100
```

### GUI

```powershell
python gui.py
```

### Benchmark

```powershell
python benchmark.py
```

### Generare grafice

```powershell
python plot_results.py
```

## Opțiuni CLI

Pentru `build\langton.exe` și `build-mpi\langton_mpi.exe`:

- `-n`, `--size` — dimensiunea grilei N×N (default `200`)
- `-t`, `--steps` — numărul de pași (default `10000`)
- `-a`, `--ants` — numărul de furnici (default `1`)
- `-k`, `--snapshot` — salvează un fișier PPM la fiecare K pași (`0` = doar final)
- `--no-wrap` — dezactivează înfășurarea toroidală
- `-g`, `--gui` — activează modul de ieșire pentru GUI în versiunea secvențială

## Ieșiri importante

- `output_final.ppm` — imagine finală pentru simulatorul secvențial
- `output_final_mpi.ppm` — imagine finală pentru simulatorul MPI
- `output_step_XXXXXX.ppm` — snapshot-uri temporare dacă `-k` este setat
- `benchmark_results.json` — date brute de benchmark
- `benchmark_plots.png` — grafic generat de `plot_results.py`

## Documentație tehnică

Documentația detaliată este în `REPORT.md` și acoperă:

- teoria automatelor celulare
- comportamentul Langton's Ant
- designul implementărilor secvențiale și MPI
- analiza performanței și scalarea
- rezultatele experimentale

---

### Observații

- `build.bat` folosește `cl.exe` și necesită Visual Studio Build Tools.
- `build-mpi.bat` poate compila fie cu Microsoft MPI, fie cu wrapperul MPI disponibil în PATH.
- `gui.py` oferă un front-end vizual, dar simulatorul core al proiectului este implementat în C++.
