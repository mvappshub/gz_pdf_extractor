#!/usr/bin/env python3
"""
PDF Extractor s multi-model AI podporou
Refaktorovaná verze s podporou více AI providerů a modelů
"""

import os
import json
import argparse
import pdfplumber
import zipfile
import io
import re
import logging
import logging.handlers
import time
import psutil
import hashlib
from typing import List, Optional, Dict, Tuple, Any
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
import concurrent.futures
import threading
from datetime import datetime

# Import nových modulů
from config_schema import ConfigManager, AppConfig
from model_manager import ModelManager
from ai_providers import CompletionRequest, ProviderFactory

# Načtení proměnných prostředí
load_dotenv()

# Výchozí prompt - zachován z původní verze
DEFAULT_PROMPT = """
You are an expert AI assistant specializing in extracting vinyl record track information from PDF documents, which may contain text, images, or scans.
Analyze the provided document and extract the following information. Return it as a single, valid JSON object with NO additional text, commentary or markdown.
- tracks: A list of tracks. Each track must be an object with:
    - side: The side letter (e.g., "A", "B"). Must be a capital letter.
    - position: The track number on the side (e.g., 1, 2). Must be an integer.
    - title: The track title.
    - duration: The track duration in MM:SS format (e.g., "03:45").
Your output MUST be only the JSON object. Example: {"tracks": [{"side": "A", "position": 1, "title": "Intro", "duration": "01:23"}]}
"""

# Zámky pro thread-safe operace
print_lock = threading.Lock()
error_log_lock = threading.Lock()

# Globální proměnné pro metriky
METRICS = {
    "total_files": 0,
    "processed_files": 0,
    "failed_files": 0,
    "total_processing_time": 0,
    "total_tokens_used": 0,
    "total_response_tokens": 0,
    "successful_parses": 0,
    "failed_parses": 0,
    "start_time": None,
    "end_time": None,
    "model_usage": {},
    "provider_usage": {}
}

# === DATOVÉ MODELY (zachováno z původní verze) ===
class TrackInfo(BaseModel):
    """Informace o skladbě z AI odpovědi"""
    side: str
    position: int
    title: str
    duration: str

class AIResponse(BaseModel):
    """Očekávaná struktura dat z AI API"""
    tracks: List[TrackInfo]

class OutputTrack(BaseModel):
    """Skladba ve výstupním JSON souboru"""
    title: str = Field(..., min_length=1)
    side: str = Field(..., pattern=r"^[A-Z]$")
    position: int = Field(..., ge=1)
    duration_seconds: int = Field(..., ge=0, le=5999)
    duration_formatted: str = Field(..., pattern=r"^(?:[0-5]\d):(?:[0-5]\d)$")

class OutputFileModel(BaseModel):
    """Finální JSON výstup podle šablony"""
    source_type: str = "pdf"
    source_path: str
    tracks: List[OutputTrack]
    side_durations: Dict[str, str]
    
    @field_validator('side_durations')
    def validate_side_durations(cls, v):
        for key, value in v.items():
            if not re.match(r"^[A-Z]$", key):
                raise ValueError(f"Neplatný klíč strany: {key}")
            if not re.match(r"^(?:[0-5]\d):(?:[0-5]\d)$", value):
                raise ValueError(f"Neplatný formát délky pro stranu {key}: {value}")
        return v

# === POMOCNÉ FUNKCE (zachováno z původní verze) ===
def safe_print(message):
    """Thread-safe printing"""
    with print_lock:
        print(message)

def parse_duration(duration_str: str) -> Optional[int]:
    """Převede řetězec s dobou trvání na sekundy"""
    if not duration_str:
        return None
    parts = duration_str.split(':')
    try:
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            return None
    except (ValueError, TypeError):
        return None

def format_duration(seconds: int) -> str:
    """Formátuje sekundy jako MM:SS"""
    if seconds < 0:
        raise ValueError(f"Doba trvání nemůže být záporná: {seconds}")
    minutes = seconds // 60
    seconds %= 60
    return f"{minutes:02d}:{seconds:02d}"

