"""
Psynex News Bot v5
Дедублікація по URL. Один запуск на день через cron-job.org.
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
            "Kyiv based startup secures funding 2026",
            "Ukrainian founder raises seed round 2026",
            "Ukraine technology company investment deal 2026",
            "Emerging Europe Ukraine startup news 2026",
            "Ukrainian tech company expansion Europe 2026",
            "Ukraine startup grant program receives 2026",
            "Ukrainian startup accelerator demo day 2026",
        ]
    },
    {
        "id": "psynex_similar",
        "emoji": "🚀",
        "label": "Стартапи схожі на Psynex",
        "queries": [
            "Hinge new feature update launch 2026",
            "Bumble new AI feature announcement 2026",
            "dating app raises funding round 2026",
            "personality test dating app news 2026",
            "relationship app AI launch 2026",
            "self-discovery app startup funding secured 2026",
            "mental wellness app series funding 2026",
            "couples therapy app startup news 2026",
        ]
    },
    {
        "id": "investments",
        "emoji": "💰",
        "label": "Залучення інвестицій",
        "queries": [
            "AI startup raises hundred million series 2026",
            "largest AI funding round closed this week 2026",
            "European AI startup secures venture capital 2026",
            "Sifted European startup funding news 2026",
            "venture capital fund launched AI focus 2026",
            "VC firm closes new fund artificial intelligence 2026",
        ]
    },
    {
        "id": "anthropic",
        "emoji": "🤖",
        "label": "Anthropic / Claude",
        "queries": [
            "Anthropic releases new Claude model 2026",
            "Claude AI new capability announced 2026",
            "Anthropic company news announcement 2026",
            "Anthropic partnership deal signed 2026",
            "Claude API new feature developers 2026",
        ]
    },
    {
        "id": "ai_trends",
        "emoji": "📈",
        "label": "AI тренди",
        "queries": [
            "OpenAI new model released 2026",
            "Google DeepMind AI announcement 2026",
            "Meta AI Mistral new model launch 2026",
            "EU AI Act implementation news 2026",
            "AI regulation United States 2026",
            "AI consumer app breakthrough 2026",
            "artificial intelligence research breakthrough 2026",
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

def news_id(title: str, url: str = "") -> str:
    # Хешуємо по URL — надійніший за назву
    key = url.strip().rstrip("/").lower() if url else title.lower().strip()[:80]
    return hashlib.md5(key.encode()).hexdigest()[:12]

def single_search(query: str, client: anthropic.Anthropic) -> list[dict]:
    prompt = f"""
Виконай веб-пошук за запитом: "{query}"

Сьогодні: {DATE_STR}. Шукай новини за останні 7 днів (після {WEEK_AGO}).

Відповідай ЛИШЕ JSON (без markdown, без тексту до або після):
[
  {{
    "title": "Точний заголовок новини мовою оригіналу",
    "url": "https://реальне пряме посилання на статтю",
    "date": "ДД.ММ.РРРР",
    "source": "назва видання",
    "geo": "UA або EU або UK або USA або Global",
    "summary_en": "2-3 речення про що новина англійською",
    "importance": 7
  }}
]

ПРАВИЛА:
- Максимум 2 результати
- Тільки реальні новини з реальними прямими URL
- Новини не старіші 7 днів
- Якщо нічого свіжого — поверни []
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

def translate_and_summarize(items: list[dict], client: anthropic.Anthropic) -> list[dict]:
    if not items:
        return []
    items_str = json.dumps(items, ensure_ascii=False, indent=2)
    prompt = f"""
Ось новини:
{items_str}

Для кожної новини зроби:
1. title — переклади заголовок українською
2. summary_ua — переказ українською 150-200 слів. Структура: хто і що зробив → яка сума або масштаб → контекст ринку → чому важливо для AI або стартап-екосистеми
3. Всі інші поля (url, date, source, geo, importance) — залиш без змін

Відповідай ЛИШЕ JSON масивом (без markdown):
[
  {{
    "title": "Заголовок українською",
    "url": "...",
    "date": "...",
    "source": "...",
    "geo": "...",
    "summary_ua": "Переказ 150-200 слів українською...",
    "importance": 7
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
    print(f"\n{'='*50}\nPsynex News Bot v5 | {now}\n{'='*50}")

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
            print(f"  🔍 {query[:55]}...")
            results = single_search(query, client)
            for r in results:
                url = r.get("url", "").strip().rstrip("/").lower()
                title = r.get("title", "")
                if url and url not in seen_urls and title:
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

        # Фільтруємо по URL хешу
        new_raw = [
            r for r in all_raw
            if news_id(r.get("title",""), r.get("url","")) not in seen
        ]

        if not new_raw:
            send_telegram(
                f"{category['emoji']} <b>{category['label']}</b>\n\n"
                f"📭 Всі знайдені новини вже надсилались."
            )
            continue

        new_raw.sort(key=lambda x: x.get("importance", 0), reverse=True)
        translated = translate_and_summarize(new_raw[:3], client)

        sent_in_category = 0
        for n in translated:
            nid = news_id(n.get("title",""), n.get("url",""))
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
