#!/usr/bin/env python3
"""
Test script pro ověření real-time monitoring funkcionality
Vytváří testovací data pro sledování v GUI aplikaci
"""

import os
import json
import time
from datetime import datetime

def create_test_album():
    """Vytvoří testovací album JSON soubor"""
    test_album = {
        "source_path": f"test_album_{datetime.now().strftime('%H%M%S')}",
        "tracks": [
            {
                "side": "A",
                "position": "1",
                "title": f"Test Track {datetime.now().strftime('%H:%M:%S')}",
                "duration_formatted": "3:45"
            },
            {
                "side": "A", 
                "position": "2",
                "title": "Another Test Track",
                "duration_formatted": "4:12"
            }
        ],
        "side_durations": {
            "A": "7:57"
        },
        "created_at": datetime.now().isoformat()
    }
    
    output_dir = "output-pdf"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    filename = f"test_album_{int(time.time())}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(test_album, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Vytvořen testovací album: {filepath}")
    return filepath

def create_test_log():
    """Vytvoří testovací log záznam"""
    test_log = {
        "timestamp": datetime.now().isoformat(),
        "level": "INFO",
        "message": f"Test log message created at {datetime.now().strftime('%H:%M:%S')}",
        "module": "test_realtime",
        "function": "create_test_log",
        "line": 42
    }
    
    logs_dir = "output-pdf/logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    log_file = os.path.join(logs_dir, "logs.jsonl")
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(test_log, ensure_ascii=False) + '\n')
    
    print(f"✅ Přidán testovací log do: {log_file}")
    return log_file

def create_test_error():
    """Vytvoří testovací error log"""
    test_error = {
        "timestamp": datetime.now().isoformat() + "Z",
        "source_id": f"test_error_{int(time.time())}",
        "source_path": "test_file.pdf",
        "error": f"Test error message created at {datetime.now().strftime('%H:%M:%S')}"
    }
    
    logs_dir = "output-pdf/logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    error_file = os.path.join(logs_dir, "errors.jsonl")
    
    with open(error_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(test_error, ensure_ascii=False) + '\n')
    
    print(f"✅ Přidán testovací error do: {error_file}")
    return error_file

def main():
    """Hlavní testovací funkce"""
    print("=== Test Real-Time Monitoring ===")
    print("1. Spusťte gui.py v jiném terminálu")
    print("2. Sledujte, jak se nová data objevují v aplikaci")
    print("3. Stiskněte Enter pro pokračování...")
    
    input()
    
    while True:
        print("\n" + "="*50)
        print("Vyberte akci:")
        print("1 - Vytvořit testovací album")
        print("2 - Vytvořit testovací log (INFO)")
        print("3 - Vytvořit testovací error")
        print("4 - Vytvořit vše najednou")
        print("5 - Automatický test (každých 10 sekund)")
        print("q - Ukončit")
        print("="*50)
        
        choice = input("Vaše volba: ").strip().lower()
        
        if choice == 'q':
            print("👋 Ukončuji test...")
            break
        elif choice == '1':
            create_test_album()
        elif choice == '2':
            create_test_log()
        elif choice == '3':
            create_test_error()
        elif choice == '4':
            create_test_album()
            create_test_log()
            create_test_error()
            print("📦 Vytvořeny všechny typy testovacích dat!")
        elif choice == '5':
            print("🔄 Spouštím automatický test...")
            print("Stiskněte Ctrl+C pro zastavení")
            try:
                counter = 1
                while True:
                    print(f"\n--- Automatický test #{counter} ---")
                    create_test_album()
                    time.sleep(2)
                    create_test_log()
                    time.sleep(2)
                    create_test_error()
                    print(f"⏰ Čekám 10 sekund do dalšího testu...")
                    time.sleep(6)  # 2+2+6 = 10 sekund celkem
                    counter += 1
            except KeyboardInterrupt:
                print("\n⏹️ Automatický test zastaven")
        else:
            print("❌ Neplatná volba!")
        
        if choice in ['1', '2', '3', '4']:
            print("👀 Zkontrolujte GUI aplikaci - data by se měla automaticky obnovit!")

if __name__ == "__main__":
    main()
