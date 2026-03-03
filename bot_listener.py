import os
import requests
import yfinance as yf
from openai import OpenAI
from datetime import datetime, timedelta
import time
import pandas as pd
import json

os.environ["PYTHONIOENCODING"] = "utf-8"

# ================== CONFIG ==================
NEWSAPI_KEY      = os.getenv("NEWSAPI_KEY")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Ton propre chat_id = ADMIN

GROQ_MODEL = "llama-3.3-70b-versatile"
TICKERS = ["BTC-USD", "ETH-USD", "GC=F", "^GSPC", "^DJI", "^IXIC", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

# Lien de paiement (mets ton lien Stripe / PayPal / SumUp ici)
PAYMENT_LINK = "https://buy.stripe.com/ton_lien_ici"
PRIX_MENSUEL = "9.99€"
PRIX_ANNUEL  = "79.99€"

USERS_FILE = "users.json"

# ================== GESTION ABONNEMENTS ==================

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def is_admin(chat_id):
    return str(chat_id) == str(TELEGRAM_CHAT_ID)

def get_user(chat_id):
    users = load_users()
    return users.get(str(chat_id), {"plan": "free", "expiry": None, "name": "Inconnu"})

def is_premium(chat_id):
    if is_admin(chat_id):
        return True
    user = get_user(chat_id)
    if user["plan"] == "premium":
        if user["expiry"] is None:
            return True
        expiry = datetime.strptime(user["expiry"], "%Y-%m-%d")
        return datetime.now() < expiry
    return False

def add_premium(chat_id, name, days):
    users = load_users()
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    users[str(chat_id)] = {"plan": "premium", "expiry": expiry, "name": name}
    save_users(users)
    return expiry

def remove_premium(chat_id):
    users = load_users()
    if str(chat_id) in users:
        users[str(chat_id)]["plan"] = "free"
        save_users(users)

def register_user(chat_id, name):
    users = load_users()
    if str(chat_id) not in users:
        users[str(chat_id)] = {"plan": "free", "expiry": None, "name": name}
        save_users(users)

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

def main_menu(chat_id):
    if is_premium(chat_id):
        return {
            "inline_keyboard": [
                [
                    {"text": "🏠 Accueil",           "callback_data": "/accueil"}
                ],
                [
                    {"text": "📰 Actu Marché",        "callback_data": "/actu"},
                    {"text": "🏆 Top 5 Actions",      "callback_data": "/top"}
                ],
                [
                    {"text": "🥇 Signal Gold",        "callback_data": "/gold"},
                    {"text": "🔷 Signal ETH",         "callback_data": "/eth"}
                ],
                [
                    {"text": "📊 RSI BTC",            "callback_data": "/rsi btc"},
                    {"text": "📊 RSI ETH",            "callback_data": "/rsi eth"}
                ],
                [
                    {"text": "📊 RSI Gold",           "callback_data": "/rsi gold"},
                    {"text": "📊 RSI S&P500",         "callback_data": "/rsi sp500"}
                ],
                [
                    {"text": "🎰 Pépite du jour",     "callback_data": "/chance"}
                ],
                [
                    {"text": "👤 Mon Compte",         "callback_data": "/moncompte"},
                    {"text": "❓ Aide",               "callback_data": "/help"}
                ]
            ]
        }
    else:
        return {
            "inline_keyboard": [
                [
                    {"text": "🏠 Accueil",                              "callback_data": "/accueil"}
                ],
                [
                    {"text": "📰 Actu Marché (gratuit)",                "callback_data": "/actu"}
                ],
                [
                    {"text": "🔓 Débloquer PREMIUM — " + PRIX_MENSUEL + "/mois", "callback_data": "/premium"}
                ],
                [
                    {"text": "👤 Mon Compte",    "callback_data": "/moncompte"},
                    {"text": "❓ Aide",          "callback_data": "/help"}
                ]
            ]
        }

def premium_lock_msg(chat_id):
    send_message(chat_id,
        "🔒 *Fonctionnalité PREMIUM*\n\n"
        "Cette analyse est réservée aux abonnés Premium.\n\n"
        f"✅ Accès illimité à toutes les analyses\n"
        f"✅ Signaux BUY/SHORT Gold & ETH\n"
        f"✅ RSI en temps réel (BTC, ETH, Gold, S&P500)\n"
        f"✅ Top 5 actions du jour\n"
        f"✅ Résumé marché automatique à 8h\n\n"
        f"💰 *{PRIX_MENSUEL}/mois* ou *{PRIX_ANNUEL}/an*",
        reply_markup={
            "inline_keyboard": [
                [{"text": f"💳 S'abonner — {PRIX_MENSUEL}/mois", "url": PAYMENT_LINK}],
                [{"text": "🔙 Retour", "callback_data": "/start"}]
            ]
        }
    )

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
    return [float(v) for v in data.values.flatten() if str(v) != 'nan']

def compute_rsi(ticker, period=14):
    data = yf.download(ticker, period="60d", interval="1d", auto_adjust=True, progress=False)
    if data.empty:
        return None
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
ACTUALITES : {chr(10).join(news_list)}
MARCHES : {market_str}

Reponds en francais avec emojis, format telephone :
*RESUME DES ACTUS* (6-8 points cles)
*DIRECTION DES MARCHES* -> Chaque actif : direction + probabilite % + explication courte
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

def generate_hidden_gem(news_list):
    today = datetime.now().strftime('%d/%m/%Y')

    # Liste d'actifs peu connus à analyser
    candidates = {
        # Cryptos small cap
        "RENDER-USD": "Render (RNDR)",
        "INJ-USD": "Injective (INJ)",
        "FET-USD": "Fetch.ai (FET)",
        "OCEAN-USD": "Ocean Protocol (OCEAN)",
        "AR-USD": "Arweave (AR)",
        "ROSE-USD": "Oasis Network (ROSE)",
        "BAND-USD": "Band Protocol (BAND)",
        "CELO-USD": "Celo (CELO)",
        # Actions small/mid cap
        "RKLB": "Rocket Lab (RKLB)",
        "IONQ": "IonQ (IONQ)",
        "ACHR": "Archer Aviation (ACHR)",
        "JOBY": "Joby Aviation (JOBY)",
        "LUNR": "Intuitive Machines (LUNR)",
        "SERV": "Serve Robotics (SERV)",
    }

    # Récupère les données de tous les candidats
    tickers = list(candidates.keys())
    try:
        data = yf.download(tickers, period="30d", interval="1d", progress=False)["Close"]
        change_7d = data.pct_change(periods=7).iloc[-1] * 100
        change_30d = data.pct_change(periods=30).iloc[-1] * 100
        latest = data.iloc[-1]
    except:
        return "Impossible de récupérer les données pour cette analyse."

    # Construit le tableau des actifs
    assets_info = []
    for ticker, name in candidates.items():
        try:
            p = float(latest[ticker])
            c7 = float(change_7d[ticker])
            c30 = float(change_30d[ticker])
            if not (pd.isna(p) or pd.isna(c7) or pd.isna(c30)):
                assets_info.append(f"- {name}: prix={p:.4f} | 7j={c7:+.1f}% | 30j={c30:+.1f}%")
        except:
            continue

    news_text = "\n".join(news_list[:8])

    prompt = f"""Tu es un analyste spécialisé dans la détection de pépites financières sous-cotées.
Aujourd'hui le {today}

ACTIFS SMALL CAP DISPONIBLES (crypto & actions) :
{chr(10).join(assets_info)}

ACTUALITES DU MOMENT :
{news_text}

Analyse ces actifs et choisis UN SEUL qui a selon toi le plus fort potentiel d'explosion à court terme (1-4 semaines).
Choisis des actifs peu connus, pas Bitcoin ou Ethereum.

Réponds en français avec emojis, format téléphone :

🎰 *PÉPITE DU JOUR* : [Nom de l'actif]

*POURQUOI CET ACTIF ?*
- Raison technique (tendance, momentum, volume)
- Raison fondamentale (secteur, catalyseur, narrative)
- Contexte macro favorable

*POTENTIEL* : +XX% à +XX% possible
*HORIZON* : X à X semaines
*RISQUE* : Faible / Modéré / Élevé

*COMMENT EN ACHETER* : [Plateforme recommandée]

⚠️ _Ceci n'est pas un conseil financier. Investis uniquement ce que tu peux te permettre de perdre._

Maximum 1500 caractères. Sois enthousiaste mais honnête sur les risques."""

    return call_groq(prompt, max_tokens=700, temperature=0.6)

# ================== COMMANDES ==================

def cmd_chance(chat_id):
    if not is_premium(chat_id):
        premium_lock_msg(chat_id)
        return
    send_message(chat_id,
        "🎰 *Recherche de la pépite du jour...*\n"
        "Analyse de 15 actifs sous-cotés en cours (~30s) 🔍"
    )
    try:
        news = get_news()
        gem = generate_hidden_gem(news)
        send_message(chat_id,
            f"🎰 *PÉPITE DU JOUR — {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n{gem}"
        )
    except Exception as e:
        print(f"Erreur /chance : {e}")
        send_message(chat_id, "❌ Erreur lors de l'analyse. Réessaie dans quelques instants.")
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu(chat_id))


