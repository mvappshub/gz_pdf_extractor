# === IMPORTY ===
import os
import json
import argparse
import pdfplumber  # Nový import pro multimodální zpracování
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
from openai import OpenAI
from dotenv import load_dotenv
import concurrent.futures
import threading
from datetime import datetime

# === KONFIGURACE A KONSTANTY ===
# Načtení proměnných prostředí
load_dotenv()

# Výchozí prompt - aktualizovaný pro multimodální zpracování
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

# Výchozí konfigurace (primárně z .env)
DEFAULT_CONFIG = {
  "openrouter": {
    "api_key": os.getenv("OPENROUTER_API_KEY", ""),
    "model": os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash"), # Změna modelu
    "max_tokens": 4096, # Mírně navýšíme pro jistotu
    "temperature": 0.0
  },
  "processing": {
    "input_directory": "C:/gz_projekt/data-for-testing",
    "output_directory": "C:/Users/marti/Desktop/pdf extractor/output-pdf",
    "max_workers": int(os.getenv("MAX_WORKERS", 5)), # Načítání z .env
    "max_file_size_mb": 5000, # Snížení limitu dle specifikace
    "skip_processed": True
  },
  "pdf": {
    "max_pages": 50,
    "min_text_length": 100,
    "language": "en"
  },
  "advanced": {
    "timeout_seconds": 30,
    "retry_attempts": 3,
    "log_level": "INFO",
    "save_extracted_text": False
  }
}

# Zámek pro thread-safe tisk
print_lock = threading.Lock()
# Zámek pro bezpečný zápis chyb
error_log_lock = threading.Lock()
# Zámek pro thread-safe aktualizace metrik
metrics_lock = threading.Lock()

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
    "end_time": None
}

# === NASTAVENÍ LOGOVÁNÍ ===
def setup_logging(log_level="INFO", log_file=None):
    """Nastavení strukturovaného logování bez konzole, pouze do JSONL"""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # JSONL handler ----------------------------------------------------------
    class JSONLHandler(logging.Handler):
        def __init__(self, filename):
            super().__init__()
            self.filename = filename
            self._lock = threading.Lock()  # Thread-safe zápis do souboru
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
                with self._lock:  # Thread-safe zápis
                    with open(self.filename, "a", encoding="utf-8") as f:
                        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except Exception:
                self.handleError(record)

    # Odstraníme pouze handlery, které sami přidáváme, abychom předešli duplikaci
    from logging.handlers import RotatingFileHandler
    handlers_to_remove = [
        h for h in logger.handlers
        if isinstance(h, (JSONLHandler, RotatingFileHandler))
    ]
    for h in handlers_to_remove:
        logger.removeHandler(h)

    # přidat JSONL handler
    jsonl_handler = JSONLHandler("output-pdf/logs/logs.jsonl")
    jsonl_handler.setFormatter(logging.Formatter())  # dummy
    logger.addHandler(jsonl_handler)

    # volitelný souborový handler (pokud chceš i klasický log)
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

# Načtení konfiguračního souboru
def load_config(config_path=None):
    """Načtení konfigurace ze souboru nebo použití výchozí"""
    # Vytvoříme kopii výchozí konfigurace
    config = DEFAULT_CONFIG.copy()

    # Pokud je poskytnut konfigurační soubor, pokusíme se ho načíst
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                # Aktualizujeme výchozí konfiguraci hodnotami ze souboru
                for section, values in file_config.items():
                    if section in config:
                        config[section].update(values)
                    else:
                        config[section] = values
        except Exception as e:
            logging.error(f"Chyba při načítání konfigurace ze souboru {config_path}: {str(e)}")

    # Vynucení načtení API klíče z proměnných prostředí, pokud není nastaven
    if not config["openrouter"]["api_key"]:
        if env_api_key := os.getenv("OPENROUTER_API_KEY", ""):
            config["openrouter"]["api_key"] = env_api_key
            logging.info("API klíč načten z proměnné prostředí")

    return config
# === DATOVÉ MODELY (PYDANTIC) ===
class TrackInfo(BaseModel):
    """Informace o skladbě z AI odpovědi"""
    side: str
    position: int
    title: str
    duration: str  # MM:SS formát

