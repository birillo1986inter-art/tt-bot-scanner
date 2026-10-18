import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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
    print("Avvio scansione profonda BsportsFan...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                locale="it-IT"
            )
            page = context.new_page()
            
            page.goto(URL_TARGET, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(6000) # Attendiamo il rendering completo
            
            html_content = page.content()
            browser.close()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        matches = []
        
        # Estraiamo tutti i blocchi potenziali (righe, div, elementi di lista)
        elements = soup.find_all(['tr', 'div', 'li'])
        for el in elements:
            text = el.get_text(separator=" ", strip=True)
            
            # Cerchiamo pattern che indicano un match (presenza di trattini o "vs")
            if ((" - " in text or " vs " in text or " v " in text) and len(text) > 6 and len(text) < 150):
                # Cerchiamo se ci sono quote decimali (es. 1.85, 2.10) nello stesso blocco o vicine
                odds = re.findall(r'\b[1-9]\.\d{2}\b', text)
                
                if len(odds) >= 2:
                    try:
                        o1 = float(odds[0])
                        o2 = float(odds[1])
                        
                        clean_match = " ".join(text.split())
                        # Filtriamo eventuali stringhe spazzatura del menu o intestazioni
                        if "cookie" not in clean_match.lower() and "privacy" not in clean_match.lower():
                            m_data = {"match": clean_match[:80], "odds1": o1, "odds2": o2}
                            if m_data not in matches:
                                matches.append(m_data)
                    except ValueError:
                        pass

        if not matches:
            send_telegram("ℹ️ **Scanner Playwright**: Pagina caricata correttamente. Nessun match attivo con quote rilevato in questo momento.")
            return

        for m in matches:
            diff = abs(m["odds1"] - m["odds2"])
            is_over_recommended = (diff <= 0.30) and (1.65 <= m["odds1"] <= 2.15) and (1.65 <= m["odds2"] <= 2.15)
            
            if is_over_recommended:
                signal_header = "🟢 **CONSIGLIATO: OVER 18.5 PUNTI**"
                advice = "🎯 **Suggerimento:** GIOCA OVER 18.5 (Match equilibrato)"
            else:
                signal_header = "⚪ **MATCH IN PALINSESTO**"
                advice = "⚠️ **Suggerimento:** PASS (Match sbilanciato)"

            msg = (
                f"{signal_header}\n\n"
                f"⚔️ **Match:** {m['match']}\n"
                f"📊 **Quote:** 1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)\n"
                f"{advice}"
            )
            send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Errore critico con Playwright: `{e}`")

if __name__ == "__main__":
    run()
