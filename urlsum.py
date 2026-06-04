#!/usr/bin/env python3
import os
import sys
import time
import json
import re
import argparse
import requests
import subprocess
import logging
import pydoc
import asyncio

# Silence all logging from libraries (crawlee, httpx, urllib3, etc.)
logging.disable(logging.CRITICAL)

try:
    CONFIG_PATH = os.path.expanduser("~/.config/urlsum/config.json")
except Exception:
    CONFIG_PATH = "/tmp/urlsum_config.json"
DEFAULT_MODEL = "gemini-2.5-flash"

def get_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to read config file: {e}", file=sys.stderr)
    return {}

def update_config(key, value):
    config = get_config()
    config[key] = value
    try:
        config_dir = os.path.dirname(CONFIG_PATH)
        os.makedirs(config_dir, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error: Failed to update config: {e}", file=sys.stderr)
        sys.exit(1)

def get_candidate_keys():
    keys = []
    # 1. Environment variables
    try:
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            keys.append(("GEMINI_API_KEY environment variable", gemini_key))
            
        google_key = os.environ.get("GOOGLE_API_KEY")
        if google_key:
            keys.append(("GOOGLE_API_KEY environment variable", google_key))
    except Exception:
        pass

    # 2. Config file
    config = get_config()
    config_key = config.get("api_key")
    if config_key:
        keys.append(("config file (~/.config/urlsum/config.json)", config_key))
            
    return keys

def save_api_key(key):
    update_config("api_key", key)
    print(f"API key successfully saved to {CONFIG_PATH}", file=sys.stderr)

async def extract_webpage_text(url, verbose=False):
    try:
        import os
        # Set environment variable for crawlee
        os.environ.setdefault('CRAWLEE_LOG_LEVEL', 'CRITICAL')
    except Exception:
        pass

    try:
        from crawlee import Request
        from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
        from crawlee.storage_clients import MemoryStorageClient
        from crawlee.errors import SessionError
    except ImportError:
        print("Error: 'crawlee' library is missing. Install with 'pip install crawlee[beautifulsoup]'", file=sys.stderr)
        return "", ""
    except Exception as e:
        print(f"Error: Failed to import crawlee components: {e}", file=sys.stderr)
        return "", ""

    title = ""
    text = ""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        crawler = BeautifulSoupCrawler(
            storage_client=MemoryStorageClient(),
            max_request_retries=1,
            max_session_rotations=1,
            configure_logging=False
        )
    except Exception as e:
        print(f"Error: Failed to initialize crawler: {e}", file=sys.stderr)
        return "", ""

    @crawler.router.default_handler
    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
        nonlocal title, text
        try:
            title = context.soup.title.string.strip() if context.soup.title else ""

            # Remove script, style, nav, footer, header, head, noscript, svg, etc.
            try:
                elements_to_remove = context.soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "head", "iframe"])
                for element in elements_to_remove:
                    try:
                        element.decompose()
                    except Exception:
                        pass
            except Exception:
                pass

            # Get raw text
            text = context.soup.get_text(separator='\n')
        except Exception as e:
            print(f"Warning: Error parsing content: {e}", file=sys.stderr)

    try:
        await crawler.run([Request.from_url(url, headers=headers)])
    except SessionError as e:
        print(f"Error: Access blocked by {url} (SessionError). The site might have anti-bot protection.", file=sys.stderr)
        return "", ""
    except Exception as e:
        print(f"Error: Failed to fetch URL {url} with crawlee: {e}", file=sys.stderr)
        return "", ""

    # Clean up whitespace
    try:
        title = re.sub(r'\s+', ' ', title).strip()
        if not verbose:
            text = re.sub(r'\s+', ' ', text).strip()
        else:
            # Clean human readable form: normalize spaces and multiple newlines
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n\s*\n+', '\n\n', text)
            text = text.strip()
    except Exception as e:
        print(f"Warning: Failed to clean up text: {e}", file=sys.stderr)

    # Limit text length to prevent too large payloads (e.g. 60,000 characters)
    max_input_chars = 60000
    if len(text) > max_input_chars:
        text = text[:max_input_chars] + "..."

    return title, text

def get_prompt(title, text):
    return (
        "You are a helpful assistant. Summarize the following webpage content in a single concise paragraph "
        "consisting of complete, non-truncated sentences. The total length of the summary MUST be strictly "
        "at most 450 characters long. This is a hard limit. Do not include any intro like 'Here is a summary' "
        "or quote the text directly unless necessary. Focus on the core message and key details.\n\n"
        f"Webpage Title: {title}\n"
        f"Webpage Content: {text}"
    )

def clean_and_truncate_summary(summary):
    # Clean up any trailing/leading whitespaces or markdown code block wrapper
    summary = summary.replace("```", "").strip()
    
    # Enforce complete sentences under the 450 character limit
    try:
        matches = list(re.finditer(r'[.!?]["\')\]}]*?(?=\s|$)', summary))
    except Exception:
        matches = []
    valid_matches = [m for m in matches if m.end() <= 450]
    
    if valid_matches:
        summary = summary[:valid_matches[-1].end()].strip()
    else:
        # Fallback if no complete sentence fits within 450 characters
        truncated = summary[:447]
        last_space = truncated.rfind(' ')
        if last_space > 300:
            summary = truncated[:last_space].strip() + "..."
        else:
            summary = truncated.strip() + "..."
    return summary