def cmd_accueil(chat_id, name=""):
    if is_premium(chat_id):
        msg = (
            f"🏠 *TABLEAU DE BORD — PREMIUM* 👑\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Bonjour *{name}* ! Voici tout ce que tu peux faire :\n\n"
            f"📰 *ACTU MARCHÉ*\n"
            f"└ Résumé complet des marchés financiers\n"
            f"└ Actualités business FR & EN\n"
            f"└ Direction de chaque actif + probabilité\n\n"
            f"🏆 *TOP 5 ACTIONS*\n"
            f"└ Les 5 actions les plus performantes du jour\n"
            f"└ Le Flop 3 à éviter absolument\n\n"
            f"🥇 *SIGNAL GOLD* / 🔷 *SIGNAL ETH*\n"
            f"└ BUY ou SHORT avec niveau de conviction %\n"
            f"└ Objectif de prix + Stop Loss précis\n"
            f"└ Analyse technique & fondamentale\n\n"
            f"📊 *RSI EN TEMPS RÉEL*\n"
            f"└ Bitcoin, Ethereum, Or, S&P 500\n"
            f"└ Barre visuelle survente / surachat\n"
            f"└ Conseil clair pour chaque actif\n\n"
            f"🎰 *PÉPITE DU JOUR*\n"
            f"└ 1 crypto ou action peu connue sélectionnée\n"
            f"└ Fort potentiel d'explosion court terme\n"
            f"└ Potentiel %, horizon & niveau de risque\n\n"
            f"🌅 *ENVOI AUTO À 8H00*\n"
            f"└ Résumé marché chaque matin automatiquement\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⬇️ *Que veux-tu analyser aujourd'hui ?*"
        )
    else:
        msg = (
            f"🏠 *BIENVENUE SUR TON ASSISTANT MARCHÉ*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆓 *GRATUIT — Disponible maintenant*\n"
            f"✅ *Actu Marché* — Résumé quotidien des marchés\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👑 *PREMIUM — {PRIX_MENSUEL}/mois*\n"
            f"✅ *Signal Gold & ETH* — BUY ou SHORT + Stop Loss\n"
            f"✅ *Top 5 Actions* — Les meilleures du jour\n"
            f"✅ *RSI* — BTC, ETH, Or, S&P500 en temps réel\n"
            f"✅ *Pépite du jour* — Petite crypto/action à fort potentiel\n"
            f"✅ *Résumé auto à 8h* — Chaque matin sans rien faire\n"
            f"✅ *Analyses illimitées* — 24h/24, 7j/7\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *Paiement sécurisé via PayPal*\n"
            f"🔓 Accès activé sous *1h* après paiement\n\n"
            f"⬇️ *Commence gratuitement ou passe Premium :*"
        )
    send_message(chat_id, msg, reply_markup=main_menu(chat_id))


