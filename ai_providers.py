"""
Abstraktní AI Provider systém pro multi-model podporu
Definuje rozhraní pro různé AI providery a jejich implementace
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
import logging
import time
import json
from dataclasses import dataclass
from openai import OpenAI
import requests

from config_schema import ProviderConfig, ModelConfig


@dataclass
class CompletionRequest:
    """Request pro AI completion"""
    messages: List[Dict[str, str]]
    model_id: str
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    timeout: Optional[int] = None


@dataclass
class CompletionResponse:
    """Response z AI completion"""
    content: str
    model_used: str
    provider_used: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_estimate: float = 0.0
    processing_time: float = 0.0
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class ModelInfo:
    """Informace o dostupném modelu"""
    id: str
    name: str
    provider: str
    max_tokens: int
    cost_per_1k_tokens: float
    available: bool = True
    description: str = ""


class AIProvider(ABC):
    """Abstraktní třída pro AI providery"""
    
    def __init__(self, name: str, config: ProviderConfig):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"ai_provider.{name}")
        self._client = None
        self._available_models: Optional[List[ModelInfo]] = None
    
    @abstractmethod
    def _create_client(self) -> Any:
        """Vytvoří klienta pro API"""
        pass
    
    @abstractmethod
    def _make_completion_request(self, request: CompletionRequest) -> CompletionResponse:
        """Provede completion request"""
        pass
    
    def get_client(self) -> Any:
        """Získá nebo vytvoří klienta"""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    def is_available(self) -> bool:
        """Zkontroluje, zda je provider dostupný"""
        if not self.config.enabled:
            return False
        
        try:
            # Pokus o jednoduchý test připojení
            models = self.get_available_models()
            return len(models) > 0
        except Exception as e:
            self.logger.warning(f"Provider {self.name} není dostupný: {e}")
            return False
    
    def get_available_models(self) -> List[ModelInfo]:
        """Získá seznam dostupných modelů"""
        if self._available_models is None:
            self._available_models = self._fetch_available_models()
        return self._available_models
    
    def _fetch_available_models(self) -> List[ModelInfo]:
        """Načte dostupné modely (kombinuje konfiguraci a auto-discovery)"""
        models = []
        
        # Přidá modely z konfigurace
        for model_config in self.config.models:
            models.append(ModelInfo(
                id=model_config.id,
                name=model_config.name,
                provider=self.name,
                max_tokens=model_config.max_tokens,
                cost_per_1k_tokens=model_config.cost_per_1k_tokens,
                description=model_config.description,
                available=True
            ))
        
        # Auto-discovery pokud je povoleno
        if self.config.auto_discover_models:
            try:
                discovered_models = self._discover_models()
                # Přidá pouze modely, které nejsou už v konfiguraci
                existing_ids = {m.id for m in models}
                for discovered in discovered_models:
                    if discovered.id not in existing_ids:
                        models.append(discovered)
            except Exception as e:
                self.logger.warning(f"Auto-discovery modelů selhalo: {e}")
        
        return models
    
    def _discover_models(self) -> List[ModelInfo]:
        """Automaticky objeví dostupné modely (implementace v potomcích)"""
        return []
    
    def create_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Vytvoří completion s retry logikou"""
        last_error = None
        
        for attempt in range(self.config.retry_attempts):
            try:
                start_time = time.time()
                response = self._make_completion_request(request)
                response.processing_time = time.time() - start_time
                response.provider_used = self.name
                
                # Výpočet nákladů
                if response.success and response.total_tokens > 0:
                    model_info = self._get_model_info(request.model_id)
                    if model_info:
                        response.cost_estimate = (response.total_tokens / 1000) * model_info.cost_per_1k_tokens
                
                return response
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Pokus {attempt + 1} selhal: {e}")
                
                if attempt < self.config.retry_attempts - 1:
                    # Exponenciální backoff
                    wait_time = (2 ** attempt) * 1
                    self.logger.info(f"Čekám {wait_time}s před dalším pokusem...")
                    time.sleep(wait_time)
        
        # Všechny pokusy selhaly
        return CompletionResponse(
            content="",
            model_used=request.model_id,
            provider_used=self.name,
            success=False,
            error_message=str(last_error)
        )
    
    def _get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """Získá informace o modelu"""
        models = self.get_available_models()
        for model in models:
            if model.id == model_id:
                return model
        return None