def query_gemini_api(title, text, api_key, model):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    prompt = get_prompt(title, text)

    generation_config = {
        "maxOutputTokens": 1024,
        "temperature": 0.2
    }

    # Disable thinking for models that support/use it to reduce latency and token usage
    try:
        if any(m in model for m in ["2.5", "3.0", "3.1", "3.5", "deep-research"]):
            generation_config["thinkingConfig"] = {"thinkingBudget": 0}
    except Exception:
        pass

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": generation_config
    }

    max_retries = 3
    backoff = 1.0 # seconds
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries:
                    print(f"Warning: Gemini API returned status {response.status_code}. Retrying in {backoff:.1f}s...", file=sys.stderr)
                    time.sleep(backoff)
                    backoff *= 2
                    continue
            return response
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                print(f"Warning: Network error ({e}). Retrying in {backoff:.1f}s...", file=sys.stderr)
                time.sleep(backoff)
                backoff *= 2
                continue
            raise

def get_summary(title, text, candidate_keys, model):
    if not candidate_keys:
        print("Error: Gemini API key not found.", file=sys.stderr)
        print("Please set the GEMINI_API_KEY or GOOGLE_API_KEY environment variable,", file=sys.stderr)
        print(f"or set it in the config file using: urlsum --set-key YOUR_API_KEY", file=sys.stderr)
        sys.exit(1)

    last_error = None
    for name, api_key in candidate_keys:
        try:
            print(f"Trying api key {name}: {api_key}")
            response = query_gemini_api(title, text, api_key, model)
            
            # Check for invalid API key response status
            if response.status_code == 400 or response.status_code == 403:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error", {}).get("message", "")
                    if "API key" in err_msg or "API_KEY_INVALID" in str(err_json):
                        last_error = f"API key error with {name}: {err_msg}"
                        continue
                except:
                    pass
            
            try:
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                last_error = f"API error with {name}: {e}"
                continue
            
            try:
                summary = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return clean_and_truncate_summary(summary)
            except (KeyError, IndexError) as e:
                print(f"Error: Failed to parse Gemini API response: {e}", file=sys.stderr)
                print(f"API Response: {data}", file=sys.stderr)
                sys.exit(1)

        except requests.exceptions.RequestException as e:
            last_error = f"HTTP Error with {name}: {e}"
            try:
                if response.status_code == 404:
                    print(f"Error: Model '{model}' not found or not supported by {name}.", file=sys.stderr)
            except:
                pass
            continue

    # If all keys failed
    print(f"Error: All attempts to call Gemini API failed.", file=sys.stderr)
    if last_error:
        print(f"Last encountered error: {last_error}", file=sys.stderr)
    sys.exit(1)

def parse_timeout(timeout_str):
    if not timeout_str:
        return 600
    if ':' in timeout_str:
        try:
            parts = timeout_str.split(':')
            if len(parts) != 2:
                raise ValueError
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        except ValueError:
            raise ValueError(f"Invalid timeout format: {timeout_str}. Use seconds or min:sec.")
    else:
        try:
            return int(timeout_str)
        except ValueError:
            raise ValueError(f"Invalid timeout format: {timeout_str}. Use seconds or min:sec.")

def get_ollama_models():
    url = "http://localhost:11434/api/tags"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        models = response.json().get("models", [])
        # Sort by size: smallest to largest
        models.sort(key=lambda x: x.get("size", 0))
        return models
    except Exception as e:
        print(f"Error fetching Ollama models: {e}", file=sys.stderr)
        return []

def query_ollama_api(title, text, model, timeout=600):
    url = "http://localhost:11434/api/generate"
    prompt = get_prompt(title, text)
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 512,
            "temperature": 0.2
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        raw_summary = data.get("response", "").strip()
        if not raw_summary:
            return None
        return clean_and_truncate_summary(raw_summary)
    except Exception as e:
        print(f"Error calling Ollama API: {e}", file=sys.stderr)
        return None

async def countdown_timer(duration_seconds, model):
    try:
        for i in range(duration_seconds, 0, -1):
            mins, secs = divmod(i, 60)
            print(f"\rOllama ({model}) is thinking... {mins:02d}:{secs:02d} remaining ", end="", flush=True, file=sys.stderr)
            await asyncio.sleep(1)
    finally:
        # Clear the line when cancelled or finished
        print("\r" + " " * 100 + "\r", end="", flush=True, file=sys.stderr)