def cmd_start(chat_id, name=""):
    register_user(chat_id, name)
    cmd_accueil(chat_id, name)


def cmd_moncompte(chat_id):
    user = get_user(chat_id)
    if is_admin(chat_id):
        msg = "👑 *Ton Compte — ADMIN*\n\nAccès illimité à tout."
    elif is_premium(chat_id):
        expiry = user.get("expiry", "Illimité")
        msg = (
            f"👑 *Ton Compte — PREMIUM*\n\n"
            f"Nom : {user.get('name', 'Inconnu')}\n"
            f"Statut : ✅ Premium actif\n"
            f"Expiration : {expiry}\n\n"
            f"Merci pour ton abonnement !"
        )
    else:
        msg = (
            f"👤 *Ton Compte — GRATUIT*\n\n"
            f"Nom : {user.get('name', 'Inconnu')}\n"
            f"Statut : 🆓 Plan gratuit\n\n"
            f"Passe en *Premium* pour tout débloquer !\n"
            f"💰 *{PRIX_MENSUEL}/mois* ou *{PRIX_ANNUEL}/an*"
        )
    send_message(chat_id, msg, reply_markup={
        "inline_keyboard": [
            [{"text": f"💳 Passer Premium — {PRIX_MENSUEL}/mois", "url": PAYMENT_LINK}],
            [{"text": "🔙 Menu principal", "callback_data": "/start"}]
        ]
    } if not is_premium(chat_id) else {
        "inline_keyboard": [[{"text": "🔙 Menu principal", "callback_data": "/start"}]]
    })

