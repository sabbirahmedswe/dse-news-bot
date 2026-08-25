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

## Configure

Create a `.env` in the project root (it is gitignored - **never commit your bot
token**):

```ini
PORTFOLIO=BEACONPHAR,SQURPHARMA,GP
TELEGRAM_BOT_TOKEN=123456:ABC-your-token-from-@BotFather
TELEGRAM_CHAT_ID=
```

| Key | Meaning |
| --- | --- |
| `PORTFOLIO` | Comma-separated trading codes to watch. Case and spacing don't matter. |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) -> `/newbot`. |
| `TELEGRAM_CHAT_ID` | Where messages go. See below. |
| `STATE_PATH` | Optional. Where the "already sent" log lives; defaults to `.state/sent.json`. |

### Finding your chat id

A bot token alone can't send anywhere - Telegram also needs a chat id, and one
only exists once you've messaged the bot.

1. Open your bot in Telegram and send it any message (e.g. `hi`).
2. Run:

   ```bash
   python main.py --chat-id
   ```

   ```
     123456789	Sabbir Ahmed (@username) [private]

   Put TELEGRAM_CHAT_ID=<id> in .env
   ```

3. Paste the id into `.env`.

To post into a group instead, add the bot to the group, send a message there,
and re-run - group ids are negative.

## Run

```bash
python main.py
```

Fetches today's DSE news, keeps the items whose trading code is in `PORTFOLIO`,
and sends one Telegram message per item. Already-sent items are recorded in
`.state/sent.json`, so running it repeatedly through the day only delivers what
is new. Exits `1` with a one-line message if anything fails.

### Scheduling

Because of the dedup log it is safe to run on a timer. On Windows, every 30
minutes on weekdays:

```powershell
schtasks /create /tn "DSE News" /sc minute /mo 30 /d MON,TUE,WED,THU,SUN `
  /tr "'E:\projects\dse-news-bot\.venv\Scripts\python.exe' 'E:\projects\dse-news-bot\main.py'"
```

Set the task's "Start in" directory to the project root so `.env` is found.
(DSE trades Sunday-Thursday.)

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
main.py                     entry point / wiring
src/dse_news_bot/
  config.py                 .env -> validated Config
  client.py                 HTTP session with retries, fetches the news page
  parser.py                 HTML -> News objects
  notifier.py               News -> Telegram message
  state.py                  log of already-sent items (dedup)
  models.py                 News dataclass
  exceptions.py             ConfigError, FetchError, ParseError, NotifyError
```
