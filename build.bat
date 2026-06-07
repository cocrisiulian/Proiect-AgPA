@echo off
setlocal

call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
if errorlevel 1 exit /b 1

if not exist build mkdir build
cd /d build
cl /nologo /std:c++17 /EHsc /O2 ..\src\main.cpp /Fe:langton.exe
