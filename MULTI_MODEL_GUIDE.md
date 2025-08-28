# PDF Extractor - Multi-Model AI Guide

Tato příručka popisuje nový multi-model systém pro PDF Extractor, který umožňuje používat více AI providerů a modelů současně.

## 🚀 Nové funkce

- **Více AI providerů**: OpenRouter, LM Studio, možnost přidat další
- **Automatický fallback**: Při selhání jednoho providera se automaticky použije záložní
- **Centrální konfigurace**: Všechna nastavení v jednom YAML/JSON souboru
- **Flexibilní výběr modelů**: Možnost specifikovat konkrétní model nebo provider
- **Sledování nákladů**: Automatické sledování tokenů a nákladů
- **Auto-discovery**: Automatické načítání dostupných modelů z API

## 📋 Požadavky

```bash
pip install pyyaml  # Nová závislost pro YAML podporu
```

## ⚙️ Konfigurace

### 1. Vytvoření konfiguračního souboru

Zkopírujte `config_example.yaml` jako `config.yaml`:

```bash
cp config_example.yaml config.yaml
```

### 2. Nastavení API klíčů

V `.env` souboru:
```env
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

### 3. Konfigurace providerů

V `config.yaml`:

```yaml
providers:
  # OpenRouter - cloudový AI provider
  openrouter:
    enabled: true
    api_key: "${OPENROUTER_API_KEY}"
    base_url: "https://openrouter.ai/api/v1"
    models:
      - id: "google/gemini-2.5-flash"
        name: "Gemini 2.5 Flash"
        max_tokens: 4096
        cost_per_1k_tokens: 0.001

  # LM Studio - lokální AI provider
  lm_studio:
    enabled: true
    api_key: "lm-studio"
    base_url: "http://localhost:1234/v1"
    auto_discover_models: true  # Automaticky načte modely
```

## 🖥️ Použití

### Základní spuštění

```bash
# Použije výchozí konfiguraci
python pdf_extractor_multimodel.py

# Použije vlastní konfiguraci
python pdf_extractor_multimodel.py --config my_config.yaml
```

### Výběr konkrétního modelu

```bash
# Použije konkrétní model
python pdf_extractor_multimodel.py --model "anthropic/claude-3-sonnet"

# Použije konkrétní provider
python pdf_extractor_multimodel.py --provider lm_studio

# Kombinace
python pdf_extractor_multimodel.py --provider openrouter --model "google/gemini-2.5-flash"
```

### Informační příkazy

```bash
# Zobrazí dostupné providery
python pdf_extractor_multimodel.py --list-providers

# Zobrazí dostupné modely
python pdf_extractor_multimodel.py --list-models

# Zobrazí stav providerů
python pdf_extractor_multimodel.py --provider-status
```

## 🏠 Nastavení LM Studio

### 1. Instalace LM Studio

1. Stáhněte LM Studio z [lmstudio.ai](https://lmstudio.ai)
2. Nainstalujte a spusťte aplikaci

### 2. Stažení modelu

1. V LM Studio přejděte na záložku "Discover"
2. Vyhledejte model (např. "llama-3.1-8b-instruct")
3. Stáhněte model

### 3. Spuštění serveru

1. Přejděte na záložku "Developer"
2. Vyberte stažený model
3. Klikněte na "Start Server"
4. Server běží na `http://localhost:1234`

### 4. Ověření připojení

```bash
# Test připojení k LM Studio
curl http://localhost:1234/v1/models
```

## 📊 Sledování metrik

Nový systém automaticky sleduje:

- **Použití tokenů** podle modelů a providerů
- **Náklady** na API volání
- **Úspěšnost** požadavků
- **Výkon** jednotlivých modelů

Metriky se ukládají do `output-pdf/zpracovani_metriky.json`.

## 🔄 Fallback systém

Při selhání primárního providera se automaticky použije záložní:

```yaml
defaults:
  provider: "openrouter"
  model: "google/gemini-2.5-flash"
  fallback_provider: "lm_studio"  # Záložní provider
  fallback_model: "llama-3.1-8b-instruct"  # Záložní model
```

## 🛠️ Přidání nového providera

### 1. Vytvoření provider třídy

```python
from ai_providers import AIProvider

class MyCustomProvider(AIProvider):
    def _create_client(self):
        # Implementace klienta
        pass
    
    def _make_completion_request(self, request):
        # Implementace completion
        pass
```

### 2. Registrace providera

```python
from ai_providers import ProviderFactory

ProviderFactory.register_provider('my_provider', MyCustomProvider)
```

### 3. Konfigurace

```yaml
providers:
  my_provider:
    enabled: true
    api_key: "your-api-key"
    base_url: "https://api.myprovider.com/v1"
    models:
      - id: "my-model"
        name: "My Custom Model"
```

## 🐛 Řešení problémů

### LM Studio se nepřipojuje

1. Ověřte, že LM Studio server běží
2. Zkontrolujte port (výchozí 1234)
3. Ověřte, že je načten model

```bash
# Test připojení
curl http://localhost:1234/v1/models
```

### Chybí API klíč

```
CHYBA: Chybí environment proměnné pro API klíče:
  openrouter: OPENROUTER_API_KEY
```

**Řešení**: Nastavte API klíč v `.env` souboru:
```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### Model není dostupný

```
CHYBA: Model 'my-model' nebyl nalezen.
```

**Řešení**: 
1. Zkontrolujte dostupné modely: `--list-models`
2. Ověřte konfiguraci providera
3. Pro LM Studio ověřte, že je model načten

### Vysoké náklady

**Řešení**:
1. Použijte lokální modely (LM Studio)
2. Nastavte `max_cost_per_1k_tokens` v konfiguraci
3. Sledujte metriky v `zpracovani_metriky.json`

## 📈 Optimalizace výkonu

### Pro rychlost
- Použijte lokální modely (LM Studio)
- Zvyšte `max_workers` v konfiguraci
- Použijte rychlé modely (Gemini Flash)

### Pro kvalitu
- Použijte větší modely (Claude 3 Sonnet)
- Snižte `temperature` na 0.0
- Použijte fallback na kvalitní model

### Pro náklady
- Preferujte lokální modely
- Použijte levnější modely jako primární
- Nastavte drahé modely jako fallback

## 🔗 Migrace ze staré verze

Stará verze (`pdf_extractor.py`) zůstává funkční. Pro migraci:

1. Zkopírujte `config_example.yaml` jako `config.yaml`
2. Přesuňte nastavení z `config.json` do nového formátu
3. Použijte `pdf_extractor_multimodel.py` místo `pdf_extractor.py`

## 📚 Další zdroje

- [LM Studio dokumentace](https://lmstudio.ai/docs)
- [OpenRouter API dokumentace](https://openrouter.ai/docs)
- [Pydantic dokumentace](https://docs.pydantic.dev/) pro konfigurační schémata
