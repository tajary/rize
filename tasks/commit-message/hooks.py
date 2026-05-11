import subprocess

def post_response(response: str, original_prompt: str):
    """After the LLM returns a commit message, ask the user to approve it."""
    print("\nCommit message:")
    print("─" * 40)
    print(response.strip())
    print("─" * 40)

    answer = input("\nCommit with this message? [y/N/e(dit)] › ").strip().lower()

    if answer == "y":
        _run_commit(response.strip())
    elif answer == "e":
        edited = _edit_in_editor(response.strip())
        if edited:
            _run_commit(edited)
    else:
        print("Commit cancelled.")

def _run_commit(message: str):
    result = subprocess.run(["git", "commit", "-m", message])
    if result.returncode == 0:
        print("✓ Committed.")
    else:
        print("✗ git commit failed.")

def _edit_in_editor(text: str):
    """Open the message in $EDITOR for manual editing."""
    import os, tempfile
    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write(text)
        tmp = f.name
    subprocess.run([editor, tmp])
    edited = open(tmp).read().strip()
    os.unlink(tmp)
    return edited or None
