import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import json
import glob
from pathlib import Path
from datetime import datetime
import re
import time

class VinylRecordViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Vinyl Record Viewer s Logy")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        # Data storage
        self.albums = []
        self.filtered_albums = []
        self.current_album = None
        self.logs = []
        self.filtered_logs = []

        # Real-time monitoring
        self.monitoring_enabled = True
        self.refresh_interval = 5000  # 5 seconds
        self.last_albums_check = 0
        self.last_logs_check = 0
        self.current_directory = None
        
        # Create main menu
        self.create_menu()
        
        # Create main frame
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.albums_tab = ttk.Frame(self.notebook)
        self.logs_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.albums_tab, text="Alba")
        self.notebook.add(self.logs_tab, text="Logy")
        
        # Create content for albums tab
        self.create_albums_tab_content()
        
        # Create content for logs tab
        self.create_logs_tab_content()
        
        # Create status bar
        self.create_status_bar()
        
        # Load data from default directory
        self.load_data_from_directory()

        # Start real-time monitoring
        self.start_monitoring()
    
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Soubor", menu=file_menu)
        file_menu.add_command(label="Načíst adresář", command=self.load_directory)
        file_menu.add_separator()
        file_menu.add_command(label="Konec", command=self.root.quit)

        # Monitoring menu
        monitoring_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Monitoring", menu=monitoring_menu)
        self.monitoring_var = tk.BooleanVar(value=True)
        monitoring_menu.add_checkbutton(label="Automatické obnovování", variable=self.monitoring_var, command=self.toggle_monitoring)
        monitoring_menu.add_command(label="Obnovit nyní", command=self.refresh_data)
        monitoring_menu.add_separator()
        monitoring_menu.add_command(label="Nastavení intervalu...", command=self.set_refresh_interval)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Nápověda", menu=help_menu)
        help_menu.add_command(label="O aplikaci", command=self.show_about)
    
    def create_albums_tab_content(self):
        # Create search frame
        search_frame = ttk.Frame(self.albums_tab)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Hledat alba:").pack(side=tk.LEFT, padx=(0, 5))

        self.album_search_var = tk.StringVar()
        self.album_search_var.trace('w', self.on_album_search_change)

        search_entry = ttk.Entry(search_frame, textvariable=self.album_search_var, width=50)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(search_frame, text="Vyčistit", command=self.clear_album_search).pack(side=tk.LEFT, padx=(5, 0))

        # Create content frame
        content_frame = ttk.Frame(self.albums_tab)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Create paned window for resizable panels
        paned = ttk.PanedWindow(content_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel - Album list
        left_frame = self._create_left_panel_with_listbox(paned, "Alba", self.on_album_select)
        self.album_listbox = left_frame['listbox']

        # Right panel - Album details
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        ttk.Label(right_frame, text="Detaily alba", font=('TkDefaultFont', 10, 'bold')).pack(pady=(0, 5))

        # Album info frame
        self.album_info_frame = ttk.LabelFrame(right_frame, text="Informace o albu")
        self.album_info_frame.pack(fill=tk.X, padx=5, pady=5)

        # Treeview for tracks
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create treeview with scrollbar
        tree_scrollbar = ttk.Scrollbar(tree_frame)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.track_tree = ttk.Treeview(
            tree_frame,
            columns=('side', 'position', 'title', 'duration'),
            show='headings',
            yscrollcommand=tree_scrollbar.set
        )
        self.track_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.config(command=self.track_tree.yview)

        # Configure columns
        self.track_tree.heading('side', text='Strana')
        self.track_tree.heading('position', text='Pořadí')
        self.track_tree.heading('title', text='Název')
        self.track_tree.heading('duration', text='Délka')

        self.track_tree.column('side', width=50, anchor=tk.CENTER)
        self.track_tree.column('position', width=50, anchor=tk.CENTER)
        self.track_tree.column('title', width=300, anchor=tk.W)
        self.track_tree.column('duration', width=70, anchor=tk.CENTER)

        # Side durations frame
        self.side_durations_frame = ttk.LabelFrame(right_frame, text="Délka stran")
        self.side_durations_frame.pack(fill=tk.X, padx=5, pady=5)

    def _create_left_panel_with_listbox(self, paned, title, select_callback):
        """Extract duplicate code for creating left panel with listbox"""
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text=title, font=('TkDefaultFont', 10, 'bold')).pack(pady=(0, 5))

        # Create listbox with scrollbar
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        listbox.bind('<<ListboxSelect>>', select_callback)

        return {'frame': left_frame, 'listbox': listbox}
    
    def create_logs_tab_content(self):
        # Create search and filter frame
        filter_frame = ttk.Frame(self.logs_tab)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        # Search
        ttk.Label(filter_frame, text="Hledat v logech:").pack(side=tk.LEFT, padx=(0, 5))

        self.log_search_var = tk.StringVar()
        self.log_search_var.trace('w', self.on_log_search_change)

        search_entry = ttk.Entry(filter_frame, textvariable=self.log_search_var, width=50)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(filter_frame, text="Vyčistit", command=self.clear_log_search).pack(side=tk.LEFT, padx=(5, 0))

        # Filter options
        ttk.Label(filter_frame, text="Filtr:").pack(side=tk.LEFT, padx=(20, 5))

        self.log_filter_var = tk.StringVar(value="Vše")
        filter_options = ["Vše", "Chyby", "Varování", "Info"]
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.log_filter_var, values=filter_options, width=15, state="readonly")
        filter_combo.pack(side=tk.LEFT, padx=(0, 5))
        filter_combo.bind('<<ComboboxSelected>>', self.on_log_filter_change)

        # Create content frame
        content_frame = ttk.Frame(self.logs_tab)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Create paned window for resizable panels
        paned = ttk.PanedWindow(content_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left panel - Log list
        left_frame = self._create_left_panel_with_listbox(paned, "Logy", self.on_log_select)
        self.log_listbox = left_frame['listbox']

        # Right panel - Log details
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        ttk.Label(right_frame, text="Detaily logu", font=('TkDefaultFont', 10, 'bold')).pack(pady=(0, 5))

        # Log details frame
        self.log_details_frame = ttk.LabelFrame(right_frame, text="Detaily")
        self.log_details_frame.pack(fill=tk.X, padx=5, pady=5)

        # Log message frame
        self.log_message_frame = ttk.LabelFrame(right_frame, text="Zpráva")
        self.log_message_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create scrolled text for log message
        self.log_message_text = scrolledtext.ScrolledText(self.log_message_frame, wrap=tk.WORD, height=10)
        self.log_message_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Statistics frame
        self.stats_frame = ttk.LabelFrame(right_frame, text="Statistiky")
        self.stats_frame.pack(fill=tk.X, padx=5, pady=5)
    
    def create_status_bar(self):
        self.status_bar = ttk.Label(self.main_frame, text="Připraveno", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, pady=(10, 0))
    
    def load_data_from_directory(self, directory=None):
        if directory is None:
            # Use default directory from config
            directory = "C:/Users/marti/Desktop/gz_pdf_extractor/output-pdf"

        if not os.path.exists(directory):
            self.update_status(f"Adresář neexistuje: {directory}")
            return

        self.current_directory = directory

        # Load albums
        self.load_albums_from_directory(directory)

        # Load logs
        self.load_logs_from_directory(directory)

        # Update last check times
        self.last_albums_check = time.time()
        self.last_logs_check = time.time()
    
    def load_albums_from_directory(self, directory):
        self.albums = []
        json_files = glob.glob(os.path.join(directory, "*.json"))
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Add file path to data
                    data['file_path'] = json_file
                    self.albums.append(data)
            except Exception as e:
                print(f"Chyba při načítání souboru {json_file}: {e}")
        
        self.filtered_albums = self.albums.copy()
        self.update_album_list()
        self.update_status(f"Načteno {len(self.albums)} alb")
    
    def load_logs_from_directory(self, directory):
        self.logs = []
        logs_dir = os.path.join(directory, "logs")

        if not os.path.exists(logs_dir):
            self.update_status("Adresář s logy neexistuje")
            return

        # Load from both errors.jsonl and logs.jsonl
        log_files = [
            os.path.join(logs_dir, "errors.jsonl"),
            os.path.join(logs_dir, "logs.jsonl")
        ]

        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    log_entry = json.loads(line.strip())
                                    # Add source file info to distinguish between error and general logs
                                    log_entry['log_source'] = os.path.basename(log_file)
                                    self.logs.append(log_entry)
                                except json.JSONDecodeError as e:
                                    print(f"Chyba při parsování logu z {log_file}: {e}")
                except Exception as e:
                    print(f"Chyba při načítání logů z {log_file}: {e}")

        # Sort logs by timestamp if available
        self.logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        self.filtered_logs = self.logs.copy()
        self.update_log_list()
        self.update_log_statistics()
        self.update_status(f"Načteno {len(self.logs)} logů")
    
    def update_album_list(self):
        self.album_listbox.delete(0, tk.END)
        
        for album in self.filtered_albums:
            # Extract album name from source path
            source_path = album.get('source_path', '')
            if '::' in source_path:
                album_name = source_path.split('::')[0]
                album_name = os.path.basename(album_name)
            else:
                album_name = os.path.basename(source_path)
            
            self.album_listbox.insert(tk.END, album_name)
    
    def update_log_list(self):
        self.log_listbox.delete(0, tk.END)

        for log in self.filtered_logs:
            timestamp = log.get('timestamp', '')

            # Format timestamp for display
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    timestamp_str = timestamp
            else:
                timestamp_str = 'Neznámý čas'

            # Determine log type and create display text
            if 'source_id' in log:
                # Error log format (errors.jsonl)
                source_id = log.get('source_id', '')
                display_text = f"{timestamp_str} - {source_id}"
            else:
                # General log format (logs.jsonl)
                level = log.get('level', 'INFO')
                message = log.get('message', '')
                # Truncate long messages for list display
                short_message = message[:50] + "..." if len(message) > 50 else message
                display_text = f"{timestamp_str} - [{level}] {short_message}"

            self.log_listbox.insert(tk.END, display_text)
    
    def update_log_statistics(self):
        # Clear previous statistics
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        # Calculate statistics
        total_logs = len(self.logs)

        # Count by log type and level
        error_count = 0
        warning_count = 0
        info_count = 0
        error_logs = 0  # From errors.jsonl
        general_logs = 0  # From logs.jsonl

        for log in self.logs:
            if 'source_id' in log:
                # Error log format
                error_logs += 1
                error_msg = log.get('error', '').lower()
                if any(keyword in error_msg for keyword in ['error', 'chyba', 'failed', 'selhalo']):
                    error_count += 1
                elif any(keyword in error_msg for keyword in ['warning', 'varování', 'warn']):
                    warning_count += 1
                else:
                    info_count += 1
            else:
                # General log format
                general_logs += 1
                level = log.get('level', '').upper()
                if level in ['ERROR', 'CRITICAL']:
                    error_count += 1
                elif level == 'WARNING':
                    warning_count += 1
                else:
                    info_count += 1

        # Display statistics
        ttk.Label(self.stats_frame, text=f"Celkem logů: {total_logs}").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(self.stats_frame, text=f"Chyby: {error_count}").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(self.stats_frame, text=f"Varování: {warning_count}").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(self.stats_frame, text=f"Info: {info_count}").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(self.stats_frame, text=f"Error logy: {error_logs}").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(self.stats_frame, text=f"Obecné logy: {general_logs}").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
    
    def on_album_select(self, event):
        selection = self.album_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index < len(self.filtered_albums):
            self.current_album = self.filtered_albums[index]
            self.display_album_details()
    
    def on_log_select(self, event):
        selection = self.log_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index < len(self.filtered_logs):
            log = self.filtered_logs[index]
            self.display_log_details(log)
    
    def display_album_details(self):
        if not self.current_album:
            return
        
        # Clear previous info
        for widget in self.album_info_frame.winfo_children():
            widget.destroy()
        
        for widget in self.side_durations_frame.winfo_children():
            widget.destroy()
        
        # Display album info
        source_path = self.current_album.get('source_path', '')
        ttk.Label(self.album_info_frame, text=f"Zdroj: {source_path}").pack(anchor=tk.W, padx=5, pady=2)
        
        # Display tracks
        self.track_tree.delete(*self.track_tree.get_children())
        
        tracks = self.current_album.get('tracks', [])
        for track in tracks:
            self.track_tree.insert('', tk.END, values=(
                track.get('side', ''),
                track.get('position', ''),
                track.get('title', ''),
                track.get('duration_formatted', '')
            ))
        
        # Display side durations
        side_durations = self.current_album.get('side_durations', {})
        for side, duration in side_durations.items():
            ttk.Label(self.side_durations_frame, text=f"Strana {side}: {duration}").pack(anchor=tk.W, padx=5, pady=2)
    
    def display_log_details(self, log):
        # Clear previous details
        for widget in self.log_details_frame.winfo_children():
            widget.destroy()

        # Display log details
        timestamp = log.get('timestamp', '')

        # Format timestamp
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                timestamp_str = timestamp
        else:
            timestamp_str = 'Neznámý čas'

        ttk.Label(self.log_details_frame, text=f"Čas: {timestamp_str}").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)

        # Display different details based on log type
        if 'source_id' in log:
            # Error log format (errors.jsonl)
            source_id = log.get('source_id', '')
            source_path = log.get('source_path', '')
            ttk.Label(self.log_details_frame, text=f"ID: {source_id}").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.log_details_frame, text=f"Cesta: {source_path}").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)

            # Display error message
            self.log_message_text.delete(1.0, tk.END)
            error_msg = log.get('error', '')
            self.log_message_text.insert(tk.END, error_msg)
        else:
            # General log format (logs.jsonl)
            level = log.get('level', '')
            module = log.get('module', '')
            function = log.get('function', '')
            line = log.get('line', '')

            ttk.Label(self.log_details_frame, text=f"Úroveň: {level}").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.log_details_frame, text=f"Modul: {module}").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.log_details_frame, text=f"Funkce: {function}").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.log_details_frame, text=f"Řádek: {line}").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)

            # Display log message
            self.log_message_text.delete(1.0, tk.END)
            message = log.get('message', '')
            self.log_message_text.insert(tk.END, message)
    
    def on_album_search_change(self, *args):
        if search_text := self.album_search_var.get().lower():
            self.filtered_albums = []
            for album in self.albums:
                # Search in album name
                source_path = album.get('source_path', '')
                if '::' in source_path:
                    album_name = source_path.split('::')[0]
                    album_name = os.path.basename(album_name)
                else:
                    album_name = os.path.basename(source_path)

                if search_text in album_name.lower():
                    self.filtered_albums.append(album)
                    continue

                # Search in track names
                tracks = album.get('tracks', [])
                for track in tracks:
                    if search_text in track.get('title', '').lower():
                        self.filtered_albums.append(album)
                        break
        else:
            self.filtered_albums = self.albums.copy()

        self.update_album_list()
        self.update_status(f"Nalezeno {len(self.filtered_albums)} alb")
    
    def on_log_search_change(self, *args):
        self.apply_log_filters()
    
    def on_log_filter_change(self, *args):
        self.apply_log_filters()
    
    def apply_log_filters(self):
        search_text = self.log_search_var.get().lower()
        filter_type = self.log_filter_var.get()

        self.filtered_logs = []

        for log in self.logs:
            # Apply search filter
            if search_text:
                # Search in different fields based on log type
                if 'source_id' in log:
                    # Error log format
                    error_msg = log.get('error', '').lower()
                    source_id = log.get('source_id', '').lower()
                    if search_text not in error_msg and search_text not in source_id:
                        continue
                else:
                    # General log format
                    message = log.get('message', '').lower()
                    module = log.get('module', '').lower()
                    function = log.get('function', '').lower()
                    if search_text not in message and search_text not in module and search_text not in function:
                        continue

            # Apply type filter
            if filter_type != "Vše":
                if 'source_id' in log:
                    # Error log format - filter by error message content
                    error_msg = log.get('error', '').lower()
                    if filter_type == "Chyby" and all(keyword not in error_msg for keyword in ['error', 'chyba', 'failed', 'selhalo']):
                        continue
                    elif filter_type == "Varování" and all(keyword not in error_msg for keyword in ['warning', 'varování', 'warn']):
                        continue
                    elif filter_type == "Info" and any(keyword in error_msg for keyword in ['error', 'chyba', 'failed', 'selhalo', 'warning', 'varování', 'warn']):
                        continue
                else:
                    # General log format - filter by level
                    level = log.get('level', '').upper()
                    if filter_type == "Chyby" and level not in ['ERROR', 'CRITICAL']:
                        continue
                    elif filter_type == "Varování" and level != 'WARNING':
                        continue
                    elif filter_type == "Info" and level not in ['INFO', 'DEBUG']:
                        continue

            self.filtered_logs.append(log)

        self.update_log_list()
        self.update_status(f"Filtrováno {len(self.filtered_logs)} logů")
    
    def clear_album_search(self):
        self.album_search_var.set("")
        self.filtered_albums = self.albums.copy()
        self.update_album_list()
        self.update_status(f"Zobrazeno {len(self.albums)} alb")
    
    def clear_log_search(self):
        self.log_search_var.set("")
        self.log_filter_var.set("Vše")
        self.filtered_logs = self.logs.copy()
        self.update_log_list()
        self.update_status(f"Zobrazeno {len(self.logs)} logů")
    
    def load_directory(self):
        if directory := filedialog.askdirectory(title="Vyberte adresář s JSON soubory"):
            self.load_data_from_directory(directory)
    
    def update_status(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        monitoring_status = "🟢 AUTO" if self.monitoring_enabled else "🔴 MANUAL"
        self.status_bar.config(text=f"[{timestamp}] {message} | {monitoring_status}")
    
    def show_about(self):
        messagebox.showinfo(
            "O aplikaci",
            "Vinyl Record Viewer s Logy\n\n"
            "Aplikace pro prohlížení dat extrahovaných z PDF souborů s informacemi o vinylových deskách\n"
            "a vizualizace logů ze zpracování.\n\n"
            "Vytvořeno pomocí Tkinter\n\n"
            "Real-time monitoring: Automaticky obnovuje data každých 5 sekund"
        )

    # Real-time monitoring methods
    def start_monitoring(self):
        """Start real-time monitoring of data files"""
        if self.monitoring_enabled:
            self.check_for_updates()

    def check_for_updates(self):
        """Check for updates in data files and refresh if needed"""
        if not self.monitoring_enabled or not self.current_directory:
            return

        try:
            # Check if albums directory has new files
            if self._has_albums_changed():
                self.load_albums_from_directory(self.current_directory)
                self.last_albums_check = time.time()

            # Check if logs have changed
            if self._has_logs_changed():
                self.load_logs_from_directory(self.current_directory)
                self.last_logs_check = time.time()

        except Exception as e:
            print(f"Chyba při kontrole aktualizací: {e}")

        # Schedule next check
        if self.monitoring_enabled:
            self.root.after(self.refresh_interval, self.check_for_updates)

    def _has_albums_changed(self):
        """Check if album files have been modified since last check"""
        if not self.current_directory:
            return False
        try:
            json_files = glob.glob(os.path.join(self.current_directory, "*.json"))
            for json_file in json_files:
                if os.path.getmtime(json_file) > self.last_albums_check:
                    return True
            return False
        except Exception:
            return False

    def _has_logs_changed(self):
        """Check if log files have been modified since last check"""
        if not self.current_directory:
            return False
        try:
            logs_dir = os.path.join(self.current_directory, "logs")
            if not os.path.exists(logs_dir):
                return False

            errors_file = os.path.join(logs_dir, "errors.jsonl")
            logs_file = os.path.join(logs_dir, "logs.jsonl")

            for log_file in [errors_file, logs_file]:
                if os.path.exists(log_file) and os.path.getmtime(log_file) > self.last_logs_check:
                    return True
            return False
        except Exception:
            return False

    def toggle_monitoring(self):
        """Toggle real-time monitoring on/off"""
        self.monitoring_enabled = self.monitoring_var.get()
        if self.monitoring_enabled:
            self.update_status("Automatické obnovování zapnuto")
            self.start_monitoring()
        else:
            self.update_status("Automatické obnovování vypnuto")

    def refresh_data(self):
        """Manually refresh all data"""
        if self.current_directory:
            self.load_data_from_directory(self.current_directory)
            self.update_status("Data byla ručně obnovena")
        else:
            self.update_status("Není vybrán žádný adresář")

    def set_refresh_interval(self):
        """Set custom refresh interval"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Nastavení intervalu obnovování")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))

        ttk.Label(dialog, text="Interval obnovování (sekundy):").pack(pady=10)

        interval_var = tk.StringVar(value=str(self.refresh_interval // 1000))
        entry = ttk.Entry(dialog, textvariable=interval_var, width=10)
        entry.pack(pady=5)
        entry.focus()

        def apply_interval():
            try:
                new_interval = int(interval_var.get())
                if new_interval < 1:
                    messagebox.showerror("Chyba", "Interval musí být alespoň 1 sekunda")
                    return
                self.refresh_interval = new_interval * 1000
                self.update_status(f"Interval obnovování nastaven na {new_interval} sekund")
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Chyba", "Zadejte platné číslo")

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Použít", command=apply_interval).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Zrušit", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Bind Enter key to apply
        entry.bind('<Return>', lambda e: apply_interval())

if __name__ == "__main__":
    root = tk.Tk()
    app = VinylRecordViewer(root)
    root.mainloop()