@echo off
REM Spouštěcí skript pro PDF Extractor s multi-model podporou
REM Zkopírujte jako run_multimodel.bat a upravte podle potřeby

echo ===================================
echo PDF Extractor - Multi-Model verze
echo ===================================

REM Aktivace virtuálního prostředí (pokud existuje)
if exist "venv\Scripts\activate.bat" (
    echo Aktivuji virtuální prostředí...
    call venv\Scripts\activate.bat
)

REM Kontrola, zda existuje konfigurační soubor
if not exist "config.yaml" (
    if not exist "config.json" (
        echo VAROVÁNÍ: Nenalezen konfigurační soubor config.yaml nebo config.json
        echo Zkopírujte config_example.yaml jako config.yaml a upravte podle potřeby
        echo.
        pause
        exit /b 1
    )
)

REM Kontrola environment proměnných
if "%OPENROUTER_API_KEY%"=="" (
    echo VAROVÁNÍ: OPENROUTER_API_KEY není nastavena
    echo Nastavte ji v .env souboru nebo jako environment proměnnou
    echo.
)

echo Spouštím PDF Extractor...
echo.

REM Spuštění s výchozí konfigurací
python pdf_extractor_multimodel.py

echo.
echo Zpracování dokončeno!
pause
