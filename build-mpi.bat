@echo off
setlocal enabledelayedexpansion

rem Ensure script runs from project root regardless of current working directory.
cd /d "%~dp0"

if not exist build-mpi mkdir build-mpi
cd /d "%~dp0build-mpi"

if not "%MSMPI_INC%"=="" (
    echo Microsoft MPI detected. Compiling using MSVC cl.exe...
    call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
    
    set "MSMPI_INC_CLEAN=%MSMPI_INC%"
    if "!MSMPI_INC_CLEAN:~-1!"=="\" set "MSMPI_INC_CLEAN=!MSMPI_INC_CLEAN:~0,-1!"
    
    set "MSMPI_LIB64_CLEAN=%MSMPI_LIB64%"
    if "!MSMPI_LIB64_CLEAN:~-1!"=="\" set "MSMPI_LIB64_CLEAN=!MSMPI_LIB64_CLEAN:~0,-1!"
    
    cl /nologo /std:c++17 /EHsc /O2 /I "!MSMPI_INC_CLEAN!" ..\src\mpi_main.cpp /link /LIBPATH:"!MSMPI_LIB64_CLEAN!" msmpi.lib /out:langton_mpi.exe
    exit /b !errorlevel!
)

set MPI_COMPILER=
where mpicxx >nul 2>nul
if not errorlevel 1 set MPI_COMPILER=mpicxx
where mpic++ >nul 2>nul
if not errorlevel 1 if "%MPI_COMPILER%"=="" set MPI_COMPILER=mpic++
where mpicc >nul 2>nul
if not errorlevel 1 if "%MPI_COMPILER%"=="" set MPI_COMPILER=mpicc

if "%MPI_COMPILER%"=="" (
    echo ERROR: MPI compiler wrapper not found in PATH.
    echo Install Open MPI, MPICH, or Microsoft MPI and add mpicxx/mpic++/mpicc to PATH.
    exit /b 1
)

"%MPI_COMPILER%" ..\src\mpi_main.cpp -O2 -std=c++17 -o langton_mpi.exe
