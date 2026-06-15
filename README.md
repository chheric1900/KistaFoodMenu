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
