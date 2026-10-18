import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_TARGET = "http://ttcup.com/schedule/"

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
    print(f"Avvio scansione ufficiale su {URL_TARGET}...")
    matches = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale="it-IT"
            )
            page = context.new_page()
            
            # Navigazione diretta al sito ufficiale senza Cloudflare
            page.goto(URL_TARGET, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000) # Attesa caricamento elementi JS del palinsesto
            
            html_content = page.content()
            browser.close()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Estraiamo righe, tabelle e blocchi di incontro dal palinsesto ufficiale
        elements = soup.find_all(['tr', 'div', 'li', 'a'])
        for el in elements:
            text = el.get_text(separator=" ", strip=True)
            
            # Identifichiamo le righe dei match (es. presenza di nomi giocatori separati da trattino o vs)
            if (" - " in text or " vs " in text or " v " in text) and len(text) > 6 and len(text) < 120:
                clean_text = " ".join(text.split())
                
                # Escludiamo intestazioni, menu o testi non inerenti alle partite
                if not any(kw in clean_text.lower() for kw in ["schedule", "results", "live", "login", "cookie", "privacy", "home"]):
                    
                    # Cerchiamo eventuali quote presenti nel blocco
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
            send_telegram("ℹ️ **TT Cup Official**: Pagina aperta con successo, ma nessun incontro rilevato nel palinsesto in questo momento.")
            return

        send_telegram(f"🔍 **TT Cup Official**: Trovati **{len(matches)}** match nel palinsesto ufficiale!")

        # Invio delle notifiche per i match trovati (limite a 15)
        for m in matches[:15]:
            if m["has_odds"]:
                diff = abs(m["odds1"] - m["odds2"])
                is_over = (diff <= 0.30) and (1.65 <= m["odds1"] <= 2.15) and (1.65 <= m["odds2"] <= 2.15)
                odds_str = f"1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)"
            else:
                is_over = False
                odds_str = "Pre-match ufficiale"

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
        send_telegram(f"❌ Errore scanner ufficiale: `{e}`")

if __name__ == "__main__":
    run()
