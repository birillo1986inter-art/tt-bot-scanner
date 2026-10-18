import os
import re
import time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URLS_TARGET = [
    "https://it.bsportsfan.com/table-tennis/l/22534/tt-cup-ukraine",
    "https://www.24live.space/",
    "https://www.betmonitor.com/"
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
    print("Avvio scansione con sblocco Cloudflare simulato...")
    all_matches = []

    try:
        with sync_playwright() as p:
            # Usiamo un browser configurato per sembrare un utente reale al 100%
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process'
                ]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale="it-IT",
                timezone_id="Europe/Rome",
                permissions=["geolocation"]
            )
            
            page = context.new_page()
            
            # Rimozione totale delle tracce di automazione WebDriver
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.navigator.chrome = {
                    runtime: {}
                };
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['it-IT', 'it', 'en-US', 'en']
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)

            for url in URLS_TARGET:
                try:
                    print(f"Accesso a {url}...")
                    page.goto(url, timeout=50000, wait_until="domcontentloaded")
                    
                    # Simuliamo movimenti del mouse e interazioni umane per superare Cloudflare
                    for _ in range(3):
                        page.mouse.move(100 + (_ * 50), 200 + (_ * 30))
                        page.wait_for_timeout(1000)
                    
                    # Attesa attiva finché la schermata di verifica Cloudflare scompare
                    max_wait = 40
                    waited = 0
                    while waited < max_wait:
                        content = page.content()
                        if "Esecuzione della verifica di sicurezza" not in content and "Ray ID" not in content and "Verifica in corso" not in content:
                            print(f"Sito {url} sbloccato correttamente!")
                            break
                        print("In attesa dello sblocco Cloudflare...")
                        page.mouse.click(500, 500)  # Simula il click sulla pagina
                        time.sleep(4)
                        waited += 4
                    
                    page.wait_for_timeout(4000)
                    html_content = page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    elements = soup.find_all(['tr', 'div', 'li', 'a'])
                    for el in elements:
                        text = el.get_text(separator=" ", strip=True)
                        if (" - " in text or " vs " in text or " v " in text) and len(text) > 8 and len(text) < 120:
                            clean_text = " ".join(text.split())
                            if not any(kw in clean_text.lower() for kw in ["privacy", "cookie", "terms", "home", "login", "register", "download", "app"]):
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
                    print(f"Errore sul sito {url}: {site_e}")

            browser.close()

    except Exception as e:
        print(f"Errore critico del browser: {e}")

    if not all_matches:
        print("Nessun match pre-match rilevato al momento.")
        return

    print(f"Trovati {len(all_matches)} match pre-match.")

    for m in all_matches[:12]:
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
            f"🌐 **Fonte:** `{m['source']}`\n"
            f"⚔️ **Match:** {m['match']}\n"
            f"📊 **Quote:** {odds_str}\n"
            f"{advice}"
        )
        send_telegram(msg)

if __name__ == "__main__":
    run()
