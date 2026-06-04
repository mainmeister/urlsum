# urlsum

AI-driven 450-character hard limit summary of the contents of a URL.

## Features

- Summarizes webpages into a single, concise paragraph.
- Enforces a strict 450-character limit with complete sentences.
- Supports Google Gemini API (default).
- Supports local Ollama models.
- Automatically copies the summary to the clipboard (supports Wayland and X11).
- Can output scraped text in a clean human-readable form.

## Installation

### Prerequisites

- Python 3.x
- `requests`
- `crawlee[beautifulsoup]`
- (Optional) `wl-copy`, `xclip`, or `xsel` for clipboard support.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/mainmeister/urlsum.git
   cd urlsum
   ```

2. Install dependencies:
   ```bash
   pip install requests "crawlee[beautifulsoup]"
   ```

3. (Optional) Make the script executable and add it to your PATH.

## Usage

```bash
usage: urlsum [-h] [--set-key SET_KEY] [-d] [-m MODEL] [-o [OLLAMA]] [-t TIMEOUT] [-v] [--no-clipboard] [url]

AI-driven 450-character hard limit summary of the contents of a URL.

positional arguments:
  url                   The URL of the webpage to summarize.

options:
  -h, --help            show this help message and exit
  --set-key SET_KEY     Save your Gemini API key to the config file.
  -d, --default         Set the default Ollama model.
  -m MODEL, --model MODEL
                        Gemini model to use (default: gemini-2.5-flash).
  -o [OLLAMA], --ollama [OLLAMA]
                        Use local Ollama service instead of Gemini. Optional: model name (default: llama3).
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout for Ollama service (e.g., 300 or 5:00). Default: 600s.
  -v, --verbose         Output the scraped text in a clean human-readable form.
  --no-clipboard        Do not copy the summary to the clipboard.
```

### Examples

#### Using Gemini (Default)

First, set your API key:
```bash
urlsum --set-key YOUR_GEMINI_API_KEY
```

Summarize a URL:
```bash
urlsum https://example.com
```

#### Using Ollama

Set a default Ollama model:
```bash
urlsum -d
```

Summarize using Ollama:
```bash
urlsum -o https://example.com
```

Specify a different model for a single run:
```bash
urlsum -o llama3.2 https://example.com
```

## Configuration

Settings are stored in `~/.config/urlsum/config.json`.

## License

MIT
