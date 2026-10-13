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

`pip install -e .` installs the dependencies from `pyproject.toml`, puts
`src/dse_news_bot` on the import path in editable mode, and creates
the `dse-news-bot` command in `.venv/Scripts/`.

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

`STATE_PATH`, `LOG_PATH` and `LOG_LEVEL` are optional and have working defaults.

| Key | Meaning |
| --- | --- |
| `PORTFOLIO` | Comma-separated trading codes to watch. Case and spacing don't matter. |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) -> `/newbot`. |
| `TELEGRAM_CHAT_ID` | Where messages go. See below. |
| `STATE_PATH` | Optional. Where the "already sent" log lives; defaults to `.state/sent.json`. |
| `LOG_PATH` | Optional. Where the log file lives; defaults to `.logs/dse-news-bot.log`. See [Logs](#logs). |
| `LOG_LEVEL` | Optional. `DEBUG`, `INFO`, `WARNING`, `ERROR`; defaults to `INFO`. |

`STATE_PATH`'s and `LOG_PATH`'s defaults are **relative to the current working
directory**, which is fine when you run from the project root and a problem under
a scheduler. See [Scheduling](#scheduling).

### Finding your chat id

A bot token alone can't send anywhere - Telegram also needs a chat id, and one
only exists once you've messaged the bot.

1. Open your bot in Telegram and send it any message (e.g. `hi`).
2. Run:

   ```bash
   dse-news-bot --chat-id
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
dse-news-bot
```

Fetches today's DSE news, keeps the items whose trading code is in `PORTFOLIO`,
and sends one Telegram message per item. Already-sent items are recorded in
`.state/sent.json`, so running it repeatedly through the day only delivers what
is new. The same run then sends the [market update](#market-update) once the
market has closed. Exits `1` with a one-line message if anything fails; a failure
in one of the two doesn't stop the other.

Everything it prints also goes to a log file - see [Logs](#logs).

### Market update

Once per trading day, after the 14:30 close, the bot sends one Telegram message
with each `PORTFOLIO` ticker's last traded price (LTP) and its change against
yesterday's close (YCP), `(LTP - YCP) x 100 / YCP`, with an arrow for the
direction. Prices come from DSE's
[latest share price](https://old.dsebd.org/latest_share_price_scroll_l.php) page.

```
Today's Update

1JANATAMF    3.50   ▲ +6.06%
BDSERVICE    5.20  no trades
GP         238.30   ▼ -1.16%
ROBI        29.80      0.00%

Not on the price page: NOTREAL
```

The title is bold in Telegram. A ticker with no trades today shows yesterday's
close; a row DSE renders with unexpected values is skipped with a warning.

Every run checks, in order, and stops at the first that fails:

1. **Not done yet today** - a `market|<date>` entry in `.state/sent.json` records
   the send, so it goes out once however often the task runs.
2. **After 14:30** Dhaka time, whatever the machine's clock zone - before the close
   the price page isn't even fetched.
3. **Prices are from today** - after the close, a page still showing an earlier
   day means no trading today (a holiday). That is recorded too, so the page isn't
   fetched again until tomorrow.
4. **Prices are the close** - the page's timestamp must be 14:30 or later. If it
   still shows an earlier time at 15:30, the page stopped at the bell and today's
   prices are sent anyway.

A page with no price table at all fails the run instead of sending an empty update,
and a later run tries again. A long update is split over several messages.

```bash
dse-news-bot --market              # just the market update, same checks, sends
dse-news-bot --market --dry-run    # print it now: no checks, no Telegram, only PORTFOLIO needed
```

Any other flag combination is rejected with exit code `2` and a usage line.

## Logs

Every run appends to `.logs/dse-news-bot.log` (override with `LOG_PATH`). This is
the point of the whole thing under a scheduler, where stdout goes nowhere: the
file is the only record that a run happened at all.

```
2026-08-26 19:12:51 INFO     dse_news_bot: Parsed 58 news items, 1 pending for your portfolio
2026-08-26 19:12:53 INFO     dse_news_bot: Sent GP: Suspension for Record Date
```

The file rotates at midnight and keeps **7 days**, so yesterday is
`dse-news-bot.log.2026-08-25`. Rotation is driven by the file's timestamp rather
than by a running clock, so it works even though each run lives about two seconds.

The console keeps the plain wording it always had - the timestamps and levels are
added only in the file. Console log lines go to stderr, so `dse-news-bot --market
--dry-run > update.txt` captures just the update.

Set `LOG_LEVEL=DEBUG` for more detail. Bot tokens are stripped from every record
before it is written, so a Telegram URL in a retry warning or a traceback lands as
`bot<redacted>` - the log file is safe to paste into a bug report.

If the log file can't be opened (a bad `LOG_PATH`, a missing drive) the run says so
once and carries on to the console. Losing the log is not worth losing the run.

## Scheduling

Target schedule: **every 5 minutes, Sunday-Thursday, 09:30 to 17:30** - an 8 hour
repetition window. The close is 14:30, but DSE's price-sensitive notices (board
meetings, dividend declarations) are usually published after it, so the window runs
well past.

### Register it

Go to **Task Scheduler** on Windows and click on **Create Task** (not *Create Basic Task*, which
cannot set a repetition interval) and set the name as "DSE News": Triggers -> Weekly, Sun-Thu, 09:30, Advanced ->
repeat every 5 minutes for 8 hours 30 minutes; Actions -> the `.exe` above with
**Start in** set to the project root; Settings -> tick *run as soon as possible
after a scheduled start is missed* and leave *do not start a new instance* selected.

```powershell
schtasks /run    /tn "DSE News"                # trigger once, now
schtasks /query  /tn "DSE News" /v /fo LIST    # check "Last Result" (0 = success)
schtasks /delete /tn "DSE News" /f             # remove
```

"Last Result" tells you only whether a run failed. For *what* it did - or why it
failed - read the log file.

The market update needs no task of its own: the first run after DSE publishes its
closing prices (around 14:40) sends it, and every later run that day skips it.

### Set STATE_PATH and LOG_PATH to absolute paths

`SentLog` treats an unreadable log as an empty one by design - a corrupt file should
cost a duplicate message, not a failed run. The side effect is that a *wrong* path
still delivers every item again, every run. At a 5-minute cadence that is the whole
day resent, roughly 66 times over.

Before creating the task, run `dse-news-bot` twice from the project root: the second
run should report `0 pending for your portfolio`. If it re-sends, the dedup key isn't
stable and the schedule would have amplified that.

## Debug

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Run dse-news-bot",
      "type": "debugpy",
      "request": "launch",
      "module": "dse_news_bot.cli",
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

## Layout

```
src/dse_news_bot/
  cli.py                    entry point / wiring
  config.py                 .env -> validated Config
  client.py                 HTTP session with retries, fetches the news and price pages
  parser.py                 HTML -> News / MarketSnapshot objects
  report.py                 MarketSnapshot -> market update text
  notifier.py               News -> Telegram message
  state.py                  log of already-sent items (dedup)
  logs.py                   console + rotating file logging setup
  models.py                 News, SharePrice, MarketSnapshot dataclasses
  exceptions.py             ConfigError, FetchError, ParseError, NotifyError
```
