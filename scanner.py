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
    print("Avvio scansione avanzata tabelle BsportsFan...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                locale="it-IT"
            )
            page = context.new_page()
            
            # Usiamo domcontentloaded per evitare blocchi dovuti al traffico continuo in background
            page.goto(URL_TARGET, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)  # Pausa per dare tempo agli script di popolare la pagina
            
            html_content = page.content()
            browser.close()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        matches = []
        
        # Cerca tutte le righe delle tabelle della pagina
        rows = soup.find_all('tr')
        for row in rows:
            text = row.get_text(separator=" ", strip=True)
            
            if re.search(r'\b(v|vs|-)\b', text, re.IGNORECASE) and len(text) > 8:
                odds = re.findall(r'\b[1-9]\.\d{2}\b', text)
                
                if len(odds) >= 2:
                    try:
                        o1 = float(odds[0])
                        o2 = float(odds[1])
                        
                        clean_text = " ".join(text.split())
                        m_data = {"match": clean_text[:80], "odds1": o1, "odds2": o2}
                        if m_data not in matches:
                            matches.append(m_data)
                    except ValueError:
                        pass

        # Fallback generico sul testo se le tabelle non bastano
        if not matches:
            text_lines = [l.strip() for l in soup.get_text(separator="\n").split('\n') if l.strip()]
            for i, line in enumerate(text_lines):
                if (" v " in line.lower() or " vs " in line.lower()) and len(line) < 70:
                    nearby_odds = []
                    for j in range(max(0, i-2), min(len(text_lines), i+5)):
                        found = re.findall(r'\b[1-9]\.\d{2}\b', text_lines[j])
                        nearby_odds.extend(found)
                    if len(nearby_odds) >= 2:
                        try:
                            o1, o2 = float(nearby_odds[0]), float(nearby_odds[1])
                            m_data = {"match": line, "odds1": o1, "odds2": o2}
                            if m_data not in matches:
                                matches.append(m_data)
                        except ValueError:
                            pass

        if not matches:
            send_telegram("ℹ️ **Scanner Playwright**: Connessione OK, ma nessun match attivo rilevato nelle tabelle BsportsFan in questo momento.")
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
