#!/usr/bin/env python3
"""
Modern Tkinter App Template (single-file)
- ttk styling with light/dark theme toggle
- Responsive grid layout
- File dialogs (Open / Save As)
- Long-running task off the UI thread with Queue updates
- Determinate + indeterminate Progressbar
- Treeview with columns, tags, sorting
- Entry validation example
- Status bar + after() scheduling
- Graceful shutdown
"""
import os
import sys
import time
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "Modern Tkinter Template"


class Themer:
    """Light/Dark theme manager for ttk using 'clam' base."""
    def __init__(self, root: tk.Tk):
        self.root = root
        self.style = ttk.Style(self.root)
        # Use a known, stylable theme as base
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.current = tk.StringVar(value="light")
        self._define_palettes()
        self.apply("light")

    def _define_palettes(self):
        self.palettes = {
            "light": {
                "bg": "#F5F7FA",
                "fg": "#1F2937",
                "muted": "#6B7280",
                "card": "#FFFFFF",
                "accent": "#3B82F6",
                "accent_fg": "#FFFFFF",
                "border": "#E5E7EB",
                "sel_bg": "#DBEAFE",
                "sel_fg": "#1F2937",
                "entry_bg": "#FFFFFF",
            },
            "dark": {
                "bg": "#0B1220",
                "fg": "#E5E7EB",
                "muted": "#9CA3AF",
                "card": "#111827",
                "accent": "#60A5FA",
                "accent_fg": "#0B1220",
                "border": "#1F2937",
                "sel_bg": "#1F3A67",
                "sel_fg": "#E5E7EB",
                "entry_bg": "#0F172A",
            },
        }

    def apply(self, mode: str):
        if mode not in self.palettes:
            mode = "light"
        self.current.set(mode)
        p = self.palettes[mode]
        # General
        self.root.configure(bg=p["bg"])
        # TFrame / TLabel / TButton / TEntry / TMenubutton / TNotebook etc.
        self.style.configure(".", background=p["bg"], foreground=p["fg"])
        self.style.configure("Card.TFrame", background=p["card"], relief="flat", borderwidth=1)
        self.style.configure("Muted.TLabel", foreground=p["muted"], background=p["bg"])
        self.style.configure("TLabel", background=p["bg"], foreground=p["fg"])

        # Buttons
        self.style.configure(
            "Accent.TButton",
            background=p["accent"],
            foreground=p["accent_fg"],
            bordercolor=p["accent"],
            focusthickness=1,
            focuscolor=p["border"],
            padding=(10, 6),
        )
        self.style.map(
            "Accent.TButton",
            background=[("pressed", p["accent"]), ("active", p["accent"])],
            foreground=[("disabled", p["muted"])],
        )
        self.style.configure(
            "TButton",
            padding=(10, 6),
            bordercolor=p["border"],
            focusthickness=1,
            focuscolor=p["border"],
        )

        # Entry
        self.style.configure(
            "TEntry",
            fieldbackground=p["entry_bg"],
            foreground=p["fg"],
            bordercolor=p["border"],
            lightcolor=p["border"],
            darkcolor=p["border"],
            padding=6,
        )

        # Notebook
        self.style.configure("TNotebook", background=p["bg"], borderwidth=0)
        self.style.configure("TNotebook.Tab", padding=(12, 6))
        self.style.map("TNotebook.Tab", background=[("selected", p["card"])])

        # Treeview
        self.style.configure(
            "Treeview",
            background=p["card"],
            fieldbackground=p["card"],
            foreground=p["fg"],
            bordercolor=p["border"],
            rowheight=24,
        )
        self.style.configure("Treeview.Heading", background=p["bg"], foreground=p["fg"])
        self.style.map("Treeview", background=[("selected", p["sel_bg"])], foreground=[("selected", p["sel_fg"])])

        # Progressbar
        self.style.configure("TProgressbar", background=p["accent"], troughcolor=p["border"])


