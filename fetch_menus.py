import requests
from bs4 import BeautifulSoup
from google import genai
import datetime
import json
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
DEBUG = os.environ.get("DEBUG", "0") == "1"
TOKEN_USAGE_FILE = os.path.join(os.path.dirname(__file__), "token_usage.json")


def easter(year):
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return datetime.date(year, month, day + 1)


def swedish_holidays(year):
    e = easter(year)
    midsommarafton = next(datetime.date(year, 6, x) for x in range(19, 26) if datetime.date(year, 6, x).weekday() == 4)
    return {
        datetime.date(year, 1, 1): "Nyårsdagen",
        datetime.date(year, 1, 6): "Trettondedag jul",
        e - datetime.timedelta(days=2): "Långfredagen",
        e: "Påskdagen",
        e + datetime.timedelta(days=1): "Annandag påsk",
        datetime.date(year, 5, 1): "Första maj",
        e + datetime.timedelta(days=39): "Kristi himmelsfärdsdag",
        datetime.date(year, 6, 6): "Nationaldagen",
        e + datetime.timedelta(days=49): "Pingstdagen",
        midsommarafton: "Midsommarafton",
        midsommarafton + datetime.timedelta(days=1): "Midsommardagen",
        datetime.date(year, 12, 24): "Julafton",
        datetime.date(year, 12, 25): "Juldagen",
        datetime.date(year, 12, 26): "Annandag jul",
        datetime.date(year, 12, 31): "Nyårsafton",
    }


def is_swedish_holiday(d):
    holidays = swedish_holidays(d.year)
    e = easter(d.year)
    kristi = e + datetime.timedelta(days=39)
    holidays[kristi + datetime.timedelta(days=1)] = "Klämdag (after Kristi himmelsfärdsdag)"
    if DEBUG:
        print("Swedish holidays this year:")
        for date, name in sorted(holidays.items()):
            print(f"  {date} - {name}")
    return holidays.get(d)


# --- Token usage tracking ---

def load_token_usage():
    if not os.path.exists(TOKEN_USAGE_FILE):
        return {
            "scheduled": {"history": [], "total_input": 0, "total_output": 0, "total_thinking": 0},
            "debug": {"history": [], "total_input": 0, "total_output": 0, "total_thinking": 0},
        }
    with open(TOKEN_USAGE_FILE, "r") as f:
        data = json.load(f)
    # Migrate old format if needed
    if "scheduled" not in data:
        old_history = data.get("history", [])
        old_total = {
            "total_input": data.get("total_input", 0),
            "total_output": data.get("total_output", 0),
            "total_thinking": data.get("total_thinking", 0),
        }
        data = {
            "scheduled": {"history": old_history, **old_total},
            "debug": {"history": [], "total_input": 0, "total_output": 0, "total_thinking": 0},
        }
    return data