class AIResponse(BaseModel):
    """Očekávaná struktura dat z AI API"""
    tracks: List[TrackInfo]

class OutputTrack(BaseModel):
    """Skladba ve výstupním JSON souboru"""
    title: str = Field(..., min_length=1)
    side: str = Field(..., pattern=r"^[A-Z]$")
    position: int = Field(..., ge=1)
    duration_seconds: int = Field(..., ge=0, le=5999) # ge = greater or equal, le = less or equal
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

# === POMOCNÉ/UTILITY FUNKCE ===
def safe_print(message):
    """Thread-safe printing"""
    with print_lock:
        print(message)

def parse_duration(duration_str: str) -> Optional[int]:
    """Převede řetězec s dobou trvání na sekundy. Vrací None pro neplatný nebo prázdný vstup."""
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
    """
    Standardizuje formát času na MM:SS:
    "7:32" -> "07:32"
    "1:02:35" -> "62:35" (konvertuje hodiny)
    """
    if not duration_str:
        return "00:00"

    seconds = parse_duration(duration_str)
    return "00:00" if seconds is None else format_duration(seconds)

def get_unique_path(path):
    """Generuje unikátní cestu k souboru přidáním _1, _2, atd."""
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

# === JÁDROVÁ LOGIKA ===
def get_openrouter_client(config):
    """Inicializace OpenRouter.ai klienta s API klíčem z konfigurace"""
    api_key = config["openrouter"]["api_key"]
    if not api_key:
        raise ValueError("OpenRouter API klíč není nakonfigurován")
    
    base_url = "https://openrouter.ai/api/v1"
    return OpenAI(base_url=base_url, api_key=api_key)

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
    max_pages = config["pdf"]["max_pages"]
    
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



def parse_and_validate_ai_response(json_content: str) -> AIResponse:
    """Parse JSON content and validate with Pydantic model"""
    parsed_data = json.loads(json_content)
    ai_response = AIResponse(**parsed_data)
    return ai_response

def fetch_structured_data_from_ai(text: str, config) -> Tuple[AIResponse, Dict[str, Any]]:
    """
    Extrakce informací o vinylové desce z textu pomocí OpenRouter
    """
    client = get_openrouter_client(config)
    prompt = load_prompt()
    model = config["openrouter"]["model"]
    max_tokens = config["openrouter"]["max_tokens"]
    temperature = config["openrouter"]["temperature"]
    timeout = config["advanced"]["timeout_seconds"]
    retry_attempts = config["advanced"]["retry_attempts"]
    
    logging.info(f"Používám OpenRouter s modelem: {model}")
    
    # Metriky pro tento request
    request_metrics = {
        "prompt_tokens": 0,
        "response_tokens": 0,
        "success": False,
        "attempts": 0
    }
    
    # Logování promptu v DEBUG režimu
    logging.debug(f"AI Prompt: {prompt}")
    logging.debug(f"AI Text (prvních 500 znaků): {text[:500]}...")
    
    last_exception = None
    
    for attempt in range(retry_attempts):
        request_metrics["attempts"] = attempt + 1
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                response_format={"type": "json_object"}
            )
            
            # Získání metrik o tokenech s kontrolou, zda response.usage není None
            if response.usage is not None:
                request_metrics["prompt_tokens"] = response.usage.prompt_tokens
                request_metrics["response_tokens"] = response.usage.completion_tokens
                
                # Aktualizace globálních metrik (thread-safe)
                with metrics_lock:
                    METRICS["total_tokens_used"] += request_metrics["prompt_tokens"]
                    METRICS["total_response_tokens"] += request_metrics["response_tokens"]
            else:
                logging.warning("Informace o použití tokenu nejsou k dispozici")
            
            # Parsování JSON odpovědi
            json_content = response.choices[0].message.content
            if not json_content:
                raise ValueError("Obdržena prázdná odpověď od AI poskytovatele")
            
            # Logování odpovědi v DEBUG režimu
            logging.debug(f"AI Odpověď: {json_content}")
            
            # Pokus o parsování JSON a validace Pydantic modelem
            try:
                ai_response = parse_and_validate_ai_response(json_content)
                
                request_metrics["success"] = True
                with metrics_lock:
                    METRICS["successful_parses"] += 1
                
                return ai_response, request_metrics
            except (json.JSONDecodeError, ValueError) as e:
                content_preview = json_content[:200] if json_content else "(prázdné)"
                last_exception = ValueError(f"Nepodařilo se zpracovat AI odpověď jako JSON: {e}. Odpověď: {content_preview}...")
                logging.warning(f"Pokus o parsování {attempt + 1} selhal: {str(last_exception)}")
                if attempt == retry_attempts - 1:
                    with metrics_lock:
                        METRICS["failed_parses"] += 1
                    raise last_exception from e
        
        except Exception as e:
            last_exception = e
            logging.warning(f"API volání pokus {attempt + 1} selhalo: {str(e)}")
            if attempt == retry_attempts - 1:
                with metrics_lock:
                    METRICS["failed_parses"] += 1
                raise RuntimeError(f"AI API volání selhalo po {retry_attempts} pokusech: {str(e)}")
            
            # Čekání před dalším pokusem (exponenciální backoff)
            wait_time = (2 ** attempt) * 1
            logging.info(f"Čekám {wait_time}s před dalším pokusem...")
            time.sleep(wait_time)

    # Tento kód by neměl být nikdy dosažen díky raise v except bloku výše,
    # ale type checker vyžaduje explicitní return/raise na konci funkce
    raise RuntimeError("Neočekávaná chyba ve funkci fetch_structured_data_from_ai")

