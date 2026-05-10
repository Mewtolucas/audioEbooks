#!/usr/bin/env python3
"""
Ebook Reader for macOS — supports EPUB and PDF formats.
DRM-free files only; for DRM books use the official Libby/Kindle/Sora apps.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import io
import os
import re
import sys
import threading

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
    "ocr_fg": "#888877",
}

DARK = {
    "bg": "#1e1e1e",
    "fg": "#e0e0e0",
    "toolbar_bg": "#2d2d2d",
    "toc_bg": "#252525",
    "select_bg": "#3d3d3d",
    "border": "#444444",
    "toc_header_bg": "#2a2a2a",
    "ocr_fg": "#888899",
}


# ── OCR Engine (Apple Vision) ─────────────────────────────────────────────────

class OCREngine:
    """
    Wraps Apple Vision text recognition (macOS 10.15+).
    Falls back gracefully when pyobjc is not installed.
    """
    _available = None

    @classmethod
    def available(cls) -> bool:
        if cls._available is None:
            try:
                import Vision  # noqa: F401
                import Quartz  # noqa: F401
                cls._available = True
            except ImportError:
                cls._available = False
        return cls._available

    @classmethod
    def recognize(cls, pil_image) -> str:
        import Vision
        import objc

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        raw = buf.getvalue()

        ns_data = objc.lookUpClass("NSData").dataWithBytes_length_(raw, len(raw))
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
            ns_data, None
        )
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        handler.performRequests_error_([request], None)

        lines = []
        for obs in request.results() or []:
            candidates = obs.topCandidates_(1)
            if candidates:
                lines.append(candidates[0].string())
        return "\n".join(lines)


# ── TTS Engine (NSSpeechSynthesizer / say fallback) ───────────────────────────

class TTSEngine:
    """
    Text-to-speech using NSSpeechSynthesizer (via pyobjc) on macOS.
    Falls back to subprocess 'say' when pyobjc/AppKit is unavailable.
    Pause/resume only work in the NSSpeechSynthesizer path.
    """
    _available = None

    @classmethod
    def available(cls) -> bool:
        if cls._available is None:
            try:
                from AppKit import NSSpeechSynthesizer  # noqa: F401
                cls._available = True
            except ImportError:
                cls._available = False
        return cls._available

    @classmethod
    def best_voice(cls):
        """Return the identifier for the best available English voice."""
        if not cls.available():
            return None
        from AppKit import NSSpeechSynthesizer
        premium, enhanced, standard = [], [], []
        for v in NSSpeechSynthesizer.availableVoices():
            attrs = NSSpeechSynthesizer.attributesForVoice_(v) or {}
            if not str(attrs.get("VoiceLocaleIdentifier", "")).startswith("en"):
                continue
            q = attrs.get("VoiceQuality", 0)
            (premium if q >= 3 else enhanced if q == 2 else standard).append(v)
        candidates = premium or enhanced or standard
        return candidates[0] if candidates else None

    def __init__(self):
        self._synth   = None
        self._proc    = None
        self._paused  = False
        if self.available():
            from AppKit import NSSpeechSynthesizer
            self._synth = NSSpeechSynthesizer.alloc().initWithVoice_(self.best_voice())

    def speak(self, text: str) -> None:
        self.stop()
        self._paused = False
        if self._synth is not None:
            self._synth.startSpeakingString_(text)
        else:
            import subprocess
            self._proc = subprocess.Popen(["say", text])

    def pause(self) -> None:
        if self._synth and self._synth.isSpeaking():
            self._synth.pauseSpeakingAtBoundary_(0)  # 0 = NSSpeechWordBoundary
            self._paused = True

    def resume(self) -> None:
        if self._synth and self._paused:
            self._synth.continueSpeaking()
            self._paused = False

    def stop(self) -> None:
        self._paused = False
        if self._synth:
            self._synth.stopSpeaking()
        if self._proc:
            self._proc.terminate()
            self._proc = None

    @property
    def is_speaking(self) -> bool:
        if self._synth:
            return bool(self._synth.isSpeaking()) and not self._paused
        return self._proc is not None and self._proc.poll() is None

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def supports_pause(self) -> bool:
        return self._synth is not None


# ── Main application ──────────────────────────────────────────────────────────

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

        # OCR state
        self._ocr_cache: dict[str, str] = {}
        self._epub_book = None
        self._render_id = 0

        # TTS state — must be initialised before _build_ui() so that
        # _build_toolbar() can call _tts_set_state() safely
        self._tts = TTSEngine()
        self._tts_poll_id = None

        self._build_ui()
        self._apply_theme()
        self._show_welcome()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_menu()
        self._build_toolbar()
        tk.Frame(self.root, height=1).pack(fill=tk.X)
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
            return tk.Button(self.toolbar, text=text, command=cmd,
                             relief=tk.FLAT, padx=10, pady=4,
                             font=("Helvetica", font_size), cursor="hand2")

        # Navigation / display controls
        self.open_btn  = btn("Open Book",  self.open_file)
        self.prev_btn  = btn("◀ Prev",     self.prev_chapter)
        self.next_btn  = btn("Next ▶",     self.next_chapter)
        self.fdec_btn  = btn("A−",          self.decrease_font, 11)
        self.finc_btn  = btn("A+",          self.increase_font, 14)
        self.dark_btn  = btn("☾ Dark",     self.toggle_dark_mode)

        for w in (self.open_btn, self.prev_btn, self.next_btn,
                  self.fdec_btn, self.finc_btn, self.dark_btn):
            w.pack(side=tk.LEFT, padx=2)

        # Visual separator before TTS controls
        self.tts_sep = tk.Frame(self.toolbar, width=1, pady=2)
        self.tts_sep.pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # TTS controls
        self.tts_play_btn  = btn("▶ Speak", self._tts_play)
        self.tts_pause_btn = btn("⏸ Pause", self._tts_pause)
        self.tts_stop_btn  = btn("⏹ Stop",  self._tts_stop)

        for w in (self.tts_play_btn, self.tts_pause_btn, self.tts_stop_btn):
            w.pack(side=tk.LEFT, padx=2)

        # Right-side labels
        self.chapter_label = tk.Label(self.toolbar, text="No book open",
                                       font=("Helvetica", 11))
        self.chapter_label.pack(side=tk.RIGHT, padx=8)

        self.ocr_status_label = tk.Label(self.toolbar, text="",
                                          font=("Helvetica", 10, "italic"))
        self.ocr_status_label.pack(side=tk.RIGHT, padx=4)

        # All widgets that need bg/fg theming
        self.toolbar_widgets = [
            self.open_btn, self.prev_btn, self.next_btn,
            self.fdec_btn, self.finc_btn, self.dark_btn,
            self.tts_play_btn, self.tts_pause_btn, self.tts_stop_btn,
            self.chapter_label,
        ]

        # Start with TTS buttons disabled (no book open)
        self._tts_set_state("no_book")

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
        self.root.bind("<Command-r>", lambda _: self._tts_play())

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

        self.tts_sep.config(bg=t["border"])
        self.ocr_status_label.config(bg=t["toolbar_bg"], fg=t["ocr_fg"])

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
        t = DARK if self.dark_mode else LIGHT
        self.text_area.tag_configure("h1",     font=("Georgia", fs + 10, "bold"), spacing3=12)
        self.text_area.tag_configure("h2",     font=("Georgia", fs + 6,  "bold"), spacing3=10)
        self.text_area.tag_configure("h3",     font=("Georgia", fs + 3,  "bold"), spacing3=8)
        self.text_area.tag_configure("bold",   font=("Georgia", fs,       "bold"))
        self.text_area.tag_configure("italic", font=("Georgia", fs,       "italic"))
        self.text_area.tag_configure("para",   spacing3=10)
        self.text_area.tag_configure("bullet", lmargin1=20, lmargin2=30)
        self.text_area.tag_configure("ocr_label", font=("Helvetica", fs - 2, "italic"),
                                      foreground=t["ocr_fg"])
        self.text_area.tag_configure("scanning", font=("Helvetica", fs - 2, "italic"),
                                      foreground=t["ocr_fg"])

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
        self._tts.stop()
        self._tts_cancel_poll()
        book = epub.read_epub(path)
        self._epub_book = book
        self._ocr_cache.clear()
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
        self._tts_set_state("idle")

    # ── PDF loading ───────────────────────────────────────────────────────────

    def _load_pdf(self, path):
        self._tts.stop()
        self._tts_cancel_poll()
        if self.pdf_doc:
            self.pdf_doc.close()
        self.pdf_doc = fitz.open(path)
        self._ocr_cache.clear()
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
        self._tts_set_state("idle")

    # ── Chapter display ───────────────────────────────────────────────────────

    def _populate_toc(self):
        self.toc_listbox.delete(0, tk.END)
        for _, ch_title, _ in self.chapters:
            self.toc_listbox.insert(tk.END, f"  {ch_title}")

    def show_chapter(self, index):
        if not self.chapters or not (0 <= index < len(self.chapters)):
            return

        # Stop any in-progress speech when navigating chapters
        if self._tts.is_speaking or self._tts.is_paused:
            self._tts.stop()
            self._tts_set_state("idle")
            self._tts_cancel_poll()

        # Invalidate any in-progress background OCR render
        self._render_id += 1
        render_id = self._render_id

        self.current_chapter = index
        kind, ch_title, data = self.chapters[index]

        self.toc_listbox.selection_clear(0, tk.END)
        self.toc_listbox.selection_set(index)
        self.toc_listbox.see(index)
        self.chapter_label.config(text=f"Chapter {index + 1} / {len(self.chapters)}")

        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)

        if kind == "epub":
            self._render_epub(data)
            self.text_area.config(state=tk.DISABLED)
            self.text_area.yview_moveto(0)
        else:
            self.text_area.config(state=tk.DISABLED)
            self.text_area.yview_moveto(0)
            self._render_pdf_async(data, render_id)

    # ── EPUB rendering ────────────────────────────────────────────────────────

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
        elif name == "img":
            self._render_epub_img(tag)
        elif name not in ("figure", "svg", "figcaption"):
            self._render_node(tag)

    def _render_epub_img(self, tag):
        """OCR an inline EPUB image and insert the recognized text."""
        if not self._epub_book or not OCREngine.available():
            return

        src = tag.get("src", "") or tag.get("xlink:href", "")
        if not src:
            return

        filename = src.split("/")[-1]
        cache_key = f"epub_img:{filename}"

        if cache_key in self._ocr_cache:
            ocr_text = self._ocr_cache[cache_key]
        else:
            ocr_text = ""
            for item in self._epub_book.get_items():
                if item.get_name().endswith(filename):
                    try:
                        from PIL import Image
                        img = Image.open(io.BytesIO(item.get_content()))
                        ocr_text = OCREngine.recognize(img)
                        self._ocr_cache[cache_key] = ocr_text
                    except Exception:
                        pass
                    break

        if ocr_text.strip():
            self.text_area.insert(tk.END, "\n")
            start = self.text_area.index(tk.INSERT)
            self.text_area.insert(tk.END, "[Image text] ")
            self.text_area.tag_add("ocr_label", start, self.text_area.index(tk.INSERT))
            start2 = self.text_area.index(tk.INSERT)
            self.text_area.insert(tk.END, ocr_text)
            self.text_area.tag_add("italic", start2, self.text_area.index(tk.INSERT))
            self.text_area.insert(tk.END, "\n\n")

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

    # ── PDF rendering (with background OCR) ──────────────────────────────────

    def _render_pdf_async(self, page_range, render_id):
        start, end = page_range
        image_page_count = 0

        self.text_area.config(state=tk.NORMAL)
        for pn in range(start, min(end, len(self.pdf_doc))):
            text = self.pdf_doc[pn].get_text().strip()
            if text:
                self.text_area.insert(tk.END, text + "\n\n")
            elif f"pdf:{pn}" in self._ocr_cache:
                cached = self._ocr_cache[f"pdf:{pn}"]
                if cached.strip():
                    self.text_area.insert(tk.END, cached + "\n\n")
            elif OCREngine.available():
                image_page_count += 1
                s = self.text_area.index(tk.INSERT)
                self.text_area.insert(tk.END, f"⟳ Scanning page {pn + 1}…\n\n")
                e = self.text_area.index(tk.INSERT)
                self.text_area.tag_add("scanning", s, e)
            else:
                s = self.text_area.index(tk.INSERT)
                self.text_area.insert(
                    tk.END,
                    f"[Page {pn + 1} is an image — install pyobjc for OCR]\n\n",
                )
                self.text_area.tag_add("ocr_label", s, self.text_area.index(tk.INSERT))
        self.text_area.config(state=tk.DISABLED)

        if image_page_count == 0:
            return

        self._set_ocr_status(f"Recognizing text in {image_page_count} image page(s)…")

        def worker():
            for pn in range(start, min(end, len(self.pdf_doc))):
                if render_id != self._render_id:
                    return

                page = self.pdf_doc[pn]
                if page.get_text().strip():
                    continue

                cache_key = f"pdf:{pn}"
                if cache_key in self._ocr_cache:
                    continue

                try:
                    from PIL import Image
                    pix = page.get_pixmap(dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = OCREngine.recognize(img)
                except Exception as exc:
                    ocr_text = f"[OCR error on page {pn + 1}: {exc}]"

                self._ocr_cache[cache_key] = ocr_text

                if render_id == self._render_id:
                    self.root.after(
                        0,
                        lambda t=ocr_text, p=pn: self._replace_scan_placeholder(t, p, render_id),
                    )

            if render_id == self._render_id:
                self.root.after(0, lambda: self._set_ocr_status(""))

        threading.Thread(target=worker, daemon=True).start()

    def _replace_scan_placeholder(self, ocr_text, page_num, render_id):
        if render_id != self._render_id:
            return

        placeholder = f"⟳ Scanning page {page_num + 1}…"
        self.text_area.config(state=tk.NORMAL)

        pos = self.text_area.search(placeholder, "1.0", tk.END)
        if pos:
            self.text_area.delete(pos, f"{pos} + {len(placeholder) + 2} chars")
            if ocr_text.strip():
                self.text_area.insert(pos, ocr_text + "\n\n")
            else:
                self.text_area.insert(pos, "\n")

        self.text_area.config(state=tk.DISABLED)

    # ── OCR status ────────────────────────────────────────────────────────────

    def _set_ocr_status(self, message: str):
        self.ocr_status_label.config(text=message)

    # ── TTS controls ──────────────────────────────────────────────────────────

    def _get_readable_text(self) -> str:
        """Return clean text from the current chapter suitable for TTS."""
        raw = self.text_area.get("1.0", tk.END)
        raw = re.sub(r'\[Image text\] ?', '', raw)
        raw = re.sub(r'⟳ Scanning page \d+…\n?', '', raw)
        raw = re.sub(r'\[Page \d+ is an image[^\]]*\]\n?', '', raw)
        raw = re.sub(r'\[OCR error[^\]]*\]\n?', '', raw)
        raw = re.sub(r'\n{3,}', '\n\n', raw)
        return raw.strip()

    def _tts_set_state(self, state: str):
        """Update TTS button labels and enabled states."""
        sp = self._tts.supports_pause
        cfg = {
            "no_book":  [("▶ Speak", tk.DISABLED), ("⏸ Pause",   tk.DISABLED), ("⏹ Stop",  tk.DISABLED)],
            "idle":     [("▶ Speak", tk.NORMAL),   ("⏸ Pause",   tk.DISABLED), ("⏹ Stop",  tk.DISABLED)],
            "speaking": [("▶ Speak", tk.DISABLED), ("⏸ Pause",   tk.NORMAL if sp else tk.DISABLED), ("⏹ Stop", tk.NORMAL)],
            "paused":   [("▶ Speak", tk.DISABLED), ("▶ Resume",  tk.NORMAL),   ("⏹ Stop",  tk.NORMAL)],
        }
        (play_lbl, play_st), (pause_lbl, pause_st), (stop_lbl, stop_st) = cfg[state]
        self.tts_play_btn.config( text=play_lbl,  state=play_st)
        self.tts_pause_btn.config(text=pause_lbl, state=pause_st)
        self.tts_stop_btn.config( text=stop_lbl,  state=stop_st)

    def _tts_play(self):
        if not self.chapters:
            return
        text = self._get_readable_text()
        if not text:
            return
        self._tts.speak(text)
        self._tts_set_state("speaking")
        self._tts_start_poll()

    def _tts_pause(self):
        if self._tts.is_paused:
            self._tts.resume()
            self._tts_set_state("speaking")
        else:
            self._tts.pause()
            self._tts_set_state("paused")

    def _tts_stop(self):
        self._tts.stop()
        self._tts_set_state("idle")
        self._tts_cancel_poll()

    def _tts_start_poll(self):
        self._tts_cancel_poll()
        self._tts_poll_id = self.root.after(300, self._tts_poll)

    def _tts_cancel_poll(self):
        if self._tts_poll_id is not None:
            self.root.after_cancel(self._tts_poll_id)
            self._tts_poll_id = None

    def _tts_poll(self):
        """Detect when speech finishes naturally and reset to idle."""
        if not self._tts.is_speaking and not self._tts.is_paused:
            self._tts_set_state("idle")
            self._tts_poll_id = None
        else:
            self._tts_poll_id = self.root.after(300, self._tts_poll)

    # ── Navigation controls ───────────────────────────────────────────────────

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
  • PDF  (.pdf)  — any standard PDF, including scanned documents

Read Aloud
  Click "▶ Speak" (or press ⌘R) to have the current chapter read aloud using
  a high-quality macOS voice. Use ⏸ Pause / ▶ Resume to pause and continue,
  and ⏹ Stop to stop. Speech stops automatically when you change chapters.

Image & OCR
  Scanned pages with no embedded text are recognized automatically using
  Apple Vision (Neural Engine, ~1s per page) and included in speech.

About DRM
  Books borrowed from Libby, Sora, or Kindle are DRM-protected and must be
  read in the official apps. This reader works with DRM-free ebooks such as
  those from Project Gutenberg or your own documents.

Getting started
  1.  Click "Open Book" (or press ⌘O) and select an EPUB or PDF.
  2.  Navigate chapters via the Table of Contents on the left.
  3.  Press ⌘R or click ▶ Speak to listen to the chapter.
  4.  Use A− / A+ (or ⌘= / ⌘−) to adjust font size.
  5.  Toggle dark mode with ☾ (or ⌘D).
""")
        self.text_area.config(state=tk.DISABLED)
        self._tts_set_state("no_book")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()

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
