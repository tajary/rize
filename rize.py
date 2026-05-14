#!/usr/bin/env python3
"""
Rize AI Agent - A terminal-based AI assistant powered by Ollama.

Features:
  - {`command`}   → runs bash command and injects output into prompt
  - {@filepath}   → reads file content and injects into prompt
  - !bash_command → runs the bash command
  - /taskname     → loads a predefined task prompt (with tab autocomplete)
  - ↑ / ↓         → navigate prompt history
  - Configurable via config.yaml
"""

import os
import re
import sys
import subprocess
import readline
import glob
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
import importlib.util

# ── Paths ──────────────────────────────────────────────────────────────────────
AGENT_DIR = Path(__file__).parent.resolve()
TASKS_DIR = AGENT_DIR / "tasks"
HISTORY_FILE = AGENT_DIR / ".agent_history"
CONFIG_FILE = AGENT_DIR / "config.yaml"

# ── Config ─────────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "ollama_url": "http://localhost:11434",
    "model": "qwen2.5-coder:3b",
    "max_history": 500,
    "stream": True,
}

def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            import yaml  # optional dependency
            with open(CONFIG_FILE) as f:
                user_cfg = yaml.safe_load(f) or {}
            config.update(user_cfg)
        except ImportError:
            pass  # yaml not installed, use defaults
        except Exception as e:
            print(f"[warn] Could not load config: {e}", file=sys.stderr)
    return config

# ── Task loading ───────────────────────────────────────────────────────────────
def list_tasks() -> list[str]:
    """Return sorted list of task names (folder names inside tasks/)."""
    if not TASKS_DIR.exists():
        return []
    return sorted(
        d.name for d in TASKS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

def load_task(name: str) -> Optional[str]:
    """Load prompt.txt (or prompt.md) from tasks/<name>/."""
    task_dir = TASKS_DIR / name
    for filename in ("prompt.txt", "prompt.md"):
        prompt_file = task_dir / filename
        if prompt_file.exists():
            return prompt_file.read_text().strip()
    return None

# ── Readline setup ─────────────────────────────────────────────────────────────
def setup_readline():
    """Configure readline for history + task autocomplete."""
    # History
    if HISTORY_FILE.exists():
        try:
            readline.read_history_file(str(HISTORY_FILE))
        except Exception:
            pass
    readline.set_history_length(DEFAULT_CONFIG["max_history"])

    # Completer
    tasks = list_tasks()
    task_completions = ["/" + t for t in tasks]

    def completer(text, state):
        # Only complete when text starts with /
        if text.startswith("/"):
            matches = [t for t in task_completions if t.startswith(text)]
        else:
            matches = []
        try:
            return matches[state]
        except IndexError:
            return None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    # Make / a word-break char so completion triggers after /
    readline.set_completer_delims(readline.get_completer_delims().replace("/", ""))

def save_history():
    try:
        readline.write_history_file(str(HISTORY_FILE))
    except Exception:
        pass

# ── Prompt expansion ───────────────────────────────────────────────────────────
def expand_bash(text: str) -> str:
    """Replace {`command`} with the stdout of that command."""
    pattern = r'\{`([^`]+)`\}'

    def run_cmd(match):
        cmd = match.group(1)
        print(f"  [cmd] $ {cmd}", file=sys.stderr)
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            output = result.stdout
            if result.returncode != 0 and result.stderr:
                output += f"\n[stderr]: {result.stderr.strip()}"
            return f"\n```\n$ {cmd}\n{output.strip()}\n```\n"
        except subprocess.TimeoutExpired:
            return f"\n[error: command timed out: {cmd}]\n"
        except Exception as e:
            return f"\n[error running command: {e}]\n"

    return re.sub(pattern, run_cmd, text)

def expand_files(text: str) -> str:
    """Replace {@filepath} with the contents of that file."""
    pattern = r'\{@([^\}]+)\}'

    def read_file(match):
        raw_path = match.group(1).strip()
        # Expand ~ and globs
        expanded = os.path.expanduser(raw_path)
        paths = glob.glob(expanded)
        if not paths:
            return f"\n[error: file not found: {raw_path}]\n"

        chunks = []
        for p in sorted(paths):
            print(f"  [file] {p}", file=sys.stderr)
            try:
                content = Path(p).read_text()
                chunks.append(f"\n--- file: {p} ---\n{content}\n--- end: {p} ---\n")
            except Exception as e:
                chunks.append(f"\n[error reading {p}: {e}]\n")
        return "".join(chunks)

    return re.sub(pattern, read_file, text)

def expand_prompt(text: str) -> str:
    """Run all expansions on the prompt text."""
    text = expand_bash(text)
    text = expand_files(text)
    return text

def run_bash(command):
    """Run a bash command and return its output."""
    # Check if the command starts with '!'
    if not command.startswith('!'):
        raise ValueError("Input does not start with '!'.")
    
    # Remove the leading '!' from the command
    bash_command = command[1:].strip()
    
    try:
        # Run the bash command using subprocess and capture the output
        result = subprocess.run(
            bash_command, shell=True, capture_output=True, text=True, timeout=30
        )
        
        # Return the stdout if the command was successful
        if result.returncode == 0:
            return f"{result.stdout.strip()}"
        else:
            # If there was an error, include both stdout and stderr in the output
            return f"\n[error: command failed]\n$ {bash_command}\n{result.stderr.strip()}\n"
    except subprocess.TimeoutExpired:
        return f"\n[error: command timed out: {bash_command}]\n"
    except Exception as e:
        return f"\n[error running command: {e}]\n"

# ── Task injection ─────────────────────────────────────────────────────────────
def resolve_task_prefix(user_input: str) -> tuple[str, Optional[str], Optional[str]]:
    """
    If the input starts with /taskname, load that task's system prompt.
    Returns (cleaned_user_input, system_prompt_or_None).
    """
    stripped = user_input.strip()
    if not stripped.startswith("/"):
        return user_input, "", None

    parts = stripped.split(None, 1)
    task_name = parts[0][1:]  # strip leading /
    remainder = parts[1] if len(parts) > 1 else ""

    task_prompt = load_task(task_name)
    if task_prompt is None:
        print(f"[warn] Task '{task_name}' not found or has no prompt file.", file=sys.stderr)
        return remainder, "", None

    print(f"  [task] Loaded: {task_name}", file=sys.stderr)
    #print(remainder,"=>", task_prompt)
    return remainder, task_prompt, task_name


def load_hooks(task_name: str):
    """Load hooks.py from a task folder, return module or None."""
    hooks_file = TASKS_DIR / task_name / "hooks.py"
    if not hooks_file.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"task_{task_name}_hooks", hooks_file)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f"[warn] Failed to load hooks for '{task_name}': {e}", file=sys.stderr)
        return None

