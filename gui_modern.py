
# -*- coding: utf-8 -*-
"""
Modern minimalist GUI for Vinyl Record Viewer + Logs
----------------------------------------------------
- Uses ttkbootstrap for a cleaner, rounded look (pip install ttkbootstrap)
- Keeps core behavior from the legacy script:
    * Choose a folder with *.json files for Albums and Logs
    * List albums/logs on the left, details on the right
    * Search/filter, open folder, refresh
- Track list rendering if data["tracks"] is present (title, duration, side)
- Falls back to key-value metadata table for unknown structures
- Soft, rounded "cards" and ample spacing to echo a chat-like, calm UI.

Run:
    python gui_modern.py
"""

import os
import sys
import json
import glob
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

# 3rd party for modern ttk styling (rounded, pleasant themes)
#   pip install ttkbootstrap
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip


APP_TITLE = "Vinyl Viewer — minimalist"
APP_MIN_SIZE = (980, 640)


# ----------------------------- Utilities -----------------------------

def human_path(path: str) -> str:
    if not path:
        return ""
    try:
        home = os.path.expanduser("~")
        return path.replace(home, "~")
    except Exception:
        return path


def open_in_explorer(path: str):
    if not path:
        return
    path = os.path.normpath(path)
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        os.system(f"open '{path}'")
    else:
        os.system(f"xdg-open '{path}'")


def duration_to_seconds(d):
    """Supports 'mm:ss' or seconds (int/str)."""
    if d is None:
        return 0
    if isinstance(d, (int, float)):
        return int(d)
    s = str(d).strip()
    if ":" in s:
        try:
            mm, ss = s.split(":")
            return int(mm) * 60 + int(ss)
        except Exception:
            return 0
    try:
        return int(float(s))
    except Exception:
        return 0


def seconds_to_mmss(sec: int) -> str:
    if sec is None:
        return ""
    sec = int(sec)
    return f"{sec // 60:02d}:{sec % 60:02d}"


# ----------------------------- App Class -----------------------------

