import os
import re
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
    print("Avvio scansione basata sulle quote dei match...")
    matches = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale="en-US"
            )
            page = context.new_page()
            
            page.goto(URL_TARGET, timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(8000)
            
            html_content = page.content()
            browser.close()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Cerchiamo tutti i blocchi che contengono potenziali quote (numeri con la virgola/punto tipo 1.xx o 2.xx)
        elements = soup.find_all(True)
        
        # Parole da scartare tassativamente se compaiono nei nomi
        ignore_words = [
            "english", "čeština", "rights", "reserved", "version", "cookie", "privacy", 
            "about", "home", "menu", "sport", "live", "schedule", "results", "login", 
            "register", "search", "odds", "settings", "terms", "contact", "download", "app"
        ]

        for el in elements:
            txt = el.get_text(separator=" ", strip=True)
            # Se un blocco contiene quote e sembra una riga di match
            if re.search(r'\b[12]\.\d{2}\b', txt):
                lines = [l.strip() for l in txt.split('\n') if l.strip()]
                
                # Cerchiamo righe che contengono nomi di atleti o trattini/vs
                for idx, line in enumerate(lines):
                    if " - " in line or " vs " in line.lower():
                        parts = re.split(r'\s+-\s+|\s+vs\s+', line, flags=re.IGNORECASE)
                        if len(parts) == 2:
                            p1, p2 = parts[0].strip(), parts[1].strip()
                            
                            # Filtriamo via le stringhe di sistema
                            combined = (p1 + " " + p2).lower()
                            if any(w in combined for w in ignore_words):
                                continue
                                
                            if len(p1) > 2 and len(p2) > 2:
                                match_name = f"{p1} - {p2}"
                                
                                # Estraiamo le quote vicine
                                odds = re.findall(r'\b[12]\.\d{2}\b', txt)
                                o1 = float(odds[0]) if len(odds) >= 1 else None
                                o2 = float(odds[1]) if len(odds) >= 2 else None
                                
                                m_data = {
                                    "match": match_name,
                                    "odds1": o1,
                                    "odds2": o2,
                                    "has_odds": (o1 is not None and o2 is not None)
                                }
                                
                                if not any(m["match"] == m_data["match"] for m in matches):
                                    matches.append(m_data)

        if not matches:
            print("Nessun match con quote trovato in questo ciclo.")
            return

        for m in matches[:6]:
            if m["has_odds"]:
                diff = abs(m["odds1"] - m["odds2"])
                is_over = (diff <= 0.30) and (1.65 <= m["odds1"] <= 2.15) and (1.65 <= m["odds2"] <= 2.15)
                odds_str = f"1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)"
            else:
                is_over = False
                odds_str = "Pre-match (Quote non ancora visibili)"

            if is_over:
                signal_header = "🟢 **CONSIGLIATO: OVER 18.5 PUNTI**"
                advice = "🎯 **Suggerimento:** GIOCA OVER 18.5"
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