def cmd_premium_info(chat_id):
    send_message(chat_id,
        f"👑 *PASSER EN PREMIUM*\n\n"
        f"💰 *{PRIX_MENSUEL}/mois* — Résiliable à tout moment\n"
        f"💰 *{PRIX_ANNUEL}/an* — 2 mois offerts\n\n"
        f"✅ Signaux BUY/SHORT Gold & ETH\n"
        f"✅ RSI BTC, ETH, Gold, S&P500\n"
        f"✅ Top 5 & Flop 3 actions du jour\n"
        f"✅ Résumé marché automatique à 8h\n"
        f"✅ Analyses illimitées 24/7\n\n"
        f"*Comment ça marche ?*\n"
        f"1️⃣ Clique sur le bouton ci-dessous\n"
        f"2️⃣ Effectue le paiement\n"
        f"3️⃣ Envoie la preuve de paiement ici\n"
        f"4️⃣ Ton accès est activé sous 1h ✅",
        reply_markup={
            "inline_keyboard": [
                [{"text": f"💳 S'abonner maintenant — {PRIX_MENSUEL}/mois", "url": PAYMENT_LINK}],
                [{"text": "🔙 Retour", "callback_data": "/start"}]
            ]
        }
    )

def cmd_actu(chat_id):
    send_message(chat_id, "⏳ *Récupération des données...*\nAnalyse en cours (~30s) ☕")
    news = get_news()
    market = get_market_data()
    summary = generate_summary(news, market)
    send_message(chat_id, f"📊 *RÉSUMÉ MARCHÉ — {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n{summary}")
    if not is_premium(chat_id):
        send_message(chat_id,
            "🔒 *Veux-tu aller plus loin ?*\n"
            f"Passe en *Premium* pour les signaux BUY/SHORT, RSI et Top 5 actions !",
            reply_markup={
                "inline_keyboard": [
                    [{"text": f"👑 Passer Premium — {PRIX_MENSUEL}/mois", "url": PAYMENT_LINK}],
                    [{"text": "🔙 Menu", "callback_data": "/start"}]
                ]
            }
        )
    else:
        send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu(chat_id))

