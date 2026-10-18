import os
import re
import requests
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
    print("Avvio ricerca pronostici Over 18.5...")
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
            
            content_text = page.inner_text("body")
            browser.close()

        lines = [line.strip() for line in content_text.split('\n') if line.strip()]
        
        # Parole da ignorare categoricamente
        ignore_list = [
            "english", "čeština", "rights", "reserved", "version", "cookie", "privacy", 
            "about", "menu", "home", "away", "login", "register", "all", "terms"
        ]

        i = 0
        while i < len(lines) - 2:
            line = lines[i]
            # Identifica gli orari del match (es. 14:30)
            if re.match(r'^\d{2}:\d{2}$', line):
                p1 = lines[i+1]
                p2 = lines[i+2]
                
                combined = (p1 + " " + p2).lower()
                if not any(ig in combined for ig in ignore_list) and len(p1) >= 3 and len(p2) >= 3:
                    # Estrae le quote adiacenti
                    chunk = " ".join(lines[max(0, i-1):min(len(lines), i+8)])
                    odds = re.findall(r'\b[12]\.\d{2}\b', chunk)
                    
                    if len(odds) >= 2:
                        o1 = float(odds[0])
                        o2 = float(odds[1])
                        
                        m_data = {
                            "time": line,
                            "match": f"{p1} - {p2}",
                            "odds1": o1,
                            "odds2": o2
                        }
                        
                        if not any(m["match"] == m_data["match"] for m in matches):
                            matches.append(m_data)
            i += 1

        signals_found = 0

        for m in matches:
            o1, o2 = m["odds1"], m["odds2"]
            diff = abs(o1 - o2)
            
            # Condizione vincolante per l'OVER 18.5
            is_over = (diff <= 0.30) and (1.65 <= o1 <= 2.15) and (1.65 <= o2 <= 2.15)

            # INVIA IL MESSAGGIO SOLO SE È UN PRONOSTICO OVER 18.5 VALIDO
            if is_over:
                signals_found += 1
                msg = (
                    f"🟢 **SEGNALE OVER 18.5 PUNTI**\n\n"
                    f"🕒 **Orario:** {m['time']}\n"
                    f"⚔️ **Match:** {m['match']}\n"
                    f"📊 **Quote:** 1: `{o1:.2f}` | 2: `{o2:.2f}` (Diff: `{diff:.2f}`)\n\n"
                    f"🎯 **Consiglio:** GIOCA OVER 18.5 PUNTI"
                )
                send_telegram(msg)

        if signals_found == 0:
            print("Nessun match al momento rispetta i criteri dell'Over 18.5.")

    except Exception as e:
        print(f"Errore nello scanner: {e}")

if __name__ == "__main__":
    run()
