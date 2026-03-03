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

# ================== TELEGRAM HELPERS ==================

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erreur envoi : {e}")

def answer_callback(callback_query_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_query_id}, timeout=5)

def main_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "📰 Actu Marché",    "callback_data": "/actu"},
                {"text": "🏆 Top 5 Actions",  "callback_data": "/top"}
            ],
            [
                {"text": "🥇 Analyse Gold",   "callback_data": "/gold"},
                {"text": "🔷 Analyse ETH",    "callback_data": "/eth"}
            ],
            [
                {"text": "📊 RSI BTC",        "callback_data": "/rsi btc"},
                {"text": "📊 RSI ETH",        "callback_data": "/rsi eth"}
            ],
            [
                {"text": "📊 RSI Gold",       "callback_data": "/rsi gold"},
                {"text": "📊 RSI S&P500",     "callback_data": "/rsi sp500"}
            ],
            [
                {"text": "❓ Aide",           "callback_data": "/help"}
            ]
        ]
    }

# ================== DONNEES MARCHE ==================

def get_news():
    articles = []
    url = "https://newsapi.org/v2/top-headlines"
    r = requests.get(url, params={"apiKey": NEWSAPI_KEY, "pageSize": 10, "category": "business", "language": "en"}, timeout=10)
    if r.status_code == 200:
        articles.extend(r.json().get("articles", []))
    r = requests.get(url, params={"apiKey": NEWSAPI_KEY, "pageSize": 10, "category": "general", "language": "fr", "country": "fr"}, timeout=10)
    if r.status_code == 200:
        articles.extend(r.json().get("articles", []))
    return [
        f"- {a['title']} : {a.get('description', '')[:150]}..."
        for a in articles[:12] if a.get("title") and a.get("description")
    ]

def get_market_data():
    data = yf.download(TICKERS, period="2d", interval="1d", progress=False)["Close"]
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
        chg = float(change_pct[t])
        emoji = "🟢" if chg >= 0 else "🔴"
        lines.append(f"{emoji} *{name}*: {float(latest[t]):,.2f} ({chg:+.2f}%)")
    return "\n".join(lines)

def get_top5():
    stock_tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD", "NFLX", "ORCL"]
    data = yf.download(stock_tickers, period="2d", interval="1d", progress=False)["Close"]
    change_pct = data.pct_change().iloc[-1] * 100
    latest = data.iloc[-1]
    sorted_tickers = change_pct.dropna().sort_values(ascending=False)
    lines = ["🏆 *TOP 5 ACTIONS DU JOUR*\n"]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, (ticker, chg) in enumerate(sorted_tickers.head(5).items()):
        lines.append(f"{medals[i]} *{ticker}*: {float(latest[ticker]):,.2f} ({float(chg):+.2f}%)")
    lines.append("\n📉 *FLOP 3 DU JOUR*")
    for ticker, chg in sorted_tickers.tail(3).iloc[::-1].items():
        lines.append(f"🔴 *{ticker}*: {float(latest[ticker]):,.2f} ({float(chg):+.2f}%)")
    return "\n".join(lines)

def get_asset_data(ticker, period="5d"):
    data = yf.download(ticker, period=period, interval="1d", progress=False)["Close"]
    data = data.dropna()
    prices = [float(v) for v in data.values.flatten() if str(v) != 'nan']
    return prices

