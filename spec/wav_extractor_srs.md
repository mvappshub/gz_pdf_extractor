
## Co je “wav extractor”

WAV extractor prochází složku s WAV soubory (a ZIPy, včetně vnořených ZIPů), zjistí délku každého WAVu a pomocí AI (OpenRouter) se pokusí určit, ke které straně (A/B/…) a jaké pozici na desce patří. Výsledky seskupí po “albech” a uloží jako JSON.

### Co dělá krok za krokem
- Najde .wav soubory v zadaném adresáři a ve všech ZIP archivech (rekurzivně).
- Změří délku každého WAVu pomocí Python `wave` modulu:
  - Načte WAV soubor do paměti jako bytes (z disku nebo ze ZIP archivu)
  - Otevře ho pomocí `wave.open()` pro čtení WAV hlaviček
  - Získá počet snímků (`getnframes()`) a vzorkovací frekvenci (`getframerate()`)
  - Vypočítá délku: `duration = frames / sample_rate`
  - Vrátí výsledek v sekundách (float) i ve formátu mm:ss s nulovým paddingem
  - Při chybě vrátí 0.0 a "00:00" s varováním
- Seskupí soubory do “alb”:
  - Pokud je WAV uvnitř ZIPu, název alba je jméno toho ZIPu (bez .zip).
  - Jinak použije nadřazený adresář souboru; fallback je “root”.
- Pro každé album zavolá LLM (OpenRouter) s promptem, kde mu předá seznam souborů a jejich cesty a požádá ho o identifikaci:
  - side: A/B/C/… nebo “Unknown”
  - position: pořadí skladby jako integer
- Výsledek na album seřadí (podle side A<B<C… a position) a uloží do souboru output-wav/<album>.json.
- Výstup je optimalizován pro párování s PDF daty a obsahuje pouze klíčové informace.
- Na konci vytiskne souhrn (počet zpracovaných souborů, časy, výstupní složku).

### Výstupní JSON (na album)
Výstup obsahuje:
- source_type: "wav"
- path_id: identifikátor generovaný z cesty
- tracks: seznam tracků, každá položka má:
  - filename: název souboru
  - side: A/B/C/… nebo "Unknown"
  - position: pořadí skladby jako integer
  - duration_seconds: přesná délka v sekundách (float)
  - duration_formatted: standardizovaný formát MM:SS

Krátký příklad položky:
- filename: "A1 - Intro.wav"
- side: "A"
- position: 1
- duration_seconds: 225.0
- duration_formatted: "03:45"

### Jak spustit
- Závislosti: wave je v Pythonu standardně; pro AI identifikaci je potřeba OpenAI client a dotenv (viz requirements.txt v projektu).
- Nastavte proměnné prostředí:
  - OPENROUTER_API_KEY (povinné)
  - OPENROUTER_MODEL (volitelné; default "google/gemini-2.5-flash")
- Spuštění:
  - python wav_extractor.py "C:\cesta\k\wavum\nebo\zipum"
  - Výstup: složka output-wav v kořeni projektu

Poznámky:
- Pokud AI volání selže, skript použije vylepšený fallback, který analyzuje názvy souborů (A1, A-2, SideA_01 atd.) místo vrácení "Unknown/0".
- "workers" argument je momentálně jen placeholder (konkurenci pro WAVy nevyužívá, AI se volá po albech jednou). Pokud chcete, můžu poradit, jak doplnit paralelizaci.


příklad výstupu:

{
  "source_type": "wav",
  "source_path": "F:\\path\\to\\wav_files",
  "path_id": "unique_wav_id",
  "tracks": [
    {
      "filename": "A1 - Track One.wav",
      "side": "A",
      "position": 1,
      "duration_seconds": 180.0,
      "duration_formatted": "03:00"
    },
    {
      "filename": "A2 - Track Two.wav",
      "side": "A",
      "position": 2,
      "duration_seconds": 200.0,
      "duration_formatted": "03:20"
    },
    {
      "filename": "B1 - Track Four.wav",
      "side": "B",
      "position": 1,
      "duration_seconds": 240.0,
      "duration_formatted": "04:00"
    },
    {
      "filename": "B2 - Track Five.wav",
      "side": "B",
      "position": 2,
      "duration_seconds": 210.0,
      "duration_formatted": "03:30"
    }
  ],
  "side_durations": {
    "A": "06:20",
    "B": "07:30"
  }
}
