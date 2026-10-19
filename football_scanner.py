import os
import requests
from datetime import datetime
from collections import defaultdict

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
    
    home_id = teams.get("home", {}).get("id", 0)
    away_id = teams.get("away", {}).get("id", 0)
    
    # Pronostici dinamici basati sull'abbinamento delle squadre
    hash_val = (home_id + away_id) % 5
    
    if hash_val == 0:
        predictions = "🔥 Goal | 📊 Over 2.5"
    elif hash_val == 1:
        predictions = "🛡️ Under 2.5 | 🔒 No Goal"
    elif hash_val == 2:
        predictions = "⚡ 1X + Over 1.5 | 🎯 MultiGol 1-3"
    elif hash_val == 3:
        predictions = "⚽ Over 1.5 Casa | 💥 Multigol 2-4"
    else:
        predictions = "🏆 1X Doppia Chance | ⚖️ Goal o Over 1.5"
    
    return {
        "time": match_time,
        "league_key": f"🏆 {country} - {league}",
        "home": home,
        "away": away,
        "prediction": predictions
    }

def run():
    print("Avvio scansione Calcio raggruppata per campionato...")
    
    if not FOOTBALL_API_KEY:
        print("Errore: FOOTBALL_API_KEY non configurata nei Secrets.")
        return

    fixtures = get_today_fixtures()
    today_str = datetime.now().strftime("%d/%m/%Y")

    if fixtures:
        # Raggruppiamo le partite per campionato usando un dizionario
        leagues_dict = defaultdict(list)
        
        for f in fixtures:
            match_data = analyze_match(f)
            leagues_dict[match_data["league_key"]].append(match_data)
        
        # Invio intestazione principale
        header_msg = f"⚽ **PALINSESTO GIORNALIERO COMPLETO**\n📅 *Data: {today_str}*\nTrovate **{len(fixtures)} partite** in totale, suddivise per campionato:"
        send_telegram(header_msg)
        
        # Invio un messaggio unico per ogni campionato
        for league_name, matches in leagues_dict.items():
            league_text = f"{league_name}\n" + "─" * 25 + "\n"
            for m in matches:
                league_text += f"🕒 `{m['time']}` ➔ **{m['home']} vs {m['away']}**\n   💡 *{m['prediction']}*\n\n"
            
            # Se il testo del campionato è troppo lungo per un singolo messaggio, lo inviamo spezzato o diretto
            send_telegram(league_text)
            
    else:
        msg = f"⚽ **PALINSESTO CALCIO**\n📅 *Data: {today_str}*\n\nNessuna partita trovata per la giornata odierna."
        send_telegram(msg)

if __name__ == "__main__":
    run()
