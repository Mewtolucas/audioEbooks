# Ebook Reader for macOS

A lightweight macOS ebook reader with EPUB and PDF support, image OCR, and read-aloud text-to-speech.

## Download

**[⬇ Download EbookReader.zip](../../releases/latest/download/EbookReader.zip)**

> Go to the [Releases page](../../releases/latest) and click **EbookReader.zip** to download.

## How to install

1. Download **EbookReader.zip** from the link above
2. Double-click the zip to unzip it — you'll get an **EbookReader** folder
3. Open **Terminal** (search for it in Spotlight with ⌘Space)
4. Type `bash ` (with a space after), then drag the **setup_and_run.sh** file from the EbookReader folder into Terminal, and press Enter
5. The first run downloads Python libraries (~30 seconds). Every launch after that is instant.

> **Alternative:** Run `bash build_app.sh` to create a proper `EbookReader.app` you can move to `/Applications` and double-click like any app.

## Requirements

- macOS 10.15 (Catalina) or later
- Python 3.9 or later ([python.org](https://python.org) or `brew install python3`)
- Internet connection on first run (to install libraries)

## Features

| Feature | Details |
|---|---|
| **EPUB support** | Full chapter navigation, headings, bold/italic, lists |
| **PDF support** | Text-based and scanned PDFs |
| **Image OCR** | Scanned pages recognized using Apple Vision (Neural Engine, ~1s/page) |
| **Read aloud** | High-quality macOS voice via NSSpeechSynthesizer; Pause/Resume/Stop |
| **Dark mode** | Toggle with ☾ button or ⌘D |
| **Font sizing** | A− / A+ or ⌘= / ⌘− |
| **Table of Contents** | Click any chapter to jump |

## Keyboard shortcuts

| Key | Action |
|---|---|
| ⌘O | Open a book |
| ⌘R | Read aloud (Speak) |
| ⌘D | Toggle dark mode |
| ⌘= | Increase font size |
| ⌘− | Decrease font size |
| ⌘Q | Quit |

## About DRM

Books borrowed from **Libby, Sora, or Kindle** are DRM-protected and can only be read in the official apps. This reader works with DRM-free ebooks:

- [Project Gutenberg](https://gutenberg.org) — thousands of free classics
- [Standard Ebooks](https://standardebooks.org) — beautifully formatted free books
- Your own documents (PDF, EPUB)
