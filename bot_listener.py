import os
import requests
import yfinance as yf
from openai import OpenAI
from datetime import datetime
import time
import pandas as pd

os.environ["PYTHONIOENCODING"] = "utf-8"

# ================== CONFIG ==================
NEWSAPI_KEY      = os.getenv("NEWSAPI_KEY")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

GROQ_MODEL = "llama-3.3-70b-versatile"
TICKERS = ["BTC-USD", "ETH-USD", "GC=F", "^GSPC", "^DJI", "^IXIC", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

# ================== FONCTIONS MARCHÉ ==================

def get_news():
    articles = []
    url = "https://newsapi.org/v2/top-headlines"
    r = requests.get(url, params={"apiKey": NEWSAPI_KEY, "pageSize": 10, "category": "business", "language": "en"})
    if r.status_code == 200:
        articles.extend(r.json().get("articles", []))
    r = requests.get(url, params={"apiKey": NEWSAPI_KEY, "pageSize": 10, "category": "general", "language": "fr", "country": "fr"})
    if r.status_code == 200:
        articles.extend(r.json().get("articles", []))
    return [
        f"- {a['title']} : {a.get('description', '')[:150]}..."
        for a in articles[:12] if a.get("title") and a.get("description")
    ]

def get_market_data():
    data = yf.download(TICKERS, period="2d", interval="1d")["Close"]
    latest = data.iloc[-1]
    change_pct = data.pct_change().iloc[-1] * 100
    mapping = {
        "BTC-USD": "Bitcoin (BTC)", "ETH-USD": "Ethereum (ETH)", "GC=F": "Or (GOLD)",
        "^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "Nasdaq",
        "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia",
        "TSLA": "Tesla", "AMZN": "Amazon"
    }
    lines = []
    for t in TICKERS:
        name = mapping.get(t, t)
        lines.append(f"{name}: {latest[t]:,.2f} ({change_pct[t]:+.2f}%)")
    return "\n".join(lines)

def generate_summary(news_list, market_str):
    news_text = "\n".join(news_list)
    today = datetime.now().strftime('%d/%m/%Y')
    prompt = f"""Tu es un analyste financier senior ultra-objectif.
Aujourd'hui le {today}

ACTUALITES :
{news_text}

MARCHES AUJOURD'HUI :
{market_str}

Reponds en francais, format clair pour telephone :

**RESUME GLOBAL DES ACTUS** (6-8 points cles)
**DIRECTION DES MARCHES** (BTC, ETH, GOLD, S&P 500, Nasdaq, Apple, Nvidia, Tesla)
-> Direction + probabilite % + explication courte
**CONCLUSION** : Tendance generale + probabilite globale

Maximum 3800 caracteres."""

    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1100
    )
    return response.choices[0].message.content

def get_asset_data(ticker, period="5d"):
    data = yf.download(ticker, period=period, interval="1d")["Close"]
    data = data.dropna()
    # Aplatir les valeurs en float simples (fix yfinance multi-index)
    prices = [float(v) for v in data.values.flatten() if str(v) != 'nan']
    dates = [str(d.date()) for d in data.index]
    return prices, dates

def compute_rsi(ticker, period=14):
    data = yf.download(ticker, period="60d", interval="1d", auto_adjust=True)

    if data.empty:
        return None

    close = data["Close"].dropna()

    if len(close) < period:
        return None

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    last_rsi = rsi.iloc[-1]

    if pd.isna(last_rsi):
        return None

    return float(last_rsi)

def generate_trade_signal(asset_name, ticker, news_list):
    prices, dates = get_asset_data(ticker)
    if len(prices) < 2:
        return "Donnees insuffisantes pour l'analyse."

    price_current = prices[-1]
    price_yesterday = prices[-2]
    change_pct = ((price_current - price_yesterday) / price_yesterday) * 100

    # Calcul SMA simple
    sma = sum(prices) / len(prices)
    trend = "au-dessus" if price_current > sma else "en-dessous"

    news_text = "\n".join(news_list[:8])
    today = datetime.now().strftime('%d/%m/%Y %H:%M')

    prompt = f"""Tu es un trader professionnel et analyste technique senior.
Aujourd'hui le {today}

ACTIF : {asset_name}
Prix actuel : {price_current:,.2f}
Variation aujourd'hui : {change_pct:+.2f}%
Prix sur 5 jours : {', '.join([f'{p:,.2f}' for p in prices])}
Moyenne 5j (SMA) : {sma:,.2f}
Position vs SMA : {trend} de la moyenne

ACTUALITES DU MOMENT :
{news_text}

Reponds UNIQUEMENT en francais, format court pour telephone :

**SIGNAL** : BUY ou SHORT (choix tranché, pas de "neutre")
**CONVICTION** : XX% (ta confiance dans ce signal)
**ANALYSE TECHNIQUE** : 2-3 lignes max
**ANALYSE FONDAMENTALE** : 2-3 lignes max (contexte macro/news)
**OBJECTIF DE PRIX** : cible si le signal se confirme
**STOP LOSS** : niveau de prix pour couper la position
**CONCLUSION** : 1 phrase claire

Sois direct et tranche. Maximum 1500 caracteres."""

    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=600
    )
    return response.choices[0].message.content