def normalize_duration_format(duration_str: str) -> str:
    """Standardizuje formát času na MM:SS"""
    if not duration_str:
        return "00:00"
    
    seconds = parse_duration(duration_str)
    return "00:00" if seconds is None else format_duration(seconds)

def get_unique_path(path):
    """Generuje unikátní cestu k souboru"""
    if not os.path.exists(path):
        return path
    
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        new_path = f"{base}_{i}{ext}"
        if not os.path.exists(new_path):
            return new_path
        i += 1

def get_cpu_usage():
    """Získá aktuální využití CPU"""
    try:
        return psutil.cpu_percent(interval=0.1)
    except Exception:
        return 0.0

def log_error_jsonl(pdf_id, abs_path, error_msg, output_dir):
    """Zapíše chybu do logs/errors.jsonl"""
    log_dir = os.path.join(output_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, "errors.jsonl")
    
    error_entry = {
        "timestamp": datetime.now().isoformat(),
        "source_id": pdf_id,
        "source_path": abs_path,
        "error": str(error_msg)
    }
    
    with error_log_lock:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_entry) + "\n")

# === NASTAVENÍ LOGOVÁNÍ (zachováno) ===
def setup_logging(log_level="INFO", log_file=None):
    """Nastavení strukturovaného logování"""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Odstranit všechny existující handlery
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    # JSONL handler
    class JSONLHandler(logging.Handler):
        def __init__(self, filename):
            super().__init__()
            self.filename = filename
            os.makedirs(os.path.dirname(filename), exist_ok=True)

        def emit(self, record):
            try:
                log_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }
                with open(self.filename, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except Exception:
                self.handleError(record)

    # Přidat JSONL handler
    jsonl_handler = JSONLHandler("output-pdf/logs/logs.jsonl")
    jsonl_handler.setFormatter(logging.Formatter())
    logger.addHandler(jsonl_handler)

    # Volitelný souborový handler
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=3
        )
        file_handler.setFormatter(logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}'
        ))
        logger.addHandler(file_handler)

    return logger

