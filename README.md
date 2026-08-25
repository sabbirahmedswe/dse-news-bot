# DSE News Telegram Bot

Get updated news on your screened stocks from DSE on Telegram.

## Requirements

- Python 3.13+

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash); PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
```

`pip install -e .` installs the dependencies from `pyproject.toml` and puts
`src/dse_news_bot` on the import path in editable mode, so `import dse_news_bot`
works from anywhere and your edits take effect without reinstalling.

`requirements.txt` is the pinned snapshot of a known-good environment. Use it
instead when you want to reproduce exact versions:

```bash
pip install -r requirements.txt
pip install -e . --no-deps
```

## Run

```bash
python main.py
```

This fetches today's news page from DSE and prints the raw HTML.

## Debug

### VS Code

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Run main.py",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceFolder}/main.py",
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

Select the `.venv` interpreter (`Ctrl+Shift+P` -> "Python: Select Interpreter"),
set breakpoints, then press `F5`. `justMyCode: false` lets you step into
`requests` and `bs4` as well.

### Terminal

Drop into the debugger on any uncaught exception:

```bash
python -m pdb -c continue main.py
```

Or inspect a value in place by adding `breakpoint()` to the code.

### Common issues

- `ModuleNotFoundError: No module named 'dse_news_bot'` - the editable install
  is missing or you are in the wrong interpreter. Re-run `pip install -e .` and
  confirm with `python -c "import dse_news_bot; print(dse_news_bot.__file__)"`.
- Import modules as `dse_news_bot.x`, never `src.dse_news_bot.x`. `src` is a
  source root, not a package; importing through it loads every module a second
  time under a different name, so classes stop comparing equal.
- SSL / certificate errors behind a corporate proxy are handled by
  `pip-system-certs`, which is already a dependency.

## Layout

```
main.py                     entry point
src/dse_news_bot/
  client.py                 HTTP session with retries, fetches the news page
  parser.py                 HTML -> News objects
  models.py                 News dataclass
  exceptions.py             FetchError
```