# === LOGIKA ZPRACOVÁNÍ A TRANSFORMACE DAT ===
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
    """
    Transformuje AI response na finální výstupní slovník pro serializaci do JSON
    """
    # Výpočet celkové doby trvání na strany
    side_durations = calculate_side_durations(ai_response.tracks)
    
    # Transformace stop - pořadí podle šablony: title, side, position, duration_seconds, duration_formatted
    output_tracks = []
    for track in ai_response.tracks:
        duration_seconds = parse_duration(track.duration)
        duration_formatted = normalize_duration_format(track.duration)

        # Logování varování pro neplatné doby trvání místo tichého nastavování na 0
        if duration_seconds is None:
            logging.warning(f"Neplatná doba trvání pro stopu '{track.title}' na straně {track.side}, pozice {track.position}: '{track.duration}'. Nastavuji na 0 sekund.")
            duration_seconds = 0

        output_tracks.append(OutputTrack(
            title=track.title,
            side=track.side,
            position=track.position,
            duration_seconds=duration_seconds,
            duration_formatted=duration_formatted
        ))
    
    # Vytvoření výstupního modelu BEZ path_id
    output_model = OutputFileModel(
        source_path=source_path,
        tracks=output_tracks,
        side_durations=side_durations
    )
    
    # Převod na slovník pro serializaci
    return output_model.model_dump()

# === ORCHESTRACE A SOUČĚŽNÉ ZPRACOVÁNÍ ===
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
                    # Vnořený ZIP - extrahujeme a zpracujeme rekurzivně
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

def collect_pdf_sources(config) -> List[Tuple[str, str, bytes]]:
    """Sbírá všechny PDF soubory z adresáře včetně ZIP archivů
    
    Returns:
        List of tuples: (absolute_path, relative_path, pdf_bytes)
    """
    pdf_files = []
    input_dir = config["processing"]["input_directory"]
    max_file_size_mb = config["processing"]["max_file_size_mb"]
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
                # ZIP archivy - zpracování pomocí _process_zip_stream
                try:
                    with open(file_path, 'rb') as f:
                        zip_bytes = f.read()
                        zip_pdfs = _process_zip_stream(zip_bytes, abs_path, rel_path)
                        pdf_files.extend(zip_pdfs)
                except Exception as e:
                    logging.error(f"Chyba při zpracování ZIP souboru {rel_path}: {str(e)}")
    
    logging.info(f"Nalezeno {len(pdf_files)} PDF souborů ke zpracování")
    return pdf_files

