import os
import requests
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_BETMONITOR = "https://www.betmonitor.com/mobile/odds-comparison/table-tennis/ukraine-tt-cup/10007095"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore Telegram: {e}")

def run():
    print("Avvio scansione automatica senza filtri...")
    try:
        response = requests.get(URL_BETMONITOR, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        content_text = soup.get_text()
        lines = [line.strip() for line in content_text.split('\n') if line.strip()]
        
        matches = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if "—" in line or "-" in line or " - " in line:
                if len(line) > 5 and "Betmonitor" not in line:
                    players = line.replace("—", "vs").replace("-", "vs")
                    odds1, odds2 = None, None
                    for j in range(i + 1, min(i + 12, len(lines))):
                        try:
                            num = float(lines[j].split('/')[0])
                            if 1.01 <= num <= 10.00:
                                if not odds1:
                                    odds1 = num
                                elif not odds2 and num != odds1:
                                    odds2 = num
                        except ValueError:
                            pass
                    if odds1 and odds2:
                        matches.append({"match": players, "odds1": odds1, "odds2": odds2})
            i += 1
            
        # Invia TUTTE le partite trovate senza alcun filtro su quote/differenziale
        for m in matches:
            diff = abs(m["odds1"] - m["odds2"])
            msg = (
                f"🏓 **MATCH TT CUP** 🏓\n\n"
                f"⚔️ **Match:** {m['match']}\n"
                f"📊 **Quote:** 1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{diff:.2f}`)\n"
                f"🎯 **Info:** Notifica inviata senza filtri di quota."
            )
            send_telegram(msg)
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    run()
