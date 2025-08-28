#!/usr/bin/env python3
"""
Test skript pro multi-model systém
Ověřuje základní funkcionalitu bez skutečného zpracování PDF
"""

import os
import sys
from pathlib import Path

# Přidání aktuálního adresáře do Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test importů všech nových modulů"""
    print("🧪 Testování importů...")
    
    try:
        from config_schema import ConfigManager, AppConfig, ModelConfig, ProviderConfig
        print("✅ config_schema import OK")
    except Exception as e:
        print(f"❌ config_schema import FAILED: {e}")
        return False
    
    try:
        from ai_providers import AIProvider, OpenRouterProvider, LMStudioProvider, ProviderFactory
        print("✅ ai_providers import OK")
    except Exception as e:
        print(f"❌ ai_providers import FAILED: {e}")
        return False
    
    try:
        from model_manager import ModelManager
        print("✅ model_manager import OK")
    except Exception as e:
        print(f"❌ model_manager import FAILED: {e}")
        return False
    
    return True

def test_config_loading():
    """Test načítání konfigurace"""
    print("\n🧪 Testování načítání konfigurace...")
    
    try:
        from config_schema import ConfigManager
        
        # Test výchozí konfigurace
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        print(f"✅ Výchozí konfigurace načtena")
        print(f"   Providery: {list(config.providers.keys())}")
        print(f"   Výchozí provider: {config.defaults.provider}")
        print(f"   Výchozí model: {config.defaults.model}")
        
        return True
    except Exception as e:
        print(f"❌ Načítání konfigurace FAILED: {e}")
        return False

def test_provider_factory():
    """Test ProviderFactory"""
    print("\n🧪 Testování ProviderFactory...")
    
    try:
        from ai_providers import ProviderFactory
        from config_schema import ProviderConfig
        
        # Test dostupných providerů
        available = ProviderFactory.get_available_providers()
        print(f"✅ Dostupné providery: {available}")
        
        # Test vytvoření OpenRouter providera
        config = ProviderConfig(
            enabled=True,
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            models=[]
        )
        
        provider = ProviderFactory.create_provider("openrouter", config)
        print(f"✅ OpenRouter provider vytvořen: {provider.name}")
        
        return True
    except Exception as e:
        print(f"❌ ProviderFactory test FAILED: {e}")
        return False

def test_model_manager():
    """Test ModelManager"""
    print("\n🧪 Testování ModelManager...")
    
    try:
        from model_manager import ModelManager
        from config_schema import ConfigManager
        
        # Načtení konfigurace
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Vytvoření ModelManager
        model_manager = ModelManager(config)
        print(f"✅ ModelManager vytvořen")
        
        # Test stavu providerů
        status = model_manager.get_provider_status()
        print(f"✅ Stav providerů získán: {list(status.keys())}")
        
        for provider_name, provider_status in status.items():
            enabled = "✅" if provider_status["enabled"] else "❌"
            available = "🟢" if provider_status["available"] else "🔴"
            print(f"   {provider_name}: {enabled} enabled, {available} available")
        
        return True
    except Exception as e:
        print(f"❌ ModelManager test FAILED: {e}")
        return False

def test_cli_imports():
    """Test importů v hlavním CLI souboru"""
    print("\n🧪 Testování CLI importů...")
    
    try:
        # Test importu hlavního souboru
        import pdf_extractor_multimodel
        print("✅ pdf_extractor_multimodel import OK")
        
        return True
    except Exception as e:
        print(f"❌ CLI import FAILED: {e}")
        return False

def test_yaml_dependency():
    """Test YAML závislosti"""
    print("\n🧪 Testování YAML závislosti...")
    
    try:
        import yaml
        print("✅ PyYAML je dostupné")
        
        # Test základního YAML parsování
        test_yaml = """
        test:
          key: value
          number: 42
        """
        parsed = yaml.safe_load(test_yaml)
        assert parsed['test']['key'] == 'value'
        assert parsed['test']['number'] == 42
        print("✅ YAML parsing funguje")
        
        return True
    except ImportError:
        print("❌ PyYAML není nainstalované - spusťte: pip install pyyaml")
        return False
    except Exception as e:
        print(f"❌ YAML test FAILED: {e}")
        return False

def main():
    """Hlavní test funkce"""
    print("🚀 Spouštím testy multi-model systému...\n")
    
    tests = [
        ("Imports", test_imports),
        ("YAML dependency", test_yaml_dependency),
        ("Config loading", test_config_loading),
        ("ProviderFactory", test_provider_factory),
        ("ModelManager", test_model_manager),
        ("CLI imports", test_cli_imports),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}")
            failed += 1
    
    print(f"\n📊 Výsledky testů:")
    print(f"   ✅ Prošlo: {passed}")
    print(f"   ❌ Selhalo: {failed}")
    print(f"   📈 Úspěšnost: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 Všechny testy prošly! Multi-model systém je připraven k použití.")
        print("\n📋 Další kroky:")
        print("   1. Nastavte API klíče v .env souboru")
        print("   2. Zkopírujte config_example.yaml jako config.yaml")
        print("   3. Spusťte: python pdf_extractor_multimodel.py --list-providers")
    else:
        print(f"\n⚠️  {failed} testů selhalo. Zkontrolujte chyby výše.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
