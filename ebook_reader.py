#!/usr/bin/env python3
"""
Ebook Reader for macOS — supports EPUB and PDF formats.
DRM-free files only; for DRM books use the official Libby/Kindle/Sora apps.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys

try:
    import ebooklib
    from ebooklib import epub
    EPUB_SUPPORT = True
except ImportError:
    EPUB_SUPPORT = False

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
    BS4_SUPPORT = True
except ImportError:
    BS4_SUPPORT = False

try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


LIGHT = {
    "bg": "#faf8f3",
    "fg": "#2c2c2c",
    "toolbar_bg": "#eeebe3",
    "toc_bg": "#f0ede5",
    "select_bg": "#d6d0b8",
    "border": "#cccccc",
    "toc_header_bg": "#e4e0d6",
}

DARK = {
    "bg": "#1e1e1e",
    "fg": "#e0e0e0",
    "toolbar_bg": "#2d2d2d",
    "toc_bg": "#252525",
    "select_bg": "#3d3d3d",
    "border": "#444444",
    "toc_header_bg": "#2a2a2a",
}


class EbookReader:
    def __init__(self, root):
        self.root = root
        self.root.title("Ebook Reader")
        self.root.geometry("1200x820")
        self.root.minsize(800, 600)

        self.chapters = []
        self.current_chapter = 0
        self.font_size = 15
        self.dark_mode = False
        self.pdf_doc = None

        self._build_ui()
        self._apply_theme()
        self._show_welcome()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_menu()
        self._build_toolbar()
        tk.Frame(self.root, height=1).pack(fill=tk.X)  # separator line
        self._build_panels()
        self._bind_keys()

    def _build_menu(self):
        mb = tk.Menu(self.root)

        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="Open Ebook…", command=self.open_file, accelerator="⌘O")
        fm.add_separator()
        fm.add_command(label="Quit", command=self.root.quit, accelerator="⌘Q")
        mb.add_cascade(label="File", menu=fm)

        vm = tk.Menu(mb, tearoff=0)
        vm.add_command(label="Increase Font", command=self.increase_font, accelerator="⌘=")
        vm.add_command(label="Decrease Font", command=self.decrease_font, accelerator="⌘-")
        vm.add_separator()
        vm.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode, accelerator="⌘D")
        mb.add_cascade(label="View", menu=vm)

        self.root.config(menu=mb)

    def _build_toolbar(self):
        self.toolbar = tk.Frame(self.root, pady=4, padx=6)
        self.toolbar.pack(fill=tk.X)

        def btn(text, cmd, font_size=12):
            b = tk.Button(self.toolbar, text=text, command=cmd,
                          relief=tk.FLAT, padx=10, pady=4,
                          font=("Helvetica", font_size), cursor="hand2")
            return b

        self.open_btn   = btn("Open Book",  self.open_file)
        self.prev_btn   = btn("◀ Prev",     self.prev_chapter)
        self.next_btn   = btn("Next ▶",     self.next_chapter)
        self.fdec_btn   = btn("A−",          self.decrease_font, 11)
        self.finc_btn   = btn("A+",          self.increase_font, 14)
        self.dark_btn   = btn("☾ Dark",     self.toggle_dark_mode)

        for w in (self.open_btn, self.prev_btn, self.next_btn,
                  self.fdec_btn, self.finc_btn, self.dark_btn):
            w.pack(side=tk.LEFT, padx=2)

        self.chapter_label = tk.Label(self.toolbar, text="No book open",
                                       font=("Helvetica", 11))
        self.chapter_label.pack(side=tk.RIGHT, padx=8)

        self.toolbar_widgets = [
            self.open_btn, self.prev_btn, self.next_btn,
            self.fdec_btn, self.finc_btn, self.dark_btn,
            self.chapter_label,
        ]

    def _build_panels(self):
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # ── Left: TOC ──────────────────────────────────────────────────────
        self.left_frame = tk.Frame(self.paned, width=230)
        self.paned.add(self.left_frame, weight=0)

        self.toc_header = tk.Label(self.left_frame, text="Table of Contents",
                                    font=("Helvetica", 11, "bold"), pady=7, padx=8,
                                    anchor=tk.W)
        self.toc_header.pack(fill=tk.X)

        toc_inner = tk.Frame(self.left_frame)
        toc_inner.pack(fill=tk.BOTH, expand=True)

        toc_sb = ttk.Scrollbar(toc_inner)
        toc_sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.toc_listbox = tk.Listbox(toc_inner, yscrollcommand=toc_sb.set,
                                       selectmode=tk.SINGLE,
                                       font=("Helvetica", 11),
                                       relief=tk.FLAT, borderwidth=0,
                                       activestyle="none")
        self.toc_listbox.pack(fill=tk.BOTH, expand=True)
        toc_sb.config(command=self.toc_listbox.yview)
        self.toc_listbox.bind("<<ListboxSelect>>", self._on_toc_select)

        # ── Right: Reading area ────────────────────────────────────────────
        self.right_frame = tk.Frame(self.paned)
        self.paned.add(self.right_frame, weight=1)

        text_inner = tk.Frame(self.right_frame)
        text_inner.pack(fill=tk.BOTH, expand=True)

        text_sb = ttk.Scrollbar(text_inner)
        text_sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_area = tk.Text(
            text_inner, yscrollcommand=text_sb.set,
            wrap=tk.WORD, padx=48, pady=24,
            relief=tk.FLAT, borderwidth=0,
            font=("Georgia", self.font_size),
            spacing1=3, spacing2=2, spacing3=5,
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        text_sb.config(command=self.text_area.yview)

        self._configure_text_tags()

    def _bind_keys(self):
        self.root.bind("<Command-o>", lambda _: self.open_file())
        self.root.bind("<Command-q>", lambda _: self.root.quit())
        self.root.bind("<Command-equal>", lambda _: self.increase_font())
        self.root.bind("<Command-minus>", lambda _: self.decrease_font())
        self.root.bind("<Command-d>", lambda _: self.toggle_dark_mode())

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        t = DARK if self.dark_mode else LIGHT

        self.root.config(bg=t["bg"])
        self.toolbar.config(bg=t["toolbar_bg"])

        for w in self.toolbar_widgets:
            kw = dict(bg=t["toolbar_bg"], fg=t["fg"])
            if isinstance(w, tk.Button):
                kw["activebackground"] = t["select_bg"]
                kw["activeforeground"] = t["fg"]
            w.config(**kw)

        self.left_frame.config(bg=t["toc_bg"])
        self.toc_header.config(bg=t["toc_header_bg"], fg=t["fg"])

        self.toc_listbox.config(
            bg=t["toc_bg"], fg=t["fg"],
            selectbackground=t["select_bg"],
            selectforeground=t["fg"],
        )

        self.right_frame.config(bg=t["bg"])
        self.text_area.config(
            bg=t["bg"], fg=t["fg"],
            insertbackground=t["fg"],
            selectbackground=t["select_bg"],
        )

        self._configure_text_tags()
        self.dark_btn.config(text="☀ Light" if self.dark_mode else "☾ Dark")

    def _configure_text_tags(self):
        fs = self.font_size
        self.text_area.tag_configure("h1",   font=("Georgia", fs + 10, "bold"), spacing3=12)
        self.text_area.tag_configure("h2",   font=("Georgia", fs + 6,  "bold"), spacing3=10)
        self.text_area.tag_configure("h3",   font=("Georgia", fs + 3,  "bold"), spacing3=8)
        self.text_area.tag_configure("bold", font=("Georgia", fs,       "bold"))
        self.text_area.tag_configure("italic", font=("Georgia", fs,     "italic"))
        self.text_area.tag_configure("para",   spacing3=10)
        self.text_area.tag_configure("bullet", lmargin1=20, lmargin2=30)

    # ── File opening ──────────────────────────────────────────────────────────

    def open_file(self):
        if not EPUB_SUPPORT and not PDF_SUPPORT:
            messagebox.showerror(
                "Missing Dependencies",
                "Required libraries are not installed.\n"
                "Please run setup_and_run.sh to install them.",
            )
            return

        types = [("All supported", "*.epub *.pdf")]
        if EPUB_SUPPORT:
            types.append(("EPUB", "*.epub"))
        if PDF_SUPPORT:
            types.append(("PDF", "*.pdf"))
        types.append(("All files", "*.*"))

        path = filedialog.askopenfilename(title="Open Ebook", filetypes=types)
        if path:
            self._load_file(path)

    def _load_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".epub" and EPUB_SUPPORT:
                self._load_epub(path)
            elif ext == ".pdf" and PDF_SUPPORT:
                self._load_pdf(path)
            else:
                messagebox.showerror(
                    "Unsupported",
                    f"Cannot open '{ext}' files. Check that dependencies are installed.",
                )
        except Exception as exc:
            messagebox.showerror("Error opening file", str(exc))

    # ── EPUB loading ──────────────────────────────────────────────────────────

    def _load_epub(self, path):
        book = epub.read_epub(path)
        self.chapters = []

        meta_title = book.get_metadata("DC", "title")
        title = meta_title[0][0] if meta_title else os.path.basename(path)
        self.root.title(f"Ebook Reader — {title}")

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            raw = item.get_content().decode("utf-8", errors="replace")
            soup = BeautifulSoup(raw, "html.parser")

            ch_title = None
            for tag in ("h1", "h2", "h3", "title"):
                found = soup.find(tag)
                if found and found.get_text(strip=True):
                    ch_title = found.get_text(strip=True)[:70]
                    break
            if not ch_title:
                ch_title = f"Section {len(self.chapters) + 1}"

            self.chapters.append(("epub", ch_title, raw))

        if not self.chapters:
            messagebox.showwarning("Empty", "No readable content found in this EPUB.")
            return

        self._populate_toc()
        self.show_chapter(0)

    # ── PDF loading ───────────────────────────────────────────────────────────

    def _load_pdf(self, path):
        if self.pdf_doc:
            self.pdf_doc.close()
        self.pdf_doc = fitz.open(path)
        self.chapters = []

        title = os.path.basename(path).removesuffix(".pdf")
        self.root.title(f"Ebook Reader — {title}")

        toc = self.pdf_doc.get_toc()
        total = len(self.pdf_doc)

        if toc:
            top = [(t, p - 1) for lvl, t, p in toc if lvl == 1]
            for i, (ch_title, start) in enumerate(top):
                end = top[i + 1][1] if i + 1 < len(top) else total
                self.chapters.append(("pdf", ch_title, (start, end)))
        else:
            chunk = max(1, min(15, total // 20 + 1))
            for s in range(0, total, chunk):
                e = min(s + chunk, total)
                self.chapters.append(("pdf", f"Pages {s+1}–{e}", (s, e)))

        self._populate_toc()
        self.show_chapter(0)

    # ── Chapter display ───────────────────────────────────────────────────────

    def _populate_toc(self):
        self.toc_listbox.delete(0, tk.END)
        for _, ch_title, _ in self.chapters:
            self.toc_listbox.insert(tk.END, f"  {ch_title}")

    def show_chapter(self, index):
        if not self.chapters or not (0 <= index < len(self.chapters)):
            return

        self.current_chapter = index
        kind, ch_title, data = self.chapters[index]

        self.toc_listbox.selection_clear(0, tk.END)
        self.toc_listbox.selection_set(index)
        self.toc_listbox.see(index)
        self.chapter_label.config(
            text=f"Chapter {index + 1} / {len(self.chapters)}"
        )

        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)

        if kind == "epub":
            self._render_epub(data)
        else:
            self._render_pdf(data)

        self.text_area.config(state=tk.DISABLED)
        self.text_area.yview_moveto(0)

    def _render_epub(self, html):
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "meta", "link"]):
            tag.decompose()
        body = soup.find("body") or soup
        self._render_node(body)

    def _render_node(self, node):
        for child in node.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text.strip():
                    self.text_area.insert(tk.END, text)
            elif isinstance(child, Tag):
                self._render_tag(child)

    def _render_tag(self, tag):
        name = (tag.name or "").lower()

        if name == "h1":
            self._tagged_block(tag.get_text(strip=True), "h1", "\n\n")
        elif name == "h2":
            self._tagged_block(tag.get_text(strip=True), "h2", "\n\n")
        elif name in ("h3", "h4", "h5", "h6"):
            self._tagged_block(tag.get_text(strip=True), "h3", "\n\n")
        elif name == "p":
            start = self.text_area.index(tk.INSERT)
            self._render_node(tag)
            end = self.text_area.index(tk.INSERT)
            self.text_area.tag_add("para", start, end)
            self.text_area.insert(tk.END, "\n\n")
        elif name in ("strong", "b"):
            self._tagged_inline(tag.get_text(), "bold")
        elif name in ("em", "i"):
            self._tagged_inline(tag.get_text(), "italic")
        elif name == "br":
            self.text_area.insert(tk.END, "\n")
        elif name in ("ul", "ol"):
            self.text_area.insert(tk.END, "\n")
            for li in tag.find_all("li", recursive=False):
                start = self.text_area.index(tk.INSERT)
                self.text_area.insert(tk.END, "  • ")
                self._render_node(li)
                end = self.text_area.index(tk.INSERT)
                self.text_area.tag_add("bullet", start, end)
                self.text_area.insert(tk.END, "\n")
            self.text_area.insert(tk.END, "\n")
        elif name == "blockquote":
            self.text_area.insert(tk.END, "\n    ")
            self._render_node(tag)
            self.text_area.insert(tk.END, "\n\n")
        elif name not in ("img", "figure", "svg", "figcaption"):
            self._render_node(tag)

    def _tagged_block(self, text, tag_name, suffix):
        self.text_area.insert(tk.END, "\n")
        start = self.text_area.index(tk.INSERT)
        self.text_area.insert(tk.END, text)
        end = self.text_area.index(tk.INSERT)
        self.text_area.tag_add(tag_name, start, end)
        self.text_area.insert(tk.END, suffix)

    def _tagged_inline(self, text, tag_name):
        start = self.text_area.index(tk.INSERT)
        self.text_area.insert(tk.END, text)
        end = self.text_area.index(tk.INSERT)
        self.text_area.tag_add(tag_name, start, end)

    def _render_pdf(self, page_range):
        start, end = page_range
        for pn in range(start, min(end, len(self.pdf_doc))):
            text = self.pdf_doc[pn].get_text()
            if text.strip():
                self.text_area.insert(tk.END, text + "\n")

    # ── Controls ──────────────────────────────────────────────────────────────

    def _on_toc_select(self, _event):
        sel = self.toc_listbox.curselection()
        if sel:
            self.show_chapter(sel[0])

    def prev_chapter(self):
        if self.current_chapter > 0:
            self.show_chapter(self.current_chapter - 1)

    def next_chapter(self):
        if self.chapters and self.current_chapter < len(self.chapters) - 1:
            self.show_chapter(self.current_chapter + 1)

    def increase_font(self):
        self.font_size = min(36, self.font_size + 2)
        self._update_font()

    def decrease_font(self):
        self.font_size = max(8, self.font_size - 2)
        self._update_font()

    def _update_font(self):
        self.text_area.config(font=("Georgia", self.font_size))
        self._configure_text_tags()
        if self.chapters:
            self.show_chapter(self.current_chapter)

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    # ── Welcome screen ────────────────────────────────────────────────────────

    def _show_welcome(self):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, """\
Ebook Reader

Open an EPUB or PDF file to start reading.

Supported formats
  • EPUB (.epub) — used by Libby, Sora, Kobo, Project Gutenberg, and more
  • PDF  (.pdf)  — any standard PDF document

About DRM
Books borrowed from Libby, Sora, or Kindle are DRM-protected and can only
be read inside the official apps. This reader works with DRM-free ebooks
such as those purchased without DRM, downloaded from Project Gutenberg, or
your own personal documents.

Getting started
  1.  Click "Open Book" in the toolbar (or press ⌘O).
  2.  Select an EPUB or PDF file.
  3.  Navigate chapters via the Table of Contents on the left.
  4.  Use A− / A+ to change font size, or ⌘= / ⌘−.
  5.  Toggle dark mode with the ☾ button or ⌘D.
""")
        self.text_area.config(state=tk.DISABLED)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()

    # Improve sharpness on Retina displays
    try:
        root.tk.call("tk", "scaling", 2.0)
    except Exception:
        pass

    app = EbookReader(root)

    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        root.after(150, lambda: app._load_file(sys.argv[1]))

    root.mainloop()


if __name__ == "__main__":
    main()
