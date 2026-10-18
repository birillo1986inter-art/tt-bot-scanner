import os
import re
import time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_TARGET = "https://it.bsportsfan.com/table-tennis/l/22534/tt-cup-ukraine"

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
    print("Avvio scansione con Stealth & Cloudflare Bypass...")
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
            
            # Applichiamo le contromisure stealth anti-rilevamento bot
            stealth_sync(page)
            
            print(f"Navigazione verso {URL_TARGET}...")
            page.goto(URL_TARGET, timeout=60000, wait_until="domcontentloaded")
            
            # Controllo dinamico: attendiamo finché Cloudflare scompare o passano max 30 secondi
            max_wait = 30
            waited = 0
            while waited < max_wait:
                content = page.content()
                if "Esecuzione della verifica di sicurezza" not in content and "Ray ID" not in content:
                    print("Verifica Cloudflare superata con successo!")
                    break
                print("In attesa che Cloudflare completi il controllo...")
                time.sleep(3)
                waited += 3
            
            # Breve pausa di stabilizzazione contenuti
            page.wait_for_timeout(3000)
            html_content = page.content()
            browser.close()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        full_text = soup.get_text(separator="\n")
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        
        matches = []
        for i, line in enumerate(lines):
            if (" - " in line or " vs " in line or " v " in line) and len(line) > 5 and len(line) < 100:
                if not any(kw in line.lower() for kw in ["bsportsfan", "privacy", "cookie", "terms", "home", "sport", "ray id", "verifica"]):
                    nearby_odds = []
                    for j in range(max(0, i-2), min(len(lines), i+5)):
                        found = re.findall(r'\b[1-9]\.\d{2}\b', lines[j])
                        nearby_odds.extend(found)
                    
                    o1 = float(nearby_odds[0]) if len(nearby_odds) >= 1 else None
                    o2 = float(nearby_odds[1]) if len(nearby_odds) >= 2 else None
                    
                    m_data = {
                        "match": line,
                        "odds1": o1,
                        "odds2": o2,
                        "has_odds": (o1 is not None and o2 is not None)
                    }
                    if m_data not in matches:
                        matches.append(m_data)

        if not matches:
            send_telegram("ℹ️ **Palinsesto TT Cup**: Superata la verifica Cloudflare, ma non ci sono match attivi in questo momento esatto.")
            return

        send_telegram(f"🔍 **TT Cup Scanner**: Verifiche superate! Trovati **{len(matches)}** match.")

        for m in matches[:12]:
            if m["has_odds"]:
                diff = abs(m["odds1"] - m["odds2"])
                is_over = (diff <= 0.30) and (1.65 <= m["odds1"] <= 2.15) and (1.65 <= m["odds2"] <= 2.15)
                odds_str = f"1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)"
            else:
                is_over = False
                odds_str = "Quote in caricamento"

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
        send_telegram(f"❌ Errore critico nello script: `{e}`")

if __name__ == "__main__":
    run()
