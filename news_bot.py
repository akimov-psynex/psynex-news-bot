"""
Psynex News Bot
Щодня о 08:00 шукає AI новини через Claude web search
та надсилає в Telegram українською мовою.
"""

import os
import json
import hashlib
import requests
import anthropic
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.environ["TELEGRAM_NEWS_TOKEN"]
TELEGRAM_CHAT  = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_KEY  = os.environ["ANTHROPIC_API_KEY"]
SEEN_FILE      = "seen_news.json"

TODAY      = datetime.now()
YESTERDAY  = (TODAY - timedelta(days=1)).strftime("%Y-%m-%d")
DAY_BEFORE = (TODAY - timedelta(days=2)).strftime("%Y-%m-%d")
DATE_STR   = TODAY.strftime("%d.%m.%Y")

CATEGORIES = [
    {
        "id": "ua_startups",
        "emoji": "🇺🇦",
        "label": "Українські стартапи",
        "queries": [
            f"Ukrainian startup funding round raised investment {YESTERDAY}",
            f"український стартап раунд інвестиція грант {YESTERDAY}",
            f"Ukraine startup grant received funding site:ain.ua OR site:dou.ua OR site:tech.liga.net",
            f"Ukraine tech startup investment TechCrunch Forbes {YESTERDAY}",
        ]
    },
    {
        "id": "psynex_similar",
        "emoji": "🚀",
        "label": "Стартапи схожі на Psynex",
        "queries": [
            f"dating app AI personality self-discovery funding news {YESTERDAY}",
            f"relationship app AI launch funding 2026 {YESTERDAY}",
            f"So Syncd PersonalityMatch Hinge Bumble AI news {YESTERDAY}",
            f"mental wellness self-discovery app startup news {YESTERDAY}",
        ]
    },
    {
        "id": "investments",
        "emoji": "💰",
        "label": "Залучення інвестицій",
        "queries": [
            f"startup venture capital funding round news {YESTERDAY}",
            f"AI startup series A B seed round raised million {YESTERDAY}",
            f"European startup investment round {YESTERDAY} site:techcrunch.com OR site:eu-startups.com",
            f"Ukraine Eastern Europe startup investment news {YESTERDAY}",
        ]
    },
    {
        "id": "anthropic",
        "emoji": "🤖",
        "label": "Anthropic / Claude",
        "queries": [
            f"Anthropic Claude update news {YESTERDAY}",
            f"Anthropic new model feature announcement {YESTERDAY}",
            f"Claude AI update release {YESTERDAY} site:anthropic.com OR site:techcrunch.com",
        ]
    },
    {
        "id": "ai_trends",
        "emoji": "📈",
        "label": "AI тренди",
        "queries": [
            f"artificial intelligence trend breakthrough {YESTERDAY}",
            f"AI consumer app trend news {YESTERDAY}",
            f"OpenAI Google DeepMind AI news {YESTERDAY}",
            f"AI regulation Europe US news {YESTERDAY}",
        ]
    },
]

def load_seen() -> set:
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)

def news_id(title: str) -> str:
    return hashlib.md5(title.lower().strip()[:80].encode()).hexdigest()[:12]

def search_news(category: dict, client: anthropic.Anthropic) -> list[dict]:
    queries_str = "\n".join(f"- {q}" for q in category["queries"])
    prompt = f"""
Ти — AI-аналітик новин для українського стартапу Psynex (AI-платформа самопізнання та стосунків).

Зроби пошук за цими запитами:
{queries_str}

Знайди МІНІМУМ 2 реальні свіжі новини за {YESTERDAY} або {DAY_BEFORE}.
Категорія: {category['label']}

Для кожної новини напиши переказ українською мовою 150-200 слів.

Відповідай ЛИШЕ JSON (без markdown):
[
  {{
    "title": "Заголовок українською",
    "url": "https://оригінальне посилання",
    "date": "ДД.ММ.РРРР",
    "source": "назва ЗМІ",
    "geo": "UA або EU або UK або USA",
    "summary_ua": "Переказ новини українською мовою, 150-200 слів. Обов'язково: хто, що зробив, яка сума/масштаб, чому важливо для ринку AI або стартапів.",
    "importance": 8
  }}
]

ВАЖЛИВО:
- Тільки реальні новини з реальними посиланнями
- Дата: {YESTERDAY} або {DAY_BEFORE} (не старіше)
- Мінімум 2 новини
- summary_ua ОБОВ'ЯЗКОВО 150-200 слів українською
- Якщо нічого — поверни []
"""
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        return json.loads(text) if text and text != "[]" else []
    except Exception as e:
        print(f"  ⚠ {e}")
        return []

def send_telegram(text: str):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "HTML"},
        timeout=15
    ).raise_for_status()

def format_news(n: dict, category: dict) -> str:
    geo_flag = {"UA":"🇺🇦","EU":"🇪🇺","UK":"🇬🇧","USA":"🇺🇸"}.get(n.get("geo",""),"🌐")
    importance = n.get("importance", 0)
    heat = "🔥" if importance >= 9 else "⭐⭐" if importance >= 7 else "⭐"
    return (
        f"{category['emoji']} {geo_flag} {heat} <b>{n['title']}</b>\n\n"
        f"{n.get('summary_ua','')}\n\n"
        f"📅 {n.get('date','?')} | 📰 {n.get('source','')}\n"
        f"🔗 {n.get('url','')}"
    )

def main():
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    print(f"\n{'='*50}\nPsynex News Bot | {now}\n{'='*50}")

    seen = load_seen()
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    send_telegram(
        f"📰 <b>AI Дайджест для Psynex — {DATE_STR}</b>\n\n"
        f"🇺🇦 Українські стартапи\n"
        f"🚀 Схожі на Psynex\n"
        f"💰 Інвестиції\n"
        f"🤖 Anthropic / Claude\n"
        f"📈 AI тренди"
    )

    total_sent = 0

    for category in CATEGORIES:
        print(f"\n📂 {category['label']}...")
        news_list = search_news(category, client)

        new_items = [
            (news_id(n["title"]), n) for n in news_list
            if news_id(n.get("title","")) not in seen
        ]
        new_items.sort(key=lambda x: x[1].get("importance",0), reverse=True)

        if not new_items:
            send_telegram(
                f"{category['emoji']} <b>{category['label']}</b>\n\n"
                f"📭 Свіжих новин за вчора/позавчора не знайдено."
            )
            continue

        sent_in_category = 0
        for nid, n in new_items[:3]:
            try:
                send_telegram(format_news(n, category))
                seen.add(nid)
                sent_in_category += 1
                total_sent += 1
            except Exception as e:
                print(f"  ❌ {e}")

        print(f"   Надіслано: {sent_in_category}")

    send_telegram(
        f"✅ <b>Дайджест завершено — {now}</b>\n"
        f"Всього новин надіслано: {total_sent}"
    )

    save_seen(seen)
    print(f"\n✅ Готово. Надіслано: {total_sent}")

if __name__ == "__main__":
    main()
