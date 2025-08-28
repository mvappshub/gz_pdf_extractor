
## K čemu slouží “pdf extractor”

“pdf extractor” je nástroj, který hromadně prochází složky s PDF (a ZIPy obsahujícími PDF) a vytahuje z nich strukturované informace o vinylových deskách. Z textu v PDF se pomocí AI vyrobí jednotný JSON se základními metadaty a tracklistem včetně součtů délek stran.

### Co přesně dělá
- Najde všechny PDF soubory v zadané složce (umí i ZIPy a vnořené ZIPy).
- Z každého PDF vytěží text (pdfplumber).
- Pošle text do AI (OpenRouter) s požadavkem na normalizovaný JSON obsahující:
  - artist, title, catalog_no, year, label, format
  - genre (seznam)
  - tracks: položky se side (A/B/…), position (1/2/… jako integer), title, duration
- Spočítá dobu trvání v sekundách a standardizovaný formát MM:SS pro každý track.
- Vytvoří zjednodušený výstup optimalizovaný pro párování s WAV daty.
- Uloží výsledky jako jeden .json soubor na jedno PDF do složky output-pdf.
- Běží souběžně (výchozí 5 vláken, max 10) a ukládá chybové logy, pokud něco selže.

### Vstupy a výstupy
- Vstup: cesta ke složce s .pdf a/nebo .zip soubory.
- Výstup: Zjednodušené JSON soubory optimalizované pro párování s WAV daty, uložené do složky output-pdf.
- Formát výstupu obsahuje: source_type, path_id, catalog_no a tracks s přesnými časy.

Příklad spouštění:
- Instalace závislostí: pip install -r requirements.txt
- Běh: python pdf_extractor.py "C:\cesta\k\souborum" --output "output-pdf" -w 5
- Ve repo je i run_pdfs.bat pro rychlé spuštění s ukázkovou cestou.

### Co potřebujete
- .env s OPENROUTER_API_KEY (přístupový klíč k OpenRouter). Volitelně OPENROUTER_MODEL (např. výchozí je google/gemini-2.0-flash-exp:free).
- Volitelně soubor normalize.txt, kterým můžete přepsat výchozí prompt pro normalizaci (jinak se použije zabudovaný).

### Chování při chybách
- Když se nepodaří vytěžit text z PDF, nástroj to zaloguje a pokračuje.
- Při selhání AI/parsování uloží k souboru i .txt s chybovou zprávou a náhledem vytěženého textu.

### Omezení a poznámky
- Nejlépe funguje u textových PDF. Skeny/obrázkové PDF bez OCR textu nepůjdou dobře zpracovat (OCR tento nástroj sám nedělá).
- Struktura tracků závisí na tom, co je v PDF – AI se snaží text rozumně napárovat na požadovaná pole.

příklad výstupu:

{
  "source_type": "pdf",
  "source_path": "F:\\path\\to\\file.pdf",
  "path_id": "unique_id_here",
  "tracks": [
    {
      "title": "Track One",
      "side": "A",
      "position": 1,
      "duration_seconds": 180,
      "duration_formatted": "03:00"
    },
    {
      "title": "Track Two",
      "side": "A",
      "position": 2,
      "duration_seconds": 200,
      "duration_formatted": "03:20"
    },
    {
      "title": "Track Three",
      "side": "B",
      "position": 1,
      "duration_seconds": 240,
      "duration_formatted": "04:00"
    },
    {
      "title": "Track Four",
      "side": "B",
      "position": 2,
      "duration_seconds": 210,
      "duration_formatted": "03:30"
    }
  ],
  "side_durations": {
    "A": "06:20",
    "B": "07:30"
  }
}