def send_to_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)

# ================== POLLING TELEGRAM ==================

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=35)
        return r.json().get("result", [])
    except:
        return []

def handle_command(chat_id, text):
    text = text.strip().lower()

    if text == "/actu" or text.startswith("/actu"):
        send_to_telegram(chat_id, "Analyse en cours, patiente 30 secondes...")
        print(f"Commande /actu recue, generation du resume...")
        news = get_news()
        market = get_market_data()
        summary = generate_summary(news, market)
        message = f"Resume Marche - {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n{summary}"
        send_to_telegram(chat_id, message)
        print("Resume envoye !")

    elif text == "/gold":
        send_to_telegram(chat_id, "Analyse Gold en cours... 30 secondes ⏳")
        print("Commande /gold recue...")
        news = get_news()
        signal = generate_trade_signal("OR (GOLD)", "GC=F", news)
        message = f"Analyse GOLD - {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n{signal}"
        send_to_telegram(chat_id, message)
        print("Analyse Gold envoyee !")

    elif text == "/eth":
        send_to_telegram(chat_id, "Analyse Ethereum en cours... 30 secondes ⏳")
        print("Commande /eth recue...")
        news = get_news()
        signal = generate_trade_signal("Ethereum (ETH)", "ETH-USD", news)
        message = f"Analyse ETH - {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n{signal}"
        send_to_telegram(chat_id, message)
        print("Analyse ETH envoyee !")
    elif text.startswith("/rsi"):
        parts = text.split()

        # Actif par défaut
        ticker = "ETH-USD"
        asset_name = "Ethereum (ETH)"

        if len(parts) > 1:
            if parts[1] == "btc":
                ticker = "BTC-USD"
                asset_name = "Bitcoin (BTC)"
            elif parts[1] == "gold":
                ticker = "GC=F"
                asset_name = "OR (GOLD)"
            elif parts[1] == "sp500":
                ticker = "^GSPC"
                asset_name = "S&P 500"

        send_to_telegram(chat_id, f"Calcul RSI en cours pour {asset_name}...")

        try:
            rsi_value = compute_rsi(ticker)

            if rsi_value is None:
                send_to_telegram(chat_id, "Donnees insuffisantes pour calculer le RSI.")
                return

            if rsi_value < 30:
                zone = "SURVENTE (zone potentiellement haussiere)"
            elif rsi_value > 70:
                zone = "SURACHAT (zone potentiellement baissiere)"
            else:
                zone = "NEUTRE"

            message = (
                f"RSI (14) - {asset_name}\n\n"
                f"Valeur actuelle : {rsi_value:.2f}\n"
                f"Zone : {zone}"
            )

            send_to_telegram(chat_id, message)

        except Exception as e:
            print(e)
            send_to_telegram(chat_id, "Erreur lors du calcul du RSI.")

    elif text == "/start" or text == "/help":
        send_to_telegram(chat_id,
            "Bonjour ! Voici les commandes disponibles :\n\n"
            "/actu - Resume marche + actualites du jour\n"
            "/gold - Signal BUY/SHORT sur l'Or\n"
            "/eth - Signal BUY/SHORT sur Ethereum\n"
            "/rsi - RSI Ethereum\n"
            "/rsi btc - RSI Bitcoin\n"
            "/rsi gold - RSI Or\n"
            "/rsi sp500 - RSI S&P 500\n"
            "/help - Affiche ce message"
        )

    else:
        send_to_telegram(chat_id, "Commande inconnue. Tape /help pour voir les commandes.")

# ================== BOUCLE PRINCIPALE ==================

print("Bot demarre ! En attente de commandes...")
print("Commandes disponibles : /actu | /gold | /eth | /help")
print("(Ctrl+C pour arreter)")

offset = None
while True:
    updates = get_updates(offset)
    for update in updates:
        offset = update["update_id"] + 1
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        if text and chat_id:
            print(f"Message recu : {text}")
            handle_command(chat_id, text)
    time.sleep(1)
