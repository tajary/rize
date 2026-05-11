# Rize AI Agent

Rize (pronounced ree-zeh, it means tiny) is a powerful terminal-based AI assistant that leverages Ollama for intelligent responses. It's designed to be flexible and user-friendly, allowing you to interact with it directly from your command line.

## Key Features:

- **Command Injection**: Easily run bash commands directly in your prompt.
- **File Content Injection**: Include the contents of any file in your conversation by using `@/path/to/file`.
- **Task Management**: Load predefined tasks for structured conversations and workflows.
- **History Navigation**: Navigate through your previous prompts using arrow keys or tab completion.
- **Customizable Configuration**: Configure Ollama settings, model parameters, and more via a YAML file.

## Installation:

1. Clone the repository:
   ```bash
   git clone https://github.com/tajary/rize.git
   cd rize
   ```

2. Install dependencies (optional):
   Rize uses Python 3 and requires `yaml` for configuration loading. If you haven't installed it yet, you can do so via pip:
   ```bash
   pip install pyyaml
   ```

## Usage:

To start the Rize AI Agent, simply run the script:

```bash
python rize.py
```

or you can make rize executable and add its path to the $PATH to be able to run it in other folders.

```bash
chmod +x rize.py
# Then add to PATH (optional):
export PATH=$PATH:/path/to/rize

#(Optional) Make globally accessible:
#sudo ln -s $(pwd)/rize.py /usr/local/bin/rize
```

### Command Line Arguments:

- **--model <name>**: Switch to a different Ollama model directly from the command line.

### Built-in Commands:

- `/taskname [extra text]`: Load a predefined task prompt.
- `/tasks`: List all available tasks.
- `/model <name>`: Switch the active Ollama model.
- `/help`: Display this help message.
- `exit / quit / Ctrl+D`: Exit the Rize AI Agent.

### Example Conversation:

```bash
/commit-message
  [task] Loaded: commit-message
  [expanding...]
  [cmd] $ git status --porcelain
  [cmd] $ git diff --staged

── qwen2.5-coder:3b ──────────────────────────────────────

fix: add a header for the list of credentials in App component
  [tokens] input: 329  output: 14  total: 343


Commit message:
────────────────────────────────────────
fix: add a header for the list of credentials in App component
────────────────────────────────────────

Commit with this message? [y/N/e(dit)] › y
[main d259c79] fix: add a header for the list of credentials in App component
 1 file changed, 1 insertion(+)
✓ Committed.
──────────────────────────────────────────────────────

```

## Configuration:

You can customize Rize by creating or editing the `config.yaml` file in the agent directory. Here's an example configuration:

```yaml
ollama_url: http://localhost:11434
model: qwen2.5-coder:3b
max_history: 500
stream: false
```

### Hooks for Advanced Customization:

Rize supports hooks that allow you to extend its functionality. Hooks are Python scripts placed in the `tasks/<task_name>/hooks.py` directory. They can include functions to modify prompts before sending them to Ollama or process responses.

## Contributing:

Contributions are welcome! Feel free to open issues, submit pull requests, or suggest improvements via the issue tracker.

## License:

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Thank you for using Rize. Enjoy your intelligent terminal-based conversations!
