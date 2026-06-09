# urlsum

AI-driven hard limit summary of the contents of a URL.

## Features

- Summarizes webpages into a single, concise paragraph.
- Enforces a strict character limit with complete sentences (default: 450).
- Supports Google Gemini API (default).
- Supports local Ollama models.
- Automatically copies the summary to the clipboard (supports Wayland and X11).
- Can output scraped text in a clean human-readable form.

## Installation

### Prerequisites

- Python 3.x
- `requests`
- `crawlee[beautifulsoup]`
- `lxml`
- (Optional) `wl-copy`, `xclip`, or `xsel` for clipboard support.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/mainmeister/urlsum.git
   cd urlsum
   ```

2. Install dependencies:
   ```bash
   pip install requests "crawlee[beautifulsoup]" lxml
   ```

3. Install the script to your local bin directory:
   ```bash
   python3 urlsum.py --install
   ```
   Or to a custom directory:
   ```bash
   python3 urlsum.py --install /usr/local/bin
   ```

   > **Note:** If the destination directory requires root access (like `/usr/local/bin`), you must run the command with `sudo`.

## Usage

```bash
usage: urlsum [-h] [--set-key SET_KEY] [--install [PATH]] [-d] [-l LIMIT] [-m MODEL] [-o] [-t TIMEOUT] [-v] [--no-clipboard] [url]

AI-driven 450-character hard limit summary of the contents of a URL.

positional arguments:
  url                   The URL of the webpage to summarize.

options:
  -h, --help            show this help message and exit
  --set-key [SET_KEY]   Save your Gemini API key to the config file (must be used alone). If no key is provided, the current key is displayed.
  --install [PATH]      Install the script to ~/bin/urlsum (or a specified alternative folder; may require sudo for system paths). Must be used alone.
  -d, --default         Set the default Ollama model (must be used alone).
  -l LIMIT, --limit LIMIT
                        Summary character limit (default: 450).
  -m MODEL, --model MODEL
                        Gemini model to use (default: gemini-2.5-flash; must be used alone).
  -o, --ollama          Use local Ollama service instead of Gemini (default model: llama3).
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout for Ollama service (e.g., 300 or 5:00). Default: 600s.
  -v, --verbose         Output the scraped text in a clean human-readable form.
  --no-clipboard        Do not copy the summary to the clipboard.

security considerations:
  Potential for Server-Side Request Forgery (SSRF): The script fetches content from any URL provided via the command line. 
  While standard for a CLI tool, if integrated into an automated environment, it could be used to probe internal network 
  resources or cloud metadata endpoints.

  Unrestricted Installation Path: The --install flag allows specifying any arbitrary directory. If run with elevated 
  privileges (e.g., via sudo), an incorrect or malicious path could result in overwriting critical system files.

  Information Leakage in Verbose Mode: The --verbose flag prints the entire scraped text. If a URL contains sensitive 
  or private data, this information is displayed in the terminal and potentially stored in pager temporary files or 
  terminal buffers.
```

### Examples

#### Using Gemini (Default)

First, set your API key:
```bash
urlsum --set-key YOUR_GEMINI_API_KEY
```

To view the currently saved key:
```bash
urlsum --set-key
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

#### Custom Summary Limit

Summarize with a custom character limit:
```bash
urlsum --limit 200 https://example.com
```

## Configuration

Settings are stored in `~/.config/urlsum/config.json`.

## Security Considerations

- **Potential for Server-Side Request Forgery (SSRF):** The script fetches content from any URL provided via the command line. While standard for a CLI tool, if integrated into an automated environment, it could be used to probe internal network resources or cloud metadata endpoints.
- **Unrestricted Installation Path:** The `--install` flag allows specifying any arbitrary directory. If run with elevated privileges (e.g., via `sudo`), an incorrect or malicious path could result in overwriting critical system files.
- **Information Leakage in Verbose Mode:** The `--verbose` flag prints the entire scraped text. If a URL contains sensitive or private data, this information is displayed in the terminal and potentially stored in pager temporary files or terminal buffers.

## License

MIT
