# Kista Lunch Menu Summarizer

Fetches daily lunch menus from restaurants near Kista and summarizes them using Google Gemini API.

## Setup

1. Push this repo to your personal GitHub account
2. Add secret: `Settings > Secrets > Actions > GEMINI_API_KEY`
3. Runs automatically Mon-Fri at 10:00 Stockholm time, or trigger manually from the Actions tab

## Local usage

```bash
export GEMINI_API_KEY=your-key-here
pip install -r requirements.txt
python fetch_menus.py
```

## Adding restaurants

Edit the `RESTAURANTS` list in `fetch_menus.py` with any publicly accessible lunch menu URL.

## Maintenance notes

- **Scheduled-workflow auto-disable:** GitHub disables `schedule` triggers on a repo after **60 days of no repository activity**. This project commits `token_usage.json` back on each run, which counts as activity and keeps the schedule alive. If you ever strip out the commit-back step, watch for the workflow going silent — re-enable it from the Actions tab.
- **Scheduling delay:** GitHub's cron is best-effort and can run hours late on free tier. The cron is set earlier than the desired delivery time to compensate.
- **Dry run:** trigger the workflow with the `dry_run` option (or run `python fetch_menus.py --dry-run` locally) to test the fetch layer without spending AI tokens or posting to the webhook. Works even without `google-genai` installed.
- **Debug:** the `debug` option skips the webhook and prints the full AI prompt + token usage to the log.