def copy_to_clipboard(text):
    try:
        # Encode text as UTF-8 bytes to prevent UnicodeEncodeError in non-UTF-8 locales
        text_bytes = text.encode('utf-8')
    except Exception:
        try:
            text_bytes = str(text).encode('utf-8', errors='replace')
        except Exception:
            return False

    # Try wl-copy (Wayland)
    try:
        if "WAYLAND_DISPLAY" in os.environ:
            try:
                subprocess.run(["wl-copy"], input=text_bytes, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass
    except Exception:
        pass

    # Try xclip (X11)
    if "DISPLAY" in os.environ:
        try:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text_bytes, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass
        try:
            subprocess.run(["xsel", "--clipboard", "--input"], input=text_bytes, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    # Fallback to trying any available command
    for tool, args in [("wl-copy", []), ("xclip", ["-selection", "clipboard"]), ("xsel", ["--clipboard", "--input"])]:
        try:
            subprocess.run([tool] + args, input=text_bytes, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            continue

    return False

async def main():
    # Force UTF-8 encoding for stdout and stderr to prevent encoding errors in non-UTF-8 locales
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    # Load config
    config = get_config()
    default_ollama = config.get("default_ollama_model", "llama3")

    try:
        parser = argparse.ArgumentParser(
            description="AI-driven 450-character hard limit summary of the contents of a URL."
        )
        parser.add_argument("url", nargs="?", help="The URL of the webpage to summarize.")
        parser.add_argument("--set-key", dest="set_key", help="Save your Gemini API key to the config file.")
        parser.add_argument("-d", "--default", action="store_true", help="Set the default Ollama model.")
        parser.add_argument("-m", "--model", default=DEFAULT_MODEL, help=f"Gemini model to use (default: {DEFAULT_MODEL}).")
        parser.add_argument("-o", "--ollama", nargs="?", const=default_ollama, help=f"Use local Ollama service instead of Gemini. Optional: model name (default: {default_ollama}).")
        parser.add_argument("-t", "--timeout", help="Timeout for Ollama service (e.g., 300 or 5:00). Default: 600s.")
        parser.add_argument("-v", "--verbose", action="store_true", help="Output the scraped text in a clean human-readable form.")
        parser.add_argument("--no-clipboard", action="store_true", help="Do not copy the summary to the clipboard.")
        
        args = parser.parse_args()
    except Exception as e:
        print(f"Error: Argument parsing failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Handle key storage
    if args.set_key:
        save_api_key(args.set_key)
        return

    # Handle default Ollama model selection
    if args.default:
        models = get_ollama_models()
        if not models:
            print("Error: No Ollama models found.", file=sys.stderr)
            sys.exit(1)
        
        print("Available Ollama models (sorted by size):")
        for i, m in enumerate(models, 1):
            size_gb = m.get("size", 0) / (1024**3)
            print(f"{i}. {m['name']} ({size_gb:.2f} GB)")
        
        try:
            choice = input(f"Select a model (1-{len(models)}): ")
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                selected_model = models[idx]['name']
                update_config("default_ollama_model", selected_model)
                print(f"Default Ollama model set to: {selected_model}")
            else:
                print("Invalid selection.")
                sys.exit(1)
        except (ValueError, EOFError, KeyboardInterrupt):
            print("\nSelection cancelled.")
            sys.exit(1)
        return

    # Check for URL
    if not args.url:
        parser.print_help()
        sys.exit(1)

    # Fetch and extract content
    try:
        title, text = await extract_webpage_text(args.url, verbose=args.verbose)
    except Exception as e:
        print(f"Error: Unexpected failure during text extraction: {e}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        header = f"--- SCRAPED TEXT: {title} ---"
        footer = "-" * (len(title) + 22)
        verbose_output = f"{header}\n{text}\n{footer}\n"
        pydoc.pager(verbose_output)

    if not text:
        print("Error: Could not extract any readable text from the webpage.", file=sys.stderr)
        sys.exit(1)

    # Get summary
    summary = None
    if args.ollama is not None:
        try:
            # Parse timeout
            try:
                timeout_seconds = parse_timeout(args.timeout)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

            # Display countdown while waiting for Ollama
            timer_task = asyncio.create_task(countdown_timer(timeout_seconds, args.ollama))
            try:
                summary = await asyncio.to_thread(query_ollama_api, title, text, args.ollama, timeout_seconds)
            finally:
                timer_task.cancel()
                try:
                    await timer_task
                except asyncio.CancelledError:
                    pass
            
            if not summary:
                sys.exit(1)
        except Exception as e:
            print(f"Error: Failed to generate summary with Ollama: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Get candidate API keys
        try:
            candidate_keys = get_candidate_keys()
        except Exception as e:
            print(f"Error: Failed to retrieve API keys: {e}", file=sys.stderr)
            sys.exit(1)

        # Get summary via Gemini
        try:
            summary = get_summary(title, text, candidate_keys, args.model)
        except Exception as e:
            print(f"Error: Failed to generate summary: {e}", file=sys.stderr)
            sys.exit(1)
    
    if summary:
        # Output to stdout
        try:
            print(summary)
        except Exception as e:
            print(f"Warning: Failed to print summary: {e}", file=sys.stderr)

        # Copy to clipboard by default
        if not args.no_clipboard:
            try:
                copy_to_clipboard(summary)
            except Exception as e:
                print(f"Warning: Failed to copy to clipboard: {e}", file=sys.stderr)

def run():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run()
