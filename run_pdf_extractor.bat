@echo off
echo Spoustim extrakci z PDF souboru...

:: 1. Aktivace virtualniho prostredi (pokud ho pouzivate)
call venv\Scripts\activate.bat

:: 2. Spusteni skriptu s konfiguracnim souborem
python pdf_extractor.py --config config.json

:: 3. Deaktivace virtualniho prostredi (pokud ho pouzivate)
call deactivate

echo.
echo Zpracovani dokonceno. Stisknete klavesu pro ukonceni.
pause