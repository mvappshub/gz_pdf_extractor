"""
Model Manager pro správu AI modelů a providerů
Poskytuje jednotné rozhraní pro práci s různými AI providery
"""

from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass

from config_schema import AppConfig, ConfigManager
from ai_providers import (
    AIProvider, ProviderFactory, CompletionRequest, CompletionResponse, 
    ModelInfo
)


@dataclass
class ModelSelectionCriteria:
    """Kritéria pro výběr modelu"""
    prefer_local: bool = False
    max_cost_per_1k_tokens: Optional[float] = None
    min_max_tokens: Optional[int] = None
    required_capabilities: List[str] = None


class ModelManager:
    """Správce modelů a providerů"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = logging.getLogger("model_manager")
        self.providers: Dict[str, AIProvider] = {}
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "provider_usage": {},
            "model_usage": {}
        }
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Inicializuje všechny povolené providery"""
        for provider_name, provider_config in self.config.providers.items():
            if provider_config.enabled:
                try:
                    provider = ProviderFactory.create_provider(provider_name, provider_config)
                    self.providers[provider_name] = provider
                    self.logger.info(f"Inicializován provider: {provider_name}")
                except Exception as e:
                    self.logger.error(f"Chyba při inicializaci providera {provider_name}: {e}")
    
    def get_available_models(self, include_unavailable: bool = False) -> List[ModelInfo]:
        """Vrátí seznam všech dostupných modelů ze všech providerů"""
        all_models = []
        
        for provider_name, provider in self.providers.items():
            try:
                if include_unavailable or provider.is_available():
                    models = provider.get_available_models()
                    all_models.extend(models)
                else:
                    self.logger.debug(f"Provider {provider_name} není dostupný")
            except Exception as e:
                self.logger.error(f"Chyba při získávání modelů z {provider_name}: {e}")
        
        return all_models
    
    def get_model_by_id(self, model_id: str) -> Optional[Tuple[ModelInfo, AIProvider]]:
        """Najde model podle ID a vrátí ho spolu s providerem"""
        for provider in self.providers.values():
            try:
                models = provider.get_available_models()
                for model in models:
                    if model.id == model_id:
                        return model, provider
            except Exception as e:
                self.logger.error(f"Chyba při hledání modelu {model_id}: {e}")
        
        return None
    
    def select_best_model(self, criteria: Optional[ModelSelectionCriteria] = None) -> Optional[Tuple[ModelInfo, AIProvider]]:
        """Vybere nejlepší model podle zadaných kritérií"""
        if criteria is None:
            criteria = ModelSelectionCriteria()
        
        available_models = self.get_available_models()
        if not available_models:
            return None
        
        # Filtrování podle kritérií
        filtered_models = []
        for model in available_models:
            # Kontrola nákladů
            if criteria.max_cost_per_1k_tokens is not None:
                if model.cost_per_1k_tokens > criteria.max_cost_per_1k_tokens:
                    continue
            
            # Kontrola max_tokens
            if criteria.min_max_tokens is not None:
                if model.max_tokens < criteria.min_max_tokens:
                    continue
            
            # Preference lokálních modelů
            if criteria.prefer_local:
                if model.cost_per_1k_tokens > 0:  # Lokální modely mají cost 0
                    continue
            
            filtered_models.append(model)
        
        if not filtered_models:
            return None
        
        # Seřazení podle preferencí (lokální první, pak podle nákladů)
        def sort_key(model: ModelInfo):
            is_local = model.cost_per_1k_tokens == 0
            return (not is_local, model.cost_per_1k_tokens, -model.max_tokens)
        
        filtered_models.sort(key=sort_key)
        best_model = filtered_models[0]
        
        # Najde příslušný provider
        result = self.get_model_by_id(best_model.id)
        return result
    
    def create_completion(
        self, 
        messages: List[Dict[str, str]], 
        model_id: Optional[str] = None,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        """Vytvoří completion s automatickým fallbackem"""
        
        # Určení modelu a providera
        target_model, target_provider = self._resolve_model_and_provider(model_id, provider_name)
        
        if not target_model or not target_provider:
            return self._create_error_response("Nepodařilo se najít vhodný model nebo provider")
        
        # Vytvoření requestu
        request = CompletionRequest(
            messages=messages,
            model_id=target_model.id,
            max_tokens=kwargs.get('max_tokens', target_model.max_tokens),
            temperature=kwargs.get('temperature', 0.0),
            timeout=kwargs.get('timeout')
        )
        
        # Pokus o completion
        response = target_provider.create_completion(request)
        
        # Aktualizace metrik
        self._update_metrics(response, target_model, target_provider)
        
        # Fallback při selhání
        if not response.success and self._should_try_fallback(target_provider.name):
            self.logger.warning(f"Pokus o fallback po selhání {target_provider.name}")
            fallback_response = self._try_fallback(request)
            if fallback_response and fallback_response.success:
                return fallback_response
        
        return response
    
    def _resolve_model_and_provider(
        self, 
        model_id: Optional[str], 
        provider_name: Optional[str]
    ) -> Tuple[Optional[ModelInfo], Optional[AIProvider]]:
        """Určí model a provider podle parametrů nebo výchozích hodnot"""
        
        # Pokud je specifikován konkrétní model
        if model_id:
            result = self.get_model_by_id(model_id)
            if result:
                model, provider = result
                # Kontrola, zda provider odpovídá požadavku
                if provider_name and provider.name != provider_name:
                    self.logger.warning(f"Model {model_id} není dostupný u providera {provider_name}")
                    return None, None
                return model, provider
            else:
                self.logger.error(f"Model {model_id} nebyl nalezen")
                return None, None
        
        # Pokud je specifikován pouze provider
        if provider_name:
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                models = provider.get_available_models()
                if models:
                    # Použije první dostupný model
                    return models[0], provider
                else:
                    self.logger.error(f"Provider {provider_name} nemá dostupné modely")
                    return None, None
            else:
                self.logger.error(f"Provider {provider_name} není dostupný")
                return None, None
        
        # Použije výchozí konfiguraci
        default_provider_name = self.config.defaults.provider
        default_model_id = self.config.defaults.model
        
        if default_provider_name in self.providers:
            provider = self.providers[default_provider_name]
            result = self.get_model_by_id(default_model_id)
            if result:
                return result
        
        # Poslední možnost - automatický výběr nejlepšího modelu
        return self.select_best_model()
    
    def _should_try_fallback(self, failed_provider: str) -> bool:
        """Určí, zda se má pokusit o fallback"""
        fallback_provider = self.config.defaults.fallback_provider
        return (
            fallback_provider and 
            fallback_provider != failed_provider and
            fallback_provider in self.providers
        )
    
    def _try_fallback(self, original_request: CompletionRequest) -> Optional[CompletionResponse]:
        """Pokusí se o fallback na záložní provider/model"""
        fallback_provider_name = self.config.defaults.fallback_provider
        fallback_model_id = self.config.defaults.fallback_model
        
        if not fallback_provider_name or fallback_provider_name not in self.providers:
            return None
        
        fallback_provider = self.providers[fallback_provider_name]
        
        # Určí fallback model
        if fallback_model_id:
            result = self.get_model_by_id(fallback_model_id)
            if result:
                fallback_model, _ = result
            else:
                # Použije první dostupný model z fallback providera
                models = fallback_provider.get_available_models()
                if not models:
                    return None
                fallback_model = models[0]
        else:
            models = fallback_provider.get_available_models()
            if not models:
                return None
            fallback_model = models[0]
        
        # Vytvoří fallback request
        fallback_request = CompletionRequest(
            messages=original_request.messages,
            model_id=fallback_model.id,
            max_tokens=original_request.max_tokens,
            temperature=original_request.temperature,
            timeout=original_request.timeout
        )
        
        self.logger.info(f"Pokus o fallback: {fallback_provider_name}/{fallback_model.id}")
        response = fallback_provider.create_completion(fallback_request)
        
        if response.success:
            self.logger.info("Fallback byl úspěšný")
            self._update_metrics(response, fallback_model, fallback_provider)
        
        return response
    
    def _update_metrics(self, response: CompletionResponse, model: ModelInfo, provider: AIProvider):
        """Aktualizuje metriky použití"""
        self.metrics["total_requests"] += 1
        
        if response.success:
            self.metrics["successful_requests"] += 1
            self.metrics["total_tokens"] += response.total_tokens
            self.metrics["total_cost"] += response.cost_estimate
        else:
            self.metrics["failed_requests"] += 1
        
        # Metriky podle providera
        if provider.name not in self.metrics["provider_usage"]:
            self.metrics["provider_usage"][provider.name] = {
                "requests": 0, "tokens": 0, "cost": 0.0
            }
        
        provider_metrics = self.metrics["provider_usage"][provider.name]
        provider_metrics["requests"] += 1
        if response.success:
            provider_metrics["tokens"] += response.total_tokens
            provider_metrics["cost"] += response.cost_estimate
        
        # Metriky podle modelu
        if model.id not in self.metrics["model_usage"]:
            self.metrics["model_usage"][model.id] = {
                "requests": 0, "tokens": 0, "cost": 0.0
            }
        
        model_metrics = self.metrics["model_usage"][model.id]
        model_metrics["requests"] += 1
        if response.success:
            model_metrics["tokens"] += response.total_tokens
            model_metrics["cost"] += response.cost_estimate
    
    def _create_error_response(self, error_message: str) -> CompletionResponse:
        """Vytvoří error response"""
        return CompletionResponse(
            content="",
            model_used="unknown",
            provider_used="unknown",
            success=False,
            error_message=error_message
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Vrátí metriky použití"""
        return self.metrics.copy()
    
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Vrátí stav všech providerů"""
        status = {}
        
        for name, provider in self.providers.items():
            try:
                is_available = provider.is_available()
                models = provider.get_available_models() if is_available else []
                
                status[name] = {
                    "available": is_available,
                    "enabled": provider.config.enabled,
                    "models_count": len(models),
                    "models": [{"id": m.id, "name": m.name} for m in models[:5]]  # Prvních 5
                }
            except Exception as e:
                status[name] = {
                    "available": False,
                    "enabled": provider.config.enabled,
                    "error": str(e),
                    "models_count": 0,
                    "models": []
                }
        
        return status
    
    def reload_config(self, new_config: AppConfig):
        """Znovu načte konfiguraci a reinicializuje providery"""
        self.config = new_config
        self.providers.clear()
        self._initialize_providers()
        self.logger.info("Konfigurace byla znovu načtena")