class OpenRouterProvider(AIProvider):
    """Provider pro OpenRouter API"""
    
    def _create_client(self) -> OpenAI:
        """Vytvoří OpenAI klienta pro OpenRouter"""
        return OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key
        )
    
    def _make_completion_request(self, request: CompletionRequest) -> CompletionResponse:
        """Provede completion request přes OpenRouter"""
        client = self.get_client()
        
        # Příprava parametrů
        params = {
            "model": request.model_id,
            "messages": request.messages,
            "temperature": request.temperature or 0.0,
            "max_tokens": request.max_tokens or 4096,
            "timeout": request.timeout or self.config.timeout,
            "response_format": {"type": "json_object"}
        }
        
        # API volání
        response = client.chat.completions.create(**params)
        
        # Zpracování odpovědi
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Prázdná odpověď od API")
        
        # Metriky tokenů
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0
        total_tokens = response.usage.total_tokens if response.usage else 0
        
        return CompletionResponse(
            content=content,
            model_used=request.model_id,
            provider_used=self.name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            success=True
        )
    
    def _discover_models(self) -> List[ModelInfo]:
        """Automaticky objeví modely z OpenRouter API"""
        try:
            client = self.get_client()
            models_response = client.models.list()
            
            discovered = []
            for model in models_response.data:
                discovered.append(ModelInfo(
                    id=model.id,
                    name=model.id,  # OpenRouter nemusí mít display name
                    provider=self.name,
                    max_tokens=4096,  # Výchozí hodnota
                    cost_per_1k_tokens=0.001,  # Výchozí hodnota
                    description=f"Auto-discovered model: {model.id}"
                ))
            
            return discovered
        except Exception as e:
            self.logger.error(f"Chyba při auto-discovery OpenRouter modelů: {e}")
            return []


class LMStudioProvider(AIProvider):
    """Provider pro LM Studio lokální API"""
    
    def _create_client(self) -> OpenAI:
        """Vytvoří OpenAI klienta pro LM Studio"""
        return OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key  # LM Studio používá "lm-studio"
        )
    
    def _make_completion_request(self, request: CompletionRequest) -> CompletionResponse:
        """Provede completion request přes LM Studio"""
        client = self.get_client()
        
        # Příprava parametrů (LM Studio má podobné API jako OpenAI)
        params = {
            "model": request.model_id,
            "messages": request.messages,
            "temperature": request.temperature or 0.0,
            "max_tokens": request.max_tokens or 4096,
            "timeout": request.timeout or self.config.timeout,
            "response_format": {"type": "json_object"}
        }
        
        # API volání
        response = client.chat.completions.create(**params)
        
        # Zpracování odpovědi
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Prázdná odpověď od LM Studio")
        
        # Metriky tokenů (LM Studio může mít omezenější usage info)
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0
        total_tokens = response.usage.total_tokens if response.usage else 0
        
        return CompletionResponse(
            content=content,
            model_used=request.model_id,
            provider_used=self.name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            success=True
        )
    
    def _discover_models(self) -> List[ModelInfo]:
        """Automaticky objeví modely z LM Studio API"""
        try:
            # Použije requests pro přímé volání /v1/models
            models_url = f"{self.config.base_url}/models"
            response = requests.get(models_url, timeout=self.config.timeout)
            response.raise_for_status()
            
            models_data = response.json()
            discovered = []
            
            for model in models_data.get('data', []):
                discovered.append(ModelInfo(
                    id=model['id'],
                    name=model.get('name', model['id']),
                    provider=self.name,
                    max_tokens=4096,  # LM Studio výchozí
                    cost_per_1k_tokens=0.0,  # Lokální modely jsou zdarma
                    description=f"Local model: {model['id']}"
                ))
            
            return discovered
        except Exception as e:
            self.logger.error(f"Chyba při auto-discovery LM Studio modelů: {e}")
            return []
    
    def is_available(self) -> bool:
        """Zkontroluje dostupnost LM Studio serveru"""
        if not self.config.enabled:
            return False
        
        try:
            # Test připojení k LM Studio
            health_url = f"{self.config.base_url}/models"
            response = requests.get(health_url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False


# Factory pro vytváření providerů
class ProviderFactory:
    """Factory pro vytváření AI providerů"""
    
    _providers = {
        'openrouter': OpenRouterProvider,
        'lm_studio': LMStudioProvider,
    }
    
    @classmethod
    def create_provider(cls, name: str, config: ProviderConfig) -> AIProvider:
        """Vytvoří provider podle názvu"""
        provider_class = cls._providers.get(name.lower())
        if not provider_class:
            raise ValueError(f"Neznámý provider: {name}")
        
        return provider_class(name, config)
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Registruje nový provider"""
        cls._providers[name.lower()] = provider_class
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Vrátí seznam dostupných providerů"""
        return list(cls._providers.keys())
