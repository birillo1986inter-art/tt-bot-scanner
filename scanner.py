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
    print("Avvio scansione totale di tutti i match e quote...")
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
        
        ignore_list = [
            "english", "čeština", "rights", "reserved", "version", "cookie", "privacy", 
            "about", "menu", "home", "away", "login", "register", "all", "terms"
        ]

        # Cerchiamo le righe con le quote e risaliamo ai nomi dei giocatori
        for i, line in enumerate(lines):
            odds = re.findall(r'\b[12]\.\d{2}\b', line)
            if odds and i > 0:
                for j in range(max(0, i-3), i):
                    candidate = lines[j]
                    if " - " in candidate or " vs " in candidate.lower():
                        parts = re.split(r'\s+-\s+|\s+vs\s+', candidate, flags=re.IGNORECASE)
                        if len(parts) == 2:
                            p1, p2 = parts[0].strip(), parts[1].strip()
                            combined = (p1 + " " + p2).lower()
                            
                            if not any(ig in combined for ig in ignore_list) and len(p1) >= 3 and len(p2) >= 3:
                                match_name = f"{p1} - {p2}"
                                
                                all_odds_near = re.findall(r'\b[12]\.\d{2}\b', " ".join(lines[max(0, j-1):min(len(lines), j+6)]))
                                
                                o1 = float(all_odds_near[0]) if len(all_odds_near) >= 1 else None
                                o2 = float(all_odds_near[1]) if len(all_odds_near) >= 2 else None
                                
                                m_data = {
                                    "match": match_name,
                                    "odds1": o1,
                                    "odds2": o2
                                }
                                
                                if not any(m["match"] == m_data["match"] for m in matches):
                                    matches.append(m_data)

        if not matches:
            send_telegram("ℹ️ **Scanner Totale**: Nessun match rilevato in questo momento.")
            return

        # Inviamo i primi 5 match trovati con qualsiasi quota
        for m in matches[:5]:
            o1_str = f"`{m['odds1']:.2f}`" if m['odds1'] else "N/D"
            o2_str = f"`{m['odds2']:.2f}`" if m['odds2'] else "N/D"
            
            msg = (
                f"📊 **MATCH RILEVATO (Tutte le quote)**\n\n"
                f"⚔️ **Match:** {m['match']}\n"
                f"📈 **Quote:** 1: {o1_str} | 2: {o2_str}"
            )
            send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Errore nello scanner: `{e}`")

if __name__ == "__main__":
    run()
