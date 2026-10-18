import os
import re
import requests
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_TARGET = "https://24live.com/page/sport/match-list/table-tennis-22"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

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
    print("Avvio scansione...")
    try:
        response = requests.get(URL_TARGET, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            send_telegram(f"⚠️ Errore di connessione al sito (Codice: {response.status_code})")
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = soup.get_text(separator="\n")
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        matches = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Cerca righe che sembrano match (es. presenza di trattini o indicatori)
            if "-" in line or "—" in line:
                if len(line) > 6 and "24live" not in line.lower():
                    # Cerca quote nei dintorni
                    nearby_odds = []
                    for j in range(max(0, i-2), min(len(lines), i+8)):
                        found = re.findall(r'\b[1-9]\.\d{2}\b', lines[j])
                        nearby_odds.extend(found)
                    
                    if len(nearby_odds) >= 2:
                        try:
                            o1 = float(nearby_odds[0])
                            o2 = float(nearby_odds[1])
                            match_name = line.replace("—", "vs").replace("-", "vs")
                            m_data = {"match": match_name, "odds1": o1, "odds2": o2}
                            if m_data not in matches:
                                matches.append(m_data)
                        except ValueError:
                            pass
            i += 1

        if not matches:
            send_telegram("ℹ️ **Scansione completata**: Connessione riuscita, ma nessun match con quote attive trovato in questo momento nel palinsesto.")
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
        send_telegram(f"❌ Errore critico nello script: `{e}`")

if __name__ == "__main__":
    run()
