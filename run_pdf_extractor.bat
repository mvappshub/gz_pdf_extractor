@echo off
echo Spoustim extrakci z PDF souboru...

:: 1. Aktivace virtualniho prostredi
call venv\Scripts\activate.bat

:: 2. Spusteni skriptu s pevne definovanou VSTUPNI a VYSTUPNI slozkou
::    ZDE MUZETE SNADNO UPRAVIT OBĚ CESTY
python pdf_extractor.py "C:\gz_projekt\data-for-testing\01" -o "C:\Users\marti\Desktop\pdf extractor\output-pdf"

:: 3. Deaktivace virtualniho prostredi
call deactivate

echo.
echo Zpracovani dokonceno. Stisknete klavesu pro ukonceni.
pause