# ── Ollama API ─────────────────────────────────────────────────────────────────
def call_ollama(prompt: str, system: Optional[str], config: dict) -> str:
    """Send prompt to Ollama and return the response text."""
    url = config["ollama_url"].rstrip("/") + "/api/generate"
    payload: dict = {
        "model": config["model"],
        "prompt": prompt,
        "stream": config.get("stream", True),
    }
    #print(payload)
    if system:
        payload["system"] = system

    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        full_response = []
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = obj.get("response", "")
                if token:
                    print(token, end="", flush=True)
                    full_response.append(token)
                if obj.get("done"):
                    prompt_tokens = obj.get("prompt_eval_count", 0)
                    gen_tokens = obj.get("eval_count", 0)
                    print(f"\n  [tokens] input: {prompt_tokens}  output: {gen_tokens}  total: {prompt_tokens + gen_tokens}", file=sys.stderr)
                    break
        print()  # newline after streaming
        return "".join(full_response)
    except urllib.error.URLError as e:
        print(f"\n[error] Could not connect to Ollama at {config['ollama_url']}: {e}", file=sys.stderr)
        print("Make sure Ollama is running: ollama serve", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"\n[error] Ollama request failed: {e}", file=sys.stderr)
        return ""

# ── REPL ───────────────────────────────────────────────────────────────────────
HELP_TEXT = """
Commands:
  /taskname [extra text]   Load a predefined task prompt
  /tasks                   List all available tasks
  /model <name>            Switch Ollama model
  /help                    Show this help
  exit / quit / Ctrl+D     Quit

Prompt syntax:
  {`bash command`}         Inject command output into prompt
  {@/path/to/file}         Inject file contents into prompt
  ! bash_command           Runs the bash_command

Navigation:
  ↑ / ↓                    Browse prompt history
  Tab                      Autocomplete /taskname
"""

def repl(config: dict):
    print(f"\n🤖 AI Agent  |  model: {config['model']}  |  /help for commands\n")
    setup_readline()

    while True:
        try:
            user_input = input("› ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            save_history()
            break

        if not user_input:
            continue

        # ── Run bash command if input starts with '!' ───────────────────────────
        if user_input.startswith('!'):
            try:
                bash_output = run_bash(user_input)
                print(bash_output)
                continue
            except ValueError as e:
                print(e)
                continue


        # ── Built-in commands ──────────────────────────────────────────────────
        if user_input.lower() in ("exit", "quit"):
            print("Bye!")
            save_history()
            break

        if user_input == "/help":
            print(HELP_TEXT)
            continue

        if user_input == "/tasks":
            tasks = list_tasks()
            if tasks:
                print("Available tasks:")
                for t in tasks:
                    print(f"  /{t}")
            else:
                print("No tasks found in", TASKS_DIR)
            continue

        if user_input.startswith("/model "):
            new_model = user_input[7:].strip()
            if new_model:
                config["model"] = new_model
                print(f"Model switched to: {new_model}")
            continue

        # ── Resolve task prefix ────────────────────────────────────────────────
        user_input, system_prompt, task_name = resolve_task_prefix(user_input)
        user_input = (system_prompt + " " + user_input).strip()
        system_prompt = ""
        # ── Expand {`cmd`} and {@file} ─────────────────────────────────────────
        has_expansions = re.search(r'\{`[^`]+`\}|\{@[^\}]+\}', user_input)
        if has_expansions:
            print("  [expanding...]", file=sys.stderr)
        expanded = expand_prompt(user_input)

        if not expanded.strip() and not system_prompt:
            continue

        hooks = load_hooks(task_name) if task_name else None
        if hooks and hasattr(hooks, "pre_send"):
            expanded = hooks.pre_send(expanded, system_prompt)
            if expanded is None:
                continue  # hook cancelled the request   
                
                
                     
        # ── Call Ollama ────────────────────────────────────────────────────────
        print(f"\n── {config['model']} ──────────────────────────────────────\n")
        response = call_ollama(expanded, system_prompt, config)
        
        # ── post_response hook ─────────────────────────────────────────────────
        if hooks and hasattr(hooks, "post_response"):
            hooks.post_response(response, expanded)        
        
        print("──────────────────────────────────────────────────────\n")

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config = load_config()

    # Allow: agent.py --model mistral
    if len(sys.argv) == 3 and sys.argv[1] == "--model":
        config["model"] = sys.argv[2]

    repl(config)