class Worker:
    """Background worker running a task and reporting progress via Queue."""
    def __init__(self, on_result, on_error, on_done):
        self.q = queue.Queue()
        self.thread = None
        self.stop_event = threading.Event()
        self.on_result = on_result
        self.on_error = on_error
        self.on_done = on_done

    def start(self, total=100, delay=0.03):
        if self.thread and self.thread.is_alive():
            return  # already running
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, args=(total, delay), daemon=True)
        self.thread.start()

    def _run(self, total, delay):
        try:
            for i in range(total + 1):
                if self.stop_event.is_set():
                    break
                time.sleep(delay)
                self.q.put(("progress", i, total))
            if not self.stop_event.is_set():
                self.q.put(("done",))
        except Exception as e:
            self.q.put(("error", e))

    def stop(self):
        self.stop_event.set()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.minsize(900, 520)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Theming
        self.themer = Themer(self)

        # Menus
        self._build_menu()

        # Layout root grid
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        hdr = ttk.Frame(self, style="Card.TFrame", padding=12)
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        hdr.columnconfigure(1, weight=1)

        ttk.Label(hdr, text=APP_NAME, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        self.theme_btn = ttk.Button(hdr, text="Toggle Theme", command=self.toggle_theme, style="Accent.TButton")
        self.theme_btn.grid(row=0, column=2, sticky="e")
        ttk.Label(hdr, text="Light/Dark, responsive, threadsafe", style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w")

        # Main content area (cards)
        body = ttk.Frame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)

        # Left controls card
        left = ttk.Frame(body, style="Card.TFrame", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.columnconfigure(1, weight=1)

        ttk.Label(left, text="Validated Input:").grid(row=0, column=0, sticky="w", pady=(0, 6))

        # Entry validation (only integers 0..9999 allowed)
        vcmd = (self.register(self._validate_int), "%P")
        self.int_var = tk.StringVar(value="42")
        self.int_entry = ttk.Entry(left, textvariable=self.int_var, validate="key", validatecommand=vcmd)
        self.int_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        self.run_btn = ttk.Button(left, text="Run Task", command=self.on_run, style="Accent.TButton")
        self.run_btn.grid(row=1, column=0, sticky="ew", pady=(0, 6), columnspan=2)

        self.stop_btn = ttk.Button(left, text="Stop Task", command=self.on_stop)
        self.stop_btn.grid(row=2, column=0, sticky="ew", pady=(0, 6), columnspan=2)

        ttk.Label(left, text="Progress (determinate):").grid(row=3, column=0, columnspan=2, sticky="w")
        self.pb = ttk.Progressbar(left, orient="horizontal", mode="determinate", maximum=100, length=200)
        self.pb.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        ttk.Label(left, text="Spinner (indeterminate):").grid(row=5, column=0, columnspan=2, sticky="w")
        self.spinner = ttk.Progressbar(left, orient="horizontal", mode="indeterminate", length=200)
        self.spinner.grid(row=6, column=0, columnspan=2, sticky="ew")

        # Right card with Treeview
        right = ttk.Frame(body, style="Card.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Items").grid(row=0, column=0, sticky="w")

        self.tree = ttk.Treeview(right, columns=("id", "name", "value"), show="headings", selectmode="extended")
        self.tree.grid(row=1, column=0, sticky="nsew")
        for col, w in zip(("id", "name", "value"), (80, 180, 120)):
            self.tree.heading(col, text=col.title(), command=lambda c=col: self._sort_tree(c, False))
            self.tree.column(col, width=w, anchor="w")
        # Tags for row styling
        self.tree.tag_configure("high", foreground="#059669")  # green-ish
        self.tree.tag_configure("low", foreground="#DC2626")   # red-ish

        # Scrollbar
        vsb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        vsb.grid(row=1, column=1, sticky="ns")

        # Populate some demo rows
        for i in range(1, 31):
            tag = "high" if i % 2 == 0 else "low"
            self.tree.insert("", "end", values=(i, f"Item {i}", round(i * 1.5, 2)), tags=(tag,))

        # Status bar
        self.status = tk.StringVar(value="Ready")
        statusbar = ttk.Frame(self, style="Card.TFrame", padding=(12, 6))
        statusbar.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 12))
        statusbar.columnconfigure(0, weight=1)
        ttk.Label(statusbar, textvariable=self.status).grid(row=0, column=0, sticky="w")

        # Background worker and UI polling
        self.worker = Worker(on_result=self._on_worker_result, on_error=self._on_worker_error, on_done=self._on_worker_done)
        self.after(100, self._poll_queue)

    # ===== Menus =====
    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open…", command=self.on_open, accelerator="Ctrl+O")
        file_menu.add_command(label="Save As…", command=self.on_save_as, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Theme", command=self.toggle_theme, accelerator="Ctrl+T")
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.on_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)
        # Bind accelerators
        self.bind_all("<Control-o>", lambda e: self.on_open())
        self.bind_all("<Control-s>", lambda e: self.on_save_as())
        self.bind_all("<Control-t>", lambda e: self.toggle_theme())

    # ===== Callbacks =====
    def toggle_theme(self):
        mode = "dark" if self.themer.current.get() == "light" else "light"
        self.themer.apply(mode)

    def on_open(self):
        path = filedialog.askopenfilename(title="Open file", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
            self._show_text_preview(data, title=f"Preview • {os.path.basename(path)}")
            self.status.set(f"Opened {path}")
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def on_save_as(self):
        path = filedialog.asksaveasfilename(title="Save As", defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not path:
            return
        try:
            # Save selected rows from Treeview as CSV-like text
            items = self.tree.selection() or self.tree.get_children("")
            lines = ["id,name,value"]
            for iid in items:
                vals = self.tree.item(iid, "values")
                lines.append(",".join(map(str, vals)))
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.status.set(f"Saved {path}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def on_about(self):
        messagebox.showinfo(APP_NAME, f"{APP_NAME}\n\n• ttk styling with light/dark\n• Responsive layout\n• Background worker\n• Treeview demo\n\nPython {sys.version.split()[0]}")

    def on_run(self):
        try:
            total = int(self.int_var.get())
        except ValueError:
            total = 100
        total = max(1, min(total, 1000))
        self.pb.configure(maximum=total, value=0)
        self.spinner.start(80)
        self.run_btn.configure(state="disabled")
        self.status.set("Running task…")
        self.worker.start(total=total, delay=0.02)

    def on_stop(self):
        self.worker.stop()
        self.spinner.stop()
        self.run_btn.configure(state="normal")
        self.status.set("Task stopped")

    # ===== Validation =====
    def _validate_int(self, proposed: str) -> bool:
        if proposed == "":
            return True
        if proposed.isdigit():
            try:
                val = int(proposed)
                return 0 <= val <= 9999
            except ValueError:
                return False
        return False

    # ===== Queue polling =====
    def _poll_queue(self):
        try:
            while True:
                msg = self.worker.q.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    i, total = msg[1], msg[2]
                    self.pb["value"] = i
                    self.status.set(f"Progress: {i}/{total}")
                elif kind == "error":
                    e = msg[1]
                    messagebox.showerror("Worker error", str(e))
                    self._reset_run_ui()
                elif kind == "done":
                    self._on_worker_done()
                else:
                    pass
        except queue.Empty:
            pass
        # schedule next poll
        self.after(80, self._poll_queue)

    def _on_worker_result(self, *args, **kwargs):
        # Placeholder if you want to push results to UI
        pass

    def _on_worker_error(self, e: Exception):
        messagebox.showerror("Worker error", str(e))

    def _on_worker_done(self):
        self._reset_run_ui()
        self.status.set("Task completed")

    def _reset_run_ui(self):
        self.spinner.stop()
        self.run_btn.configure(state="normal")

    # ===== Helpers =====
    def _show_text_preview(self, text: str, title: str = "Preview"):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("720x420")
        win.transient(self)
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)
        txt = tk.Text(win, wrap="word")
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        txt.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(win, command=txt.yview, orient="vertical")
        txt.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

    def _sort_tree(self, col, reverse):
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        # Try numerical sort, fallback to string
        try:
            data.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            data.sort(key=lambda t: t[0], reverse=reverse)
        for index, (_, k) in enumerate(data):
            self.tree.move(k, "", index)
        # Toggle sort direction next time
        self.tree.heading(col, command=lambda c=col: self._sort_tree(c, not reverse))

    def on_close(self):
        self.worker.stop()
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