def cmd_top(chat_id):
    if not is_premium(chat_id):
        premium_lock_msg(chat_id)
        return
    send_message(chat_id, "⏳ *Chargement du classement...*")
    send_message(chat_id, get_top5())
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu(chat_id))

def cmd_gold(chat_id):
    if not is_premium(chat_id):
        premium_lock_msg(chat_id)
        return
    send_message(chat_id, "⏳ *Analyse Or en cours...*")
    news = get_news()
    signal = generate_trade_signal("OR (GOLD)", "GC=F", news)
    send_message(chat_id, f"🥇 *ANALYSE GOLD — {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n{signal}")
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu(chat_id))

def cmd_eth(chat_id):
    if not is_premium(chat_id):
        premium_lock_msg(chat_id)
        return
    send_message(chat_id, "⏳ *Analyse Ethereum en cours...*")
    news = get_news()
    signal = generate_trade_signal("Ethereum (ETH)", "ETH-USD", news)
    send_message(chat_id, f"🔷 *ANALYSE ETH — {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n{signal}")
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu(chat_id))

def cmd_rsi(chat_id, asset_key):
    if not is_premium(chat_id):
        premium_lock_msg(chat_id)
        return
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
    send_message(chat_id, "🔄 *Que veux-tu faire ensuite ?*", reply_markup=main_menu(chat_id))

# ================== COMMANDES ADMIN ==================

def cmd_admin(chat_id, text):
    if not is_admin(chat_id):
        return

    parts = text.strip().split()

    # /addpremium [chat_id] [nom] [jours]
    # Ex: /addpremium 123456789 Jean 30
    if parts[0] == "/addpremium" and len(parts) >= 4:
        target_id = parts[1]
        name = parts[2]
        days = int(parts[3])
        expiry = add_premium(target_id, name, days)
        send_message(chat_id, f"✅ *Premium activé*\nUser: {name} ({target_id})\nExpiration: {expiry}")
        send_message(int(target_id),
            f"🎉 *Ton accès Premium a été activé !*\n\n"
            f"Expiration : {expiry}\n\n"
            f"Tape /start pour accéder à toutes les fonctionnalités 👑"
        )

    # /removepremium [chat_id]
    elif parts[0] == "/removepremium" and len(parts) >= 2:
        target_id = parts[1]
        remove_premium(target_id)
        send_message(chat_id, f"✅ Premium supprimé pour {target_id}")

    # /listusers
    elif parts[0] == "/listusers":
        users = load_users()
        if not users:
            send_message(chat_id, "Aucun utilisateur enregistré.")
            return
        lines = ["👥 *LISTE DES UTILISATEURS*\n"]
        for uid, info in users.items():
            plan = "👑 Premium" if info["plan"] == "premium" else "🆓 Gratuit"
            expiry = info.get("expiry", "N/A")
            lines.append(f"{plan} | {info.get('name','?')} | ID: {uid} | Exp: {expiry}")
        send_message(chat_id, "\n".join(lines))

    # /stats
    elif parts[0] == "/stats":
        users = load_users()
        total = len(users)
        premium_count = sum(1 for u in users.values() if u["plan"] == "premium")
        free_count = total - premium_count
        send_message(chat_id,
            f"📈 *STATISTIQUES BOT*\n\n"
            f"👥 Total utilisateurs : {total}\n"
            f"👑 Premium : {premium_count}\n"
            f"🆓 Gratuit : {free_count}\n"
            f"💰 Revenus estimés : {premium_count * float(PRIX_MENSUEL.replace('€','')):.2f}€/mois"
        )

    else:
        send_message(chat_id,
            "🛠️ *COMMANDES ADMIN*\n\n"
            "`/addpremium [id] [nom] [jours]`\n"
            "`/removepremium [id]`\n"
            "`/listusers`\n"
            "`/stats`"
        )

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
            users = load_users()
            # Envoyer à tous les premium + admin
            targets = [TELEGRAM_CHAT_ID] + [uid for uid, u in users.items() if u["plan"] == "premium"]
            for target in set(targets):
                send_message(target, "🌅 *Bonjour ! Voici ton résumé marché du matin.*")
                news = get_news()
                market = get_market_data()
                summary = generate_summary(news, market)
                send_message(target, f"📊 *RÉSUMÉ MARCHÉ — {now.strftime('%d/%m/%Y')}*\n\n{summary}")
                send_message(target, "🔄 *Menu rapide :*", reply_markup=main_menu(int(target)))
            print("Envoi auto 8h OK !")
        except Exception as e:
            print(f"Erreur envoi auto : {e}")