def process_single_pdf(pdf_data: Tuple[str, str, bytes], config, output_dir, processed_files=None, stop_event: Optional[threading.Event] = None) -> Optional[Dict[str, Any]]:
    """Zpracování jednoho PDF souboru"""
    abs_path, pdf_id, pdf_bytes = pdf_data
    start_time = time.time()

    if stop_event and stop_event.is_set():
        logging.info(f"Zpracování souboru {pdf_id} přerušeno.")
        return None
    
    # Vytvoření bezpečného názvu souboru z cesty s hash pro jedinečnost
    safe_filename = pdf_id.replace('::', '_').replace('/', '_').replace('\\', '_')
    # Přidání hash pro zajištění jedinečnosti
    pdf_hash = hashlib.md5(pdf_id.encode('utf-8')).hexdigest()[:8]
    output_file = f"{os.path.splitext(safe_filename)[0]}_{pdf_hash}.json"
    base_output_path = os.path.join(output_dir, output_file)
    
    # Získání unikátní cesty
    output_path = get_unique_path(base_output_path)
    
    # Kontrola, zda byl soubor již zpracován (kontrola podle pdf_id hash)
    if processed_files is not None:
        # Kontrola podle hash v názvu souboru místo přesné cesty
        for processed_file in processed_files:
            if pdf_hash in os.path.basename(processed_file):
                logging.info(f"Přeskakuji již zpracovaný soubor: {pdf_id}")
                return None
    
    logging.info(f"Zpracovávám: {pdf_id}")
    logging.debug(f"Zdrojová cesta: {abs_path}")
    
    try:
        # Extrakce textu z PDF
        text = extract_text_from_pdf(pdf_bytes, config)
        
        if not text.strip() or len(text.strip()) < config["pdf"]["min_text_length"]:
            logging.warning(f"Přeskakuji {pdf_id}: Není dostatek extrahovaného textu ({len(text.strip())} znaků)")
            return None
        
        # Uložení extrahovaného textu pro debugování (pokud je povoleno)
        if config["advanced"]["save_extracted_text"]:
            debug_file = f"{os.path.splitext(safe_filename)[0]}_extrahovany_text.txt"
            debug_path = os.path.join(output_dir, debug_file)
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(text)
        
        # Kontrola zastavení před dlouhotrvající operací
        if stop_event and stop_event.is_set():
            logging.info(f"Zpracování souboru {pdf_id} přerušeno.")
            return None

        # Extrakce dat pomocí AI
        ai_response, request_metrics = fetch_structured_data_from_ai(text, config)
        
        # Transformace dat na výstupní formát
        output_data = transform_ai_response(ai_response, abs_path)
        
        # Uložení výstupního JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        processing_time = time.time() - start_time
        
        # Aktualizace metrik (thread-safe)
        with metrics_lock:
            METRICS["processed_files"] += 1
            METRICS["total_processing_time"] += processing_time
        
        logging.info(f"Úspěch: Data uložena do {output_path}")
        logging.debug(f"Skladby: {len(output_data['tracks'])} s daty o celkové době trvání")
        logging.debug(f"Doba zpracování: {processing_time:.2f}s")
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
        with metrics_lock:
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
def run_processing_pipeline(config, stop_event: Optional[threading.Event] = None):
    """
    Zpracování všech PDF souborů v zadaném adresáři paralelně
    """
    input_dir = config["processing"]["input_directory"]
    output_dir = config["processing"]["output_directory"]
    max_workers = config["processing"]["max_workers"]
    skip_processed = config["processing"]["skip_processed"]
    
    if not os.path.isdir(input_dir):
        logging.error(f"Vstupní adresář '{input_dir}' neexistuje.")
        return
    
    # Vytvoření výstupního adresáře, pokud neexistuje
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
    
    with metrics_lock:
        METRICS["total_files"] = len(pdf_files)
        METRICS["start_time"] = datetime.now()
    
    logging.info(f"Nalezeno {len(pdf_files)} PDF souborů ke zpracování (sběr trval {collection_time:.2f} sekund).")
    logging.info(f"Zpracovávám s {max_workers} paralelními vlákny...")
    
    # Paralelní zpracování pomocí ThreadPoolExecutor
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Vytvoření úloh pro každé PDF
        futures = [executor.submit(process_single_pdf, pdf_data, config, output_dir, processed_files, stop_event) for pdf_data in pdf_files]

        # Sledování průběhu
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            if stop_event and stop_event.is_set():
                logging.warning("Zpracování přerušeno uživatelem.")
                # Zrušení zbývajících úkolů
                for f in futures:
                    if not f.done():
                        f.cancel()
                break

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
    
    with metrics_lock:
        METRICS["end_time"] = datetime.now()

    # Výpočet celkových metrik (čtení je thread-safe)
    total_time = (METRICS["end_time"] - METRICS["start_time"]).total_seconds()
    avg_time_per_file = METRICS["total_processing_time"] / max(METRICS["processed_files"], 1)
    
    logging.info(f"\n=== Souhrn zpracování ===")
    logging.info(f"Úspěšně zpracováno: {METRICS['processed_files']}/{METRICS['total_files']} souborů")
    logging.info(f"Selhalo: {METRICS['failed_files']} souborů")
    logging.info(f"Celkový čas: {total_time:.2f} sekund")
    logging.info(f"Průměrný čas na soubor: {avg_time_per_file:.2f} sekund")
    logging.info(f"Celkem použitých tokenů: {METRICS['total_tokens_used']}")
    logging.info(f"Celkem odpovědních tokenů: {METRICS['total_response_tokens']}")
    logging.info(f"Úspěšných AI parsování: {METRICS['successful_parses']}")
    logging.info(f"Neúspěšných AI parsování: {METRICS['failed_parses']}")
    
    # Uložení metrik do souboru - OPRAVENÁ VERZE
    metrics_file = os.path.join(output_dir, "zpracovani_metriky.json")
    try:
        # Vytvoření kopie METRICS pro serializaci
        metrics_copy = METRICS.copy()
        
        # Převod datetime objektů na ISO řetězce
        if metrics_copy.get("start_time") is not None:
            metrics_copy["start_time"] = metrics_copy["start_time"].isoformat()
        if metrics_copy.get("end_time") is not None:
            metrics_copy["end_time"] = metrics_copy["end_time"].isoformat()
        
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "config": config,
                "metrics": metrics_copy,
                "results": results
            }, f, indent=2, ensure_ascii=False)
        logging.info(f"Metriky uloženy do {metrics_file}")
    except Exception as e:
        logging.error(f"Nepodařilo se uložit metriky: {str(e)}")

