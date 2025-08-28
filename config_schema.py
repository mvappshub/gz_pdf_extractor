"""
Konfigurační schéma pro multi-provider AI systém
Definuje struktury pro různé AI providery a jejich modely
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
import os
import json
import yaml
from pathlib import Path


class ModelConfig(BaseModel):
    """Konfigurace jednotlivého modelu"""
    id: str = Field(..., description="Unikátní identifikátor modelu")
    name: str = Field(..., description="Lidsky čitelný název modelu")
    max_tokens: int = Field(default=4096, ge=1, le=100000)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    cost_per_1k_tokens: float = Field(default=0.0, ge=0.0, description="Cena za 1000 tokenů")
    description: Optional[str] = Field(default="", description="Popis modelu")
    
    @validator('id')
    def validate_id(cls, v):
        if not v or not v.strip():
            raise ValueError("Model ID nesmí být prázdné")
        return v.strip()


class ProviderConfig(BaseModel):
    """Konfigurace AI providera"""
    enabled: bool = Field(default=True, description="Zda je provider aktivní")
    api_key: str = Field(..., description="API klíč (může obsahovat env proměnné)")
    base_url: str = Field(..., description="Základní URL pro API")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout v sekundách")
    retry_attempts: int = Field(default=3, ge=1, le=10, description="Počet pokusů při chybě")
    auto_discover_models: bool = Field(default=False, description="Automaticky načítat modely z API")
    models: List[ModelConfig] = Field(default_factory=list, description="Seznam dostupných modelů")
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or not v.strip():
            raise ValueError("API klíč nesmí být prázdný")
        return v.strip()
    
    @validator('base_url')
    def validate_base_url(cls, v):
        if not v or not v.strip():
            raise ValueError("Base URL nesmí být prázdná")
        # Základní validace URL formátu
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("Base URL musí začínat http:// nebo https://")
        return v.strip().rstrip('/')


class DefaultsConfig(BaseModel):
    """Výchozí nastavení"""
    provider: str = Field(..., description="Výchozí provider")
    model: str = Field(..., description="Výchozí model")
    fallback_provider: Optional[str] = Field(default=None, description="Záložní provider")
    fallback_model: Optional[str] = Field(default=None, description="Záložní model")


class ProcessingConfig(BaseModel):
    """Konfigurace zpracování"""
    input_directory: str = Field(..., description="Vstupní adresář")
    output_directory: str = Field(..., description="Výstupní adresář")
    max_workers: int = Field(default=4, ge=1, le=32, description="Počet paralelních vláken")
    max_file_size_mb: int = Field(default=1000, ge=1, le=10000, description="Maximální velikost souboru v MB")
    skip_processed: bool = Field(default=True, description="Přeskočit již zpracované soubory")
    batch_size: int = Field(default=10, ge=1, le=1000, description="Velikost dávky")


class PDFConfig(BaseModel):
    """Konfigurace PDF zpracování"""
    max_pages: int = Field(default=50, ge=1, le=1000, description="Maximální počet stránek")
    min_text_length: int = Field(default=100, ge=1, le=10000, description="Minimální délka textu")
    language: str = Field(default="en", description="Jazyk dokumentu")
    extract_images: bool = Field(default=False, description="Extrahovat obrázky")


class AdvancedConfig(BaseModel):
    """Pokročilá nastavení"""
    log_level: str = Field(default="INFO", description="Úroveň logování")
    save_extracted_text: bool = Field(default=False, description="Uložit extrahovaný text")
    enable_metrics: bool = Field(default=True, description="Povolit metriky")
    enable_cost_tracking: bool = Field(default=True, description="Sledovat náklady")
    auto_retry_on_failure: bool = Field(default=True, description="Automaticky opakovat při chybě")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level musí být jeden z: {valid_levels}")
        return v.upper()


class AppConfig(BaseModel):
    """Hlavní konfigurační třída"""
    providers: Dict[str, ProviderConfig] = Field(..., description="Konfigurace providerů")
    defaults: DefaultsConfig = Field(..., description="Výchozí nastavení")
    processing: ProcessingConfig = Field(..., description="Konfigurace zpracování")
    pdf: PDFConfig = Field(..., description="Konfigurace PDF")
    advanced: AdvancedConfig = Field(..., description="Pokročilá nastavení")
    
    @validator('providers')
    def validate_providers(cls, v):
        if not v:
            raise ValueError("Musí být definován alespoň jeden provider")
        return v
    
    def validate_references(self):
        """Validuje odkazy mezi sekcemi konfigurace"""
        # Kontrola, zda výchozí provider existuje
        if self.defaults.provider not in self.providers:
            raise ValueError(f"Výchozí provider '{self.defaults.provider}' není definován")
        
        # Kontrola, zda výchozí model existuje u výchozího providera
        default_provider = self.providers[self.defaults.provider]
        model_ids = [m.id for m in default_provider.models]
        if self.defaults.model not in model_ids:
            raise ValueError(f"Výchozí model '{self.defaults.model}' není definován u providera '{self.defaults.provider}'")
        
        # Kontrola záložního providera a modelu
        if self.defaults.fallback_provider:
            if self.defaults.fallback_provider not in self.providers:
                raise ValueError(f"Záložní provider '{self.defaults.fallback_provider}' není definován")
            
            if self.defaults.fallback_model:
                fallback_provider = self.providers[self.defaults.fallback_provider]
                fallback_model_ids = [m.id for m in fallback_provider.models]
                if self.defaults.fallback_model not in fallback_model_ids:
                    raise ValueError(f"Záložní model '{self.defaults.fallback_model}' není definován u providera '{self.defaults.fallback_provider}'")


class ConfigManager:
    """Správce konfigurace s podporou načítání z různých formátů"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config: Optional[AppConfig] = None
    
    def load_config(self, config_path: Optional[str] = None) -> AppConfig:
        """Načte konfiguraci ze souboru"""
        if config_path:
            self.config_path = config_path
        
        if not self.config_path:
            # Pokusí se najít konfigurační soubor
            self.config_path = self._find_config_file()
        
        if not self.config_path or not os.path.exists(self.config_path):
            # Vytvoří výchozí konfiguraci
            self.config = self._create_default_config()
            return self.config
        
        # Načte konfiguraci ze souboru
        try:
            config_data = self._load_config_file(self.config_path)

            # Rozšíří environment proměnné
            config_data = self._expand_env_variables(config_data)

            # Vytvoří a validuje konfiguraci
            self.config = AppConfig(**config_data)
            self.config.validate_references()

            return self.config
        except Exception as e:
            # Při chybě načítání použije výchozí konfiguraci
            print(f"Varování: Nepodařilo se načíst konfiguraci z {self.config_path}: {e}")
            print("Používám výchozí konfiguraci.")
            self.config = self._create_default_config()
            return self.config
    
    def _find_config_file(self) -> Optional[str]:
        """Najde konfigurační soubor v aktuálním adresáři"""
        possible_names = [
            'config.yaml', 'config.yml', 'config.json',
            'app_config.yaml', 'app_config.yml', 'app_config.json'
        ]
        
        for name in possible_names:
            if os.path.exists(name):
                return name
        
        return None
    
    def _load_config_file(self, path: str) -> dict:
        """Načte konfigurační soubor (YAML nebo JSON)"""
        with open(path, 'r', encoding='utf-8') as f:
            if path.endswith(('.yaml', '.yml')):
                return yaml.safe_load(f)
            else:
                return json.load(f)
    
    def _expand_env_variables(self, data: Any) -> Any:
        """Rozšíří environment proměnné v konfiguraci"""
        if isinstance(data, dict):
            return {k: self._expand_env_variables(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._expand_env_variables(item) for item in data]
        elif isinstance(data, str):
            # Rozšíří ${VAR} a $VAR formáty
            if data.startswith('${') and data.endswith('}'):
                var_name = data[2:-1]
                return os.getenv(var_name, data)
            elif data.startswith('$'):
                var_name = data[1:]
                return os.getenv(var_name, data)
            return data
        else:
            return data
    
    def _create_default_config(self) -> AppConfig:
        """Vytvoří výchozí konfiguraci"""
        return AppConfig(
            providers={
                "openrouter": ProviderConfig(
                    enabled=True,
                    api_key="${OPENROUTER_API_KEY}",
                    base_url="https://openrouter.ai/api/v1",
                    timeout=30,
                    retry_attempts=3,
                    models=[
                        ModelConfig(
                            id="google/gemini-2.5-flash",
                            name="Gemini 2.5 Flash",
                            max_tokens=4096,
                            temperature=0.0,
                            cost_per_1k_tokens=0.001
                        )
                    ]
                ),
                "lm_studio": ProviderConfig(
                    enabled=False,  # Výchozně vypnuté
                    api_key="lm-studio",
                    base_url="http://localhost:1234/v1",
                    timeout=60,
                    retry_attempts=2,
                    auto_discover_models=True,
                    models=[]
                )
            },
            defaults=DefaultsConfig(
                provider="openrouter",
                model="google/gemini-2.5-flash",
                fallback_provider="lm_studio",
                fallback_model=None
            ),
            processing=ProcessingConfig(
                input_directory="./input",
                output_directory="./output-pdf",
                max_workers=4,
                max_file_size_mb=1000,
                skip_processed=True,
                batch_size=10
            ),
            pdf=PDFConfig(
                max_pages=50,
                min_text_length=100,
                language="en",
                extract_images=False
            ),
            advanced=AdvancedConfig(
                log_level="INFO",
                save_extracted_text=False,
                enable_metrics=True,
                enable_cost_tracking=True,
                auto_retry_on_failure=True
            )
        )
    
    def save_config(self, path: Optional[str] = None, format: str = 'yaml') -> str:
        """Uloží konfiguraci do souboru"""
        if not self.config:
            raise ValueError("Žádná konfigurace není načtena")
        
        if not path:
            path = f"config.{format}"
        
        config_dict = self.config.model_dump()
        
        with open(path, 'w', encoding='utf-8') as f:
            if format.lower() in ['yaml', 'yml']:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True, indent=2)
            else:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        return path