def compute_rsi(ticker, period=14):
    data = yf.download(ticker, period="60d", interval="1d", auto_adjust=True, progress=False)
    if data.empty:
        return None
    # Fix yfinance multi-index : aplatir les colonnes
    close = data["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    close = pd.Series([float(v) for v in close.values.flatten()], index=close.index).dropna()
    if len(close) < period:
        return None
    delta = close.diff()
    avg_gain = delta.clip(lower=0).rolling(window=period).mean()
    avg_loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    last_rsi = float(rsi.iloc[-1])
    return None if pd.isna(last_rsi) else last_rsi

# ================== IA ==================

def call_groq(prompt, max_tokens=1100, temperature=0.4):
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def generate_summary(news_list, market_str):
    today = datetime.now().strftime('%d/%m/%Y')
    prompt = f"""Tu es un analyste financier senior.
Aujourd'hui le {today}

ACTUALITES :
{chr(10).join(news_list)}

MARCHES :
{market_str}

Reponds en francais avec emojis, format telephone :

*RESUME DES ACTUS* (6-8 points cles)
*DIRECTION DES MARCHES*
-> Chaque actif : direction + probabilite % + explication courte
*CONCLUSION* : Tendance generale + probabilite

Maximum 3500 caracteres."""
    return call_groq(prompt, max_tokens=1100)

def generate_trade_signal(asset_name, ticker, news_list):
    prices = get_asset_data(ticker)
    if len(prices) < 2:
        return "Donnees insuffisantes."
    price_current = prices[-1]
    change_pct = ((price_current - prices[-2]) / prices[-2]) * 100
    sma = sum(prices) / len(prices)
    today = datetime.now().strftime('%d/%m/%Y %H:%M')
    prompt = f"""Tu es un trader professionnel.
{today} — Actif : {asset_name}
Prix : {price_current:,.2f} | Variation : {change_pct:+.2f}%
Prix 5j : {', '.join([f'{p:,.2f}' for p in prices])}
SMA 5j : {sma:,.2f} | Position : {'au-dessus' if price_current > sma else 'en-dessous'}

ACTUALITES : {chr(10).join(news_list[:6])}

Format telephone avec emojis :
*SIGNAL* : BUY 🟢 ou SHORT 🔴
*CONVICTION* : XX%
*TECHNIQUE* : 2 lignes
*FONDAMENTAL* : 2 lignes
*OBJECTIF* : prix cible
*STOP LOSS* : niveau
*CONCLUSION* : 1 phrase

Max 1200 caracteres."""
    return call_groq(prompt, max_tokens=600, temperature=0.3)

# ================== COMMANDES ==================

def cmd_start(chat_id):
    msg = (
        "👋 *Bienvenue sur ton Assistant Marché !*\n\n"
        "📅 Chaque matin à *8h00*, tu recevras automatiquement\n"
        "un résumé complet des marchés financiers.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 *COMMANDES DISPONIBLES*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📰 `/actu` — Résumé marché + actualités\n"
        "🏆 `/top` — Top 5 & Flop 3 actions du jour\n"
        "🥇 `/gold` — Signal BUY/SHORT sur l'Or\n"
        "🔷 `/eth` — Signal BUY/SHORT sur Ethereum\n"
        "📊 `/rsi btc` — RSI Bitcoin\n"
        "📊 `/rsi eth` — RSI Ethereum\n"
        "📊 `/rsi gold` — RSI Or\n"
        "📊 `/rsi sp500` — RSI S&P 500\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⬇️ *Utilise le menu rapide ci-dessous :*"
    )
    send_message(chat_id, msg, reply_markup=main_menu())

def cmd_help(chat_id):
    send_message(chat_id, "📋 *Que veux-tu analyser ?*", reply_markup=main_menu())

def cmd_actu(chat_id):
    send_message(chat_id, "⏳ *Récupération des données...*\nAnalyse en cours (~30s) ☕")
    news = get_news()
    market = get_market_data()
    summary = generate_summary(news, market)
    send_message(chat_id, f"📊 *RÉSUMÉ MARCHÉ — {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n{summary}")
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu())

def cmd_top(chat_id):
    send_message(chat_id, "⏳ *Chargement du classement...*")
    send_message(chat_id, get_top5())
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu())

def cmd_gold(chat_id):
    send_message(chat_id, "⏳ *Analyse Or en cours...*")
    news = get_news()
    signal = generate_trade_signal("OR (GOLD)", "GC=F", news)
    send_message(chat_id, f"🥇 *ANALYSE GOLD — {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n{signal}")
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu())

def cmd_eth(chat_id):
    send_message(chat_id, "⏳ *Analyse Ethereum en cours...*")
    news = get_news()
    signal = generate_trade_signal("Ethereum (ETH)", "ETH-USD", news)
    send_message(chat_id, f"🔷 *ANALYSE ETH — {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n{signal}")
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu())