def load_prompt():
    """Načtení normalizačního promptu ze souboru nebo použití výchozího"""
    prompt_path = os.path.join(os.path.dirname(__file__), "normalize.txt")
    try:
        with open(prompt_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return DEFAULT_PROMPT

def extract_text_from_pdf(pdf_bytes, config):
    """Extrakce textu z PDF souboru z bajtů"""
    text = ""
    max_pages = config.pdf.max_pages
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_to_process = min(len(pdf.pages), max_pages)
            
            for i in range(pages_to_process):
                page = pdf.pages[i]
                if page_text := page.extract_text():
                    text += page_text + "\n"
    except Exception as e:
        logging.error(f"Chyba při extrakci textu z PDF: {str(e)}")
        raise
    
    return text

def ensure_track_positions_are_integers(tracks):
    """Zajistí, že všechny pozice skladeb jsou integers"""
    for track in tracks:
        if isinstance(track.position, str):
            try:
                track.position = int(track.position)
            except ValueError:
                track.position = 1
    return tracks

def parse_and_validate_ai_response(json_content: str) -> AIResponse:
    """Parsuje JSON obsah a validuje pomocí Pydantic modelu"""
    parsed_data = json.loads(json_content)
    ai_response = AIResponse(**parsed_data)
    ensure_track_positions_are_integers(ai_response.tracks)
    return ai_response

# === NOVÁ AI LOGIKA S MULTI-MODEL PODPOROU ===
def fetch_structured_data_from_ai(text: str, model_manager: ModelManager, model_id: Optional[str] = None, provider_name: Optional[str] = None) -> Tuple[AIResponse, Dict[str, Any]]:
    """
    Extrakce informací o vinylové desce z textu pomocí multi-model systému
    """
    prompt = load_prompt()

    # Příprava zpráv pro AI
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text}
    ]

    logging.info(f"Používám model: {model_id or 'auto'}, provider: {provider_name or 'auto'}")

    # Metriky pro tento request
    request_metrics = {
        "prompt_tokens": 0,
        "response_tokens": 0,
        "success": False,
        "attempts": 1,
        "model_used": "unknown",
        "provider_used": "unknown",
        "cost_estimate": 0.0
    }

    # Logování promptu v DEBUG režimu
    logging.debug(f"AI Prompt: {prompt}")
    logging.debug(f"AI Text (prvních 500 znaků): {text[:500]}...")

    try:
        # Vytvoření completion přes ModelManager
        response = model_manager.create_completion(
            messages=messages,
            model_id=model_id,
            provider_name=provider_name
        )

        # Aktualizace metrik
        request_metrics.update({
            "prompt_tokens": response.prompt_tokens,
            "response_tokens": response.completion_tokens,
            "success": response.success,
            "model_used": response.model_used,
            "provider_used": response.provider_used,
            "cost_estimate": response.cost_estimate
        })

        if not response.success:
            raise RuntimeError(f"AI API volání selhalo: {response.error_message}")

        # Aktualizace globálních metrik
        METRICS["total_tokens_used"] += response.prompt_tokens
        METRICS["total_response_tokens"] += response.completion_tokens

        # Logování odpovědi v DEBUG režimu
        logging.debug(f"AI Odpověď: {response.content}")

        # Pokus o parsování JSON a validace Pydantic modelem
        try:
            ai_response = parse_and_validate_ai_response(response.content)
            METRICS["successful_parses"] += 1
            return ai_response, request_metrics

        except (json.JSONDecodeError, ValueError) as e:
            content_preview = response.content[:200] if response.content else "(prázdné)"
            METRICS["failed_parses"] += 1
            raise ValueError(f"Nepodařilo se zpracovat AI odpověď jako JSON: {e}. Odpověď: {content_preview}...")

    except Exception as e:
        METRICS["failed_parses"] += 1
        raise RuntimeError(f"AI API volání selhalo: {str(e)}")

# === LOGIKA ZPRACOVÁNÍ A TRANSFORMACE DAT (zachováno) ===
def calculate_side_durations(tracks: List[TrackInfo]) -> Dict[str, str]:
    """Vypočítá celkovou dobu trvání pro každou stranu"""
    side_durations_seconds = {}

    for track in tracks:
        side = track.side
        duration_seconds = parse_duration(track.duration)

        if side not in side_durations_seconds:
            side_durations_seconds[side] = 0
        if duration_seconds is not None:
            side_durations_seconds[side] += duration_seconds

    # Formátování výsledků
    return {side: format_duration(total) for side, total in side_durations_seconds.items()}

def transform_ai_response(ai_response: AIResponse, source_path: str) -> dict:
    """Transformuje AI response na finální výstupní slovník"""
    # Výpočet celkové doby trvání na strany
    side_durations = calculate_side_durations(ai_response.tracks)

    # Transformace stop
    output_tracks = []
    for track in ai_response.tracks:
        duration_seconds = parse_duration(track.duration)
        duration_formatted = normalize_duration_format(track.duration)

        # Použití 0 jako fallback pro neplatné doby trvání
        if duration_seconds is None:
            duration_seconds = 0

        output_tracks.append(OutputTrack(
            title=track.title,
            side=track.side,
            position=track.position,
            duration_seconds=duration_seconds,
            duration_formatted=duration_formatted
        ))

    # Vytvoření výstupního modelu
    output_model = OutputFileModel(
        source_path=source_path,
        tracks=output_tracks,
        side_durations=side_durations
    )

    # Převod na slovník pro serializaci
    return output_model.model_dump()

