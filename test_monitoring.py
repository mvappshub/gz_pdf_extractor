#!/usr/bin/env python3
"""
Test script pro ověření real-time monitoring funkcionality
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
            }
        ],
        "side_durations": {
            "A": "3:45"
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
    
    print(f"Vytvořen testovací album: {filepath}")
    return filepath

def create_test_log():
    """Vytvoří testovací log záznam"""
    test_log = {
        "timestamp": datetime.now().isoformat() + "Z",
        "source_id": f"test_{int(time.time())}",
        "source_path": "test_file.pdf",
        "error": f"Test log message created at {datetime.now().strftime('%H:%M:%S')}",
        "log_source": "logs.jsonl"
    }
    
    logs_dir = "output-pdf/logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    log_file = os.path.join(logs_dir, "logs.jsonl")
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(test_log, ensure_ascii=False) + '\n')
    
    print(f"Přidán testovací log do: {log_file}")
    return log_file

def main():
    """Hlavní testovací funkce"""
    print("=== Test Real-Time Monitoring ===")
    print("1. Spusťte gui.py v jiném terminálu")
    print("2. Sledujte, jak se nová data objevují v aplikaci")
    print("3. Stiskněte Enter pro vytvoření testovacích dat...")
    
    input()
    
    while True:
        print("\nVyberte akci:")
        print("1 - Vytvořit testovací album")
        print("2 - Vytvořit testovací log")
        print("3 - Vytvořit obojí")
        print("q - Ukončit")
        
        choice = input("Vaše volba: ").strip().lower()
        
        if choice == 'q':
            break
        elif choice == '1':
            create_test_album()
        elif choice == '2':
            create_test_log()
        elif choice == '3':
            create_test_album()
            create_test_log()
        else:
            print("Neplatná volba!")
        
        print("Zkontrolujte GUI aplikaci - data by se měla automaticky obnovit!")

if __name__ == "__main__":
    main()
