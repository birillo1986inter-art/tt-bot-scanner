import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_BASE = "https://it.bsportsfan.com"
URL_TARGET = f"{URL_BASE}/table-tennis/l/22534/tt-cup-ukraine"

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
    print("Avvio scansione profonda TT Cup...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                locale="it-IT"
            )
            page = context.new_page()
            
            # Step 1: Apri la pagina della lega
            page.goto(URL_TARGET, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            
            soup = BeautifulSoup(page.content(), 'html.parser')
            
            # Cerca tutti i link dei match della TT Cup (/r/XXXXX)
            links = soup.find_all('a', href=re.compile(r'/r/\d+'))
            match_list = []
            
            for link in links:
                text = link.get_text(strip=True)
                href = link.get('href')
                if (" v " in text.lower() or " vs " in text.lower()) and href:
                    full_url = URL_BASE + href if href.startswith('/') else href
                    if not any(m['url'] == full_url for m in match_list):
                        match_list.append({"match": text, "url": full_url})

            if not match_list:
                send_telegram("ℹ️ **TT Cup Scanner**: Nessun match programmato o in corso trovato al momento nel palinsesto.")
                browser.close()
                return

            results = []
            # Step 2: Apri i primi 5 match per estrarre le quote reali dalla scheda interna
            for item in match_list[:5]:
                try:
                    page.goto(item['url'], timeout=20000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                    detail_soup = BeautifulSoup(page.content(), 'html.parser')
                    
                    # Estrai quote decimali presenti nella scheda del match
                    text_detail = detail_soup.get_text(separator=" ")
                    odds = re.findall(r'\b[1-9]\.\d{2}\b', text_detail)
                    
                    if len(odds) >= 2:
                        o1, o2 = float(odds[0]), float(odds[1])
                    else:
                        o1, o2 = 1.85, 1.85  # Quota neutra standard se non visibili
                    
                    results.append({
                        "match": item['match'],
                        "odds1": o1,
                        "odds2": o2,
                        "has_odds": len(odds) >= 2
                    })
                except Exception as inner_e:
                    print(f"Errore lettura match {item['match']}: {inner_e}")
            
            browser.close()

        # Step 3: Elabora i dati e invia i segnali Telegram
        for m in results:
            diff = abs(m["odds1"] - m["odds2"])
            is_over = m["has_odds"] and (diff <= 0.30) and (1.65 <= m["odds1"] <= 2.15) and (1.65 <= m["odds2"] <= 2.15)
            
            if is_over:
                signal_header = "🟢 **CONSIGLIATO: OVER 18.5 PUNTI**"
                advice = "🎯 **Suggerimento:** GIOCA OVER 18.5 (Match equilibrato)"
            else:
                signal_header = "⚪ **MATCH IN PALINSESTO**"
                advice = "⚠️ **Suggerimento:** PASS (Quote non bilanciate o standard)"

            odds_str = f"1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)" if m["has_odds"] else "Quote in aggiornamento"

            msg = (
                f"{signal_header}\n\n"
                f"⚔️ **Match:** {m['match']}\n"
                f"📊 **Quote:** {odds_str}\n"
                f"{advice}"
            )
            send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Errore nello scanner: `{e}`")

if __name__ == "__main__":
    run()
