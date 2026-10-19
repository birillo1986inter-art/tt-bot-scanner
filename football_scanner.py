import os
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY')

API_HOST = "v3.football.api-sports.io"
HEADERS_API = {
    'x-rapidapi-host': API_HOST,
    'x-rapidapi-key': FOOTBALL_API_KEY
}

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Mancano i parametri Telegram")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def get_today_fixtures():
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://{API_HOST}/fixtures?date={today}"
    try:
        response = requests.get(url, headers=HEADERS_API, timeout=15)
        data = response.json()
        return data.get("response", [])
    except Exception as e:
        print(f"Errore recupero partite API: {e}")
        return []

def analyze_match(fixture):
    teams = fixture.get("teams", {})
    home = teams.get("home", {}).get("name", "Home")
    away = teams.get("away", {}).get("name", "Away")
    league_info = fixture.get("league", {})
    league = league_info.get("name", "Campionato")
    country = league_info.get("country", "")
    match_time = fixture.get("fixture", {}).get("date", "")[11:16]
    
    predictions = [
        "⚽ Over 0.5 Primo Tempo",
        "🎯 MultiGol 2-4"
    ]
    
    return {
        "time": match_time,
        "league": f"{country} - {league}",
        "home": home,
        "away": away,
        "predictions": predictions
    }

def run():
    print("Avvio scansione Calcio completa...")
    
    if not FOOTBALL_API_KEY:
        print("Errore: FOOTBALL_API_KEY non configurata nei Secrets.")
        return

    fixtures = get_today_fixtures()
    today_str = datetime.now().strftime("%d/%m/%Y")

    if fixtures:
        analyzed_matches = []
        for f in fixtures:
            match_data = analyze_match(f)
            analyzed_matches.append(match_data)
        
        # Prende fino a 30 partite della giornata
        analyzed_matches = analyzed_matches[:30]
        
        header_msg = f"⚽ **PALINSESTO CALCIO - PRONOSTICI TOP**\n📅 *Data: {today_str}*\nAnalizzate **{len(analyzed_matches)} partite in programma**:"
        send_telegram(header_msg)
        
        for m in analyzed_matches:
            preds_formatted = "\n".join([f"  • {p}" for p in m['predictions']])
            msg = (
                f"🕒 `{m['time']}` | 🏆 *{m['league']}*\n"
                f"⚔️ **{m['home']} vs {m['away']}**\n"
                f"📊 **Pronostici Consigliati:**\n{preds_formatted}"
            )
            send_telegram(msg)
    else:
        msg = f"⚽ **PALINSESTO CALCIO**\n📅 *Data: {today_str}*\n\nNessuna partita trovata per la giornata odierna."
        send_telegram(msg)

if __name__ == "__main__":
    run()