def save_token_usage(data):
    with open(TOKEN_USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def update_token_usage(input_tokens, output_tokens, thinking_tokens=0):
    data = load_token_usage()
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    run_type = "debug" if DEBUG else "scheduled"
    data[run_type]["history"].append({
        "date": today_str,
        "input": input_tokens,
        "output": output_tokens,
        "thinking": thinking_tokens,
    })
    data[run_type]["total_input"] += input_tokens
    data[run_type]["total_output"] += output_tokens
    data[run_type]["total_thinking"] += thinking_tokens
    save_token_usage(data)
    return data


def get_30day_usage(data, run_type):
    cutoff = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    recent = [e for e in data[run_type]["history"] if e["date"] >= cutoff]
    return {
        "input": sum(e["input"] for e in recent),
        "output": sum(e["output"] for e in recent),
        "thinking": sum(e["thinking"] for e in recent),
    }


def format_token_usage(um, data, model_path):
    input_t = um.prompt_token_count or 0
    output_t = um.candidates_token_count or 0
    thinking_t = getattr(um, 'thoughts_token_count', 0) or 0
    run_type = "debug" if DEBUG else "scheduled"
    usage_30d = get_30day_usage(data, run_type)
    lines = [
        "--- Token Usage ---",
        f"  Input:    {input_t} tokens",
        f"  Output:   {output_t} tokens",
    ]
    if thinking_t:
        lines.append(f"  Thinking: {thinking_t} tokens")
    lines.append(f"  Total:    {input_t + output_t + thinking_t} tokens")
    lines.append(f"  [Scheduled] 30-day: in {get_30day_usage(data, 'scheduled')['input']} | out {get_30day_usage(data, 'scheduled')['output']} | think {get_30day_usage(data, 'scheduled')['thinking']} | all-time: in {data['scheduled']['total_input']} | out {data['scheduled']['total_output']} | think {data['scheduled']['total_thinking']}")
    lines.append(f"  [Debug]     30-day: in {get_30day_usage(data, 'debug')['input']} | out {get_30day_usage(data, 'debug')['output']} | think {get_30day_usage(data, 'debug')['thinking']} | all-time: in {data['debug']['total_input']} | out {data['debug']['total_output']} | think {data['debug']['total_thinking']}")
    lines.append(f"  Model: {model_path}")
    return "\n".join(lines)


# --- Fetch ---

def fetch_menu(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return {"url": url, "status": "ok", "content": text[:3000]}
    except requests.exceptions.HTTPError as e:
        return {"url": url, "status": "error", "code": e.response.status_code if e.response else 0}
    except Exception as e:
        return {"url": url, "status": "error", "code": str(e)}


# --- AI ---

def summarize(fetched_results):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    today = datetime.date.today()
    weekday = today.strftime("%A")
    date_str = today.strftime("%Y-%m-%d")

    # Separate successful fetches from failures
    ok_menus = [r for r in fetched_results if r["status"] == "ok"]
    failed = [r for r in fetched_results if r["status"] == "error"]

    menus_text = "\n\n".join(f"=== {r['url']} ===\n{r['content']}" for r in ok_menus)

    prompt = (
        f"Today is {weekday}, {date_str}. "
        "The following pages contain lunch menus, often listing all 5 weekdays. "
        f"Extract ONLY today's ({weekday}) menu for each restaurant. "
        "Output the summary in the following order: The Courtyard/The Bistro first, then Food & Co Kista, then the rest. "
        "NOTE: The URL 'ericssonbynordrest.se/restaurang/the-courtyard' may serve as 'The Bistro' during summer instead of 'The Courtyard'. "
        "Check the page content to determine which restaurant name is currently active and use that name in the output. "
        "If a restaurant's menu is not for today, or the restaurant is closed/on holiday, "
        "put it in a section called '餐厅关闭或信息不可用' with format: '关闭: 餐厅名 (从 X月X日 到 Y月Y日)' or '信息不可用: 餐厅名'. "
        "Include prices if available.\n\n"
        f"{menus_text}\n\n"
    )

    # Add failed restaurants info for AI
    if failed:
        prompt += "以下餐厅网页无法访问:\n"
        for r in failed:
            prompt += f"  - {r['url']} (Response code: {r['code']})\n"
        prompt += "\n"

    prompt += (
        "IMPORTANT FORMAT RULES:\n"
        "1. Every dish name MUST be written in Chinese first, followed by the original Swedish or English name in parenthesis. "
        "Example: '瑞典肉丸 (Köttbullar)', '烤三文鱼 (Grillad lax)'. NO exceptions. Do NOT put Swedish/English first.\n"
        "2. Closed restaurants and unreachable restaurants should ALL be grouped together at the end in a section titled "
        "'📋 餐厅关闭或信息不可用', using this format:\n"
        "   关闭: XXX餐厅 (从 X月X日 到 Y月Y日)\n"
        "   信息不可用: YYY餐厅 (Response code: ZZZ)\n"
    )

    if DEBUG:
        print("--- [DEBUG] Full prompt to AI ---")
        print(prompt)
        print("--- [DEBUG] End of prompt ---\n")

    models = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]
    tried_models = []
    for model in models:
        tried_models.append(model)
        try:
            response = client.models.generate_content(model=model, contents=prompt)
        except Exception as e:
            print(f"Model {model} failed: {e}")
            continue

        model_path = " → ".join(tried_models) + (" (fallback)" if len(tried_models) > 1 else "")
        print(f"Used model: {model_path}")

        # Token usage
        usage_str = ""
        if response.usage_metadata:
            um = response.usage_metadata
            input_t = um.prompt_token_count or 0
            output_t = um.candidates_token_count or 0
            thinking_t = getattr(um, 'thoughts_token_count', 0) or 0
            data = update_token_usage(input_t, output_t, thinking_t)
            usage_str = "\n" + format_token_usage(um, data, model_path)
            print(usage_str)
            if DEBUG:
                print(f"  [DEBUG] Full usage_metadata: {um}")
        return response.text, usage_str
    raise RuntimeError("All models failed")


# --- Webhook ---

def send_webhook(text):
    if DEBUG:
        print("[DEBUG] Skipping webhook")
        return
    if not WEBHOOK_URL:
        return
    for i in range(0, len(text), 2000):
        requests.post(WEBHOOK_URL, json={"content": text[i:i+2000]}, timeout=10)


# --- Main ---

def main():
    today = datetime.date.today()
    if today.month == 7:
        print("July - skipping (summer break)")
        return
    holiday = is_swedish_holiday(today)
    if holiday:
        print(f"Today is {holiday} - skipping")
        return
    print(f"Fetching lunch menus for Kista - {today.strftime('%A %Y-%m-%d')}\n")

    fetched_results = [fetch_menu(url) for url in RESTAURANTS]

    if DEBUG:
        ok_count = sum(1 for r in fetched_results if r["status"] == "ok")
        err_count = sum(1 for r in fetched_results if r["status"] == "error")
        print(f"Fetched: {ok_count} ok, {err_count} failed\n")

    summary, usage_str = summarize(fetched_results)
    print(summary)
    send_webhook(summary + usage_str)


if __name__ == "__main__":
    main()
