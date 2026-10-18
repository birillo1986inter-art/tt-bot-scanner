import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_TARGET = "https://www.24live.com/table-tennis"

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
    print(f"Avvio scansione Pre-Match su {URL_TARGET}...")
    matches = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--window-size=1920,1080'
                ]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale="it-IT"
            )
            
            page = context.new_page()
            
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            print("Caricamento pagina 24live...")
            page.goto(URL_TARGET, timeout=50000, wait_until="networkidle")
            page.wait_for_timeout(6000) # Attesa rendering widget e quote 24live
            
            html_content = page.content()
            browser.close()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Scansione di elementi e righe di partita
        elements = soup.find_all(['tr', 'div', 'li', 'a'])
        for el in elements:
            text = el.get_text(separator=" ", strip=True)
            
            # Cerca incontri con trattino o vs tipici di TT Cup / Tennistavolo
            if (" - " in text or " vs " in text or " v " in text) and len(text) > 8 and len(text) < 120:
                clean_text = " ".join(text.split())
                
                # Filtra parole chiave di sistema o menu
                if not any(kw in clean_text.lower() for kw in ["privacy", "cookie", "terms", "home", "login", "register", "download", "app", "24live"]):
                    
                    # Estrazione quote decimali (es. 1.85, 1.90)
                    odds = re.findall(r'\b[1-9]\.\d{2}\b', clean_text)
                    o1 = float(odds[0]) if len(odds) >= 1 else None
                    o2 = float(odds[1]) if len(odds) >= 2 else None
                    
                    m_data = {
                        "match": clean_text[:90],
                        "odds1": o1,
                        "odds2": o2,
                        "has_odds": (o1 is not None and o2 is not None)
                    }
                    
                    if not any(m["match"] == m_data["match"] for m in matches):
                        matches.append(m_data)

        if not matches:
            full_text = soup.get_text(separator="\n")
            sample = "\n".join([line.strip() for line in full_text.split('\n') if line.strip()][:25])[:350]
            send_telegram(f"ℹ️ **24live Scanner**: Nessun match intercettato dai filtri.\n\n**Testo rilevato:**\n`{sample}`")
            return

        send_telegram(f"🔍 **24live Scanner**: Trovati **{len(matches)}** incontri pre-match!")

        # Invio risultati su Telegram
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
                signal_header = "⚪ **PRE-MATCH IN PALINSESTO**"
                advice = "⚠️ **Suggerimento:** PASS"

            msg = (
                f"{signal_header}\n\n"
                f"⚔️ **Match:** {m['match']}\n"
                f"📊 **Quote:** {odds_str}\n"
                f"{advice}"
            )
            send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Errore critico su 24live: `{e}`")

if __name__ == "__main__":
    run()
