import os
import re
import time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# I tre siti di riferimento per il palinsesto e i pre-match
URLS_TARGET = [
    "https://it.bsportsfan.com/table-tennis/l/22534/tt-cup-ukraine",
    "https://www.24live.space/table-tennis/", # Sezione tennis tavolo live/pre-match
    "https://www.betmonitor.com/"            # Monitoraggio quote e palinsesti
]

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
    print("Avvio scansione multi-fonte Pre-Match (Bsport, 24live, Betmonitor)...")
    all_matches = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-size=1920,1080'
                ]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale="it-IT",
                timezone_id="Europe/Rome"
            )
            
            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            for url in URLS_TARGET:
                try:
                    print(f"Scansione in corso su: {url}")
                    page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    page.wait_for_timeout(5000)
                    
                    html_content = page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Estrazione generica ma mirata per identificare i match e le quote pre-match
                    rows = soup.find_all(['tr', 'div', 'li'])
                    for row in rows:
                        text = row.get_text(separator=" ", strip=True)
                        
                        # Filtriamo per individuare sfide di TT Cup o incontri con "v", "vs", "-"
                        if (" - " in text or " vs " in text or " v " in text) and len(text) > 8 and len(text) < 130:
                            # Cerchiamo riferimenti alla TT Cup o al tennistavolo nelle vicinanze o nel testo
                            clean_text = " ".join(text.split())
                            
                            if not any(kw in clean_text.lower() for kw in ["privacy", "cookie", "terms", "home", "login", "register"]):
                                odds = re.findall(r'\b[1-9]\.\d{2}\b', clean_text)
                                
                                o1 = float(odds[0]) if len(odds) >= 1 else None
                                o2 = float(odds[1]) if len(odds) >= 2 else None
                                
                                m_data = {
                                    "source": url.split('/')[2],
                                    "match": clean_text[:90],
                                    "odds1": o1,
                                    "odds2": o2,
                                    "has_odds": (o1 is not None and o2 is not None)
                                }
                                
                                if not any(m["match"] == m_data["match"] for m in all_matches):
                                    all_matches.append(m_data)
                except Exception as site_e:
                    print(f"Errore durante la scansione di {url}: {site_e}")

            browser.close()

    except Exception as e:
        print(f"Errore critico browser: {e}")

    if not all_matches:
        send_telegram("ℹ️ **Scanner Multi-Fonte**: Nessun incontro pre-match rilevato al momento sulle piattaforme monitorate.")
        return

    send_telegram(f"🔍 **Scanner Multi-Fonte**: Trovati complessivamente **{len(all_matches)}** match pre-match!")

    # Inviamo i match trovati (limite a 15 per evitare spam su Telegram)
    for m in all_matches[:15]:
        if m["has_odds"]:
            diff = abs(m["odds1"] - m["odds2"])
            is_over = (diff <= 0.30) and (1.65 <= m["odds1"] <= 2.15) and (1.65 <= m["odds2"] <= 2.15)
            odds_str = f"1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)"
        else:
            is_over = False
            odds_str = "Quote in arrivo (Pre-match)"

        if is_over:
            signal_header = "🟢 **CONSIGLIATO: OVER 18.5 PUNTI**"
            advice = "🎯 **Suggerimento:** GIOCA OVER 18.5 (Match equilibrato)"
        else:
            signal_header = "⚪ **PRE-MATCH IN PALINSESTO**"
            advice = "⚠️ **Suggerimento:** PASS"

        msg = (
            f"{signal_header}\n\n"
            f"🌐 **Fonte:** `{m['source']}`\n"
            f"⚔️ **Match:** {m['match']}\n"
            f"📊 **Quote:** {odds_str}\n"
            f"{advice}"
        )
        send_telegram(msg)

if __name__ == "__main__":
    run()
