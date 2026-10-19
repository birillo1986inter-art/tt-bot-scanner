import os
import re
import requests
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# URL Betmonitor specifico per la TT Cup Ucraina
URL_BETMONITOR = "https://www.betmonitor.com/mobile/odds-comparison/table-tennis/ukraine-tt-cup/10007095"
URL_BETMONITOR_ALT = "https://www.betmonitor.com/odds-comparison/tabletennis/today"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
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

def parse_betmonitor():
    matches = []
    try:
        response = requests.get(URL_BETMONITOR, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            response = requests.get(URL_BETMONITOR_ALT, headers=HEADERS, timeout=15)
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Betmonitor organizza i match in righe o blocchi puliti
        text_content = soup.get_text(separator="\n")
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        for i, line in enumerate(lines):
            # Cerca separatori di partita tra due tennisti (es. "Player A — Player B" o "Player A vs Player B")
            if " — " in line or " vs " in line.lower() or " - " in line:
                parts = re.split(r'\s+[—\-vs]+\s+', line, flags=re.IGNORECASE)
                if len(parts) == 2:
                    p1, p2 = parts[0].strip(), parts[1].strip()
                    
                    # Filtra voci generali del sito
                    if len(p1) >= 3 and len(p2) >= 3 and not any(w in (p1+p2).lower() for w in ["league", "table", "tennis", "cup", "odds"]):
                        match_name = f"{p1} - {p2}"
                        
                        # Recupera orario e quote nelle righe vicine
                        context_window = " ".join(lines[max(0, i-3):min(len(lines), i+8)])
                        
                        # Cerca l'orario (es. 14:30)
                        time_match = re.search(r'\b\d{2}:\d{2}\b', context_window)
                        match_time = time_match.group(0) if time_match else "In corso / Oramai"
                        
                        # Cerca quote decimali (es. 1.85, 1.90)
                        odds = re.findall(r'\b[12]\.\d{2}\b', context_window)
                        
                        o1 = float(odds[0]) if len(odds) >= 1 else None
                        o2 = float(odds[1]) if len(odds) >= 2 else None
                        
                        m_data = {
                            "time": match_time,
                            "match": match_name,
                            "odds1": o1,
                            "odds2": o2,
                            "has_odds": (o1 is not None and o2 is not None)
                        }
                        
                        if not any(m["match"] == m_data["match"] for m in matches):
                            matches.append(m_data)
    except Exception as e:
        print(f"Errore lettura Betmonitor: {e}")
        
    return matches

def run():
    print("Avvio scansione diretta su Betmonitor...")
    matches = parse_betmonitor()

    if not matches:
        send_telegram("ℹ️ **Scanner Betmonitor**: Collegamento riuscito! Nessun match TT Cup attivo in questo istante.")
        return

    over_signals = 0

    for m in matches:
        if m["has_odds"]:
            o1, o2 = m["odds1"], m["odds2"]
            diff = abs(o1 - o2)
            
            # Criteri rigidi Over 18.5 (Quota tra 1.65 e 2.15, scarto <= 0.30)
            is_over = (diff <= 0.30) and (1.65 <= o1 <= 2.15) and (1.65 <= o2 <= 2.15)
            
            if is_over:
                over_signals += 1
                msg = (
                    f"🟢 **SEGNALE OVER 18.5 PUNTI**\n\n"
                    f"🕒 **Orario:** {m['time']}\n"
                    f"⚔️ **Match:** {m['match']}\n"
                    f"📊 **Quote:** 1: `{o1:.2f}` | 2: `{o2:.2f}` (Diff: `{diff:.2f}`)\n\n"
                    f"🎯 **Consiglio:** GIOCA OVER 18.5 PUNTI"
                )
                send_telegram(msg)

    # Se ci sono match ma nessuno rispetta i criteri dell'Over 18.5
    if over_signals == 0:
        send_telegram(f"🤖 **Scanner Betmonitor**: Trovati **{len(matches)}** match in palinsesto, ma nessuno rispetta i parametri Over 18.5 al momento.")

if __name__ == "__main__":
    run()