# ================== ROUTING ==================

def handle_command(chat_id, text, user_name=""):
    t = text.strip().lower()

    # Commandes admin (case sensitive pour la sécurité)
    if text.startswith("/addpremium") or text.startswith("/removepremium") or \
       text.startswith("/listusers") or text.startswith("/stats") or text.startswith("/admin"):
        cmd_admin(chat_id, text)
        return

    if t == "/start":
        cmd_start(chat_id, user_name)
    elif t in ["/help", "/accueil"]:
        cmd_accueil(chat_id, user_name)
    elif t == "/actu":
        cmd_actu(chat_id)
    elif t == "/top":
        cmd_top(chat_id)
    elif t == "/gold":
        cmd_gold(chat_id)
    elif t == "/eth":
        cmd_eth(chat_id)
    elif t.startswith("/rsi"):
        parts = t.split()
        cmd_rsi(chat_id, parts[1] if len(parts) > 1 else "eth")
    elif t == "/premium":
        cmd_premium_info(chat_id)
    elif t == "/moncompte":
        cmd_moncompte(chat_id)
    elif t == "/chance":
        cmd_chance(chat_id)
    else:
        # Si l'utilisateur envoie un message libre (ex: preuve de paiement)
        if not is_premium(chat_id):
            send_message(chat_id,
                "💬 *Message reçu !*\n\n"
                "Si tu as effectué un paiement, l'admin va vérifier et activer ton accès sous 1h.\n"
                "Merci pour ta patience ! 🙏",
                reply_markup=main_menu(chat_id)
            )
            # Notifier l'admin
            send_message(TELEGRAM_CHAT_ID,
                f"📩 *Nouveau message d'un utilisateur*\n\n"
                f"ID: `{chat_id}`\n"
                f"Nom: {user_name}\n"
                f"Message: {text}\n\n"
                f"Pour activer : `/addpremium {chat_id} {user_name} 30`"
            )
        else:
            send_message(chat_id, "❓ Commande inconnue.", reply_markup=main_menu(chat_id))

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

print("Bot demarre avec systeme d'abonnement !")
print("Commandes admin : /addpremium | /removepremium | /listusers | /stats")
print("Envoi automatique chaque jour a 8h00 (Premium uniquement)")

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
                user_name = cq["message"]["chat"].get("first_name", "")
                print(f"Bouton : {cq['data']} par {chat_id}")
                handle_command(chat_id, cq["data"], user_name)
            elif "message" in update:
                msg = update["message"]
                text = msg.get("text", "")
                chat_id = msg["chat"]["id"]
                user_name = msg["chat"].get("first_name", "")
                if text:
                    print(f"Message : {text} par {chat_id}")
                    handle_command(chat_id, text, user_name)
        check_auto_send()
        time.sleep(1)
    except Exception as e:
        print(f"Erreur : {e}")
        time.sleep(5)