# === ORCHESTRACE A SOUČĚŽNÉ ZPRACOVÁNÍ (zachováno s úpravami) ===
def _process_zip_stream(zip_bytes: bytes, abs_path_prefix: str, rel_path_prefix: str) -> List[Tuple[str, str, bytes]]:
    """Rekurzivní zpracování ZIP archivu z bajtového proudu"""
    pdf_files = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_ref:
            for zip_info in zip_ref.infolist():
                if zip_info.filename.startswith('__') or zip_info.filename.startswith('.'):
                    continue

                if zip_info.filename.lower().endswith('.pdf'):
                    # PDF v ZIPu
                    with zip_ref.open(zip_info) as pdf_file:
                        zip_abs_path = f"{abs_path_prefix}::{zip_info.filename}"
                        zip_rel_path = f"{rel_path_prefix}::{zip_info.filename}"
                        pdf_files.append((zip_abs_path, zip_rel_path, pdf_file.read()))

                elif zip_info.filename.lower().endswith('.zip'):
                    # Vnořený ZIP
                    with zip_ref.open(zip_info) as nested_zip_file:
                        nested_zip_bytes = nested_zip_file.read()
                        nested_zip_abs_path = f"{abs_path_prefix}::{zip_info.filename}"
                        nested_zip_rel_path = f"{rel_path_prefix}::{zip_info.filename}"

                        # Rekurzivní zpracování vnořeného ZIPu
                        nested_pdfs = _process_zip_stream(
                            nested_zip_bytes,
                            nested_zip_abs_path,
                            nested_zip_rel_path
                        )
                        pdf_files.extend(nested_pdfs)
    except Exception as e:
        logging.error(f"Chyba při zpracování ZIP proudu {rel_path_prefix}: {str(e)}")

    return pdf_files

def collect_pdf_sources(config: AppConfig) -> List[Tuple[str, str, bytes]]:
    """Sbírá všechny PDF soubory z adresáře včetně ZIP archivů"""
    pdf_files = []
    input_dir = config.processing.input_directory
    max_file_size_mb = config.processing.max_file_size_mb
    max_file_size_bytes = max_file_size_mb * 1024 * 1024

    logging.info(f"Prohledávám adresář: {input_dir}")

    for root, _, files in os.walk(input_dir):
        for file in files:
            file_path = os.path.join(root, file)
            abs_path = os.path.abspath(file_path)
            rel_path = os.path.relpath(file_path, input_dir)

            # Kontrola velikosti souboru
            try:
                file_size = os.path.getsize(file_path)
                if file_size > max_file_size_bytes:
                    logging.warning(f"Přeskakuji soubor {rel_path} kvůli velikosti ({file_size/1024/1024:.2f}MB > {max_file_size_mb}MB)")
                    continue
            except Exception as e:
                logging.warning(f"Nelze získat velikost souboru {rel_path}: {str(e)}")
                continue

            if file.lower().endswith('.pdf'):
                # Přímé PDF soubory
                try:
                    with open(file_path, 'rb') as f:
                        pdf_files.append((abs_path, rel_path, f.read()))
                except Exception as e:
                    logging.error(f"Chyba při čtení PDF souboru {rel_path}: {str(e)}")

            elif file.lower().endswith('.zip'):
                # ZIP archivy
                try:
                    with open(file_path, 'rb') as f:
                        zip_bytes = f.read()
                        zip_pdfs = _process_zip_stream(zip_bytes, abs_path, rel_path)
                        pdf_files.extend(zip_pdfs)
                except Exception as e:
                    logging.error(f"Chyba při zpracování ZIP souboru {rel_path}: {str(e)}")

    logging.info(f"Nalezeno {len(pdf_files)} PDF souborů ke zpracování")
    return pdf_files

