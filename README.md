README.md – finální verze (s **explicitní verzí Pythonu 3.11+**)

```markdown
# PDF Extractor – rychlé zprovoznění

Tento nástroj automaticky extrahuje tracklisty z PDF (včetně PDF ukrytých v ZIP) pomocí **Google Gemini 2.5 Flash** a uloží je jako čistý JSON.

🔗 **Oficiální repo:** https://github.com/mvappshub/gz_pdf_extractor

---

## 1. Předpoklady
- **Windows 10/11**  
- **Python 3.11+ 64-bit** (musí být dostupný jako `py -3.11`)  
  ```powershell
  py -3.11 --version   # ověř verzi
  ```
- **PowerShell 7+** (volitelné, ale doporučené)  
  ```powershell
  pwsh --version
  ```

---

## 2. Krok za krokem

### 2.1 Klonuj repozitář
```powershell
git clone https://github.com/mvappshub/gz_pdf_extractor.git
cd gz_pdf_extractor
```

### 2.2 Vytvoření prostředí **přesně s Python 3.11**
```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate          # PowerShell
# nebo .venv\Scripts\activate.bat pro cmd
```

### 2.3 Instalace závislostí
```powershell
pip install -r requirements.txt
```

### 2.4 Nastavení klíče
1. Zkopíruj `.env.example` na `.env`  
   ```powershell
   copy .env.example .env
   ```
2. Otevři `.env` a vlož **skutečný** klíč od OpenRouter:  
   ```
   OPENROUTER_API_KEY=sk-tvoj-tajny-klíč
   OPENROUTER_MODEL=google/gemini-2.5-flash
   MAX_WORKERS=4
   ```

> Klíč získáš na [openrouter.ai/keys](https://openrouter.ai/keys)

---

## 3. Spuštění

### 3.1 Rychlé spuštění z PowerShellu
```powershell
.\run.bat "C:\Moje PDF Sbírka"
```
Hotovo – výsledky najdeš ve `output-pdf\`.

### 3.2 Manuálně (libovolný shell)
```powershell
py -3.11 src\main.py "C:\Moje PDF Sbírka"
```

---

## 4. Co se stane
1. Skript projde adresář **rekurzivně** a najde všechny PDF i ZIP.  
2. Každé PDF pošle do OpenRouter → vrátí JSON.  
3. Výsledky uloží do `output-pdf\<název_pdf>.json`.  
4. Chyby se zapíší do `logs/errors.jsonl` – **běh se nikdy nezastaví**.

---

## 5. Výstupní příklad
`output-pdf\my_album.json`
```json
{
  "source_type": "pdf",
  "source_path": "C:\\Moje PDF Sbírka\\my_album.pdf",
  "tracks": [
    {
      "title": "Intro",
      "side": "A",
      "position": 1,
      "duration_seconds": 92,
      "duration_formatted": "01:32"
    }
  ],
  "side_durations": {
    "A": "20:15",
    "B": "18:42"
  }
}
```

---

## 6. Časté otázky

| Otázka | Řešení |
|--------|--------|
| ZIP je heslovaný | automaticky přeskočeno + log |
| API vrací 429 | retry 3×, pak přeskočit |
| Chci jiný model | uprav pouze `.env`, kód se nemění |
| Kolik vláken? | v `.env` nastav `MAX_WORKERS=1..10` |

---

## 7. Aktualizace a formátování
```powershell
py -3.11 -m black src tests
py -3.11 -m ruff check --fix src tests
```

---

## 8. Odinstalace
```powershell
deactivate   # opustit venv
rmdir /s .venv
```
```