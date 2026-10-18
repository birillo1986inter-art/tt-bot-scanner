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
    print(f"Avvio scansione con blocco menu e filtri rigidi...")
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
            
            page.goto(URL_TARGET, timeout=50000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            
            html_content = page.content()
            browser.close()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        full_text = soup.get_text(separator="\n")
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        
        # Lista nera tassativa per cancellare ogni voce di menu o interfaccia di 24live
        forbidden = [
            "about us", "notification", "center", "menu", "home", "away", "table", 
            "cookie", "privacy", "sport", "all", "live", "schedule", "results", 
            "login", "register", "search", "odds", "settings", "terms", "contact",
            "download", "app", "help", "support", "statistics", "standings"
        ]

        i = 0
        while i < len(lines) - 2:
            current_line = lines[i]
            
            # Individua l'inizio di un match (orari es. 12:30 o "Not started")
            if "Not started" in current_line or re.search(r'\d{2}:\d{2}', current_line):
                if i + 2 < len(lines):
                    p1 = lines[i+1]
                    p2 = lines[i+2]
                    
                    p1_low, p2_low = p1.lower(), p2.lower()
                    
                    # Se anche solo uno dei due nomi contiene parole di menu, scartalo subito
                    if any(bad in p1_low for bad in forbidden) or any(bad in p2_low for bad in forbidden):
                        i += 1
                        continue
                    
                    # Un nome di tennistavolo ha una lunghezza sensata e non è un comando di sistema
                    if len(p1) < 4 or len(p2) < 4 or len(p1) > 35 or len(p2) > 35:
                        i += 1
                        continue
                        
                    match_name = f"{p1} - {p2}"
                    
                    # Cerca quote decimali valide (es. 1.85) nelle vicinanze
                    nearby_odds = []
                    for k in range(i, min(i + 10, len(lines))):
                        found = re.findall(r'\b[1-9]\.\d{2}\b', lines[k])
                        nearby_odds.extend(found)
                    
                    o1 = float(nearby_odds[0]) if len(nearby_odds) >= 1 else None
                    o2 = float(nearby_odds[1]) if len(nearby_odds) >= 2 else None
                    
                    m_data = {
                        "match": match_name,
                        "odds1": o1,
                        "odds2": o2,
                        "has_odds": (o1 is not None and o2 is not None)
                    }
                    
                    if not any(m["match"] == m_data["match"] for m in matches):
                        matches.append(m_data)
            i += 1

        if not matches:
            # Se non ci sono match puliti, non intasiamo Telegram con falsi positivi
            print("Nessun match valido trovato in questo ciclo.")
            return

        send_telegram(f"🔍 **24live Prono**: Trovati **{len(matches)}** match reali!")

        for m in matches[:12]:
            if m["has_odds"]:
                diff = abs(m["odds1"] - m["odds2"])
                is_over = (diff <= 0.30) and (1.65 <= m["odds1"] <= 2.15) and (1.65 <= m["odds2"] <= 2.15)
                odds_str = f"1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)"
            else:
                is_over = False
                odds_str = "Pre-match (Quote in attesa)"

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
        send_telegram(f"❌ Errore script 24live: `{e}`")

if __name__ == "__main__":
    run()
