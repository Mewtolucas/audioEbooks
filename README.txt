Ebook Reader — macOS
====================

A lightweight ebook reader for macOS that supports EPUB and PDF files.

────────────────────────────────────────────────────────────────────────────────
QUICK START (two options)
────────────────────────────────────────────────────────────────────────────────

Option A — Run directly (easiest):
  1. Open Terminal
  2. cd into this folder
  3. Run:  bash setup_and_run.sh
     (First run installs Python libraries; subsequent launches are instant.)

Option B — Build a proper .app (recommended for everyday use):
  1. Open Terminal
  2. cd into this folder
  3. Run:  bash build_app.sh
  4. The script creates EbookReader.app and EbookReader.zip in this folder.
  5. Move EbookReader.app to /Applications.
  6. First launch: right-click → Open (bypasses macOS Gatekeeper warning).

────────────────────────────────────────────────────────────────────────────────
REQUIREMENTS
────────────────────────────────────────────────────────────────────────────────

• macOS 10.15 (Catalina) or later
• Python 3.9 or later
  — Check with: python3 --version
  — Install from https://python.org or via Homebrew: brew install python3
• Internet connection on first run only (to download Python libraries)

The setup script automatically installs:
  • ebooklib   — EPUB parsing
  • BeautifulSoup4 + lxml — HTML rendering
  • PyMuPDF    — PDF rendering
  • Pillow     — image support

────────────────────────────────────────────────────────────────────────────────
FEATURES
────────────────────────────────────────────────────────────────────────────────

• Open EPUB and PDF files
• Automatic OCR for scanned/image-only pages using Apple Vision (built-in macOS)
• OCR for images embedded inside EPUB files
• Background OCR — UI stays responsive while pages are scanned
• OCR result caching — re-navigating a chapter is instant (no re-scanning)
• Table of Contents panel with chapter navigation
• Previous / Next chapter buttons
• Adjustable font size (A− / A+ or ⌘= / ⌘−)
• Dark mode toggle (⌘D)
• Open a file directly:  EbookReader.app mybook.epub
• Keyboard shortcuts:
    ⌘O  Open a book
    ⌘D  Toggle dark mode
    ⌘=  Increase font size
    ⌘−  Decrease font size
    ⌘Q  Quit

────────────────────────────────────────────────────────────────────────────────
OCR (IMAGE TEXT RECOGNITION)
────────────────────────────────────────────────────────────────────────────────

The app uses Apple's Vision framework — the same engine behind macOS's "Live
Text" feature — to read text from images automatically.

How it works:
  • Normal PDFs with embedded text: displayed instantly, no OCR needed.
  • Scanned PDFs (image-only pages): the app shows "⟳ Scanning page N…" then
    replaces each placeholder with the recognized text as it finishes.
  • EPUBs with images containing text: recognized text appears below the image
    in italic, labeled "[Image text]".

Speed: Apple Vision uses the Mac's Neural Engine, not the CPU, so a typical
page processes in under 1 second. Results are cached so revisiting a chapter
is instant.

Requirements: pyobjc (installed automatically by setup_and_run.sh).
Without pyobjc, the app still works for text-based files — image pages just
show a "[install pyobjc for OCR]" note.

────────────────────────────────────────────────────────────────────────────────
ABOUT DRM
────────────────────────────────────────────────────────────────────────────────

Books borrowed from Libby, Sora, or Kindle are DRM-protected (encrypted).
DRM decryption is legally restricted, so this app cannot open those files —
you must use the official Libby, Sora, or Kindle app to borrow/read them.

This reader works great with:
  • DRM-free EPUB purchases (many indie and academic publishers)
  • Project Gutenberg (gutenberg.org) — thousands of free classics
  • Standard Ebooks (standardebooks.org) — beautifully formatted free books
  • Your own documents converted to EPUB or PDF
  • Any PDF file

────────────────────────────────────────────────────────────────────────────────
TROUBLESHOOTING
────────────────────────────────────────────────────────────────────────────────

"Python not found"
  Install Python from https://python.org or run: brew install python3

"App can't be opened because it's from an unidentified developer"
  Right-click (or Control-click) the app → Open → Open

App opens but shows a blank window
  The book may be DRM-protected. Try a DRM-free EPUB from gutenberg.org.

Libraries fail to install
  Run manually in Terminal:
    pip3 install ebooklib beautifulsoup4 lxml PyMuPDF Pillow
