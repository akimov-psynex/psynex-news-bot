"""
Psynex News Bot v3
Кожен пошук = окремий Claude API виклик.
Без site: операторів. Прості природні запити.
"""

import os
import json
import hashlib
import requests
import anthropic
from datetime import datetime, timedelta
import time

TELEGRAM_TOKEN = os.environ["TELEGRAM_NEWS_TOKEN"]
TELEGRAM_CHAT  = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_KEY  = os.environ["ANTHROPIC_API_KEY"]
SEEN_FILE      = "seen_news.json"

TODAY    = datetime.now()
DATE_STR = TODAY.strftime("%d.%m.%Y")
WEEK_AGO = (TODAY - timedelta(days=7)).strftime("%d.%m.%Y")

CATEGORIES = [
    {
        "id": "ua_startups",
        "emoji": "🇺🇦",
        "label": "Українські стартапи",
        "queries": [
            "Ukrainian startup raised investment round April 2026",
            "Ukraine tech company funding million 2026",
            "Ukrainian startup grant received 2026",
            "Kyiv Independent startup news April 2026",
        ]
    },
    {
        "id": "psynex_similar",
        "emoji": "🚀",
        "label": "Стартапи схожі на Psynex",
        "queries": [
            "dating app AI feature launch funding April 2026",
            "Hinge Bumble new AI feature update 2026",
            "personality matching relationship app news April 2026",
            "self-discovery psychology app startup funding 2026",
        ]
    },
    {
        "id": "investments",
        "emoji": "💰",
        "label": "Залучення інвестицій",
        "queries": [
            "AI startup biggest funding round April 2026",
            "European AI startup investment series 2026",
            "AI company raised hundred million 2026",
            "venture capital AI fund launch 2026",
        ]
    },
    {
        "id": "anthropic",
        "emoji": "🤖",
        "label": "Anthropic / Claude",
        "queries": [
            "Anthropic news announcement April 2026",
            "Claude AI new model update April 2026",
            "Anthropic Claude new feature release 2026",
        ]
    },
    {
        "id": "ai_trends",
        "emoji": "📈",
        "label": "AI тренди",
        "queries": [
            "OpenAI Google new AI model announcement April 2026",
            "artificial intelligence breakthrough news April 2026",
            "EU AI Act regulation news April 2026",
            "AI consumer product trend April 2026",
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

def single_search(query: str, client: anthropic.Anthropic) -> list[dict]:
    prompt = f"""
Виконай веб-пошук за запитом: "{query}"

Сьогодні: {DATE_STR}
Шукай новини за останні 7 днів (після {WEEK_AGO}).

Якщо знайшов реальні новини — поверни JSON масив.
Якщо нічого свіжого немає — поверни [].

Відповідай ЛИШЕ JSON (без markdown):
[
  {{
    "title": "Заголовок новини мовою оригіналу",
    "url": "https://реальне посилання",
    "date": "ДД.ММ.РРРР",
    "source": "назва видання",
    "geo": "UA або EU або UK або USA або Global",
    "summary_en": "Короткий переказ 2-3 речення англійською",
    "importance": 8
  }}
]
Максимум 2 результати. Тільки реальні новини з реальними URL.
"""
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            text = text[start:end]
        return json.loads(text) if text else []
    except Exception as e:
        print(f"    ⚠ {e}")
        return []

def translate_and_format(items: list[dict], client: anthropic.Anthropic) -> list[dict]:
    if not items:
        return []
    items_str = json.dumps(items, ensure_ascii=False, indent=2)
    prompt = f"""
Ось список новин:
{items_str}

Для кожної новини:
1. Перекладіть title українською
2. Напишіть summary_ua — переказ 150-200 слів українською. Що сталось, хто головний герой, яка сума або масштаб, чому важливо для AI ринку або стартап-екосистеми.
3. Збережіть всі інші поля без змін

Відповідай ЛИШЕ JSON масивом (без markdown):
[
  {{
    "title": "Заголовок українською",
    "url": "...",
    "date": "...",
    "source": "...",
    "geo": "...",
    "summary_ua": "Переказ 150-200 слів українською...",
    "importance": 8
  }}
]
"""
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            text = text[start:end]
        return json.loads(text) if text else items
    except Exception as e:
        print(f"    ⚠ translate error: {e}")
        return items

def send_telegram(text: str):
    if len(text) > 4096:
        text = text[:4090] + "..."
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "HTML"},
        timeout=15
    ).raise_for_status()

def format_news(n: dict, category: dict) -> str:
    geo_flag = {"UA":"🇺🇦","EU":"🇪🇺","UK":"🇬🇧","USA":"🇺🇸","Global":"🌍"}.get(n.get("geo",""),"🌐")
    importance = n.get("importance", 0)
    heat = "🔥" if importance >= 9 else "⭐⭐" if importance >= 7 else "⭐"
    summary = n.get("summary_ua") or n.get("summary_en","")
    return (
        f"{category['emoji']} {geo_flag} {heat} <b>{n['title']}</b>\n\n"
        f"{summary}\n\n"
        f"📅 {n.get('date','?')} | 📰 {n.get('source','')}\n"
        f"🔗 {n.get('url','')}"
    )

def main():
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    print(f"\n{'='*50}\nPsynex News Bot v3 | {now}\n{'='*50}")

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
        all_raw = []
        seen_urls = set()

        for query in category["queries"]:
            print(f"  🔍 {query[:50]}...")
            results = single_search(query, client)
            for r in results:
                url = r.get("url","")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_raw.append(r)
            time.sleep(1)

        print(f"  Знайдено: {len(all_raw)}")

        if not all_raw:
            send_telegram(
                f"{category['emoji']} <b>{category['label']}</b>\n\n"
                f"📭 Свіжих новин не знайдено."
            )
            continue

        new_raw = [r for r in all_raw if news_id(r.get("title","")) not in seen]

        if not new_raw:
            send_telegram(
                f"{category['emoji']} <b>{category['label']}</b>\n\n"
                f"📭 Всі знайдені новини вже надсилались раніше."
            )
            continue

        new_raw.sort(key=lambda x: x.get("importance",0), reverse=True)
        translated = translate_and_format(new_raw[:3], client)

        sent_in_category = 0
        for n in translated:
            nid = news_id(n.get("title",""))
            try:
                send_telegram(format_news(n, category))
                seen.add(nid)
                sent_in_category += 1
                total_sent += 1
            except Exception as e:
                print(f"  ❌ {e}")

        print(f"  Надіслано: {sent_in_category}")

    send_telegram(
        f"✅ <b>Дайджест завершено — {now}</b>\n"
        f"Всього новин надіслано: {total_sent}"
    )

    save_seen(seen)
    print(f"\n✅ Готово. Надіслано: {total_sent}")

if __name__ == "__main__":
    main()
