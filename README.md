# Ebook Reader for macOS

A lightweight macOS ebook reader with EPUB and PDF support, image OCR, and read-aloud text-to-speech.

---

## ⬇ Download

<p align="center">
  <a href="../../releases/latest/download/EbookReader.zip">
    <img src="https://img.shields.io/badge/⬇%20Download-EbookReader.zip-blue?style=for-the-badge&logo=apple" alt="Download EbookReader.zip"/>
  </a>
</p>

<p align="center">
  Click the button above, or go to the <a href="../../releases/latest"><strong>Releases page</strong></a> and click <strong>EbookReader.zip</strong>.
</p>

---

## 🚀 Setup Instructions

> **Requirements:** macOS 10.15+, Python 3.9+
> Don't have Python? Install it from [python.org](https://python.org) or run `brew install python3` in Terminal.

### Step 1 — Download

Click the **Download** button above. Your browser will save `EbookReader.zip`.

### Step 2 — Unzip

Double-click `EbookReader.zip` in your Downloads folder. This creates an **EbookReader** folder.

### Step 3 — Run

Open **Terminal** (press ⌘Space, type `Terminal`, press Enter), then run:

```bash
bash ~/Downloads/EbookReader/setup_and_run.sh
```

Or drag `setup_and_run.sh` from the EbookReader folder into Terminal and press Enter.

**First launch** installs Python libraries automatically (~30 seconds, needs internet).
**Every launch after that** opens instantly.

---

### Optional: Install as a proper .app

If you'd like to double-click the app from Finder or your Dock:

```bash
bash ~/Downloads/EbookReader/build_app.sh
```

This creates `EbookReader.app`. Move it to `/Applications`, then:
- **First open only:** right-click → Open (to bypass the macOS Gatekeeper warning)
- After that, double-click it like any normal app

---

## Features

| Feature | Details |
|---|---|
| **EPUB support** | Full chapter navigation, headings, bold/italic, lists |
| **PDF support** | Text-based and scanned PDFs |
| **Image OCR** | Scanned pages recognized using Apple Vision (Neural Engine, ~1s/page) |
| **Read aloud** | High-quality macOS voice; Pause/Resume/Stop controls |
| **Dark mode** | Toggle with ☾ button or ⌘D |
| **Font sizing** | A− / A+ or ⌘= / ⌘− |
| **Table of Contents** | Click any chapter to jump instantly |

## Keyboard shortcuts

| Key | Action |
|---|---|
| ⌘O | Open a book |
| ⌘R | Read aloud |
| ⌘D | Toggle dark mode |
| ⌘= | Increase font size |
| ⌘− | Decrease font size |
| ⌘Q | Quit |

---

## About DRM

Books borrowed from **Libby, Sora, or Kindle** are DRM-protected and can only be read in their official apps. This reader works with DRM-free ebooks:

- [Project Gutenberg](https://gutenberg.org) — thousands of free classics
- [Standard Ebooks](https://standardebooks.org) — beautifully formatted free books
- Your own PDF or EPUB documents

---

## Troubleshooting

**"Python not found"** — Install from [python.org](https://python.org) or run `brew install python3`

**"App can't be opened because it's from an unidentified developer"** — Right-click the app → Open → Open

**App opens but book is blank** — The file may be DRM-protected. Try a free book from [gutenberg.org](https://gutenberg.org)

**Libraries fail to install** — Run manually: `pip3 install ebooklib beautifulsoup4 lxml PyMuPDF Pillow`
