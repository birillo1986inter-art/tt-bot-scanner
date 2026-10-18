import os
import re
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

URL_TARGET = "https://24live.com/page/sport/event/table-tennis-22/22339;sid=70504?lang=en"

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
    print("Avvio scansione di controllo...")
    matches = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                locale="en-US"
            )
            page = context.new_page()
            
            page.goto(URL_TARGET, timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(8000)
            
            content_text = page.inner_text("body")
            browser.close()

        lines = [line.strip() for line in content_text.split('\n') if line.strip()]
        
        ignore_list = [
            "english", "čeština", "rights", "reserved", "version", "cookie", "privacy", 
            "about", "menu", "home", "away", "login", "register", "all", "terms"
        ]

        # Cerchiamo qualsiasi riga che contenga un trattino o i nomi dei giocatori vicino alle quote
        for i, line in enumerate(lines):
            # Cerca pattern di quote decimali nella riga o nelle immediate vicinanze
            odds = re.findall(r'\b[12]\.\d{2}\b', line)
            if odds and i > 0:
                # Esaminiamo le righe sopra per trovare i nomi dei giocatori
                for j in range(max(0, i-3), i):
                    candidate = lines[j]
                    if " - " in candidate or " vs " in candidate.lower():
                        parts = re.split(r'\s+-\s+|\s+vs\s+', candidate, flags=re.IGNORECASE)
                        if len(parts) == 2:
                            p1, p2 = parts[0].strip(), parts[1].strip()
                            combined = (p1 + " " + p2).lower()
                            
                            if not any(ig in combined for ig in ignore_list) and len(p1) >= 3 and len(p2) >= 3:
                                match_name = f"{p1} - {p2}"
                                
                                # Preleviamo le prime due quote trovate nel blocco
                                all_odds_near = re.findall(r'\b[12]\.\d{2}\b', " ".join(lines[max(0, j-1):min(len(lines), j+6)]))
                                if len(all_odds_near) >= 2:
                                    try:
                                        o1 = float(all_odds_near[0])
                                        o2 = float(all_odds_near[1])
                                        
                                        m_data = {
                                            "match": match_name,
                                            "odds1": o1,
                                            "odds2": o2
                                        }
                                        
                                        if not any(m["match"] == m_data["match"] for m in matches):
                                            matches.append(m_data)
                                    except ValueError:
                                        pass

        signals_found = 0
        signal_messages = []

        for m in matches:
            o1, o2 = m["odds1"], m["odds2"]
            diff = abs(o1 - o2)
            
            # Condizione rigorosa Over 18.5
            is_over = (diff <= 0.30) and (1.65 <= o1 <= 2.15) and (1.65 <= o2 <= 2.15)

            if is_over:
                signals_found += 1
                msg = (
                    f"🟢 **SEGNALE OVER 18.5 PUNTI**\n\n"
                    f"⚔️ **Match:** {m['match']}\n"
                    f"📊 **Quote:** 1: `{o1:.2f}` | 2: `{o2:.2f}` (Diff: `{diff:.2f}`)\n\n"
                    f"🎯 **Consiglio:** GIOCA OVER 18.5"
                )
                signal_messages.append(msg)

        # Invio dei segnali trovati
        if signal_messages:
            for sm in signal_messages:
                send_telegram(sm)
        else:
            # Mandiamo un singolo messaggio di test per confermare che lo script gira
            # (Lo puoi rimuovere in seguito quando sei sicuro che arrivano i segnali)
            send_telegram("🤖 **Scanner 24live attivo**: Controllo eseguito. Nessun match rispetta i criteri Over 18.5 in questo istante.")

    except Exception as e:
        send_telegram(f"❌ Errore nello scanner: `{e}`")

if __name__ == "__main__":
    run()
