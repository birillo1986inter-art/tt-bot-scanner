import os
import re
import requests
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_24LIVE = "https://24live.com/page/sport/match-list/table-tennis-22"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://24live.com/"
}

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ATTENZIONE: Credenziali Telegram mancanti!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore Telegram: {e}")

def run():
    print("Avvio scansione 24live per Tennistavolo...")
    try:
        response = requests.get(URL_24LIVE, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            send_telegram(f"⚠️ **Attenzione**: 24live ha risposto con codice HTTP `{response.status_code}`.")
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Estraiamo tutti i testi possibili dai blocchi della pagina
        elements = soup.find_all(['div', 'span', 'a', 'p'])
        texts = [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]
        
        matches = []
        
        # Cerchiamo riferimenti alla TT Cup e ai match
        for i, text in enumerate(texts):
            if "tt cup" in text.lower() or "ukraine" in text.lower() or "-" in text or "—" in text:
                # Vediamo se nelle vicinanze ci sono quote o nomi di giocatori
                if len(text) > 6 and len(text) < 100:
                    # Cerchiamo numeri decimali che assomigliano a quote
                    nearby_text = " ".join(texts[max(0, i-3):min(len(texts), i+4)])
                    odds = re.findall(r'\b[1-9]\.\d{2}\b', nearby_text)
                    
                    if len(odds) >= 2:
                        try:
                            o1 = float(odds[0])
                            o2 = float(odds[1])
                            match_name = text.replace("—", "vs").replace("-", "vs")
                            
                            match_data = {"match": match_name, "odds1": o1, "odds2": o2}
                            if match_data not in matches:
                                matches.append(match_data)
                        except ValueError:
                            pass

        if not matches:
            # Fallback: inviamo un messaggio di stato se non trova match specifici con quote
            send_telegram("ℹ️ **Scansione 24live completata**: Nessun match con quote attive rilevato in questo momento.")
            return

        # Invia tutte le partite trovate
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
        send_telegram(f"❌ **Errore durante lo script 24live**: `{e}`")

if __name__ == "__main__":
    run()