def process_single_pdf(pdf_data: Tuple[str, str, bytes], config: AppConfig, model_manager: ModelManager, output_dir: str, processed_files=None, model_id: Optional[str] = None, provider_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Zpracování jednoho PDF souboru s multi-model podporou"""
    abs_path, pdf_id, pdf_bytes = pdf_data
    start_time = time.time()

    # Vytvoření bezpečného názvu souboru
    safe_filename = pdf_id.replace('::', '_').replace('/', '_').replace('\\', '_')
    pdf_hash = hashlib.md5(pdf_id.encode('utf-8')).hexdigest()[:8]
    output_file = f"{os.path.splitext(safe_filename)[0]}_{pdf_hash}.json"
    base_output_path = os.path.join(output_dir, output_file)

    # Získání unikátní cesty
    output_path = get_unique_path(base_output_path)

    # Kontrola, zda byl soubor již zpracován
    if processed_files is not None:
        for processed_file in processed_files:
            if pdf_hash in os.path.basename(processed_file):
                logging.info(f"Přeskakuji již zpracovaný soubor: {pdf_id}")
                return None

    logging.info(f"Zpracovávám: {pdf_id}")
    logging.debug(f"Zdrojová cesta: {abs_path}")

    try:
        # Extrakce textu z PDF
        text = extract_text_from_pdf(pdf_bytes, config)

        if not text.strip() or len(text.strip()) < config.pdf.min_text_length:
            logging.warning(f"Přeskakuji {pdf_id}: Není dostatek extrahovaného textu ({len(text.strip())} znaků)")
            return None

        # Uložení extrahovaného textu pro debugování
        if config.advanced.save_extracted_text:
            debug_file = f"{os.path.splitext(safe_filename)[0]}_extrahovany_text.txt"
            debug_path = os.path.join(output_dir, debug_file)
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(text)

        # Extrakce dat pomocí AI s multi-model podporou
        ai_response, request_metrics = fetch_structured_data_from_ai(
            text, model_manager, model_id, provider_name
        )

        # Transformace dat na výstupní formát
        output_data = transform_ai_response(ai_response, abs_path)

        # Uložení výstupního JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        processing_time = time.time() - start_time

        # Aktualizace metrik
        METRICS["processed_files"] += 1
        METRICS["total_processing_time"] += processing_time

        # Aktualizace metrik podle modelu a providera
        model_used = request_metrics.get("model_used", "unknown")
        provider_used = request_metrics.get("provider_used", "unknown")

        if model_used not in METRICS["model_usage"]:
            METRICS["model_usage"][model_used] = {"count": 0, "tokens": 0, "cost": 0.0}
        METRICS["model_usage"][model_used]["count"] += 1
        METRICS["model_usage"][model_used]["tokens"] += request_metrics.get("prompt_tokens", 0) + request_metrics.get("response_tokens", 0)
        METRICS["model_usage"][model_used]["cost"] += request_metrics.get("cost_estimate", 0.0)

        if provider_used not in METRICS["provider_usage"]:
            METRICS["provider_usage"][provider_used] = {"count": 0, "tokens": 0, "cost": 0.0}
        METRICS["provider_usage"][provider_used]["count"] += 1
        METRICS["provider_usage"][provider_used]["tokens"] += request_metrics.get("prompt_tokens", 0) + request_metrics.get("response_tokens", 0)
        METRICS["provider_usage"][provider_used]["cost"] += request_metrics.get("cost_estimate", 0.0)

        logging.info(f"Úspěch: Data uložena do {output_path}")
        logging.debug(f"Skladby: {len(output_data['tracks'])} s daty o celkové době trvání")
        logging.debug(f"Doba zpracování: {processing_time:.2f}s")
        logging.debug(f"Model: {model_used}, Provider: {provider_used}")
        logging.debug(f"Metriky požadavku: {json.dumps(request_metrics)}")

        return {
            "path": output_path,
            "success": True,
            "processing_time": processing_time,
            "tracks_count": len(output_data["tracks"]),
            "request_metrics": request_metrics
        }

    except Exception as e:
        processing_time = time.time() - start_time
        METRICS["failed_files"] += 1
        METRICS["total_processing_time"] += processing_time

        logging.error(f"Chyba při zpracování {pdf_id}: {str(e)}")

        # Logování chyby do JSONL souboru
        log_error_jsonl(pdf_id, abs_path, e, output_dir)

        return {
            "path": pdf_id,
            "success": False,
            "processing_time": processing_time,
            "error": str(e)
        }

def run_processing_pipeline(config: AppConfig, model_manager: ModelManager, model_id: Optional[str] = None, provider_name: Optional[str] = None):
    """Zpracování všech PDF souborů s multi-model podporou"""
    input_dir = config.processing.input_directory
    output_dir = config.processing.output_directory
    max_workers = config.processing.max_workers
    skip_processed = config.processing.skip_processed

    if not os.path.isdir(input_dir):
        logging.error(f"Vstupní adresář '{input_dir}' neexistuje.")
        return

    # Vytvoření výstupního adresáře
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Sada pro sledování již zpracovaných souborů
    processed_files = set()
    if skip_processed:
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith('.json'):
                    processed_files.add(os.path.join(root, file))
        logging.info(f"Nalezeno {len(processed_files)} již zpracovaných souborů k přeskočení")

    # Sběr všech PDF souborů
    logging.info("Sbírám PDF soubory...")
    start_time = time.time()
    pdf_files = collect_pdf_sources(config)
    collection_time = time.time() - start_time

    if not pdf_files:
        logging.warning(f"Nebyly nalezeny žádné PDF soubory v '{input_dir}'.")
        return

    METRICS["total_files"] = len(pdf_files)
    METRICS["start_time"] = datetime.now()

    logging.info(f"Nalezeno {len(pdf_files)} PDF souborů ke zpracování (sběr trval {collection_time:.2f} sekund).")
    logging.info(f"Zpracovávám s {max_workers} paralelními vlákny...")

    # Zobrazení informací o použitém modelu/provideru
    if model_id or provider_name:
        logging.info(f"Použitý model: {model_id or 'auto'}, provider: {provider_name or 'auto'}")
    else:
        logging.info(f"Použitý výchozí model: {config.defaults.model}, provider: {config.defaults.provider}")

    # Paralelní zpracování
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Vytvoření úloh pro každé PDF
        futures = [
            executor.submit(
                process_single_pdf,
                pdf_data,
                config,
                model_manager,
                output_dir,
                processed_files,
                model_id,
                provider_name
            )
            for pdf_data in pdf_files
        ]

        # Sledování průběhu
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            try:
                if result := future.result():
                    results.append(result)
                completed += 1

                # Aktualizace průběhu
                progress = (completed / len(pdf_files)) * 100
                cpu_usage = get_cpu_usage()

                logging.info(f"Průběh: {completed}/{len(pdf_files)} ({progress:.1f}%), CPU: {cpu_usage:.1f}%")

            except Exception as e:
                logging.error(f"Neočekávaná chyba ve vlákně: {str(e)}")

    METRICS["end_time"] = datetime.now()

    # Výpočet celkových metrik
    total_time = (METRICS["end_time"] - METRICS["start_time"]).total_seconds()
    avg_time_per_file = METRICS["total_processing_time"] / max(METRICS["processed_files"], 1)

    # Zobrazení souhrnu
    logging.info(f"\n=== Souhrn zpracování ===")
    logging.info(f"Úspěšně zpracováno: {METRICS['processed_files']}/{METRICS['total_files']} souborů")
    logging.info(f"Selhalo: {METRICS['failed_files']} souborů")
    logging.info(f"Celkový čas: {total_time:.2f} sekund")
    logging.info(f"Průměrný čas na soubor: {avg_time_per_file:.2f} sekund")
    logging.info(f"Celkem použitých tokenů: {METRICS['total_tokens_used']}")
    logging.info(f"Celkem odpovědních tokenů: {METRICS['total_response_tokens']}")
    logging.info(f"Úspěšných AI parsování: {METRICS['successful_parses']}")
    logging.info(f"Neúspěšných AI parsování: {METRICS['failed_parses']}")

    # Zobrazení metrik podle modelů a providerů
    if METRICS["model_usage"]:
        logging.info("\n=== Použití modelů ===")
        for model, stats in METRICS["model_usage"].items():
            logging.info(f"{model}: {stats['count']} požadavků, {stats['tokens']} tokenů, ${stats['cost']:.4f}")

    if METRICS["provider_usage"]:
        logging.info("\n=== Použití providerů ===")
        for provider, stats in METRICS["provider_usage"].items():
            logging.info(f"{provider}: {stats['count']} požadavků, {stats['tokens']} tokenů, ${stats['cost']:.4f}")

    # Uložení metrik do souboru
    metrics_file = os.path.join(output_dir, "zpracovani_metriky.json")
    try:
        metrics_copy = METRICS.copy()

        # Převod datetime objektů na ISO řetězce
        if metrics_copy.get("start_time") is not None:
            metrics_copy["start_time"] = metrics_copy["start_time"].isoformat()
        if metrics_copy.get("end_time") is not None:
            metrics_copy["end_time"] = metrics_copy["end_time"].isoformat()

        # Přidání metrik z ModelManageru
        model_manager_metrics = model_manager.get_metrics()

        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "config_summary": {
                    "default_provider": config.defaults.provider,
                    "default_model": config.defaults.model,
                    "enabled_providers": [name for name, cfg in config.providers.items() if cfg.enabled]
                },
                "processing_metrics": metrics_copy,
                "model_manager_metrics": model_manager_metrics,
                "results": results
            }, f, indent=2, ensure_ascii=False)
        logging.info(f"Metriky uloženy do {metrics_file}")
    except Exception as e:
        logging.error(f"Nepodařilo se uložit metriky: {str(e)}")

# === HLAVNÍ SPUŠTĚCÍ BLOK ===
def main():
    parser = argparse.ArgumentParser(
        description='PDF Extractor s multi-model AI podporou - extrakce informací o vinylových deskách z PDF souborů.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Příklady použití:
  %(prog)s                                    # Použije výchozí konfiguraci
  %(prog)s --config config.yaml              # Použije vlastní konfiguraci
  %(prog)s --model "anthropic/claude-3-sonnet"  # Použije konkrétní model
  %(prog)s --provider lm_studio              # Použije konkrétní provider
  %(prog)s --list-models                     # Zobrazí dostupné modely
  %(prog)s --list-providers                  # Zobrazí dostupné providery
        """
    )

    # Základní argumenty
    parser.add_argument('--config', '-c',
                        help='Cesta ke konfiguračnímu souboru (YAML nebo JSON)')
    parser.add_argument('--log-level', '-l', default="INFO",
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Úroveň logování')
    parser.add_argument('--log-file',
                        help='Cesta k logovacímu souboru')

    # Multi-model argumenty
    parser.add_argument('--model', '-m',
                        help='ID konkrétního modelu k použití (např. "google/gemini-2.5-flash")')
    parser.add_argument('--provider', '-p',
                        help='Název providera k použití (např. "openrouter", "lm_studio")')

    # Informační argumenty
    parser.add_argument('--list-models', action='store_true',
                        help='Zobrazí seznam dostupných modelů a ukončí program')
    parser.add_argument('--list-providers', action='store_true',
                        help='Zobrazí seznam dostupných providerů a ukončí program')
    parser.add_argument('--provider-status', action='store_true',
                        help='Zobrazí stav všech providerů a ukončí program')

    # Zpracování argumentů
    args = parser.parse_args()

    try:
        # Načtení konfigurace
        config_manager = ConfigManager(args.config)
        config = config_manager.load_config()

        # Nastavení logování
        setup_logging(args.log_level, args.log_file)

        # Inicializace ModelManageru
        model_manager = ModelManager(config)

        # Informační příkazy
        if args.list_providers:
            print("\n=== Dostupné AI providery ===")
            available_providers = ProviderFactory.get_available_providers()
            for provider_name in available_providers:
                enabled = provider_name in config.providers and config.providers[provider_name].enabled
                status = "✓ povolen" if enabled else "✗ zakázán"
                print(f"  {provider_name}: {status}")
            return

        if args.provider_status:
            print("\n=== Stav AI providerů ===")
            status = model_manager.get_provider_status()
            for provider_name, provider_status in status.items():
                available = "✓ dostupný" if provider_status["available"] else "✗ nedostupný"
                enabled = "✓ povolen" if provider_status["enabled"] else "✗ zakázán"
                models_count = provider_status["models_count"]
                print(f"  {provider_name}: {available}, {enabled}, {models_count} modelů")
                if provider_status.get("error"):
                    print(f"    Chyba: {provider_status['error']}")
            return

        if args.list_models:
            print("\n=== Dostupné AI modely ===")
            models = model_manager.get_available_models(include_unavailable=True)
            if not models:
                print("  Žádné modely nejsou dostupné.")
                return

            # Seskupení podle providerů
            by_provider = {}
            for model in models:
                if model.provider not in by_provider:
                    by_provider[model.provider] = []
                by_provider[model.provider].append(model)

            for provider_name, provider_models in by_provider.items():
                print(f"\n  Provider: {provider_name}")
                for model in provider_models:
                    cost_info = f"${model.cost_per_1k_tokens:.4f}/1k tokens" if model.cost_per_1k_tokens > 0 else "zdarma"
                    print(f"    {model.id}")
                    print(f"      Název: {model.name}")
                    print(f"      Max tokeny: {model.max_tokens}")
                    print(f"      Náklady: {cost_info}")
                    if model.description:
                        print(f"      Popis: {model.description}")
            return

        # Validace argumentů
        if args.model and args.provider:
            # Ověření, že model existuje u daného providera
            result = model_manager.get_model_by_id(args.model)
            if not result:
                print(f"CHYBA: Model '{args.model}' nebyl nalezen.")
                return
            model_info, provider = result
            if provider.name != args.provider:
                print(f"CHYBA: Model '{args.model}' není dostupný u providera '{args.provider}'.")
                print(f"Model je dostupný u providera: {provider.name}")
                return

        # Ověření API klíčů pro povolené providery
        missing_keys = []
        for provider_name, provider_config in config.providers.items():
            if provider_config.enabled:
                # Kontrola, zda API klíč obsahuje environment proměnnou
                api_key = provider_config.api_key
                if api_key.startswith('${') and api_key.endswith('}'):
                    env_var = api_key[2:-1]
                    if not os.getenv(env_var):
                        missing_keys.append(f"{provider_name}: {env_var}")
                elif api_key.startswith('$'):
                    env_var = api_key[1:]
                    if not os.getenv(env_var):
                        missing_keys.append(f"{provider_name}: {env_var}")

        if missing_keys:
            print("CHYBA: Chybí environment proměnné pro API klíče:")
            for missing in missing_keys:
                print(f"  {missing}")
            print("\nNastavte je v .env souboru nebo jako environment proměnné.")
            return

        # Hlavní zpracování
        logging.info("=== PDF Extractor s Multi-Model AI podporou ===")
        logging.info(f"Vstupní adresář: {config.processing.input_directory}")
        logging.info(f"Výstupní adresář: {config.processing.output_directory}")
        logging.info(f"Počet paralelních vláken: {config.processing.max_workers}")

        # Zobrazení informací o konfiguraci
        enabled_providers = [name for name, cfg in config.providers.items() if cfg.enabled]
        logging.info(f"Povolené providery: {', '.join(enabled_providers)}")
        logging.info(f"Výchozí provider: {config.defaults.provider}")
        logging.info(f"Výchozí model: {config.defaults.model}")

        if config.defaults.fallback_provider:
            logging.info(f"Záložní provider: {config.defaults.fallback_provider}")
            if config.defaults.fallback_model:
                logging.info(f"Záložní model: {config.defaults.fallback_model}")

        logging.info("=" * 50)

        # Spuštění zpracování
        run_processing_pipeline(config, model_manager, args.model, args.provider)
        logging.info("\nZpracování dokončeno!")

    except KeyboardInterrupt:
        logging.info("\nZpracování bylo přerušeno uživatelem.")
    except Exception as e:
        logging.error(f"Kritická chyba: {str(e)}")
        raise

if __name__ == "__main__":
    main()