def cmd_rsi(chat_id, asset_key):
    mapping = {
        "btc":   ("BTC-USD", "Bitcoin (BTC)"),
        "eth":   ("ETH-USD", "Ethereum (ETH)"),
        "gold":  ("GC=F",    "Or (GOLD)"),
        "sp500": ("^GSPC",   "S&P 500"),
    }
    ticker, name = mapping.get(asset_key, ("ETH-USD", "Ethereum (ETH)"))
    send_message(chat_id, f"⏳ *Calcul RSI pour {name}...*")
    try:
        rsi_value = compute_rsi(ticker)
        if rsi_value is None:
            send_message(chat_id, "❌ Données insuffisantes.")
            return
        if rsi_value < 30:
            zone = "🟢 SURVENTE — Zone potentiellement *haussière*"
            conseil = "Signal d'achat possible, prudence tout de même"
            bar = "🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜"
        elif rsi_value > 70:
            zone = "🔴 SURACHAT — Zone potentiellement *baissière*"
            conseil = "Risque de retournement, éviter d'acheter"
            bar = "🟩🟩🟩🟩🟩🟩🟩🟥🟥🟥"
        else:
            zone = "⚪ NEUTRE — Pas de signal fort"
            conseil = "Attendre une sortie de zone (< 30 ou > 70)"
            bar = "🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜"
        msg = (
            f"📊 *RSI (14) — {name}*\n\n"
            f"{bar}\n"
            f"Valeur : *{rsi_value:.1f} / 100*\n\n"
            f"Zone : {zone}\n"
            f"💡 _{conseil}_\n\n"
            f"_RSI < 30 = survente | RSI > 70 = surachat_"
        )
        send_message(chat_id, msg)
    except Exception as e:
        print(e)
        send_message(chat_id, "❌ Erreur lors du calcul du RSI.")
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu())

# ================== ENVOI AUTO 8H ==================

auto_sent_today = None

def check_auto_send():
    global auto_sent_today
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    if now.hour == 8 and now.minute == 0 and auto_sent_today != today:
        auto_sent_today = today
        print("Envoi automatique 8h...")
        try:
            send_message(TELEGRAM_CHAT_ID, "🌅 *Bonjour ! Voici ton résumé marché du matin.*")
            news = get_news()
            market = get_market_data()
            summary = generate_summary(news, market)
            send_message(TELEGRAM_CHAT_ID, f"📊 *RÉSUMÉ MARCHÉ — {now.strftime('%d/%m/%Y')}*\n\n{summary}")
            send_message(TELEGRAM_CHAT_ID, "🔄 *Menu rapide :*", reply_markup=main_menu())
            print("Envoi auto 8h OK !")
        except Exception as e:
            print(f"Erreur envoi auto : {e}")

# ================== ROUTING ==================

def handle_command(chat_id, text):
    text = text.strip().lower()
    if text == "/start":
        cmd_start(chat_id)
    elif text == "/help":
        cmd_help(chat_id)
    elif text == "/actu":
        cmd_actu(chat_id)
    elif text == "/top":
        cmd_top(chat_id)
    elif text == "/gold":
        cmd_gold(chat_id)
    elif text == "/eth":
        cmd_eth(chat_id)
    elif text.startswith("/rsi"):
        parts = text.split()
        cmd_rsi(chat_id, parts[1] if len(parts) > 1 else "eth")
    else:
        send_message(chat_id, "❓ Commande inconnue.", reply_markup=main_menu())

# ================== BOUCLE PRINCIPALE ==================

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

print("Bot demarre !")
print("Commandes : /start | /actu | /top | /gold | /eth | /rsi")
print("Envoi automatique chaque jour a 8h00")

offset = None
while True:
    try:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "callback_query" in update:
                cq = update["callback_query"]
                answer_callback(cq["id"])
                chat_id = cq["message"]["chat"]["id"]
                print(f"Bouton : {cq['data']}")
                handle_command(chat_id, cq["data"])
            elif "message" in update:
                msg = update["message"]
                text = msg.get("text", "")
                chat_id = msg["chat"]["id"]
                if text:
                    print(f"Message : {text}")
                    handle_command(chat_id, text)
        check_auto_send()
        time.sleep(1)
    except Exception as e:
        print(f"Erreur : {e}")
        time.sleep(5)
