import os
import re
import requests
from bs4نهار import BeautifulSoup
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_BETMONITOR = "https://www.betmonitor.com/mobile/odds-comparison/table-tennis/ukraine-tt-cup/10007095"
URL_BETMONITOR_ALT = "https://www.betmonitor.com/odds-comparison/tabletennis/today"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def parse_betmonitor():
    valid_matches = []
    try:
        response = requests.get(URL_BETMONITOR, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            response = requests.get(URL_BETMONITOR_ALT, headers=HEADERS, timeout=15)
            
        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = soup.get_text(separator="\n")
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        for i, line in enumerate(lines):
            if " — " in line or " vs " in line.lower() or " - " in line:
                parts = re.split(r'\s+[—\-vs]+\s+', line, flags=re.IGNORECASE)
                if len(parts) == 2:
                    p1, p2 = parts[0].strip(), parts[1].strip()
                    if len(p1) >= 3 and len(p2) >= 3 and not any(w in (p1+p2).lower() for w in ["league", "table", "tennis", "cup", "odds"]):
                        match_name = f"{p1} - {p2}"
                        
                        context_window = " ".join(lines[max(0, i-3):min(len(lines), i+8)])
                        time_match = re.search(r'\b\d{2}:\d{2}\b', context_window)
                        match_time = time_match.group(0) if time_match else "Live"
                        
                        odds = re.findall(r'\b[12]\.\d{2}\b', context_window)
                        o1 = float(odds[0]) if len(odds) >= 1 else None
                        o2 = float(odds[1]) if len(odds) >= 2 else None
                        
                        if o1 is not None and o2 is not None:
                            diff = abs(o1 - o2)
                            # Filtri Over 18.5
                            is_over = (diff <= 0.30) and (1.65 <= o1 <= 2.15) and (1.65 <= o2 <= 2.15)
                            
                            if is_over:
                                match_item = {
                                    "time": match_time,
                                    "match": match_name,
                                    "odds1": o1,
                                    "odds2": o2,
                                    "diff": diff
                                }
                                if match_item not in valid_matches:
                                    valid_matches.append(match_item)
    except Exception as e:
        print(f"Errore lettura Betmonitor: {e}")
        
    return valid_matches

def run():
    print("Generazione palinsesto giornaliero Over 18.5...")
    matches = parse_betmonitor()
    
    today_str = datetime.now().strftime("%d/%m/%Y")
    
    if matches:
        msg = f"📋 **PALINSESTO TT CUP - OVER 18.5**\n📅 *Data: {today_str}*\n\n"
        msg += f"Ho trovato **{len(matches)} match** ideali per oggi:\n\n"
        
        for m in matches:
            msg += (
                f"🕒 `{m['time']}` | ⚔️ **{m['match']}**\n"
                f"📊 Quote: 1: `{m['odds1']:.2f}` | 2: `{m['odds2']:.2f}` (Diff: `{m['diff']:.2f}`)\n"
                f"──────────────────\n"
            )
        msg += f"\n🎯 *Buona fortuna con le giocate di oggi!*"
    else:
        msg = f"📋 **PALINSESTO TT CUP - OVER 18.5**\n📅 *Data: {today_str}*\n\nNessun match rispetta i criteri rigidi al momento della scansione."
        
    send_telegram(msg)

if __name__ == "__main__":
    run()