# === HLAVNÍ SPUŠTĚCÍ BLOK ===
def main():
    
    parser = argparse.ArgumentParser(description='Extrakce informací o vinylových deskách z PDF souborů pomocí OpenRouter AI.')
    parser.add_argument('--config', '-c', help='Cesta ke konfiguračnímu souboru')
    parser.add_argument('--log-level', '-l', default="INFO", 
                        help='Úroveň logování (DEBUG, INFO, WARNING, ERROR)')
    parser.add_argument('--log-file', help='Cesta k logovacímu souboru')
    
    args = parser.parse_args()
    
    # Načtení konfigurace
    config = load_config(args.config)

    
    # Ověření, zda je nastaven API klíč
    if not config["openrouter"]["api_key"]:
        print("CHYBA: OpenRouter API klíč není nakonfigurován. Nastavte ho v .env souboru nebo v konfiguračním JSON souboru.")
        print("Příklad .env souboru:")
        print("OPENROUTER_API_KEY=sk-vas-api-klic")
        return   
    # Nastavení logování
    setup_logging(args.log_level, args.log_file)
    
    logging.info("=== Cue-AI Vinyl Record Extractor ===")
    logging.info(f"Vstupní adresář: {config['processing']['input_directory']}")
    logging.info(f"Výstupní adresář: {config['processing']['output_directory']}")
    logging.info(f"Počet paralelních vláken: {config['processing']['max_workers']}")
    logging.info(f"OpenRouter model: {config['openrouter']['model']}")
    logging.info("=====================================")
    
    try:
        run_processing_pipeline(config)
        logging.info("\nZpracování dokončeno!")
    except Exception as e:
        logging.error(f"Kritická chyba: {str(e)}")
        raise

if __name__ == "__main__":
    main()