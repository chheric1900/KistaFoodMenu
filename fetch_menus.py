import requests
from bs4 import BeautifulSoup
from google import genai
import datetime
import os

RESTAURANTS = [
    "https://ericssonbynordrest.se/restaurang/the-courtyard/#lunch-menu",
    "https://www.compass-group.se/restauranger-och-menyer/foodandco/kista/",
    "https://www.compass-group.se/restauranger-och-menyer/foodandco/food--co-timebuilding/",
    "https://restaurang88.se/LunchBuffet.html",
    "https://www.kvartersmenyn.se/index.php/rest/16302",
    "https://www.kvartersmenyn.se/index.php/rest/9464",
    "https://www.kvartersmenyn.se/index.php/rest/16966",
]

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
USER_AGENT = "Mozilla/5.0"


def fetch_menu(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return f"=== {url} ===\n{text[:3000]}"
    except Exception as e:
        return f"=== {url} ===\n[Failed to fetch: {e}]"


def summarize(menus_text):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    today = datetime.date.today()
    weekday = today.strftime("%A")
    date_str = today.strftime("%Y-%m-%d")
    prompt = (
        f"Today is {weekday}, {date_str}. "
        "The following pages contain lunch menus, often listing all 5 weekdays. "
        f"Extract ONLY today's ({weekday}) menu for each restaurant. "
        "Output the summary in the following order: The Courtyard first, then Food & Co Kista, then the rest. "
        "Include dish names and prices if available. "
        "Dish names should be noted in Swedish if they are written as Swedish in the webpage, otherwise put in English. "
        "Add Chinese translation in parenthesis after each dish name. "
        "If a restaurant failed to load or today's menu is not found, note it briefly.\n\n"
        f"{menus_text}"
    )
    models = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]
    for model in models:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            print(f"Used model: {model}")
            return response.text
        except Exception as e:
            print(f"Model {model} failed: {e}")
    raise RuntimeError("All models failed")


def send_webhook(text):
    if not WEBHOOK_URL:
        return
    for i in range(0, len(text), 2000):
        requests.post(WEBHOOK_URL, json={"content": text[i:i+2000]}, timeout=10)


def main():
    today = datetime.date.today()
    print(f"Fetching lunch menus for Kista - {today.strftime('%A %Y-%m-%d')}\n")
    menus = [fetch_menu(url) for url in RESTAURANTS]
    combined = "\n\n".join(menus)
    summary = summarize(combined)
    print(summary)
    send_webhook(summary)


if __name__ == "__main__":
    main()
