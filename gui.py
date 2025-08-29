
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import queue
import json
import os
import logging
import glob
import subprocess
import platform
from pdf_extractor import run_processing_pipeline, load_config, setup_logging

class GuiHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.queue = queue.Queue()
        self.text_widget.after(100, self.process_queue)

    def emit(self, record):
        msg = self.format(record)
        self.queue.put(msg)

    def process_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
        self.text_widget.after(100, self.process_queue)

class PdfExtractorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Extractor GUI")
        self.geometry("1400x800")

        self.config = load_config()
        self.stop_event = threading.Event()

        # Hlavní horizontální rozdělení
        self.main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Levý panel pro současné GUI
        self.left_frame = ttk.Frame(self.main_paned, padding="10")
        self.main_paned.add(self.left_frame, weight=1)

        # Pravý panel pro viewer výsledků
        self.right_frame = ttk.Frame(self.main_paned, padding="10")
        self.main_paned.add(self.right_frame, weight=1)

        self.create_widgets()
        self.create_results_viewer()

    def create_widgets(self):
        # Frame for parameters
        params_frame = ttk.LabelFrame(self.left_frame, text="Nastavení", padding="10")
        params_frame.pack(fill=tk.X, pady=5)

        # Input Directory
        ttk.Label(params_frame, text="Vstupní adresář:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.input_dir_var = tk.StringVar(value=self.config['processing']['input_directory'])
        self.input_dir_entry = ttk.Entry(params_frame, textvariable=self.input_dir_var, width=60)
        self.input_dir_entry.grid(row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(params_frame, text="Procházet...", command=self.browse_input_dir).grid(row=0, column=2, padx=5)

        # Output Directory
        ttk.Label(params_frame, text="Výstupní adresář:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.output_dir_var = tk.StringVar(value=self.config['processing']['output_directory'])
        self.output_dir_entry = ttk.Entry(params_frame, textvariable=self.output_dir_var, width=60)
        self.output_dir_entry.grid(row=1, column=1, sticky=tk.EW, padx=5)
        ttk.Button(params_frame, text="Procházet...", command=self.browse_output_dir).grid(row=1, column=2, padx=5)

        # Model
        ttk.Label(params_frame, text="Model:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_var = tk.StringVar(value=self.config['openrouter']['model'])
        self.model_combo = ttk.Combobox(params_frame, textvariable=self.model_var, values=[
            "google/gemini-flash-1.5",
            "google/gemini-pro-1.5",
            "anthropic/claude-3-haiku",
            "anthropic/claude-3-sonnet",
            "openai/gpt-4o"
        ])
        self.model_combo.grid(row=2, column=1, sticky=tk.EW, padx=5)

        # Max Workers
        ttk.Label(params_frame, text="Max vláken:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_workers_var = tk.IntVar(value=self.config['processing']['max_workers'])
        self.max_workers_spinbox = ttk.Spinbox(params_frame, from_=1, to=16, textvariable=self.max_workers_var)
        self.max_workers_spinbox.grid(row=3, column=1, sticky=tk.W, padx=5)
        
        params_frame.columnconfigure(1, weight=1)

        # Frame for controls
        controls_frame = ttk.Frame(self.left_frame, padding="10")
        controls_frame.pack(fill=tk.X)

        self.run_button = ttk.Button(controls_frame, text="Spustit zpracování", command=self.run_processing)
        self.run_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(controls_frame, text="Zastavit", command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)


        # Frame for logs and output
        output_frame = ttk.LabelFrame(self.left_frame, text="Výstup a logy", padding="10")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = tk.Text(output_frame, wrap=tk.WORD, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Set up logging to the GUI
        self.gui_handler = GuiHandler(self.log_text)
        self.gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(self.gui_handler)
        logging.getLogger().setLevel(logging.INFO)

    def create_results_viewer(self):
        """Vytvoří pravý panel s viewerem výsledků"""
        # Hlavní label pro pravý panel
        results_label = ttk.Label(self.right_frame, text="Výsledky zpracování", font=("Arial", 12, "bold"))
        results_label.pack(pady=(0, 10))

        # Vertikální rozdělení pravého panelu
        self.results_paned = ttk.PanedWindow(self.right_frame, orient=tk.VERTICAL)
        self.results_paned.pack(fill=tk.BOTH, expand=True)

        # Horní část - tabulka se stranami
        top_frame = ttk.LabelFrame(self.results_paned, text="PDF soubory a strany", padding="5")
        self.results_paned.add(top_frame, weight=1)

        # Tabulka se stranami
        columns = ("pdf_name", "open", "side", "duration", "tracks")
        self.sides_tree = ttk.Treeview(top_frame, columns=columns, show="headings", height=8)

        # Nastavení sloupců
        self.sides_tree.heading("pdf_name", text="PDF File")
        self.sides_tree.heading("open", text="Open")
        self.sides_tree.heading("side", text="Side")
        self.sides_tree.heading("duration", text="Duration")
        self.sides_tree.heading("tracks", text="Tracks")

        self.sides_tree.column("pdf_name", width=300)
        self.sides_tree.column("open", width=50)
        self.sides_tree.column("side", width=50)
        self.sides_tree.column("duration", width=80)
        self.sides_tree.column("tracks", width=60)

        # Scrollbar pro horní tabulku
        sides_scrollbar = ttk.Scrollbar(top_frame, orient=tk.VERTICAL, command=self.sides_tree.yview)
        self.sides_tree.configure(yscrollcommand=sides_scrollbar.set)

        self.sides_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sides_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Spodní část - detail vybrané strany
        bottom_frame = ttk.LabelFrame(self.results_paned, text="Detail vybrané strany", padding="5")
        self.results_paned.add(bottom_frame, weight=1)

        # Tabulka s tracky
        track_columns = ("title", "position", "duration_sec", "duration_formatted")
        self.tracks_tree = ttk.Treeview(bottom_frame, columns=track_columns, show="headings", height=8)

        # Nastavení sloupců pro tracky
        self.tracks_tree.heading("title", text="Title")
        self.tracks_tree.heading("position", text="Position")
        self.tracks_tree.heading("duration_sec", text="Duration (sec)")
        self.tracks_tree.heading("duration_formatted", text="Duration (mm:ss)")

        self.tracks_tree.column("title", width=250)
        self.tracks_tree.column("position", width=80)
        self.tracks_tree.column("duration_sec", width=100)
        self.tracks_tree.column("duration_formatted", width=100)

        # Scrollbar pro spodní tabulku
        tracks_scrollbar = ttk.Scrollbar(bottom_frame, orient=tk.VERTICAL, command=self.tracks_tree.yview)
        self.tracks_tree.configure(yscrollcommand=tracks_scrollbar.set)

        self.tracks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tracks_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Tlačítko pro refresh dat
        refresh_button = ttk.Button(self.right_frame, text="Obnovit výsledky", command=self.refresh_results)
        refresh_button.pack(pady=(10, 0))

        # Bind události
        self.sides_tree.bind("<<TreeviewSelect>>", self.on_side_select)
        self.sides_tree.bind("<Double-1>", self.on_open_pdf)

        # Načtení dat při startu
        self.refresh_results()

    def browse_input_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.input_dir_var.set(directory)

    def browse_output_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_var.set(directory)

    def run_processing(self):
        self.log_text.delete('1.0', tk.END)
        self.stop_event.clear()

        # Update config from GUI
        self.config['processing']['input_directory'] = self.input_dir_var.get()
        self.config['processing']['output_directory'] = self.output_dir_var.get()
        self.config['openrouter']['model'] = self.model_var.get()
        self.config['processing']['max_workers'] = self.max_workers_var.get()

        if not self.config["openrouter"].get("api_key"):
            messagebox.showerror("Chyba", "OpenRouter API klíč není nastaven. Zkontrolujte .env soubor.")
            return

        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        self.processing_thread = threading.Thread(target=self.processing_task, daemon=True)
        self.processing_thread.start()

    def processing_task(self):
        try:
            # Inicializace logování do souboru z backendu
            log_dir = os.path.join(self.config['processing']['output_directory'], "logs")
            os.makedirs(log_dir, exist_ok=True)
            # Použijeme setup_logging z importovaného modulu
            setup_logging(
                log_level=self.config['advanced']['log_level'],
                log_file=os.path.join(log_dir, "processing.log")
            )

            run_processing_pipeline(self.config, stop_event=self.stop_event)
        except Exception as e:
            logging.error(f"Došlo k neočekávané chybě: {e}")
        finally:
            self.run_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            # Automatické obnovení výsledků po dokončení zpracování
            self.refresh_results()
            messagebox.showinfo("Hotovo", "Zpracování dokončeno.")
            
    def stop_processing(self):
        logging.info("Signál k zastavení zpracování...")
        self.stop_event.set()
        self.stop_button.config(state=tk.DISABLED)

    def refresh_results(self):
        """Načte a zobrazí výsledky ze všech JSON souborů"""
        # Spustí načítání v samostatném vlákně, aby GUI nezamrzlo
        threading.Thread(target=self._load_results_task, daemon=True).start()

    def _load_results_task(self):
        """Tato metoda běží na pozadí"""
        try:
            # Načtení dat z JSON souborů
            output_dir = self.config['processing']['output_directory']
            json_pattern = os.path.join(output_dir, "*.json")
            json_files = glob.glob(json_pattern)

            sides_data = []

            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Extrakce názvu PDF ze source_path
                    source_path = data.get('source_path', '')
                    pdf_name = os.path.basename(source_path) if source_path else os.path.basename(json_file).replace('.json', '')

                    # Zpracování každé strany
                    side_durations = data.get('side_durations', {})
                    tracks = data.get('tracks', [])

                    for side, duration in side_durations.items():
                        # Počet tracků pro tuto stranu
                        side_tracks = [t for t in tracks if t.get('side') == side]
                        track_count = len(side_tracks)

                        sides_data.append({
                            'pdf_name': pdf_name,
                            'source_path': source_path,
                            'side': side,
                            'duration': duration,
                            'track_count': track_count,
                            'tracks': side_tracks
                        })

                except Exception as e:
                    logging.warning(f"Chyba při načítání {json_file}: {e}")
                    continue

            # Seřazení podle názvu PDF a strany
            sides_data.sort(key=lambda x: (x['pdf_name'], x['side']))

            # Po dokončení naplánuj aktualizaci UI v hlavním vlákně
            self.after(0, self._update_results_in_gui, sides_data)

        except Exception as e:
            logging.error(f"Chyba při načítání výsledků: {e}")
            # Pro chyby také použijeme hlavní vlákno
            self.after(0, lambda: messagebox.showerror("Chyba", f"Nepodařilo se načíst výsledky: {e}"))

    def _update_results_in_gui(self, sides_data):
        """Tato metoda běží v hlavním vlákně a je bezpečná pro UI"""
        try:
            # Vyčištění tabulek
            for item in self.sides_tree.get_children():
                self.sides_tree.delete(item)
            for item in self.tracks_tree.get_children():
                self.tracks_tree.delete(item)

            # Uložení dat pro pozdější použití
            self.sides_data = {i: side_data for i, side_data in enumerate(sides_data)}

            # Vložení dat do tabulky
            for i, side_data in enumerate(sides_data):
                self.sides_tree.insert('', 'end', values=(
                    side_data['pdf_name'],
                    '📁',  # Ikona pro otevření
                    side_data['side'],
                    side_data['duration'],
                    side_data['track_count']
                ), tags=(str(i),))

            logging.info(f"Zobrazeno {len(sides_data)} stran.")
        except Exception as e:
            logging.error(f"Chyba při aktualizaci GUI: {e}")
            messagebox.showerror("Chyba", f"Nepodařilo se aktualizovat zobrazení: {e}")

    def on_side_select(self, event):
        """Obsluha výběru strany - zobrazí tracky"""
        selection = self.sides_tree.selection()
        if not selection:
            return

        # Vyčištění tabulky tracků
        for item in self.tracks_tree.get_children():
            self.tracks_tree.delete(item)

        # Získání dat vybrané strany
        item = selection[0]
        tags = self.sides_tree.item(item, 'tags')
        if not tags:
            return

        try:
            index = int(tags[0])
            side_data = self.sides_data[index]
            tracks = side_data['tracks']

            # Vložení tracků do spodní tabulky
            for track in tracks:
                self.tracks_tree.insert('', 'end', values=(
                    track.get('title', 'N/A'),
                    track.get('position', 'N/A'),
                    track.get('duration_seconds', 'N/A'),
                    track.get('duration_formatted', 'N/A')
                ))
        except (ValueError, KeyError) as e:
            logging.warning(f"Chyba při načítání tracků: {e}")

    def on_open_pdf(self, event):
        """Obsluha dvojkliku - otevře PDF soubor"""
        selection = self.sides_tree.selection()
        if not selection:
            return

        item = selection[0]
        tags = self.sides_tree.item(item, 'tags')
        if not tags:
            return

        try:
            index = int(tags[0])
            side_data = self.sides_data[index]
            source_path = side_data['source_path']

            if source_path and os.path.exists(source_path):
                try:
                    if platform.system() == 'Windows':
                        os.startfile(source_path)
                    elif platform.system() == 'Darwin':  # macOS
                        subprocess.run(['open', source_path])
                    else:  # Linux
                        subprocess.run(['xdg-open', source_path])
                    logging.info(f"Otevírám PDF: {source_path}")
                except Exception as e:
                    logging.error(f"Nepodařilo se otevřít PDF {source_path}: {e}")
                    messagebox.showerror("Chyba", f"Nepodařilo se otevřít PDF: {e}")
            else:
                messagebox.showwarning("Varování", f"PDF soubor nebyl nalezen: {source_path}")
        except (ValueError, KeyError) as e:
            logging.warning(f"Chyba při otevírání PDF: {e}")


if __name__ == "__main__":
    app = PdfExtractorGUI()
    app.mainloop()