class VinylApp(tb.Window):
    def __init__(self):
        super().__init__(themename="minty")  # calm, rounded; try "flatly", "pulse", "cosmo" if you prefer
        self.title(APP_TITLE)
        self.minsize(*APP_MIN_SIZE)
        try:
            # slightly larger base scaling for gentle look
            self.tk.call("tk", "scaling", 1.2)
        except Exception:
            pass

        # State
        self.album_dir = ""
        self.log_dir = ""
        self.albums = []
        self.filtered_albums = []
        self.logs = []
        self.filtered_logs = []

        # Build UI
        self._build_style()
        self._build_layout()
        self._bind_events()

    # ------------------------- Styling -------------------------
    def _build_style(self):
        style = self.style  # ttkbootstrap style
        # Use subtle rounded cards via labelframe & frame styles
        style.configure("Card.TFrame", relief="flat", padding=12)
        style.configure("Card.TLabelframe", relief="flat", padding=12)
        style.configure("Card.TLabelframe.Label", padding=(6, 2, 6, 2))

        # Treeview
        style.configure("Treeview", rowheight=28, padding=4)
        style.configure("TNotebook", padding=6)
        style.configure("TNotebook.Tab", padding=(16, 8))

        # Entries and buttons
        style.configure("TEntry", padding=10)
        style.configure("TButton", padding=10)
        style.configure("Round.TButton", padding=10, borderwidth=0)

    # ------------------------- Layout --------------------------
    def _build_layout(self):
        # Root container as two columns: sidebar and main
        root = self
        root.columnconfigure(0, weight=0)  # sidebar fixed
        root.columnconfigure(1, weight=1)  # main grows
        root.rowconfigure(0, weight=1)
        root["background"] = self.style.colors.bg  # smooth bg

        # Sidebar (left)
        self.sidebar = tb.Frame(root, bootstyle=SECONDARY, style="Card.TFrame")
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=(14, 8), pady=14)
        self.sidebar.grid_propagate(False)
        self.sidebar.configure(width=300)

        # Main (right)
        self.main = tb.Frame(root, style="Card.TFrame")
        self.main.grid(row=0, column=1, sticky="nsew", padx=(8, 14), pady=14)
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(1, weight=1)

        # -- Sidebar content --
        # Albums card
        albums_card = tb.Labelframe(self.sidebar, text=" Alba ", bootstyle=INFO, style="Card.TLabelframe")
        albums_card.pack(fill="x", padx=2, pady=(0, 12))

        self.album_dir_lbl = tb.Label(albums_card, text="(žádná složka)", wraplength=250, anchor="w", justify="left")
        self.album_dir_lbl.pack(fill="x", pady=(0, 6))

        album_btns = tb.Frame(albums_card)
        album_btns.pack(fill="x", pady=4)
        tb.Button(album_btns, text="Vybrat složku", command=self.choose_album_dir, bootstyle=PRIMARY).pack(side="left")
        tb.Button(album_btns, text="Otevřít", command=lambda: open_in_explorer(self.album_dir), bootstyle=SECONDARY).pack(side="left", padx=6)
        tb.Button(album_btns, text="Obnovit", command=self.refresh_albums, bootstyle=LIGHT).pack(side="left")

        self.album_search = tb.Entry(albums_card)
        self.album_search.pack(fill="x", pady=(8, 6))
        self.album_search.insert(0, "Hledat…")
        ToolTip(self.album_search, text="Hledejte podle názvu/umělce/roku/žánru")

        self.album_list = tb.ScrolledListbox(albums_card, height=12, bootstyle=LIGHT)
        self.album_list.pack(fill="both", expand=True, pady=(6, 0))

        # Logs card
        logs_card = tb.Labelframe(self.sidebar, text=" Logy ", bootstyle=WARNING, style="Card.TLabelframe")
        logs_card.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        self.log_dir_lbl = tb.Label(logs_card, text="(žádná složka)", wraplength=250, anchor="w", justify="left")
        self.log_dir_lbl.pack(fill="x", pady=(0, 6))

        log_btns = tb.Frame(logs_card)
        log_btns.pack(fill="x", pady=4)
        tb.Button(log_btns, text="Vybrat složku", command=self.choose_log_dir, bootstyle=DANGER).pack(side="left")
        tb.Button(log_btns, text="Otevřít", command=lambda: open_in_explorer(self.log_dir), bootstyle=SECONDARY).pack(side="left", padx=6)
        tb.Button(log_btns, text="Obnovit", command=self.refresh_logs, bootstyle=LIGHT).pack(side="left")

        self.log_search = tb.Entry(logs_card)
        self.log_search.pack(fill="x", pady=(8, 6))
        self.log_search.insert(0, "Hledat v logách…")

        self.log_list = tb.ScrolledListbox(logs_card, height=8, bootstyle=LIGHT)
        self.log_list.pack(fill="both", expand=True, pady=(6, 0))

        # -- Main content --
        # Header
        header = tb.Frame(self.main, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        tb.Label(header, text="Vinyl Viewer", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        self.status_lbl = tb.Label(header, text="", bootstyle=SECONDARY)
        self.status_lbl.grid(row=0, column=1, sticky="e")

        # Notebook (Album / Logs detail)
        self.tabs = tb.Notebook(self.main, bootstyle=PRIMARY)
        self.tabs.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        # Album tab
        self.album_tab = tb.Frame(self.tabs, style="Card.TFrame")
        self.tabs.add(self.album_tab, text="Album")

        self._build_album_tab(self.album_tab)

        # Logs tab
        self.logs_tab = tb.Frame(self.tabs, style="Card.TFrame")
        self.tabs.add(self.logs_tab, text="Log")

        self._build_logs_tab(self.logs_tab)

        # Footer
        footer = tb.Frame(self.main, style="Card.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.footer_lbl = tb.Label(footer, text="Připraveno.", bootstyle=SECONDARY)
        self.footer_lbl.pack(side="left")

    def _build_album_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Top meta panel
        meta = tb.Labelframe(parent, text=" Metadata ", style="Card.TLabelframe", bootstyle=INFO)
        meta.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        for i in range(6):
            meta.columnconfigure(i, weight=1)

        self.meta_title = tb.Label(meta, text="—", font=("Segoe UI", 13, "bold"))
        self.meta_title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        self.meta_artist = tb.Label(meta, text="—")
        self.meta_year = tb.Label(meta, text="—")
        self.meta_genre = tb.Label(meta, text="—")
        self.meta_path = tb.Label(meta, text="—", wraplength=600, bootstyle=SECONDARY)

        self.meta_artist.grid(row=1, column=0, sticky="w")
        self.meta_year.grid(row=1, column=1, sticky="w")
        self.meta_genre.grid(row=1, column=2, sticky="w")
        self.meta_path.grid(row=2, column=0, columnspan=6, sticky="w")

        # Track list
        tracks_card = tb.Labelframe(parent, text=" Skladby ", style="Card.TLabelframe", bootstyle=PRIMARY)
        tracks_card.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        tracks_card.rowconfigure(0, weight=1)
        tracks_card.columnconfigure(0, weight=1)

        cols = ("#","Název","Strana","Délka")
        self.tracks_tv = tb.Treeview(tracks_card, columns=cols, show="headings", height=12, bootstyle=LIGHT)
        for c in cols:
            self.tracks_tv.heading(c, text=c)
        self.tracks_tv.column("#", width=60, anchor="center")
        self.tracks_tv.column("Název", width=400, anchor="w")
        self.tracks_tv.column("Strana", width=80, anchor="center")
        self.tracks_tv.column("Délka", width=90, anchor="center")

        self.tracks_tv.grid(row=0, column=0, sticky="nsew")
        tb.Scrollbar(tracks_card, command=self.tracks_tv.yview, orient="vertical").grid(row=0, column=1, sticky="ns")
        self.tracks_tv.configure(yscrollcommand=lambda *a: None)

        # Side totals
        totals = tb.Frame(parent, style="Card.TFrame")
        totals.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))
        self.side_a_lbl = tb.Label(totals, text="Strana A: 00:00")
        self.side_b_lbl = tb.Label(totals, text="Strana B: 00:00")
        self.total_lbl = tb.Label(totals, text="Celkem: 00:00", bootstyle=SECONDARY)
        self.side_a_lbl.pack(side="left")
        self.side_b_lbl.pack(side="left", padx=12)
        self.total_lbl.pack(side="right")

    def _build_logs_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        meta = tb.Labelframe(parent, text=" Detail logu ", style="Card.TLabelframe", bootstyle=WARNING)
        meta.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        for i in range(4):
            meta.columnconfigure(i, weight=1)

        self.log_title = tb.Label(meta, text="—", font=("Segoe UI", 13, "bold"))
        self.log_title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))

        self.log_error = tb.Label(meta, text="—", wraplength=900, bootstyle=DANGER)
        self.log_path = tb.Label(meta, text="—", wraplength=900, bootstyle=SECONDARY)
        self.log_error.grid(row=1, column=0, columnspan=4, sticky="w")
        self.log_path.grid(row=2, column=0, columnspan=4, sticky="w")

        body = tb.Labelframe(parent, text=" JSON ", style="Card.TLabelframe", bootstyle=SECONDARY)
        body.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        self.log_text = tk.Text(body, wrap="word", relief="flat", height=14)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        tb.Scrollbar(body, command=self.log_text.yview).grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=lambda *a: None)

    # ------------------------- Events --------------------------
    def _bind_events(self):
        self.album_list.bind("<<ListboxSelect>>", lambda e: self._on_album_selected())
        self.log_list.bind("<<ListboxSelect>>", lambda e: self._on_log_selected())
        self.album_search.bind("<KeyRelease>", lambda e: self._filter_albums())
        self.log_search.bind("<KeyRelease>", lambda e: self._filter_logs())
        self.bind("<Control-f>", lambda e: self._focus_search())

    def _focus_search(self):
        if self.tabs.index("current") == 0:
            self.album_search.focus_set()
            self.album_search.select_range(0, "end")
        else:
            self.log_search.focus_set()
            self.log_search.select_range(0, "end")

    # ------------------------- Data I/O -------------------------
    def choose_album_dir(self):
        d = filedialog.askdirectory(title="Vyberte složku s alby (*.json)")
        if not d:
            return
        self.album_dir = d
        self.album_dir_lbl.configure(text=human_path(d))
        self.refresh_albums()

    def choose_log_dir(self):
        d = filedialog.askdirectory(title="Vyberte složku s logy (*.json)")
        if not d:
            return
        self.log_dir = d
        self.log_dir_lbl.configure(text=human_path(d))
        self.refresh_logs()

    def refresh_albums(self):
        self.albums = self._load_jsons(self.album_dir)
        self.filtered_albums = list(self.albums)
        self._fill_album_listbox()
        self._set_status(f"Načteno alb: {len(self.albums)}")

    def refresh_logs(self):
        self.logs = self._load_jsons(self.log_dir)
        self.filtered_logs = list(self.logs)
        self._fill_log_listbox()
        self._set_status(f"Načteno logů: {len(self.logs)}")

    def _load_jsons(self, directory):
        out = []
        if not directory or not os.path.isdir(directory):
            return out
        for path in glob.glob(os.path.join(directory, "*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data["_file_path"] = path
                    out.append(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            item["_file_path"] = path
                            out.append(item)
            except Exception as e:
                print(f"Chyba při načítání {path}: {e}")
        return out

    # ------------------------- Populate UI -------------------------
    def _album_label(self, a: dict) -> str:
        # Try best-effort friendly label
        name = a.get("name") or a.get("album") or a.get("title") or a.get("source_path") or os.path.basename(a.get("_file_path",""))
        artist = a.get("artist") or a.get("artist_name")
        year = a.get("year")
        label = str(name)
        if artist:
            label = f"{artist} — {label}"
        if year:
            label += f" ({year})"
        return label

    def _log_label(self, l: dict) -> str:
        err = l.get("error") or l.get("message") or l.get("status") or "Log"
        base = os.path.basename(l.get("_file_path",""))
        return f"{base}: {err[:60]}"

    def _fill_album_listbox(self):
        self.album_list.delete(0, "end")
        for a in self.filtered_albums:
            self.album_list.insert("end", self._album_label(a))

    def _fill_log_listbox(self):
        self.log_list.delete(0, "end")
        for l in self.filtered_logs:
            self.log_list.insert("end", self._log_label(l))

    # ------------------------- Filters -------------------------
    def _filter_albums(self):
        q = self.album_search.get().strip().lower()
        if not q or q in ("hledat…", "hledat..."):
            self.filtered_albums = list(self.albums)
        else:
            def hit(a):
                blob = " ".join([str(a.get(k, "")) for k in ("name","album","title","artist","artist_name","genre","year","source_path")]).lower()
                return q in blob
            self.filtered_albums = [a for a in self.albums if hit(a)]
        self._fill_album_listbox()

    def _filter_logs(self):
        q = self.log_search.get().strip().lower()
        if not q or q in ("hledat v logách…",):
            self.filtered_logs = list(self.logs)
        else:
            def hit(l):
                blob = " ".join([str(l.get(k, "")) for k in ("error","message","status","file","_file_path")]).lower()
                return q in blob
            self.filtered_logs = [l for l in self.logs if hit(l)]
        self._fill_log_listbox()

    # ------------------------- Selection handlers -------------------------
    def _on_album_selected(self):
        i = self._get_selected(self.album_list)
        if i is None or i >= len(self.filtered_albums):
            return
        a = self.filtered_albums[i]
        # Update meta
        title = a.get("name") or a.get("album") or a.get("title") or "—"
        artist = a.get("artist") or a.get("artist_name") or "—"
        year = a.get("year") or "—"
        genre = a.get("genre") or a.get("style") or "—"
        path = a.get("_file_path") or a.get("source_path") or ""

        self.meta_title.configure(text=str(title))
        self.meta_artist.configure(text=f"Umělec: {artist}")
        self.meta_year.configure(text=f"Rok: {year}")
        self.meta_genre.configure(text=f"Žánr: {genre}")
        self.meta_path.configure(text=f"Soubor: {human_path(path)}")

        # Fill tracks
        for r in self.tracks_tv.get_children():
            self.tracks_tv.delete(r)

        tracks = a.get("tracks") or a.get("tracklist") or []
        total = 0
        side_a = 0
        side_b = 0
        for idx, t in enumerate(tracks, start=1):
            title = t.get("title") or t.get("name") or f"Skladba {idx}"
            dur = t.get("duration") or t.get("length")
            sec = duration_to_seconds(dur)
            side = (t.get("side") or "").upper().strip()
            total += sec
            if side == "A":
                side_a += sec
            elif side == "B":
                side_b += sec
            self.tracks_tv.insert("", "end", values=(idx, title, side or "—", seconds_to_mmss(sec)))

        self.side_a_lbl.configure(text=f"Strana A: {seconds_to_mmss(side_a)}")
        self.side_b_lbl.configure(text=f"Strana B: {seconds_to_mmss(side_b)}")
        self.total_lbl.configure(text=f"Celkem: {seconds_to_mmss(total)}")

        self.tabs.select(self.album_tab)
        self._set_status("Album vybráno.")

    def _on_log_selected(self):
        i = self._get_selected(self.log_list)
        if i is None or i >= len(self.filtered_logs):
            return
        l = self.filtered_logs[i]
        base = os.path.basename(l.get("_file_path",""))
        self.log_title.configure(text=f"{base}")
        err = l.get("error") or l.get("message") or l.get("status") or "—"
        self.log_error.configure(text=f"Zpráva: {err}")
        self.log_path.configure(text=f"Soubor: {human_path(l.get('_file_path',''))}")

        # Pretty JSON
        try:
            pretty = json.dumps(l, ensure_ascii=False, indent=2)
        except Exception:
            pretty = str(l)
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", pretty)

        self.tabs.select(self.logs_tab)
        self._set_status("Log vybrán.")

    # ------------------------- Helpers -------------------------
    def _get_selected(self, listbox) -> int | None:
        try:
            sel = listbox.curselection()
            if not sel:
                return None
            return int(sel[0])
        except Exception:
            return None

    def _set_status(self, txt: str):
        self.status_lbl.configure(text=txt)
        self.footer_lbl.configure(text=txt)


def main():
    app = VinylApp()
    app.mainloop()


if __name__ == "__main__":
    main()
