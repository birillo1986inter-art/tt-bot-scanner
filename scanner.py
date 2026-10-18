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
    print("Avvio scansione con filtro rigoroso sui nomi...")
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
        
        # Estraiamo tutti i testi possibili dai tag di testo dei match (spans, divs)
        elements = soup.find_all(['div', 'span', 'a', 'p'])
        texts = [el.get_text().strip() for el in elements if el.get_text().strip()]

        # Parole bloccate tassativamente (footer, menu, interfaccia)
        blocklist = [
            "rights", "reserved", "version", "cookie", "privacy", "about", "home", 
            "menu", "sport", "live", "schedule", "results", "login", "register", 
            "search", "odds", "settings", "terms", "contact", "download", "app"
        ]

        # Cerchiamo coppie di stringhe che sembrano nomi di giocatori (es. Cognome N. o Nome Cognome)
        i = 0
        while i < len(texts) - 1:
            t1 = texts[i]
            t2 = texts[i+1]
            
            t1_l, t2_l = t1.lower(), t2.lower()
            
            # Condizioni rigide: devono sembrare due atleti distinti senza parole di sistema
            is_garbage = any(b in t1_l or b in t2_l for b in blocklist)
            is_valid_length = (3 <= len(t1) <= 30) and (3 <= len(t2) <= 30)
            has_letters = any(c.isalpha() for c in t1) and any(c.isalpha() for c in t2)
            
            if not is_garbage and is_valid_length and has_letters and t1 != t2:
                # Se la struttura somiglia a un match
                match_name = f"{t1} - {t2}"
                
                # Cerchiamo se ci sono quote decimali vicine nel raggio di 5 elementi
                nearby_text = " ".join(texts[max(0, i-2):min(len(texts), i+6)])
                odds = re.findall(r'\b[1-9]\.\d{2}\b', nearby_text)
                
                o1 = float(odds[0]) if len(odds) >= 1 else None
                o2 = float(odds[1]) if len(odds) >= 2 else None
                
                m_data = {
                    "match": match_name,
                    "odds1": o1,
                    "odds2": o2,
                    "has_odds": (o1 is not None and o2 is not None)
                }
                
                # Evitiamo duplicati evidenti
                if not any(m["match"] == m_data["match"] for m in matches):
                    matches.append(m_data)
            i += 1

        if not matches:
            print("Nessun match valido trovato in questo ciclo.")
            return

        # Limitiamo l'invio ai primi 5 match reali trovati per evitare spam
        for m in matches[:5]:
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
