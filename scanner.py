import os
import re
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_TARGET = "https://24live.com/page/sport/event/table-tennis-22/22339;sid=70504?lang=en"

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Credenziali Telegram mancanti.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def run():
    print(f"Avvio scansione avanzata con intercettazione dati su 24live...")
    captured_data = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                locale="en-US"
            )
            page = context.new_page()

            # Intercettiamo le risposte di rete JSON da 24live
            def handle_response(response):
                try:
                    if "json" in response.headers.get("content-type", "") or "event" in response.url or "api" in response.url:
                        data = response.json()
                        captured_data.append(data)
                except Exception:
                    pass

            page.on("response", handle_response)

            page.goto(URL_TARGET, timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(8000)

            html_content = page.content()
            browser.close()

        matches = []

        # 1. Analizziamo i dati JSON catturati dalla rete
        json_str = json.dumps(captured_data)
        # Cerchiamo pattern di eventi / quote / nomi nel JSON
        events = re.findall(r'"([A-Za-z0-9\s\.\-]+)\s+(?:vs|v|\-)\s+([A-Za-z0-9\s\.\-]+)"', json_str, re.IGNORECASE)
        
        for e in events:
            p1, p2 = e[0].strip(), e[1].strip()
            if len(p1) > 2 and len(p2) > 2 and not any(kw in p1.lower() for kw in ["table", "tennis", "live", "sport"]):
                m_name = f"{p1} - {p2}"
                if m_name not in [m["match"] for m in matches]:
                    matches.append({"match": m_name, "odds1": None, "odds2": None, "has_odds": False})

        # 2. Se il JSON non ha estratto nulla, analizziamo l'HTML con selettori generici
        if not matches:
            soup = BeautifulSoup(html_content, 'html.parser')
            # Cerchiamo tutte le righe contenenti i trattini dei match
            for div in soup.find_all(['div', 'tr', 'li']):
                text = div.get_text(separator=" ", strip=True)
                if (" - " in text or " vs " in text) and len(text) > 8 and len(text) < 120:
                    clean = " ".join(text.split())
                    if not any(kw in clean.lower() for kw in ["cookie", "privacy", "table tennis", "menu", "home", "search"]):
                        odds = re.findall(r'\b[1-9]\.\d{2}\b', clean)
                        o1 = float(odds[0]) if len(odds) >= 1 else None
                        o2 = float(odds[1]) if len(odds) >= 2 else None
                        m_data = {
                            "match": clean[:90],
                            "odds1": o1,
                            "odds2": o2,
                            "has_odds": (o1 is not None and o2 is not None)
                        }
                        if not any(m["match"] == m_data["match"] for m in matches):
                            matches.append(m_data)

        if not matches:
            send_telegram("ℹ️ **24live Prono**: Pagina caricata con successo! In questo momento non ci sono match attivi o quote pre-match pubblicate su questa scheda.")
            return

        send_telegram(f"🔍 **24live Prono**: Trovati **{len(matches)}** match!")

        for m in matches[:15]:
            if m["has_odds"]:
                diff = abs(m["odds1"] - m["odds2"])
                is_over = (diff <= 0.30) and (1.65 <= m["odds1"] <= 2.15) and (1.65 <= m["odds2"] <= 2.15)
                odds_str = f"1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)"
            else:
                is_over = False
                odds_str = "Pre-match (Quote in arrivo)"

            if is_over:
                signal_header = "🟢 **CONSIGLIATO: OVER 18.5 PUNTI**"
                advice = "🎯 **Suggerimento:** GIOCA OVER 18.5 (Match equilibrato)"
            else:
                signal_header = "⚪ **MATCH IN PALINSESTO**"
                advice = "⚠️ **Suggerimento:** PASS"

            msg = (
                f"{signal_header}\n\n"
                f"⚔️ **Match:** {m['match']}\n"
                f"📊 **Quote:** {odds_str}\n"
                f"{advice}"
            )
            send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Errore durante l'estrazione: `{e}`")

if __name__ == "__main__":
    run()
