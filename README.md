# Local AI Coding Agent (Cursor-like, 100% local)

Python terminal-based coding agent that connects to a local OpenAI-compatible LLM server and uses basic file/terminal tools. It also maintains a persistent "Neuron" memory in an Obsidian folder (`neuron.md`).

## What you get

- **Local model**: Uses `http://localhost:1234/v1` (OpenAI compatible)
- **Tools**:
  - `read_file`
  - `write_file`
  - `list_directory`
  - `run_terminal_command`
- **Memory (Neuron)**:
  - Reads `neuron.md` before every task (context without chat history)
  - After every successful code change, appends a summary to `neuron.md`
- **UI**: Simple interactive loop in terminal

## Setup

1. Create and activate a virtualenv (optional).
2. Install deps:

```bash
pip install -r requirements.txt
```

3. Start your local OpenAI-compatible server at `http://localhost:1234/v1`.

## Run

```bash
python -m local_coder
```

## Configuration

Environment variables:

- `LOCAL_CODER_BASE_URL` (default `http://localhost:1234/v1`)
- `LOCAL_CODER_API_KEY` (default `local`) – some servers require any non-empty key
- `LOCAL_CODER_MODEL` (default `local-model`)
- `LOCAL_CODER_OBSIDIAN_DIR` (default `./obsidian`)
- `LOCAL_CODER_NEURON_FILE` (default `neuron.md`)

The Neuron file will live at:

`$LOCAL_CODER_OBSIDIAN_DIR/$LOCAL_CODER_NEURON_FILE`

## Notes

- Tool calling is done via OpenAI-compatible `tools` (function calling). If your local server doesn’t support tool calling, you can still use the app, but you may need to switch the server/model to one that supports it.

