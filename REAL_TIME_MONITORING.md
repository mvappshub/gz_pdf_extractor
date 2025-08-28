# Real-Time Monitoring - Vinyl Record Viewer

## Přehled

Aplikace Vinyl Record Viewer nyní podporuje real-time monitoring dat z adresářů `output-pdf` a `output-pdf/logs`. Automaticky detekuje změny v JSON souborech a log souborech a obnovuje zobrazení v reálném čase.

## Nové funkce

### 1. Automatické obnovování dat
- **Interval**: Výchozí 5 sekund (konfigurovatelný)
- **Monitorované soubory**:
  - `output-pdf/*.json` - Alba a tracklist data
  - `output-pdf/logs/errors.jsonl` - Error logy
  - `output-pdf/logs/logs.jsonl` - Obecné logy

### 2. Menu "Monitoring"
Nové menu s následujícími možnostmi:
- **Automatické obnovování** - Zapnutí/vypnutí real-time monitoringu
- **Obnovit nyní** - Ruční obnovení všech dat
- **Nastavení intervalu** - Změna intervalu kontroly (1-999 sekund)

### 3. Status indikátor
V status baru se zobrazuje:
- 🟢 AUTO - Automatické obnovování je zapnuto
- 🔴 MANUAL - Automatické obnovování je vypnuto

## Jak to funguje

### Detekce změn
Aplikace kontroluje čas poslední modifikace souborů:
- Při každé kontrole porovnává `mtime` souborů s časem poslední kontroly
- Pokud je soubor novější, data se automaticky znovu načtou

### Optimalizace
- Kontroluje se pouze existence a čas modifikace, ne obsah
- Načítají se pouze změněné kategorie dat (alba nebo logy)
- Zachovává se aktuální výběr a filtry

### Podpora více log souborů
Aplikace nyní načítá logy z obou souborů:
- `errors.jsonl` - Chybové logy
- `logs.jsonl` - Obecné logy
- Logy jsou seřazeny podle času (nejnovější první)

## Použití

### Zapnutí/vypnutí monitoringu
1. Menu → Monitoring → Automatické obnovování
2. Nebo použijte checkbox v menu

### Změna intervalu
1. Menu → Monitoring → Nastavení intervalu...
2. Zadejte nový interval v sekundách (1-999)
3. Klikněte "Použít"

### Ruční obnovení
1. Menu → Monitoring → Obnovit nyní
2. Nebo vypněte automatické obnovování a data se budou načítat pouze ručně

## Technické detaily

### Nové atributy třídy
```python
self.monitoring_enabled = True          # Stav monitoringu
self.refresh_interval = 5000           # Interval v ms
self.last_albums_check = 0             # Čas poslední kontroly alb
self.last_logs_check = 0               # Čas poslední kontroly logů
self.current_directory = None          # Aktuální monitorovaný adresář
```

### Klíčové metody
- `start_monitoring()` - Spuštění monitoringu
- `check_for_updates()` - Kontrola aktualizací
- `_has_albums_changed()` - Detekce změn v albech
- `_has_logs_changed()` - Detekce změn v lozích
- `toggle_monitoring()` - Přepnutí monitoringu
- `refresh_data()` - Ruční obnovení

### Výhody real-time monitoringu
1. **Okamžitá vizualizace** - Nová data se zobrazí automaticky
2. **Žádné ruční obnovování** - Aplikace sleduje změny sama
3. **Efektivní** - Kontroluje pouze časy modifikace, ne obsah
4. **Konfigurovatelné** - Uživatel může nastavit interval nebo vypnout
5. **Zachování stavu** - Filtry a výběry zůstávají zachovány

## Podporované formáty logů

### 1. Error logy (errors.jsonl)
```json
{
  "timestamp": "2025-08-28T17:20:08.052204Z",
  "source_id": "test_123",
  "source_path": "/path/to/file.pdf",
  "error": "Chyba při zpracování souboru"
}
```

### 2. Obecné logy (logs.jsonl)
```json
{
  "timestamp": "2025-08-28T17:20:08.052204",
  "level": "INFO",
  "message": "Zpracování dokončeno úspěšně",
  "module": "pdf_extractor",
  "function": "process_file",
  "line": 123
}
```

## Testování real-time funkcionality

### Ruční testování
```bash
# Spusťte GUI aplikaci
python gui.py

# V jiném terminálu spusťte test script
python test_realtime.py
```

### Automatické testování
Test script nabízí několik možností:
1. **Jednotlivé testy** - Vytvoření alba, logu nebo erroru
2. **Kompletní test** - Vytvoření všech typů dat najednou
3. **Automatický test** - Kontinuální vytváření dat každých 10 sekund

## Příklady použití

### Vývoj a testování
- Spusťte aplikaci s automatickým obnovováním
- Spusťte PDF extractor v jiném terminálu
- Sledujte, jak se nová alba a logy objevují v reálném čase

### Monitoring produkce
- Nastavte delší interval (např. 30 sekund) pro produkční prostředí
- Sledujte chyby a úspěšné zpracování v real-time

### Debugging
- Použijte krátký interval (1-2 sekundy) pro rychlé testování
- Okamžitě vidíte výsledky změn v konfiguraci nebo kódu

## Řešení problémů

### Aplikace nenačítá nová data
1. Zkontrolujte, zda je zapnuto automatické obnovování (🟢 AUTO v status baru)
2. Ověřte, že soubory se skutečně mění (čas modifikace)
3. Zkuste ruční obnovení (Menu → Monitoring → Obnovit nyní)

### Pomalé obnovování
1. Zkontrolujte nastavený interval (Menu → Monitoring → Nastavení intervalu)
2. Zkraťte interval pro rychlejší odezvu
3. Ověřte, že není problém s přístupem k souborům

### Chybějící logy
1. Zkontrolujte, zda existuje adresář `output-pdf/logs/`
2. Ověřte, zda obsahuje soubory `logs.jsonl` nebo `errors.jsonl`
3. Zkontrolujte formát JSON v log souborech
