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
    print("Avvio scansione approfondita Pre-Match TT Cup Ukraine...")
    matches = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                locale="it-IT"
            )
            page = context.new_page()
            
            # Apertura pagina principale della lega
            page.goto(URL_TARGET, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            
            soup = BeautifulSoup(page.content(), 'html.parser')
            
            # Cerca tutte le righe della tabella o blocchi contenenti gli incontri pre-match
            rows = soup.find_all('tr') + soup.find_all('div', class_=re.compile(r'match|event|row', re.I))
            
            for row in rows:
                text = row.get_text(separator=" ", strip=True)
                
                # Identifica se la riga contiene una partita (presenza di " v ", " vs " o "-")
                if re.search(r'\b(v|vs|-)\b', text, re.IGNORECASE) and len(text) > 8:
                    # Estrai quote decimali presenti nella riga (es. 1.85, 1.90)
                    odds = re.findall(r'\b[1-9]\.\d{2}\b', text)
                    
                    # Pulizia nome partita
                    clean_text = " ".join(text.split())
                    
                    # Escludi parole chiave non inerenti
                    if not any(kw in clean_text.lower() for kw in ["bsportsfan", "privacy", "cookie", "terms", "league"]):
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

            # Se con il primo metodo trova pochi elementi, cerca tutti i link dei match (/r/XXXXX)
            if len(matches) < 2:
                links = soup.find_all('a', href=re.compile(r'/r/\d+'))
                for link in links:
                    t = link.get_text(strip=True)
                    if re.search(r'\b(v|vs|-)\b', t, re.IGNORECASE):
                        parent = link.find_parent(['tr', 'div', 'td'])
                        p_text = parent.get_text(separator=" ", strip=True) if parent else t
                        odds = re.findall(r'\b[1-9]\.\d{2}\b', p_text)
                        
                        o1 = float(odds[0]) if len(odds) >= 1 else None
                        o2 = float(odds[1]) if len(odds) >= 2 else None
                        
                        m_data = {
                            "match": t,
                            "odds1": o1,
                            "odds2": o2,
                            "has_odds": (o1 is not None and o2 is not None)
                        }
                        if not any(m["match"] == m_data["match"] for m in matches):
                            matches.append(m_data)

            browser.close()

    except Exception as e:
        print(f"Errore durante l'esecuzione del browser: {e}")

    if not matches:
        send_telegram("ℹ️ **TT Cup Scanner**: Nessuna partita pre-match trovata nella pagina. Verifica che la struttura della pagina non sia cambiata.")
        return

    # Notifica quanti match pre-match sono stati rilevati
    send_telegram(f"🔍 **TT Cup Scanner**: Trovate **{len(matches)}** partite Pre-Match in palinsesto.")

    # Invia dettagli per ciascuna partita trovata (max 15 per evitare limiti Telegram)
    for m in matches[:15]:
        if m["has_odds"]:
            diff = abs(m["odds1"] - m["odds2"])
            is_over = (diff <= 0.30) and (1.65 <= m["odds1"] <= 2.15) and (1.65 <= m["odds2"] <= 2.15)
            odds_str = f"1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)"
        else:
            is_over = False
            odds_str = "Quote Pre-Match in aggiornamento"

        if is_over:
            signal_header = "🟢 **CONSIGLIATO: OVER 18.5 PUNTI**"
            advice = "🎯 **Suggerimento:** GIOCA OVER 18.5 (Match equilibrato)"
        else:
            signal_header = "⚪ **PRE-MATCH IN PALINSESTO**"
            advice = "⚠️ **Suggerimento:** PASS (Quote non bilanciate o standard)"

        msg = (
            f"{signal_header}\n\n"
            f"⚔️ **Match:** {m['match']}\n"
            f"📊 **Quote:** {odds_str}\n"
            f"{advice}"
        )
        send_telegram(msg)

if __name__ == "__main__":
    run()
