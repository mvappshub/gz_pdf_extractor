
import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
from ttkbootstrap import Style, ttk
from ttkbootstrap.constants import LEFT, RIGHT, TOP, BOTTOM, X, Y, BOTH, END

class ScrolledListbox(ttk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master)
        self.listbox = tk.Listbox(self, **kwargs)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=self.scrollbar.set)

        self.listbox.pack(side=LEFT, fill=BOTH, expand=True)
        self.scrollbar.pack(side=RIGHT, fill=Y)

    def insert(self, *args):
        return self.listbox.insert(*args)

    def delete(self, *args):
        return self.listbox.delete(*args)

    def get(self, *args):
        return self.listbox.get(*args)

    def bind(self, sequence=None, func=None, add=None):
        return self.listbox.bind(sequence, func, add)

    def curselection(self):
        return self.listbox.curselection()

class ModernApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF Extractor - Modern GUI")
        self.geometry("1000x600")

        # ttkbootstrap style
        self.style = Style(theme="cosmo")
        self.font = ("Segoe UI", 11)

        # Header
        header = ttk.Frame(self, bootstyle="secondary")
        header.pack(side=TOP, fill=X)
        ttk.Label(header, text="PDF Extractor", font=("Segoe UI", 14, "bold")).pack(side=LEFT, padx=10, pady=10)
        self.theme_button = ttk.Button(header, text="🌙 Dark Mode", bootstyle="secondary", command=self.toggle_theme)
        self.theme_button.pack(side=RIGHT, padx=10, pady=10)

        # Main layout (left list + right content)
        main_frame = ttk.Frame(self)
        main_frame.pack(side=TOP, fill=BOTH, expand=True, padx=10, pady=10)

        # Left panel
        left_frame = ttk.LabelFrame(main_frame, text="Albums", bootstyle="secondary")
        left_frame.pack(side=LEFT, fill=Y, padx=(0,10))

        self.album_list = ScrolledListbox(left_frame, font=self.font, height=25)
        self.album_list.pack(fill=BOTH, expand=True, padx=5, pady=5)
        ttk.Button(left_frame, text="📂 Load Folder", command=self.load_folder, bootstyle="secondary-outline").pack(fill=X, padx=5, pady=5)

        # Right panel
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=RIGHT, fill=BOTH, expand=True)

        # Treeview for album details
        columns = ("track", "title", "pages")
        self.tree = ttk.Treeview(right_frame, columns=columns, show="headings", bootstyle="info")
        self.tree.heading("track", text="Track")
        self.tree.heading("title", text="Title")
        self.tree.heading("pages", text="Pages")
        self.tree.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # Status bar
        self.status = ttk.Label(self, text="Ready", anchor="w", bootstyle="secondary")
        self.status.pack(side=BOTTOM, fill=X)

    def toggle_theme(self):
        if self.style.theme.name == "cosmo":
            self.style.theme_use("darkly")
            self.theme_button.config(text="☀️ Light Mode")
        else:
            self.style.theme_use("cosmo")
            self.theme_button.config(text="🌙 Dark Mode")

    def load_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        self.album_list.delete(0, END)
        for file in os.listdir(folder):
            if file.endswith(".json"):
                self.album_list.insert(END, file)

        self.status.config(text=f"Loaded folder: {folder}")

if __name__ == "__main__":
    app = ModernApp()
    app.mainloop()
