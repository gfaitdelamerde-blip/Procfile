import os
import requests
import yfinance as yf
from openai import OpenAI
from datetime import datetime, timedelta, timezone
import time
import pandas as pd
import json
import random
import pytz
import threading

os.environ["PYTHONIOENCODING"] = "utf-8"

PARIS_TZ = pytz.timezone("Europe/Paris")

def now_paris():
    return datetime.now(pytz.utc).astimezone(PARIS_TZ).replace(tzinfo=None)


# ================== CONFIG ==================
NEWSAPI_KEY      = os.getenv("NEWSAPI_KEY")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

GROQ_MODEL   = "llama-3.3-70b-versatile"
PAYMENT_LINK = "https://paypal.me/tonnom/9.99EUR"
PRIX_MENSUEL = "9.99€"
PRIX_ANNUEL        = "79.99€"
PAYMENT_LINK_ANNUEL = "https://paypal.me/tonnom/79.99EUR"
PRICE_TRACKING_FILE = "price_tracking.json"   # suivi des prix pour alertes mouvement fort
LESSON_SENT_FILE    = "lesson_sent.json"       # suivi leçons hebdo déjà envoyées
USERS_FILE   = "users.json"
USER_WALLETS_FILE = "user_wallets.json"
UW_INITIAL        = 10000

# Assets disponibles pour les trades du wallet user
AI_TRADABLE = {
    "btc":  ("BTC-USD", "Bitcoin"),
    "eth":  ("ETH-USD", "Ethereum"),
    "sol":  ("SOL-USD", "Solana"),
    "nvda": ("NVDA",    "Nvidia"),
    "tsla": ("TSLA",    "Tesla"),
    "aapl": ("AAPL",    "Apple"),
    "msft": ("MSFT",    "Microsoft"),
    "amzn": ("AMZN",    "Amazon"),
    "meta": ("META",    "Meta"),
    "gold": ("GC=F",    "Gold"),
}

# ─── URL DU DASHBOARD (100% automatique Railway) ───
RAILWAY_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
DASHBOARD_BASE_URL = f"https://{RAILWAY_DOMAIN}" if RAILWAY_DOMAIN else "http://localhost:8080"

TICKERS = ["BTC-USD","ETH-USD","GC=F","^GSPC","^DJI","^IXIC","AAPL","MSFT","NVDA","TSLA","AMZN"]

SIGNAL_ASSETS = {
    "btc":   ("BTC-USD",  "₿ Bitcoin (BTC)"),
    "eth":   ("ETH-USD",  "🔷 Ethereum (ETH)"),
    "bnb":   ("BNB-USD",  "🟡 BNB"),
    "sol":   ("SOL-USD",  "🔵 Solana (SOL)"),
    "xrp":   ("XRP-USD",  "🟣 XRP"),
    "gold":  ("GC=F",     "🥇 Or (GOLD)"),
    "aapl":  ("AAPL",     "🍎 Apple"),
    "nvda":  ("NVDA",     "🟢 Nvidia"),
    "msft":  ("MSFT",     "🔵 Microsoft"),
    "tsla":  ("TSLA",     "🚗 Tesla"),
    "amzn":  ("AMZN",     "📦 Amazon"),
    "googl": ("GOOGL",    "🔍 Google"),
    "meta":  ("META",     "📘 Meta"),
    "amd":   ("AMD",      "🔴 AMD"),
}

RSI_ASSETS = {
    "btc":   ("BTC-USD", "₿ Bitcoin"),
    "eth":   ("ETH-USD", "🔷 Ethereum"),
    "bnb":   ("BNB-USD", "🟡 BNB"),
    "sol":   ("SOL-USD", "🔵 Solana"),
    "gold":  ("GC=F",    "🥇 Or"),
    "sp500": ("^GSPC",   "📈 S&P 500"),
    "aapl":  ("AAPL",    "🍎 Apple"),
    "nvda":  ("NVDA",    "🟢 Nvidia"),
    "tsla":  ("TSLA",    "🚗 Tesla"),
}

# ================== TRADUCTIONS ==================
LANGS = {
    "fr": {
        # Accueil
        "welcome_title": "💎 ESPACE MEMBRE PREMIUM",
        "morning": ["🌅 Bonjour", "☀️ Bon après-midi", "🌙 Bonsoir"],
        "tools": "Voici tes outils exclusifs :",
        "briefing_auto": "🌅 Briefing auto chaque matin à *8h00*",
        "hebdo_auto": "📅 Bilan hebdo chaque *dimanche soir*",
        "verified": "✔️ Vérifié par des professionnels de la finance",
        # Traitement
        "processing": "⏳ Analyse en cours... (~30s) ☕",
        "processing_short": "⏳ Analyse en cours...",
        "error": "❌ Erreur lors de l'analyse. Réessaie.",
        "no_data": "❌ Données insuffisantes.",
        # Signaux
        "signal_title": "📈 SIGNAL",
        "signal_choose": "📈 *Choisis un actif :*",
        "signal_analyzing": "⏳ *Analyse {} en cours...*",
        "signal_other": "🔄 *Autre signal ?*",
        # RSI
        "rsi_title": "📊 RSI (14)",
        "rsi_choose": "📊 *Choisis un actif :*",
        "rsi_analyzing": "⏳ *RSI {}...*",
        "rsi_other": "🔄 *Autre RSI ?*",
        "rsi_oversold": "🟢 SURVENTE — Zone haussière potentielle",
        "rsi_overbought": "🔴 SURACHAT — Zone baissière potentielle",
        "rsi_neutral": "⚪ NEUTRE — Pas de signal fort",
        "rsi_buy_hint": "Signal d'achat possible",
        "rsi_sell_hint": "Risque de retournement",
        "rsi_wait_hint": "Attendre RSI sous 30 ou au-dessus de 70",
        "rsi_legend": "RSI sous 30 = survente  |  RSI au-dessus de 70 = surachat",
        # Pépite
        "gem_searching": "🎰 *Recherche de la pépite... (~30s)*",
        "gem_title": "🎰 *PÉPITE DU JOUR —",
        # Citation
        "quote_title": "💬 *CITATION DU JOUR —",
        # Score
        "score_title": "📅 *SCORE MARCHÉ —",
        "score_bullish": "🟢 *Haussier*",
        "score_neutral": "🟡 *Neutre*",
        "score_bearish": "🔴 *Baissier*",
        "score_bull_tip": "Les marchés sont en forme. Momentum positif.",
        "score_neut_tip": "Marchés indécis. Prudence et sélectivité.",
        "score_bear_tip": "Pression vendeuse. Gestion du risque prioritaire.",
        "score_sentiment": "Sentiment :",
        # Top 5
        "top_loading": "⏳ *Chargement...*",
        "top_title": "🏆 *TOP 5 ACTIONS DU JOUR*",
        "flop_title": "📉 *FLOP 3 DU JOUR*",
        # Paper trading
        "paper_buy_help": "📥 *ACHETER*\n\nFormat : `buy [actif] [montant$]`\nEx : `buy btc 500`\nEx : `buy nvda 200`",
        "paper_sell_help": "📤 *VENDRE*\n\nFormat : `sell [actif] [%]`\nEx : `sell btc 100` (vend 100%)\nEx : `sell tsla 50` (vend 50%)",
        "paper_reset_done": "🔄 *Paper Trading réinitialisé à 10 000$*",
        "paper_balance": "💰 Solde :",
        "paper_positions": "📋 *POSITIONS OUVERTES*",
        "paper_no_position": "_Aucune position ouverte._",
        "paper_total": "Valeur totale",
        # Alertes
        "alert_new_help": (
            "🔔 *NOUVELLE ALERTE DE PRIX*\n\n"
            "Écris ton alerte dans ce format :\n\n"
            "`alerte btc 100000 above`\n"
            "_→ Préviens-moi quand BTC dépasse 100 000$_\n\n"
            "`alerte eth 2000 below`\n"
            "_→ Préviens-moi quand ETH passe sous 2 000$_\n\n"
            "Actifs : btc, eth, bnb, sol, xrp, gold, aapl, nvda, msft, tsla, amzn, googl, meta, amd"
        ),
        "alert_created": "✅ *Alerte créée !*\n\n🔔 {} — Alerte quand le prix *{}* {:.2f}$\n\nTu recevras une notification automatiquement.",
        "alert_above": "dépasse",
        "alert_below": "passe sous",
        "alert_triggered": "🔔 *ALERTE DÉCLENCHÉE !*\n\n{} *{}* a atteint *{:,.2f}$*\n_(Seuil fixé : {:,.2f}$)_",
        "alert_deleted": "✅ Alerte supprimée :",
        # SAV
        "sav_title": "🛎️ *SERVICE CLIENT*\n━━━━━━━━━━━━━━━━━━━━\n\n*Pour quel motif nous contacter ?*",
        "sav_tech": "🔧 Problème technique",
        "sav_payment": "💳 Problème de paiement",
        "sav_suggestion": "💡 Suggestion",
        "sav_other": "❓ Autre",
        "sav_write": "\n\n📝 *Décris ton problème ci-dessous.*\n_L'équipe te répond directement ici._",
        "sav_sent": "✅ *Ton message a bien été envoyé !*\n\nNotre équipe te répondra directement ici. 🙏",
        "payment_received": "⚡ *Message reçu !*\n\nTon paiement va être vérifié et ton accès activé quasi-instantanément.\nMerci 🙏",
        # Compte
        "account_premium_title": "━━━━━━━━━━━━━━━━━━━━\n💎 *CARTE MEMBRE PREMIUM*\n━━━━━━━━━━━━━━━━━━━━",
        "account_status": "🏆 Statut : *Premium Actif* ✅",
        "account_expiry": "📅 Valable jusqu'au :",
        "account_thanks": "_Merci de faire partie du cercle Premium._ 🙏",
        # Langue
        "lang_changed": "✅ Langue changée :",
        # Premium lock
        "lock_msg": (
            f"🔒 *Fonctionnalité Premium*\n\nDébloque tout pour *{{price}}/mois* :\n"
            "📈 Signaux • 📊 RSI • 🎰 Pépite • 📊 Paper Trading • 🔔 Alertes\n\n"
            "⚡ Activation quasi-instantanée"
        ),
        "subscribe_btn": "👑 Passer Premium —",
        # Boutons navigation
        "btn_back": "🔙 Retour",
        "btn_menu": "🔙 Menu",
        "btn_refresh": "🔄 Actualiser",
        "btn_sav": "🛎️ Contacter le SAV",
        # Menu retour contextuel
        "menu_return_morning": ["☀️ *Que veux-tu analyser ce matin{} ?*", "🌅 *Les marchés t'attendent. Par où commencer ?*", "📊 *Bonne session ! Que veux-tu explorer ?*"],
        "menu_return_noon":    ["🍽️ *Pause méritée. On reprend quand tu veux.*", "☀️ *Les marchés n'attendent pas. Que veux-tu voir ?*"],
        "menu_return_us":      ["📈 *Wall Street est ouvert. Qu'est-ce qu'on analyse ?*", "⚡ *Séance US en cours. Saisis les opportunités.*", "🎯 *Que veux-tu surveiller maintenant ?*"],
        "menu_return_evening": ["🌙 *Marchés US en clôture. Bilan ou prochain trade ?*", "📉 *Fin de séance. Que veux-tu analyser ?*"],
        "menu_return_night":   ["🌙 *Le crypto ne dort jamais. Que surveilles-tu ?*", "🦉 *Noctambule des marchés ! Que surveilles-tu ?*"],
        "menu_return_score":   "Score marché :",
        "menu_return_free":    "🏠 *Que veux-tu faire ?*\n\n📰 L'actu marché est gratuite et disponible maintenant.\n👑 Toutes les autres fonctionnalités sont *Premium*.",
    },
    "en": {
        "welcome_title": "💎 PREMIUM MEMBER AREA",
        "morning": ["🌅 Good morning", "☀️ Good afternoon", "🌙 Good evening"],
        "tools": "Here are your exclusive tools:",
        "briefing_auto": "🌅 Auto briefing every morning at *8:00 AM*",
        "hebdo_auto": "📅 Weekly summary every *Sunday evening*",
        "verified": "✔️ Verified by professional traders",
        "processing": "⏳ Analysis in progress... (~30s) ☕",
        "processing_short": "⏳ Analyzing...",
        "error": "❌ Analysis error. Please try again.",
        "no_data": "❌ Insufficient data.",
        "signal_title": "📈 SIGNAL",
        "signal_choose": "📈 *Choose an asset:*",
        "signal_analyzing": "⏳ *Analyzing {}...*",
        "signal_other": "🔄 *Another signal?*",
        "rsi_title": "📊 RSI (14)",
        "rsi_choose": "📊 *Choose an asset:*",
        "rsi_analyzing": "⏳ *RSI {}...*",
        "rsi_other": "🔄 *Another RSI?*",
        "rsi_oversold": "🟢 OVERSOLD — Potential bullish zone",
        "rsi_overbought": "🔴 OVERBOUGHT — Potential bearish zone",
        "rsi_neutral": "⚪ NEUTRAL — No strong signal",
        "rsi_buy_hint": "Possible buy signal",
        "rsi_sell_hint": "Reversal risk",
        "rsi_wait_hint": "Wait for RSI below 30 or above 70",
        "rsi_legend": "RSI below 30 = oversold  |  RSI above 70 = overbought",
        "gem_searching": "🎰 *Looking for today's gem... (~30s)*",
        "gem_title": "🎰 *GEM OF THE DAY —",
        "quote_title": "💬 *QUOTE OF THE DAY —",
        "score_title": "📅 *MARKET SCORE —",
        "score_bullish": "🟢 *Bullish*",
        "score_neutral": "🟡 *Neutral*",
        "score_bearish": "🔴 *Bearish*",
        "score_bull_tip": "Markets are strong. Positive momentum.",
        "score_neut_tip": "Indecisive markets. Be selective.",
        "score_bear_tip": "Selling pressure. Risk management first.",
        "score_sentiment": "Sentiment:",
        "top_loading": "⏳ *Loading...*",
        "top_title": "🏆 *TOP 5 STOCKS TODAY*",
        "flop_title": "📉 *WORST 3 TODAY*",
        "paper_buy_help": "📥 *BUY*\n\nFormat: `buy [asset] [amount$]`\nEx: `buy btc 500`\nEx: `buy nvda 200`",
        "paper_sell_help": "📤 *SELL*\n\nFormat: `sell [asset] [%]`\nEx: `sell btc 100` (sell 100%)\nEx: `sell tsla 50` (sell 50%)",
        "paper_reset_done": "🔄 *Paper Trading reset to $10,000*",
        "paper_balance": "💰 Balance:",
        "paper_positions": "📋 *OPEN POSITIONS*",
        "paper_no_position": "_No open positions._",
        "paper_total": "Total value",
        "alert_new_help": (
            "🔔 *NEW PRICE ALERT*\n\n"
            "Write your alert in this format:\n\n"
            "`alert btc 100000 above`\n"
            "_→ Notify me when BTC goes above $100,000_\n\n"
            "`alert eth 2000 below`\n"
            "_→ Notify me when ETH drops below $2,000_\n\n"
            "Assets: btc, eth, bnb, sol, xrp, gold, aapl, nvda, msft, tsla, amzn, googl, meta, amd"
        ),
        "alert_created": "✅ *Alert created!*\n\n🔔 {} — Alert when price *{}* ${:.2f}\n\nYou'll get an automatic notification.",
        "alert_above": "goes above",
        "alert_below": "drops below",
        "alert_triggered": "🔔 *ALERT TRIGGERED!*\n\n{} *{}* has reached *${:,.2f}*\n_(Set threshold: ${:,.2f})_",
        "alert_deleted": "✅ Alert deleted:",
        "sav_title": "🛎️ *SUPPORT*\n━━━━━━━━━━━━━━━━━━━━\n\n*What's the reason for contacting us?*",
        "sav_tech": "🔧 Technical issue",
        "sav_payment": "💳 Payment issue",
        "sav_suggestion": "💡 Suggestion",
        "sav_other": "❓ Other",
        "sav_write": "\n\n📝 *Describe your issue below.*\n_Our team will reply here directly._",
        "sav_sent": "✅ *Your message has been sent!*\n\nOur team will reply here shortly. 🙏",
        "payment_received": "⚡ *Message received!*\n\nYour payment will be verified and access activated instantly.\nThank you 🙏",
        "account_premium_title": "━━━━━━━━━━━━━━━━━━━━\n💎 *PREMIUM MEMBER CARD*\n━━━━━━━━━━━━━━━━━━━━",
        "account_status": "🏆 Status: *Premium Active* ✅",
        "account_expiry": "📅 Valid until:",
        "account_thanks": "_Thank you for being part of the Premium circle._ 🙏",
        "lang_changed": "✅ Language changed:",
        "lock_msg": "🔒 *Premium Feature*\n\nUnlock everything for *{price}/month*:\n📈 Signals • 📊 RSI • 🎰 Gem • 📊 Paper Trading • 🔔 Alerts\n\n⚡ Near-instant activation",
        "subscribe_btn": "👑 Go Premium —",
        "btn_back": "🔙 Back",
        "btn_menu": "🔙 Menu",
        "btn_refresh": "🔄 Refresh",
        "btn_sav": "🛎️ Contact Support",
        "menu_return_morning": ["☀️ *What do you want to analyze this morning{} ?*", "🌅 *Markets are waiting. Where to start?*", "📊 *Good session! What do you want to explore?*"],
        "menu_return_noon":    ["🍽️ *Well-deserved break. Back whenever you're ready.*", "☀️ *Markets don't wait. What do you want to check?*"],
        "menu_return_us":      ["📈 *Wall Street is open. What are we analyzing?*", "⚡ *US session live. Seize the opportunities.*", "🎯 *What do you want to monitor now?*"],
        "menu_return_evening": ["🌙 *US markets closing. Review or next trade?*", "📉 *End of session. What do you want to analyze?*"],
        "menu_return_night":   ["🌙 *Crypto never sleeps. What are you watching?*", "🦉 *Night owl trader! What are you monitoring?*"],
        "menu_return_score":   "Market score:",
        "menu_return_free":    "🏠 *What do you want to do?*\n\n📰 Market news is free and available now.\n👑 All other features are *Premium*.",
    },
    "es": {
        "welcome_title": "💎 ÁREA MIEMBRO PREMIUM",
        "morning": ["🌅 Buenos días", "☀️ Buenas tardes", "🌙 Buenas noches"],
        "tools": "Aquí están tus herramientas exclusivas:",
        "briefing_auto": "🌅 Briefing automático cada mañana a las *8:00*",
        "hebdo_auto": "📅 Resumen semanal cada *domingo por la noche*",
        "verified": "✔️ Verificado por profesionales de las finanzas",
        "processing": "⏳ Análisis en curso... (~30s) ☕",
        "processing_short": "⏳ Analizando...",
        "error": "❌ Error de análisis. Inténtalo de nuevo.",
        "no_data": "❌ Datos insuficientes.",
        "signal_title": "📈 SEÑAL",
        "signal_choose": "📈 *Elige un activo:*",
        "signal_analyzing": "⏳ *Analizando {}...*",
        "signal_other": "🔄 *¿Otra señal?*",
        "rsi_title": "📊 RSI (14)",
        "rsi_choose": "📊 *Elige un activo:*",
        "rsi_analyzing": "⏳ *RSI {}...*",
        "rsi_other": "🔄 *¿Otro RSI?*",
        "rsi_oversold": "🟢 SOBREVENDIDO — Zona alcista potencial",
        "rsi_overbought": "🔴 SOBRECOMPRADO — Zona bajista potencial",
        "rsi_neutral": "⚪ NEUTRAL — Sin señal fuerte",
        "rsi_buy_hint": "Posible señal de compra",
        "rsi_sell_hint": "Riesgo de reversión",
        "rsi_wait_hint": "Esperar RSI bajo 30 o sobre 70",
        "rsi_legend": "RSI bajo 30 = sobrevendido  |  RSI sobre 70 = sobrecomprado",
        "gem_searching": "🎰 *Buscando la joya del día... (~30s)*",
        "gem_title": "🎰 *JOYA DEL DÍA —",
        "quote_title": "💬 *CITA DEL DÍA —",
        "score_title": "📅 *PUNTUACIÓN MERCADO —",
        "score_bullish": "🟢 *Alcista*",
        "score_neutral": "🟡 *Neutral*",
        "score_bearish": "🔴 *Bajista*",
        "score_bull_tip": "Los mercados están fuertes. Momentum positivo.",
        "score_neut_tip": "Mercados indecisos. Sé selectivo.",
        "score_bear_tip": "Presión vendedora. Gestión del riesgo primero.",
        "score_sentiment": "Sentimiento:",
        "top_loading": "⏳ *Cargando...*",
        "top_title": "🏆 *TOP 5 ACCIONES HOY*",
        "flop_title": "📉 *PEORES 3 HOY*",
        "paper_buy_help": "📥 *COMPRAR*\n\nFormato: `buy [activo] [importe$]`\nEj: `buy btc 500`",
        "paper_sell_help": "📤 *VENDER*\n\nFormato: `sell [activo] [%]`\nEj: `sell btc 100` (vende 100%)",
        "paper_reset_done": "🔄 *Paper Trading reiniciado a $10,000*",
        "paper_balance": "💰 Saldo:",
        "paper_positions": "📋 *POSICIONES ABIERTAS*",
        "paper_no_position": "_Sin posiciones abiertas._",
        "paper_total": "Valor total",
        "alert_new_help": (
            "🔔 *NUEVA ALERTA DE PRECIO*\n\n"
            "Escribe tu alerta en este formato:\n\n"
            "`alerta btc 100000 above`\n"
            "_→ Notifícame cuando BTC supere $100,000_\n\n"
            "`alerta eth 2000 below`\n"
            "_→ Notifícame cuando ETH caiga bajo $2,000_\n\n"
            "Activos: btc, eth, bnb, sol, xrp, gold, aapl, nvda, msft, tsla, amzn, googl, meta, amd"
        ),
        "alert_created": "✅ *¡Alerta creada!*\n\n🔔 {} — Alerta cuando el precio *{}* ${:.2f}\n\nRecibirás una notificación automática.",
        "alert_above": "supera",
        "alert_below": "cae bajo",
        "alert_triggered": "🔔 *¡ALERTA ACTIVADA!*\n\n{} *{}* ha alcanzado *${:,.2f}*\n_(Umbral fijado: ${:,.2f})_",
        "alert_deleted": "✅ Alerta eliminada:",
        "sav_title": "🛎️ *SOPORTE*\n━━━━━━━━━━━━━━━━━━━━\n\n*¿Cuál es el motivo de tu consulta?*",
        "sav_tech": "🔧 Problema técnico",
        "sav_payment": "💳 Problema de pago",
        "sav_suggestion": "💡 Sugerencia",
        "sav_other": "❓ Otro",
        "sav_write": "\n\n📝 *Describe tu problema abajo.*\n_El equipo te responderá directamente aquí._",
        "sav_sent": "✅ *¡Tu mensaje ha sido enviado!*\n\nNuestro equipo te responderá aquí pronto. 🙏",
        "payment_received": "⚡ *¡Mensaje recibido!*\n\nTu pago será verificado y el acceso activado casi instantáneamente.\n¡Gracias 🙏",
        "account_premium_title": "━━━━━━━━━━━━━━━━━━━━\n💎 *TARJETA MIEMBRO PREMIUM*\n━━━━━━━━━━━━━━━━━━━━",
        "account_status": "🏆 Estado: *Premium Activo* ✅",
        "account_expiry": "📅 Válido hasta:",
        "account_thanks": "_Gracias por ser parte del círculo Premium._ 🙏",
        "lang_changed": "✅ Idioma cambiado:",
        "lock_msg": "🔒 *Función Premium*\n\nDesbloquea todo por *{price}/mes*:\n📈 Señales • 📊 RSI • 🎰 Joya • 📊 Paper Trading • 🔔 Alertas\n\n⚡ Activación casi instantánea",
        "subscribe_btn": "👑 Ir a Premium —",
        "btn_back": "🔙 Volver",
        "btn_menu": "🔙 Menú",
        "btn_refresh": "🔄 Actualizar",
        "btn_sav": "🛎️ Contactar Soporte",
        "menu_return_morning": ["☀️ *¿Qué quieres analizar esta mañana{} ?*", "🌅 *Los mercados te esperan. ¿Por dónde empezamos?*"],
        "menu_return_noon":    ["🍽️ *Pausa merecida. Volvemos cuando quieras.*", "☀️ *Los mercados no esperan. ¿Qué quieres ver?*"],
        "menu_return_us":      ["📈 *Wall Street abierto. ¿Qué analizamos?*", "⚡ *Sesión US en vivo. Aprovecha las oportunidades.*"],
        "menu_return_evening": ["🌙 *Cierre de mercados US. ¿Balance o próximo trade?*"],
        "menu_return_night":   ["🌙 *El cripto nunca duerme. ¿Qué estás vigilando?*", "🦉 *¡Trader nocturno! ¿Qué monitorizas?*"],
        "menu_return_score":   "Puntuación mercado:",
        "menu_return_free":    "🏠 *¿Qué quieres hacer?*\n\n📰 Las noticias del mercado son gratuitas.\n👑 Todas las demás funciones son *Premium*.",
    },
}

def tr(chat_id, key, *args):
    """Traduit une clé selon la langue de l'utilisateur"""
    lang = get_lang(chat_id)
    val = LANGS.get(lang, LANGS["fr"]).get(key) or LANGS["fr"].get(key, key)
    if args:
        try:
            return val.format(*args)
        except:
            return val
    return val

def t(chat_id, key):
    return tr(chat_id, key)

def get_lang(chat_id):
    return get_user(chat_id).get("lang", "fr")


# ================== CITATIONS ==================
CITATIONS = [
    ("L'investissement, c'est mettre de l'argent aujourd'hui pour en avoir plus demain.", "Warren Buffett"),
    ("Le marché est un dispositif qui transfère de l'argent des impatients aux patients.", "Warren Buffett"),
    ("Le risque vient de ne pas savoir ce que vous faites.", "Warren Buffett"),
    ("Ne jamais investir dans ce que vous ne comprenez pas.", "Peter Lynch"),
    ("Le temps sur le marché bat le timing du marché.", "Ken Fisher"),
    ("Les marchés peuvent rester irrationnels plus longtemps que vous ne pouvez rester solvable.", "John Maynard Keynes"),
    ("Achetez quand tout le monde vend, vendez quand tout le monde achète.", "J. Paul Getty"),
    ("La bourse est le seul endroit où on vend moins quand les soldes commencent.", "Warren Buffett"),
    ("Il faut être craintif quand les autres sont avides, et avide quand les autres sont craintifs.", "Warren Buffett"),
    ("La première règle : ne jamais perdre d'argent. La deuxième : ne jamais oublier la première.", "Warren Buffett"),
    ("Un investisseur qui achète et vend frénétiquement paie des frais inutiles.", "Peter Lynch"),
    ("Les corrections de marché sont les meilleures opportunités pour les investisseurs.", "Peter Lynch"),
    ("La patience est la vertu la plus précieuse pour un investisseur.", "Charlie Munger"),
    ("Invert, always invert — comprendre l'échec pour l'éviter.", "Charlie Munger"),
    ("Le prix est ce que vous payez. La valeur est ce que vous obtenez.", "Warren Buffett"),
    ("Les quatre mots les plus dangereux : cette fois c'est différent.", "John Templeton"),
    ("La volatilité est le prix à payer pour la performance.", "Howard Marks"),
    ("Un portefeuille bien construit résiste à la peur autant qu'à la cupidité.", "Ray Dalio"),
    ("Cash is king quand tout le monde panique.", "Anonyme, Wall Street"),
    ("Les marchés montent par escalier et descendent par ascenseur.", "Proverbe boursier"),
    ("Dans les marchés comme dans la vie, la discipline sépare les gagnants des perdants.", "Paul Tudor Jones"),
    ("Je perds certains jours. Ce qui compte, c'est combien je perds quand j'ai tort.", "George Soros"),
    ("Achetez de belles entreprises à des prix raisonnables.", "Warren Buffett"),
    ("Savoir ce qu'on ne sait pas est plus utile que croire savoir ce qu'on ne sait pas.", "Howard Marks"),
    ("L'or est la mémoire du temps.", "Marc Faber"),
    ("Ne jamais vendre par panique, jamais acheter par euphorie.", "Bernard Baruch"),
    ("Le marché récompense ceux qui pensent à long terme.", "Benjamin Graham"),
    ("Diversifier, c'est admettre qu'on ne sait pas tout.", "Charlie Munger"),
    ("Un bon trader sait perdre. Un mauvais trader ne sait pas s'arrêter.", "Ed Seykota"),
    ("Tout le monde a un plan jusqu'à ce qu'il prenne un coup.", "Mike Tyson"),
    ("Le succès en bourse, c'est 90% de psychologie et 10% d'analyse.", "Peter Lynch"),
]

def get_daily_quote():
    idx = now_paris().timetuple().tm_yday % len(CITATIONS)
    text, author = CITATIONS[idx]
    return f'"{text}"\n— *{author}*'

# ================== GESTION USERS ==================
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
    return load_users().get(str(chat_id), {"plan": "free", "expiry": None, "name": "?", "lang": "fr"})

def is_premium(chat_id):
    if is_admin(chat_id):
        return True
    user = get_user(chat_id)
    if user.get("plan") == "premium":
        exp = user.get("expiry")
        if not exp:
            return True
        return now_paris() < datetime.strptime(exp, "%Y-%m-%d")
    return False

def add_premium(chat_id, name, days):
    users = load_users()
    expiry = (now_paris() + timedelta(days=days)).strftime("%Y-%m-%d")
    if str(chat_id) not in users:
        users[str(chat_id)] = {}
    users[str(chat_id)].update({"plan": "premium", "expiry": expiry, "name": name})
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
        users[str(chat_id)] = {"plan": "free", "expiry": None, "name": name, "lang": "fr"}
        save_users(users)

def set_user_field(chat_id, key, value):
    users = load_users()
    if str(chat_id) not in users:
        users[str(chat_id)] = {"plan": "free", "expiry": None, "name": "?", "lang": "fr"}
    users[str(chat_id)][key] = value
    save_users(users)

# ================== TELEGRAM ==================
def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        if not data.get("ok"):
            print(f"Markdown error: {data.get('description','?')} — retry plain")
            payload.pop("parse_mode", None)
            requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erreur envoi : {e}")

def answer_callback(callback_query_id, text=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_query_id, "text": text}, timeout=5)

# ================== MENUS ==================
def main_menu(chat_id):
    if is_premium(chat_id):
        return {"inline_keyboard": [
            [{"text": "📰 Actu",          "callback_data": "/actu"},
             {"text": "🎰 Pépite",        "callback_data": "/chance"}],
            [{"text": "📈 Signaux",       "callback_data": "/menu_signaux"},
             {"text": "📊 RSI",           "callback_data": "/menu_rsi"}],
            [{"text": "🏆 Top 5",         "callback_data": "/top"},
             {"text": "💬 Citation",      "callback_data": "/quote"}],
            [{"text": "🤖 Wallet IA",     "callback_data": "/aiwallet"}],
            [{"text": "🧰 Mes Outils",    "callback_data": "/menu_outils"}],
            [{"text": "🏠 Accueil",       "callback_data": "/accueil"},
             {"text": "⚙️ Compte",        "callback_data": "/menu_compte"}],
        ]}
    else:
        return {"inline_keyboard": [
            [{"text": "📰 Actu Marché — Gratuit",               "callback_data": "/actu"}],
            [{"text": "🔒 Signaux BUY/SHORT",                   "callback_data": "/premium"},
             {"text": "🔒 RSI",                                 "callback_data": "/premium"}],
            [{"text": "🔒 Pépite du jour",                      "callback_data": "/premium"},
             {"text": "🔒 Top 5 Actions",                       "callback_data": "/premium"}],
            [{"text": "🔒 Paper Trading",                       "callback_data": "/premium"},
             {"text": "🔒 Alertes de prix",                     "callback_data": "/premium"}],
            [{"text": "🔒 Score Marché",                        "callback_data": "/premium"},
             {"text": "🔒 Bilan hebdo",                         "callback_data": "/premium"}],
            [{"text": "🔒 Citation du jour",                    "callback_data": "/premium"}],
            [{"text": "🤖 Wallet IA — PUBLIC 👀",               "callback_data": "/aiwallet"}],
            [{"text": "━━━━━━━━━━━━━━━━━━━━━━━━━━",             "callback_data": "/noop"}],
            [{"text": "👑 PASSER PREMIUM — " + PRIX_MENSUEL + "/mois ⚡", "url": PAYMENT_LINK}],
            [{"text": "🏠 Accueil",  "callback_data": "/accueil"},
             {"text": "⚙️ Compte",  "callback_data": "/menu_compte"},
             {"text": "🛎️ SAV",    "callback_data": "/sav"}],
        ]}

def menu_signaux():
    return {"inline_keyboard": [
        [{"text": "─── 🪙 CRYPTO ───────────", "callback_data": "/noop"}],
        [{"text": "₿ Bitcoin",   "callback_data": "/signal btc"},
         {"text": "🔷 Ethereum", "callback_data": "/signal eth"}],
        [{"text": "🟡 BNB",      "callback_data": "/signal bnb"},
         {"text": "🔵 Solana",   "callback_data": "/signal sol"}],
        [{"text": "🟣 XRP",      "callback_data": "/signal xrp"},
         {"text": "🥇 Gold",     "callback_data": "/signal gold"}],
        [{"text": "─── 📈 ACTIONS ──────────", "callback_data": "/noop"}],
        [{"text": "🍎 Apple",    "callback_data": "/signal aapl"},
         {"text": "🟢 Nvidia",   "callback_data": "/signal nvda"}],
        [{"text": "🔵 Microsoft","callback_data": "/signal msft"},
         {"text": "🚗 Tesla",    "callback_data": "/signal tsla"}],
        [{"text": "📦 Amazon",   "callback_data": "/signal amzn"},
         {"text": "🔍 Google",   "callback_data": "/signal googl"}],
        [{"text": "📘 Meta",     "callback_data": "/signal meta"},
         {"text": "🔴 AMD",      "callback_data": "/signal amd"}],
        [{"text": "🔙 Retour",   "callback_data": "/menu_retour"}],
    ]}

def menu_rsi():
    return {"inline_keyboard": [
        [{"text": "₿ BTC",        "callback_data": "/rsi btc"},
         {"text": "🔷 ETH",       "callback_data": "/rsi eth"}],
        [{"text": "🟡 BNB",       "callback_data": "/rsi bnb"},
         {"text": "🔵 Solana",    "callback_data": "/rsi sol"}],
        [{"text": "🥇 Gold",      "callback_data": "/rsi gold"},
         {"text": "📈 S&P500",    "callback_data": "/rsi sp500"}],
        [{"text": "🍎 Apple",     "callback_data": "/rsi aapl"},
         {"text": "🟢 Nvidia",    "callback_data": "/rsi nvda"}],
        [{"text": "🚗 Tesla",     "callback_data": "/rsi tsla"}],
        [{"text": "🔙 Retour",    "callback_data": "/menu_retour"}],
    ]}

def menu_outils():
    return {"inline_keyboard": [
        [{"text": "🔔 Mes Alertes",        "callback_data": "/menu_alertes"}],
        [{"text": "📊 Paper Trading",      "callback_data": "/menu_paper"}],
        [{"text": "📅 Score Marché",       "callback_data": "/score"}],
        [{"text": "📚 Leçon du moment",    "callback_data": "/lecon"}],
        [{"text": "📈 Ma Performance",     "callback_data": "/performance"}],
        [{"text": "⭐ Donner un avis",     "callback_data": "/avis"}],
        [{"text": "🔙 Retour",            "callback_data": "/menu_retour"}],
    ]}

def menu_compte():
    return {"inline_keyboard": [
        [{"text": "👤 Mon Compte",         "callback_data": "/moncompte"}],
        [{"text": "🌐 Langue",             "callback_data": "/menu_langue"}],
        [{"text": "🤝 Parrainer un ami",   "callback_data": "/parrainage"}],
        [{"text": "👑 Voir les offres",    "callback_data": "/premium"}],
        [{"text": "🛎️ SAV",              "callback_data": "/sav"}],
        [{"text": "🔙 Retour",            "callback_data": "/menu_retour"}],
    ]}

def menu_langue():
    return {"inline_keyboard": [
        [{"text": "🇫🇷 Français",         "callback_data": "/lang fr"},
         {"text": "🇬🇧 English",          "callback_data": "/lang en"},
         {"text": "🇪🇸 Español",          "callback_data": "/lang es"}],
        [{"text": "🔙 Retour",            "callback_data": "/menu_compte"}],
    ]}

def menu_alertes(chat_id):
    user = get_user(chat_id)
    alertes = user.get("alertes", [])
    rows = []
    for i, a in enumerate(alertes):
        rows.append([{"text": f"❌ Suppr. {a['asset']} @ {a['price']}", "callback_data": f"/alerte_del {i}"}])
    rows.append([{"text": "➕ Nouvelle alerte",  "callback_data": "/alerte_new"}])
    rows.append([{"text": "🔙 Retour",           "callback_data": "/menu_outils"}])
    return {"inline_keyboard": rows}

def menu_paper(chat_id):
    user = get_user(chat_id)
    balance = user.get("paper_balance", 10000)
    return {"inline_keyboard": [
        [{"text": f"💰 Solde : {balance:,.2f}$",  "callback_data": "/noop"}],
        [{"text": "📥 Acheter (BUY)",              "callback_data": "/paper_buy"},
         {"text": "📤 Vendre (SELL)",              "callback_data": "/paper_sell"}],
        [{"text": "📋 Mon Portefeuille",           "callback_data": "/paper_portfolio"}],
        [{"text": "📊 Mes Performances",           "callback_data": "/paper_perf"}],
        [{"text": "🔄 Réinitialiser (10 000$)",    "callback_data": "/paper_reset"}],
        [{"text": "🔙 Retour",                     "callback_data": "/menu_outils"}],
    ]}

# ================== DONNÉES MARCHÉ ==================
# ============================================================
# Cache global — rafraîchi en arrière-plan uniquement
# Les threads utilisateurs lisent instantanément, sans jamais attendre
# ============================================================
_news_cache = {}
_news_list_cache = []
_market_cache = ""
_price_cache = {}         # {ticker: float} — prix unitaires
_cache_ts = 0
_CACHE_TTL = 300          # 5 min
_cache_lock = threading.Lock()
_cache_refreshing = False  # évite les doubles refreshs simultanés

def _do_refresh_cache():
    """Appelé UNIQUEMENT en arrière-plan — ne jamais appeler depuis un thread user"""
    global _news_cache, _news_list_cache, _market_cache, _price_cache, _cache_ts, _cache_refreshing
    import time as _time
    if _cache_refreshing:
        return  # déjà en cours
    _cache_refreshing = True
    try:
        # 1. News
        articles = []
        url_api = "https://newsapi.org/v2/top-headlines"
        for params in [
            {"apiKey": NEWSAPI_KEY, "pageSize": 10, "category": "business", "language": "en"},
            {"apiKey": NEWSAPI_KEY, "pageSize": 8,  "category": "general",  "language": "fr", "country": "fr"},
        ]:
            try:
                r = requests.get(url_api, params=params, timeout=8)
                if r.status_code == 200:
                    articles.extend(r.json().get("articles", []))
            except: pass
        valid = [a for a in articles[:12] if a.get("title") and a.get("description")]
        with _cache_lock:
            _news_cache = {str(i): {"title": a["title"], "description": a.get("description",""), "url": a.get("url","")} for i, a in enumerate(valid)}
            _news_list_cache = [f"- {a['title']} : {a.get('description','')[:150]}..." for a in valid]

        # 2. Marché (yfinance — lent, fait séparément)
        try:
            MKTMAP = {"BTC-USD":"₿ Bitcoin","ETH-USD":"🔷 Ethereum","GC=F":"🥇 Or",
                      "^GSPC":"📈 S&P 500","^DJI":"📊 Dow Jones","^IXIC":"💻 Nasdaq",
                      "AAPL":"🍎 Apple","MSFT":"🔵 Microsoft","NVDA":"🟢 Nvidia",
                      "TSLA":"🚗 Tesla","AMZN":"📦 Amazon"}
            data_raw = _yf_safe(TICKERS, period="2d")
            data = data_raw["Close"] if data_raw is not None and not data_raw.empty else None
            if data is None: raise Exception("yf cache timeout")
            latest = data.iloc[-1]; chg = data.pct_change().iloc[-1] * 100
            lines = []; prices = {}
            for tk in TICKERS:
                try:
                    c = float(chg[tk]); p = float(latest[tk])
                    lines.append(f"{'🟢' if c >= 0 else '🔴'} *{MKTMAP.get(tk,tk)}*: {p:,.2f} ({c:+.2f}%)")
                    prices[tk] = p
                except: pass
            with _cache_lock:
                _market_cache = "\n".join(lines)
                _price_cache.update(prices)
        except Exception as e:
            print(f"Cache marché: {e}")

        _cache_ts = _time.time()
        print(f"Cache OK: {len(_news_list_cache)} news | {len(_market_cache)} chars")
    except Exception as e:
        print(f"Erreur cache: {e}")
    finally:
        _cache_refreshing = False

def _refresh_cache_if_needed():
    """Lance un refresh en arrière-plan si le cache est périmé — RETOURNE IMMÉDIATEMENT"""
    import time as _time
    if _time.time() - _cache_ts < _CACHE_TTL and _news_list_cache:
        return  # cache frais, rien à faire
    threading.Thread(target=_do_refresh_cache, daemon=True).start()

def get_news():
    """Retourne les news du cache — déclenche un refresh bg si périmé"""
    _refresh_cache_if_needed()  # lance en bg si besoin, retour immédiat
    with _cache_lock:
        return list(_news_list_cache) if _news_list_cache else ["Marché : données en cours de chargement..."]

def get_news_with_buttons():
    """Retourne les boutons news — utilise le cache instantanément"""
    _refresh_cache_if_needed()
    keyboard = []
    with _cache_lock:
        for i, art in _news_cache.items():
            title = art["title"][:80]
            keyboard.append([{"text": f"🔍 {title[:40]}...", "callback_data": f"/news_deep {i}"}])
    return "", keyboard

def cmd_news_deep(chat_id, idx_str):
    """Analyse approfondie d'une news avec Groq"""
    news = _news_cache.get(str(idx_str)) or _news_cache.get(idx_str)
    if not news:
        send_message(chat_id, "Cette news n'est plus disponible. Recharge l'actu.")
        return
    lang = get_lang(chat_id)
    instr = {"fr": "Analyse en français", "en": "Analysis in English", "es": "Análisis en español"}.get(lang, "Analyse en français")
    send_message(chat_id, "🔍 _Analyse en cours..._")
    prompt = f"""{instr}. Tu es un analyste financier senior. Analyse cette actualite pour un investisseur particulier.

TITRE: {news['title']}
DESCRIPTION: {news['description']}

Fournis:
1. RÉSUMÉ : Ce qui s'est passé en 2 phrases simples
2. IMPACT MARCHÉ : Quels actifs (actions, crypto, matieres premieres) sont affectés et comment
3. OPPORTUNITÉ : Y a-t-il un trade potentiel ? (BUY/SHORT/HOLD) — sois précis
4. RISQUES : Quels sont les risques à surveiller
5. HORIZON : Court terme (1-3j) / Moyen terme (1-4 semaines)

Format téléphone, utilise des emojis, max 400 mots."""
    try:
        analyse = call_groq(prompt, max_tokens=600, temperature=0.3, model="llama-3.1-8b-instant")
        header = {"fr": "🔍 *ANALYSE APPROFONDIE*\n\n📰 _" + news['title'][:80] + "_\n\n", "en": "🔍 *DEEP ANALYSIS*\n\n📰 _" + news['title'][:80] + "_\n\n", "es": "🔍 *ANÁLISIS PROFUNDO*\n\n📰 _" + news['title'][:80] + "_\n\n"}.get(lang, "")
        btns = [[{"text": "📈 Voir les signaux", "callback_data": "/menu_signaux"}], [{"text": "📊 RSI", "callback_data": "/menu_rsi"}], [{"text": "🔙 Retour actu", "callback_data": "/actu"}]]
        send_message(chat_id, header + analyse, reply_markup={"inline_keyboard": btns})
    except Exception as e:
        print(f"Erreur news_deep: {e}")
        send_message(chat_id, "Erreur lors de l'analyse. Réessaie.")

def get_market_data():
    _refresh_cache_if_needed()  # lance en bg si périmé, retour immédiat
    with _cache_lock:
        return _market_cache if _market_cache else "Données marché en cours..."

def get_asset_price(ticker):
    """Retourne le prix — priorité au cache marché, sinon yf.fast_info"""
    # 1. Prix dans le cache (mis à jour toutes les 5 min)
    if ticker in _price_cache:
        return _price_cache[ticker]
    # 2. Fallback: yf.fast_info avec timeout
    try:
        def _get_fast():
            info = yf.Ticker(ticker).fast_info
            return getattr(info, 'last_price', None) or getattr(info, 'regularMarketPrice', None)
        future = _yf_executor.submit(_get_fast)
        price = future.result(timeout=5)
        if price:
            _price_cache[ticker] = float(price)
            return float(price)
    except: pass
    # 3. Fallback final: yf.download
    try:
        data_raw = _yf_safe(ticker, period="2d")
        if data_raw is None or data_raw.empty: return None
        data = data_raw["Close"]
        vals = [float(v) for v in data.values.flatten() if str(v) != 'nan']
        if vals:
            _price_cache[ticker] = vals[-1]
            return vals[-1]
    except: pass
    return None

# ============================================================
# yfinance SAFE WRAPPER — timeout strict 8s
# yf.download peut geler indéfiniment sur Railway sans ce wrapper
# ============================================================
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
_yf_executor = ThreadPoolExecutor(max_workers=4)

def _yf_safe(ticker, period="2d", interval="1d", auto_adjust=False, extra_cols=False):
    """yf.download avec timeout strict 8s — jamais bloquant"""
    def _dl():
        return yf.download(ticker, period=period, interval=interval,
                           auto_adjust=auto_adjust, progress=False)
    try:
        future = _yf_executor.submit(_dl)
        return future.result(timeout=8)
    except FuturesTimeout:
        print(f"⚠️ yf timeout: {ticker} ({period}) — skip")
        return None
    except Exception as e:
        print(f"⚠️ yf error: {ticker}: {e}")
        return None

def get_asset_data(ticker, period="5d"):
    data = _yf_safe(ticker, period=period)
    if data is None or data.empty: return []
    close = data["Close"]
    return [float(v) for v in close.dropna().values.flatten() if str(v) != 'nan']

# Cache RSI par ticker (valable 30 min)
_rsi_cache = {}  # {ticker: (value, timestamp)}
_RSI_TTL = 1800  # 30 min

def compute_rsi(ticker, period=14):
    import time as _t
    # Retourne le RSI depuis le cache si récent
    if ticker in _rsi_cache:
        cached_val, cached_ts = _rsi_cache[ticker]
        if _t.time() - cached_ts < _RSI_TTL:
            return cached_val
    try:
        data = _yf_safe(ticker, period="60d", auto_adjust=True)
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
        val = float(rsi.iloc[-1])
        result = None if pd.isna(val) else val
        if result is not None:
            _rsi_cache[ticker] = (result, _t.time())
        return result
    except Exception as e:
        print(f"RSI error {ticker}: {e}")
        return None

def get_top5():
    tickers = ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META","AMD","NFLX","ORCL"]
    data_raw = _yf_safe(tickers, period="2d")
    if data_raw is None or data_raw.empty: return "Données top5 indisponibles"
    data = data_raw["Close"]
    chg = data.pct_change().iloc[-1] * 100
    latest = data.iloc[-1]
    sorted_t = chg.dropna().sort_values(ascending=False)
    lines = ["🏆 *TOP 5 ACTIONS DU JOUR*\n"]
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
    for i, (tk, c) in enumerate(sorted_t.head(5).items()):
        lines.append(f"{medals[i]} *{tk}*: {float(latest[tk]):,.2f} ({float(c):+.2f}%)")
    lines.append("\n📉 *FLOP 3 DU JOUR*")
    for tk, c in sorted_t.tail(3).iloc[::-1].items():
        lines.append(f"🔴 *{tk}*: {float(latest[tk]):,.2f} ({float(c):+.2f}%)")
    return "\n".join(lines)

# ================== IA ==================
def call_groq(prompt, max_tokens=1100, temperature=0.4, model=None):
    """Appel Groq avec gestion rate limit + logs détaillés"""
    import time as _t
    target_model = model or GROQ_MODEL
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1", timeout=30.0)
    _log_groq_call()
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature, max_tokens=max_tokens
            )
            return r.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            # Rate limit → attendre et réessayer
            if "429" in err_str or "rate_limit" in err_str.lower() or "Too Many Requests" in err_str:
                wait = 60 * (attempt + 1)
                print(f"⚠️ Groq rate limit (tentative {attempt+1}/3) — attente {wait}s | model={target_model}")
                _t.sleep(wait)
                continue
            # Auth error → inutile de réessayer
            if "401" in err_str or "403" in err_str or "invalid_api_key" in err_str.lower():
                print(f"🔴 Groq AUTH ERROR: {err_str[:200]}")
                raise
            # Modèle déprécié
            if "decommissioned" in err_str or "deprecated" in err_str:
                print(f"🔴 Groq MODEL ERROR: {err_str[:200]}")
                raise
            print(f"🔴 Groq erreur (tentative {attempt+1}/3): {err_str[:200]}")
            if attempt < 2:
                _t.sleep(5)
    raise Exception(f"Groq indisponible après 3 tentatives (model={target_model})")

# ---- Compteur d'appels Groq (pour debug quota) ----
import time as _time_module
_groq_call_log = []  # timestamps des appels

def _log_groq_call():
    now_ts = _time_module.time()
    _groq_call_log.append(now_ts)
    # Garde seulement les 24 dernières heures
    cutoff = now_ts - 86400
    while _groq_call_log and _groq_call_log[0] < cutoff:
        _groq_call_log.pop(0)
    count = len(_groq_call_log)
    if count in [50, 80, 100]:
        print(f"⚠️ QUOTA GROQ: {count} appels dans les dernières 24h")
        try:
            send_message(int(TELEGRAM_CHAT_ID), f"⚠️ *Quota Groq* : {count} appels/24h\nApproximation limite free tier: ~100-200/jour selon le modèle.")
        except: pass
    return count

def generate_summary(news_list, market_str, lang="fr"):
    today = now_paris().strftime('%d/%m/%Y')
    if lang == "en":
        instr = "Answer in English with emojis, phone format:"
    elif lang == "es":
        instr = "Responde en español con emojis, formato teléfono:"
    else:
        instr = "Réponds en français avec emojis, format téléphone :"
    prompt = f"""You are a senior financial analyst. Today: {today}
NEWS: {chr(10).join(news_list)}
MARKETS: {market_str}
{instr}
*SUMMARY* (6-8 key points)
*MARKET DIRECTION* -> Each asset: direction + probability % + short explanation
*CONCLUSION*: General trend + probability
Max 3500 characters."""
    return call_groq(prompt, max_tokens=1100, model="llama-3.1-8b-instant")


# ================== LECONS HEBDOMADAIRES ==================
LECONS = [
    {
        "titre": "RSI — Quand acheter, quand vendre",
        "corps": (
            "*Le RSI (Relative Strength Index)*\n\n"
            "Le RSI mesure la force d'un mouvement de 0 a 100.\n\n"
            "SURVENDU (RSI < 30)\n"
            "Le marche a trop baisse, rebond potentiel.\n"
            "Signal d'ACHAT pour les traders aguerris.\n\n"
            "SURACHETE (RSI > 70)\n"
            "Le marche a trop monte, correction possible.\n"
            "Moment de PRUDENCE ou de VENTE partielle.\n\n"
            "NEUTRE (30-70) : Pas de signal fort, attendre.\n\n"
            "Astuce pro : Combine le RSI avec la tendance (SMA) pour de meilleurs resultats.\n\n"
            "_Notre IA utilise le RSI 14j sur tous ses trades._"
        )
    },
    {
        "titre": "MACD — Lire les croisements",
        "corps": (
            "*Le MACD (Moving Average Convergence Divergence)*\n\n"
            "Detecte les changements de tendance grace a 2 lignes :\n"
            "- La ligne MACD (rapide)\n"
            "- La ligne Signal (lente)\n\n"
            "Croisement HAUSSIER : MACD passe AU-DESSUS du Signal\n"
            "Tendance qui s'inverse a la hausse -> signal d'ACHAT\n\n"
            "Croisement BAISSIER : MACD passe EN-DESSOUS du Signal\n"
            "Tendance qui s'inverse a la baisse -> signal de VENTE\n\n"
            "L'histogramme : difference entre les deux lignes.\n"
            "Barres vertes croissantes = momentum haussier.\n"
            "Barres rouges croissantes = momentum baissier.\n\n"
            "_Notre IA surveille les croisements MACD 12/26/9 en temps reel._"
        )
    },
    {
        "titre": "Support & Resistance — Les niveaux cles",
        "corps": (
            "*Support & Resistance*\n\n"
            "Ces niveaux sont les planchers et plafonds invisibles du marche.\n\n"
            "Le Support : Zone ou le prix rebondit vers le haut.\n"
            "Le marche refuse de descendre en-dessous.\n"
            "Ideal pour ACHETER (risque limite).\n\n"
            "La Resistance : Zone ou le prix bute vers le bas.\n"
            "Le marche refuse de depasser ce niveau.\n"
            "Ideal pour VENDRE ou eviter d'acheter.\n\n"
            "La regle d'or :\n"
            "Un ancien support casse devient une resistance.\n"
            "Une ancienne resistance cassee devient un support.\n\n"
            "_Notre IA calcule le support et la resistance sur 20 jours glissants._"
        )
    },
    {
        "titre": "Les SMA — Suivre la tendance",
        "corps": (
            "*Moyennes Mobiles (SMA)*\n\n"
            "La SMA lisse le prix pour reveler la tendance profonde.\n\n"
            "SMA 20 = Tendance court terme (1 mois)\n"
            "SMA 50 = Tendance moyen terme (2 mois)\n"
            "SMA 200 = Tendance long terme (annee)\n\n"
            "Prix AU-DESSUS de la SMA20 -> Tendance haussiere -> favorise les achats.\n"
            "Prix EN-DESSOUS de la SMA20 -> Tendance baissiere -> prudence.\n\n"
            "La Croix d'Or : SMA20 passe au-dessus de SMA50 = signal haussier puissant.\n"
            "La Croix de la Mort : SMA20 passe en-dessous de SMA50 = signal baissier fort.\n\n"
            "_Notre IA utilise SMA20 et SMA50 pour valider chaque trade._"
        )
    },
    {
        "titre": "Gestion du risque — La regle des 1%",
        "corps": (
            "*Gestion du Risque*\n\n"
            "La regle la plus importante : proteger son capital.\n\n"
            "La regle des 1-2% :\n"
            "Ne jamais risquer plus de 1-2% de son capital sur un seul trade.\n"
            "Sur 10 000$ -> max 200$ de perte par trade.\n\n"
            "Le Stop Loss : ordre automatique qui vend si le prix descend trop.\n"
            "Notre IA utilise un stop loss automatique a -8%.\n\n"
            "Le Take Profit : vend quand l'objectif est atteint.\n"
            "Notre IA prend ses profits a +18%.\n\n"
            "Le ratio Risk/Reward :\n"
            "Vise toujours au moins 1:2 (risquer 1 pour gagner 2).\n"
            "Avec un winrate de 50%, tu es rentable !\n\n"
            "_Notre IA applique ces regles sur chaque trade automatiquement._"
        )
    },
    {
        "titre": "Les volumes — La verite du marche",
        "corps": (
            "*Les Volumes*\n\n"
            "Le volume = le nombre de transactions. C'est le carburant des mouvements.\n\n"
            "Principe cle : Un mouvement est fiable s'il est accompagne de volumes eleves.\n\n"
            "Hausse + Volume fort -> Tendance haussiere solide.\n"
            "Hausse + Volume faible -> Mefiance, mouvement peu credible.\n"
            "Baisse + Volume fort -> Tendance baissiere solide.\n"
            "Baisse + Volume faible -> Correction temporaire, possible rebond.\n\n"
            "Le ratio de volume :\n"
            "Comparer le volume actuel a la moyenne des 20 derniers jours.\n"
            "Volume x2 = signal fort et fiable.\n"
            "Volume < 0.5x = signal faible a ignorer.\n\n"
            "_Notre IA calcule le ratio de volume sur 20j pour valider ses signaux._"
        )
    },
]

def get_this_week_lesson():
    """Retourne la leçon de la semaine courante (rotation sur 6 semaines)"""
    week_num = int(now_paris().strftime("%W"))
    return LECONS[week_num % len(LECONS)]

def load_lesson_sent():
    if os.path.exists(LESSON_SENT_FILE):
        try:
            with open(LESSON_SENT_FILE) as f: return json.load(f)
        except: pass
    return {}

def save_lesson_sent(data):
    with open(LESSON_SENT_FILE, "w") as f: json.dump(data, f)


# ================== PRICE TRACKING (alertes mouvements forts) ==================
def load_price_tracking():
    if os.path.exists(PRICE_TRACKING_FILE):
        try:
            with open(PRICE_TRACKING_FILE) as f: return json.load(f)
        except: pass
    return {}

def save_price_tracking(data):
    with open(PRICE_TRACKING_FILE, "w") as f: json.dump(data, f)

MOVE_WATCH = {
    "BTC-USD":  ("₿ Bitcoin",   "btc"),
    "ETH-USD":  ("🔷 Ethereum", "eth"),
    "NVDA":     ("🟢 Nvidia",   "nvda"),
    "TSLA":     ("🚗 Tesla",    "tsla"),
    "AAPL":     ("🍎 Apple",    "aapl"),
    "META":     ("📘 Meta",     "meta"),
    "AMZN":     ("📦 Amazon",   "amzn"),
    "GC=F":     ("🥇 Or",       "gold"),
}

def check_strong_moves():
    """Détecte les mouvements >5% sur les actifs clés et notifie TOUS les utilisateurs"""
    tracking = load_price_tracking()
    now_str = now_paris().strftime("%Y-%m-%d")
    tickers = list(MOVE_WATCH.keys())
    try:
        data_raw = _yf_safe(tickers, period="2d")
        if data_raw is None or data_raw.empty: return
        data = data_raw["Close"]
        if data.empty: return
        chg = data.pct_change().iloc[-1] * 100
        current = data.iloc[-1]
        users = load_users()
        all_ids = set([int(TELEGRAM_CHAT_ID)] + [int(uid) for uid in users.keys()])
        for ticker, (name, key) in MOVE_WATCH.items():
            try:
                pct = float(chg[ticker])
                price = float(current[ticker])
                if abs(pct) < 5.0: continue
                alert_key = f"{ticker}_{now_str}_{int(abs(pct)//5)}"
                if tracking.get(alert_key): continue
                tracking[alert_key] = True
                direction = "monté" if pct > 0 else "chuté"
                icon = "🚀" if pct > 0 else "📉"
                signal_dir = "BUY" if pct > 0 else "SHORT"
                # Message pour TOUS
                msg_free = (
                    f"{icon} *{name}* vient de {direction} de *{abs(pct):.1f}%* aujourd'hui !\n\n"
                    f"💰 Prix actuel : *{price:,.2f}$*\n\n"
                    f"🔒 Nos membres Premium ont reçu le signal *{signal_dir}* "
                    f"bien avant ce mouvement.\n\n"
                    f"⚡ *Rejoins Premium pour ne plus rater ces opportunités.*"
                )
                msg_premium = (
                    f"{icon} *MOUVEMENT FORT — {name}*\n\n"
                    f"Variation : *{pct:+.1f}%* — Prix : *{price:,.2f}$*\n\n"
                    f"📊 Consulte le signal *{signal_dir}* dans le menu Signaux pour l'analyse complète."
                )
                for uid in all_ids:
                    try:
                        if is_premium(uid):
                            send_message(uid, msg_premium, reply_markup={"inline_keyboard":[
                                [{"text": f"📈 Voir signal {name}", "callback_data": f"/signal {key}"}],
                                [{"text": "🔙 Menu", "callback_data": "/menu_retour"}]
                            ]})
                        else:
                            send_message(uid, msg_free, reply_markup={"inline_keyboard":[
                                [{"text": f"👑 Rejoindre Premium — {PRIX_MENSUEL}/mois", "url": PAYMENT_LINK}],
                                [{"text": "🔙 Menu", "callback_data": "/menu_retour"}]
                            ]})
                    except: pass
                print(f"MOUVEMENT FORT: {name} {pct:+.1f}%")
            except: continue
        save_price_tracking(tracking)
    except Exception as e:
        print(f"Erreur check_strong_moves: {e}")


# ================== PARRAINAGE ==================
import hashlib

def generate_referral_code(chat_id):
    """Génère un code de parrainage unique et stable"""
    return "REF" + hashlib.md5(str(chat_id).encode()).hexdigest()[:6].upper()

def cmd_parrainage(chat_id, user_name):
    code = generate_referral_code(chat_id)
    user = get_user(chat_id)
    filleuls = user.get("referrals", [])
    bonus_days = user.get("referral_bonus_days", 0)
    bot_username = "MonResumeMarche_bot"
    link = f"https://t.me/{bot_username}?start={code}"
    msg = (
        f"*TON PROGRAMME DE PARRAINAGE*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Invite tes amis et gagnez *7 jours Premium GRATUITS* chacun !\n\n"
        f"🔗 *Ton lien unique :*\n`{link}`\n\n"
        f"📋 *Ton code :* `{code}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Amis parraines : *{len(filleuls)}*\n"
        f"🎁 Jours bonus gagnes : *{bonus_days} jours*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Comment ca marche ?*\n"
        f"1. Partage ton lien ou code\n"
        f"2. Ton ami rejoint et passe Premium\n"
        f"3. Vous gagnez tous les 2 *7 jours gratuits* !\n\n"
        f"_Les jours s\'ajoutent automatiquement a ton abonnement._"
    )
    send_message(chat_id, msg, reply_markup={"inline_keyboard": [
        [{"text": "🔙 Retour", "callback_data": "/menu_retour"}]
    ]})


def apply_referral(new_chat_id, ref_code, new_name):
    """Applique le parrainage quand un nouveau user arrive avec un code"""
    users = load_users()
    # Trouver le parrain
    parrain_id = None
    for uid, u in users.items():
        if generate_referral_code(int(uid)) == ref_code.upper():
            parrain_id = uid
            break
    if not parrain_id or parrain_id == str(new_chat_id):
        return False
    # Enregistrer le filleul chez le parrain
    if "referrals" not in users[parrain_id]:
        users[parrain_id]["referrals"] = []
    if str(new_chat_id) not in users[parrain_id]["referrals"]:
        users[parrain_id]["referrals"].append(str(new_chat_id))
        users[parrain_id]["referral_bonus_days"] = users[parrain_id].get("referral_bonus_days", 0) + 7
    # Enregistrer le parrain chez le filleul (pour bonus futur)
    if str(new_chat_id) not in users:
        users[str(new_chat_id)] = {"plan": "free", "expiry": None, "name": new_name, "lang": "fr"}
    users[str(new_chat_id)]["referred_by"] = parrain_id
    users[str(new_chat_id)]["pending_bonus"] = 7  # 7 jours offerts à l\'activation premium
    save_users(users)
    # Notifier le parrain
    send_message(int(parrain_id),
        "\U0001f389 *Nouveau filleul !*\n\n"
        f"*{new_name}* vient de rejoindre via ton lien.\n"
        "Des qu'il active son Premium, vous gagnez tous les deux *7 jours gratuits* !"
    )
    return True

def apply_referral_bonus_on_premium(chat_id):
    """Appele quand admin active le premium d'un utilisateur"""
    user = get_user(chat_id)
    if user.get("pending_bonus", 0) > 0:
        bonus = user.get("pending_bonus", 0)
        set_user_field(chat_id, "pending_bonus", 0)
        send_message(chat_id,
            f"+{bonus} jours offerts grace au parrainage !\n"
            "Bienvenue dans le cercle Premium."
        )
    parrain_id = user.get("referred_by")
    if parrain_id:
        parrain = get_user(int(parrain_id))
        bonus_days = parrain.get("referral_bonus_days", 0)
        if parrain.get("plan") == "premium" and bonus_days > 0:
            exp = parrain.get("expiry")
            if exp:
                new_exp = (datetime.strptime(exp, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")
                set_user_field(int(parrain_id), "expiry", new_exp)
                set_user_field(int(parrain_id), "referral_bonus_days", max(0, bonus_days - 7))
                send_message(int(parrain_id),
                    "+7 jours offerts !\n\n"
                    f"Ton abonnement prolonge jusqu'au {new_exp}."
                )

def generate_trade_signal(asset_name, ticker, news_list, lang="fr"):
    prices = get_asset_data(ticker)
    if len(prices) < 2:
        return "Insufficient data."
    pc = prices[-1]
    chg = ((pc - prices[-2]) / prices[-2]) * 100
    sma = sum(prices) / len(prices)
    today = now_paris().strftime('%d/%m/%Y %H:%M')
    lang_instr = {"fr": "Réponds en français", "en": "Answer in English", "es": "Responde en español"}
    prompt = f"""Professional trader. {today} — {asset_name}
Price: {pc:,.2f} | Change: {chg:+.2f}% | SMA5: {sma:,.2f}
5d prices: {', '.join([f'{p:,.2f}' for p in prices])}
News: {chr(10).join(news_list[:6])}
{lang_instr.get(lang,'Réponds en français')} avec emojis :
*SIGNAL*: BUY 🟢 ou SHORT 🔴 | *CONVICTION*: XX%
*TECHNIQUE*: 2 lines | *FUNDAMENTAL*: 2 lines
*TARGET*: price | *STOP LOSS*: level | *CONCLUSION*: 1 sentence
Max 1200 chars."""
    return call_groq(prompt, max_tokens=600, temperature=0.3)

def generate_market_score():
    """Score global du marché de 0 à 100"""
    try:
        data_raw = _yf_safe(["BTC-USD","^GSPC","^IXIC","GC=F"], period="5d")
        if data_raw is None or data_raw.empty: return "Score indisponible"
        data = data_raw["Close"]
        chg = data.pct_change().iloc[-1] * 100
        scores = []
        for tk in ["BTC-USD","^GSPC","^IXIC","GC=F"]:
            c = float(chg[tk])
            scores.append(min(100, max(0, 50 + c * 5)))
        score = int(sum(scores) / len(scores))
        if score >= 70:
            sentiment = "🟢 *Haussier*"
            conseil = "Les marchés sont en forme. Momentum positif."
        elif score >= 45:
            sentiment = "🟡 *Neutre*"
            conseil = "Marchés indécis. Prudence et sélectivité."
        else:
            sentiment = "🔴 *Baissier*"
            conseil = "Pression vendeuse. Gestion du risque prioritaire."
        filled = "█" * (score // 10)
        empty = "░" * (10 - score // 10)
        bar = filled + empty
        return score, sentiment, conseil, bar
    except Exception as e:
        return 50, "🟡 *Neutre*", "Données indisponibles.", "█████░░░░░"

def generate_weekly_report(news_list, market_str, lang="fr"):
    today = now_paris().strftime('%d/%m/%Y')
    lang_instr = {"fr": "Réponds en français", "en": "Answer in English", "es": "Responde en español"}
    prompt = f"""Senior financial analyst. Week ending {today}.
MARKETS THIS WEEK: {market_str}
NEWS THIS WEEK: {chr(10).join(news_list)}
{lang_instr.get(lang,'Réponds en français')} avec emojis, format téléphone :
*BILAN DE LA SEMAINE* (5-6 points majeurs)
*ACTIFS GAGNANTS & PERDANTS* cette semaine
*TENDANCES À SURVEILLER* la semaine prochaine
*PROBABILITÉS* pour la semaine à venir
Max 3500 chars."""
    return call_groq(prompt, max_tokens=1100, model="llama-3.1-8b-instant")

def generate_hidden_gem(news_list, lang="fr"):
    today = now_paris().strftime('%d/%m/%Y')
    candidates = {
        "RENDER-USD":"Render (RNDR)","INJ-USD":"Injective (INJ)",
        "FET-USD":"Fetch.ai (FET)","OCEAN-USD":"Ocean Protocol",
        "AR-USD":"Arweave (AR)","ROSE-USD":"Oasis (ROSE)",
        "RKLB":"Rocket Lab","IONQ":"IonQ","ACHR":"Archer Aviation",
        "JOBY":"Joby Aviation","LUNR":"Intuitive Machines","SERV":"Serve Robotics",
    }
    tickers = list(candidates.keys())
    try:
        data_raw = _yf_safe(tickers, period="30d")
        if data_raw is None or data_raw.empty: return "Rapport indisponible"
        data = data_raw["Close"]
        chg7 = data.pct_change(periods=7).iloc[-1] * 100
        chg30 = data.pct_change(periods=30).iloc[-1] * 100
        latest = data.iloc[-1]
        info = []
        for tk, name in candidates.items():
            try:
                p,c7,c30 = float(latest[tk]),float(chg7[tk]),float(chg30[tk])
                if not any(pd.isna(x) for x in [p,c7,c30]):
                    info.append(f"- {name}: {p:.4f} | 7d={c7:+.1f}% | 30d={c30:+.1f}%")
            except: continue
    except:
        return "Données indisponibles."
    if not info:
        return "Données de marché indisponibles pour les pépites aujourd'hui."
    prompt = f"""Specialist in undervalued assets. Today: {today}
ASSETS: {chr(10).join(info)}
NEWS: {chr(10).join(news_list[:8])}
Choose ONE with highest short-term explosion potential (1-4 weeks).
Respond in French with emojis:
🎰 *PÉPITE DU JOUR*: [Name]
*POURQUOI*: technical + fundamental + macro (3 points)
*POTENTIEL*: +XX% à +XX% | *HORIZON*: X semaines | *RISQUE*: niveau
*ACHETER SUR*: platform
⚠️ _Pas un conseil financier. Investis ce que tu peux perdre._
Max 1500 chars."""
    return call_groq(prompt, max_tokens=700, temperature=0.6, model="llama-3.1-8b-instant")

# ================== PAPER TRADING ==================
def paper_get_portfolio(chat_id):
    return get_user(chat_id).get("paper_portfolio", {})

def paper_get_balance(chat_id):
    return get_user(chat_id).get("paper_balance", 10000.0)

def paper_buy(chat_id, ticker_key, amount_usd):
    asset = SIGNAL_ASSETS.get(ticker_key)
    if not asset:
        return False, "Actif inconnu."
    ticker, name = asset
    price = get_asset_price(ticker)
    if not price:
        return False, "Prix indisponible."
    balance = paper_get_balance(chat_id)
    if amount_usd > balance:
        return False, f"Solde insuffisant ({balance:,.2f}$)"
    qty = amount_usd / price
    users = load_users()
    uid = str(chat_id)
    if uid not in users:
        users[uid] = {}
    portfolio = users[uid].get("paper_portfolio", {})
    if ticker_key in portfolio:
        total_qty = portfolio[ticker_key]["qty"] + qty
        total_cost = portfolio[ticker_key]["cost"] + amount_usd
        portfolio[ticker_key] = {"qty": total_qty, "cost": total_cost, "name": name, "ticker": ticker}
    else:
        portfolio[ticker_key] = {"qty": qty, "cost": amount_usd, "name": name, "ticker": ticker}
    users[uid]["paper_portfolio"] = portfolio
    users[uid]["paper_balance"] = balance - amount_usd
    if "paper_history" not in users[uid]:
        users[uid]["paper_history"] = []
    users[uid]["paper_history"].append({
        "date": now_paris().strftime("%d/%m/%Y %H:%M"),
        "type": "BUY", "asset": name, "amount": amount_usd, "price": price, "qty": qty
    })
    save_users(users)
    return True, f"✅ *Achat exécuté*\n{name}: {qty:.4f} unités @ {price:,.2f}$\nCoût: {amount_usd:,.2f}$"

def paper_sell(chat_id, ticker_key, pct=100):
    asset = SIGNAL_ASSETS.get(ticker_key)
    if not asset:
        return False, "Actif inconnu."
    ticker, name = asset
    price = get_asset_price(ticker)
    if not price:
        return False, "Prix indisponible."
    users = load_users()
    uid = str(chat_id)
    portfolio = users.get(uid, {}).get("paper_portfolio", {})
    if ticker_key not in portfolio:
        return False, "Tu ne possèdes pas cet actif."
    pos = portfolio[ticker_key]
    qty_sell = pos["qty"] * (pct / 100)
    proceeds = qty_sell * price
    pnl = proceeds - (pos["cost"] * pct / 100)
    pnl_pct = (pnl / (pos["cost"] * pct / 100)) * 100 if pos["cost"] > 0 else 0
    if pct == 100:
        del portfolio[ticker_key]
    else:
        portfolio[ticker_key]["qty"] -= qty_sell
        portfolio[ticker_key]["cost"] -= pos["cost"] * pct / 100
    users[uid]["paper_portfolio"] = portfolio
    users[uid]["paper_balance"] = users[uid].get("paper_balance", 10000) + proceeds
    if "paper_history" not in users[uid]:
        users[uid]["paper_history"] = []
    users[uid]["paper_history"].append({
        "date": now_paris().strftime("%d/%m/%Y %H:%M"),
        "type": "SELL", "asset": name, "amount": proceeds, "price": price, "pnl": pnl
    })
    save_users(users)
    emoji = "🟢" if pnl >= 0 else "🔴"
    return True, (f"✅ *Vente exécutée*\n{name}: {qty_sell:.4f} unités @ {price:,.2f}$\n"
                  f"Reçu: {proceeds:,.2f}$ | {emoji} P&L: {pnl:+,.2f}$ ({pnl_pct:+.1f}%)")

def paper_portfolio_summary(chat_id):
    portfolio = paper_get_portfolio(chat_id)
    balance = paper_get_balance(chat_id)
    if not portfolio:
        return f"💰 *Solde cash*: {balance:,.2f}$\n\n_Aucune position ouverte._"
    lines = [f"💰 *Solde cash*: {balance:,.2f}$\n\n📋 *POSITIONS OUVERTES*"]
    total_value = balance
    total_cost = 0
    for key, pos in portfolio.items():
        price = get_asset_price(pos["ticker"]) or 0
        value = pos["qty"] * price
        pnl = value - pos["cost"]
        pnl_pct = (pnl / pos["cost"]) * 100 if pos["cost"] > 0 else 0
        e = "🟢" if pnl >= 0 else "🔴"
        lines.append(f"{e} *{pos['name']}*: {value:,.2f}$ ({pnl_pct:+.1f}%)")
        total_value += value
        total_cost += pos["cost"]
    initial = 10000.0
    total_pnl = total_value - initial
    total_pnl_pct = (total_pnl / initial) * 100
    e2 = "🟢" if total_pnl >= 0 else "🔴"
    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"{e2} *Valeur totale*: {total_value:,.2f}$")
    lines.append(f"{e2} *P&L total*: {total_pnl:+,.2f}$ ({total_pnl_pct:+.1f}%)")
    return "\n".join(lines)

# ================== ALERTES ==================
def check_alerts():
    users = load_users()
    for uid, user in users.items():
        alertes = user.get("alertes", [])
        triggered = []
        remaining = []
        for a in alertes:
            price = get_asset_price(a.get("ticker", "BTC-USD"))
            if price is None:
                remaining.append(a)
                continue
            cond = a.get("cond", "above")
            if (cond == "above" and price >= a["price"]) or (cond == "below" and price <= a["price"]):
                triggered.append((a, price))
            else:
                remaining.append(a)
        if triggered:
            users[uid]["alertes"] = remaining
            save_users(users)
            for a, price in triggered:
                e = "🚀" if a.get("cond") == "above" else "📉"
                send_message(int(uid),
                    f"🔔 *ALERTE DÉCLENCHÉE !*\n\n"
                    f"{e} *{a['asset']}* a atteint *{price:,.2f}$*\n"
                    f"_(Seuil fixé : {a['price']:,.2f}$)_",
                    reply_markup=main_menu(int(uid))
                )

# ================== COMMANDES ==================
def premium_lock(chat_id):
    send_message(chat_id,
        tr(chat_id, "lock_msg").replace("{price}", PRIX_MENSUEL),
        reply_markup={"inline_keyboard": [
            [{"text": f"{tr(chat_id,'subscribe_btn')} {PRIX_MENSUEL}/mois", "url": PAYMENT_LINK}],
            [{"text": tr(chat_id, "btn_back"), "callback_data": "/menu_retour"}]
        ]}
    )

def cmd_accueil(chat_id, name=""):
    lang = get_lang(chat_id)
    L = LANGS.get(lang, LANGS["fr"])
    if is_premium(chat_id):
        h = now_paris().hour
        sal = L["morning"][0] if 5<=h<12 else L["morning"][1] if 12<=h<18 else L["morning"][2]
        features = {
            "fr": "📰 *Actu* — Résumé + direction des marchés\n📈 *Signaux* — BUY/SHORT sur 14 actifs\n📊 *RSI* — 9 actifs en temps réel\n🏆 *Top 5* — Meilleures actions du jour\n🎰 *Pépite* — Actif sous-coté à fort potentiel\n💬 *Citation* — Sagesse des grands traders\n🔔 *Alertes* — Notifications sur tes prix cibles\n📊 *Paper Trading* — Investis sans risque\n📅 *Score marché* — Santé globale en 1 chiffre",
            "en": "📰 *News* — Summary + market direction\n📈 *Signals* — BUY/SHORT on 14 assets\n📊 *RSI* — 9 assets in real time\n🏆 *Top 5* — Best stocks today\n🎰 *Gem* — Undervalued asset with high potential\n💬 *Quote* — Wisdom from great traders\n🔔 *Alerts* — Notifications on your target prices\n📊 *Paper Trading* — Practice risk-free\n📅 *Market Score* — Global health in 1 number",
            "es": "📰 *Noticias* — Resumen + dirección de mercados\n📈 *Señales* — BUY/SHORT en 14 activos\n📊 *RSI* — 9 activos en tiempo real\n🏆 *Top 5* — Mejores acciones del día\n🎰 *Joya* — Activo infravalorado con alto potencial\n💬 *Cita* — Sabiduría de grandes traders\n🔔 *Alertas* — Notificaciones en tus precios objetivo\n📊 *Paper Trading* — Practica sin riesgo\n📅 *Puntuación* — Salud global del mercado",
        }
        msg = (
            f"━━━━━━━━━━━━━━━━━━━━\n{L['welcome_title']}\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{sal}, *{name}* 👋\n\n{L['tools']}\n\n"
            f"{features.get(lang, features['fr'])}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{L['briefing_auto']}\n{L['hebdo_auto']}\n{L['verified']}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        msgs = {
            "fr": f"🏠 *ASSISTANT MARCHÉ FINANCIER*\n━━━━━━━━━━━━━━━━━━━━\n\n🆓 *GRATUIT* — Actu marché quotidienne\n\n━━━━━━━━━━━━━━━━━━━━\n\n👑 *PREMIUM — {PRIX_MENSUEL}/mois*\n✅ Signaux BUY/SHORT — 14 actifs\n✅ RSI — 9 actifs en temps réel\n✅ Paper Trading sans risque\n✅ Alertes de prix personnalisées\n✅ Score marché quotidien\n✅ Pépite du jour + Citation exclusive\n✅ Briefing auto 8h + Bilan hebdo\n\n━━━━━━━━━━━━━━━━━━━━\n💳 PayPal • ⚡ Accès quasi-instantané\n\n⬇️ *Commence ou passe Premium :*",
            "en": f"🏠 *FINANCIAL MARKET ASSISTANT*\n━━━━━━━━━━━━━━━━━━━━\n\n🆓 *FREE* — Daily market news\n\n━━━━━━━━━━━━━━━━━━━━\n\n👑 *PREMIUM — {PRIX_MENSUEL}/month*\n✅ BUY/SHORT Signals — 14 assets\n✅ RSI — 9 assets in real time\n✅ Risk-free Paper Trading\n✅ Custom price alerts\n✅ Daily market score\n✅ Gem of the day + exclusive quote\n✅ Auto briefing 8h + weekly summary\n\n━━━━━━━━━━━━━━━━━━━━\n💳 PayPal • ⚡ Near-instant access\n\n⬇️ *Start free or go Premium:*",
            "es": f"🏠 *ASISTENTE DE MERCADO FINANCIERO*\n━━━━━━━━━━━━━━━━━━━━\n\n🆓 *GRATIS* — Noticias diarias del mercado\n\n━━━━━━━━━━━━━━━━━━━━\n\n👑 *PREMIUM — {PRIX_MENSUEL}/mes*\n✅ Señales BUY/SHORT — 14 activos\n✅ RSI — 9 activos en tiempo real\n✅ Paper Trading sin riesgo\n✅ Alertas de precio personalizadas\n✅ Puntuación diaria del mercado\n✅ Joya del día + cita exclusiva\n✅ Briefing auto 8h + resumen semanal\n\n━━━━━━━━━━━━━━━━━━━━\n💳 PayPal • ⚡ Acceso casi instantáneo\n\n⬇️ *Empieza gratis o ve a Premium:*",
        }
        msg = msgs.get(lang, msgs["fr"])
    send_message(chat_id, msg, reply_markup=main_menu(chat_id))

def cmd_start(chat_id, name=""):
    register_user(chat_id, name)
    cmd_accueil(chat_id, name)

def cmd_welcome_premium(chat_id, name):
    msgs = {
        "fr": "✨ ✨ ✨\n\n*Bienvenue dans le cercle Premium.*\n\n✨ ✨ ✨",
        "en": "✨ ✨ ✨\n\n*Welcome to the Premium circle.*\n\n✨ ✨ ✨",
        "es": "✨ ✨ ✨\n\n*Bienvenido al círculo Premium.*\n\n✨ ✨ ✨",
    }
    lang = get_lang(chat_id)
    send_message(chat_id, msgs.get(lang, msgs["fr"]))
    time.sleep(1)
    quote = get_daily_quote()
    bodies = {
        "fr": f"━━━━━━━━━━━━━━━━━━━━\n💎 *TON ACCÈS VIP EST ACTIF*\n━━━━━━━━━━━━━━━━━━━━\n\nTu rejoins une sélection d'investisseurs qui reçoivent chaque jour les meilleures analyses, vérifiées par des professionnels de la finance.\n\n🌅 Dès demain matin à *8h00*, ton briefing t'attendra.\n📅 Chaque dimanche soir, ton bilan de la semaine.\n\n━━━━━━━━━━━━━━━━━━━━\n💬 *Citation du jour*\n\n_{quote}_\n━━━━━━━━━━━━━━━━━━━━\n\n⬇️ *Explore tes outils exclusifs :*",
        "en": f"━━━━━━━━━━━━━━━━━━━━\n💎 *YOUR VIP ACCESS IS ACTIVE*\n━━━━━━━━━━━━━━━━━━━━\n\nYou join a select group of investors receiving the best market analyses daily, verified by financial professionals.\n\n🌅 Starting tomorrow at *8:00 AM*, your briefing will be waiting.\n📅 Every Sunday evening, your weekly summary.\n\n━━━━━━━━━━━━━━━━━━━━\n💬 *Quote of the day*\n\n_{quote}_\n━━━━━━━━━━━━━━━━━━━━\n\n⬇️ *Explore your exclusive tools:*",
        "es": f"━━━━━━━━━━━━━━━━━━━━\n💎 *TU ACCESO VIP ESTÁ ACTIVO*\n━━━━━━━━━━━━━━━━━━━━\n\nTe unes a un grupo selecto de inversores que reciben cada día los mejores análisis de mercado, verificados por profesionales.\n\n🌅 Desde mañana a las *8:00*, tu briefing te esperará.\n📅 Cada domingo por la noche, tu resumen semanal.\n\n━━━━━━━━━━━━━━━━━━━━\n💬 *Cita del día*\n\n_{quote}_\n━━━━━━━━━━━━━━━━━━━━\n\n⬇️ *Explora tus herramientas exclusivas:*",
    }
    send_message(chat_id, bodies.get(lang, bodies["fr"]).format(quote=quote), reply_markup=main_menu(chat_id))

def menu_retour_msg(chat_id):
    if is_premium(chat_id):
        h = now_paris().hour
        fn = get_user(chat_id).get("name","").split()[0] if get_user(chat_id).get("name") else ""
        fn_str = f", {fn}" if fn else ""
        if 5  <= h < 12: key = "menu_return_morning"
        elif 12 <= h < 14: key = "menu_return_noon"
        elif 14 <= h < 18: key = "menu_return_us"
        elif 18 <= h < 22: key = "menu_return_evening"
        else:              key = "menu_return_night"
        phrases = tr(chat_id, key)
        phrase = random.choice(phrases).format(fn_str)
        msg = phrase
    else:
        msg = tr(chat_id, "menu_return_free")
    send_message(chat_id, msg, reply_markup=main_menu(chat_id))


def cmd_lecon(chat_id):
    """Affiche la leçon de la semaine"""
    lecon = get_this_week_lesson()
    send_message(chat_id, lecon["corps"], reply_markup={"inline_keyboard": [
        [{"text": "📚 Prochaine leçon", "callback_data": "/lecon_next"}],
        [{"text": "🔙 Retour", "callback_data": "/menu_retour"}]
    ]})

def cmd_lecon_next(chat_id):
    """Leçon aléatoire différente de la semaine"""
    week_num = int(now_paris().strftime("%W"))
    idx = (week_num + random.randint(1, len(LECONS)-1)) % len(LECONS)
    lecon = LECONS[idx]
    send_message(chat_id, lecon["corps"], reply_markup={"inline_keyboard": [
        [{"text": "📚 Autre leçon", "callback_data": "/lecon_next"}],
        [{"text": "🔙 Retour", "callback_data": "/menu_retour"}]
    ]})

def cmd_premium_page(chat_id):
    """Page Premium avec plan mensuel ET annuel"""
    lang = get_lang(chat_id)
    msgs = {
        "fr": (
            f"👑 *PASSER PREMIUM*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Signaux BUY/SHORT — 14 actifs\n"
            f"✅ RSI en temps réel — 9 actifs\n"
            f"✅ Paper Trading sans risque\n"
            f"✅ Alertes de prix personnalisées\n"
            f"✅ Score marché quotidien\n"
            f"✅ Pépite du jour + Citation exclusive\n"
            f"✅ Briefing auto 8h + Bilan hebdo\n"
            f"✅ Mode Apprentissage (1 leçon/semaine)\n"
            f"✅ Wallet IA en temps réel\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *Plan mensuel :* {PRIX_MENSUEL}/mois\n"
            f"💎 *Plan annuel :* {PRIX_ANNUEL}/an\n"
            f"   ➜ _Économise 2 mois ! (≈ {PRIX_MENSUEL} x 10)_\n\n"
            f"1️⃣ Choisis ton plan → 2️⃣ Paie → 3️⃣ Envoie la confirmation ici\n"
            f"⚡ Accès quasi-instantané"
        ),
        "en": (
            f"👑 *GO PREMIUM*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ BUY/SHORT Signals — 14 assets\n"
            f"✅ Real-time RSI — 9 assets\n"
            f"✅ Risk-free Paper Trading\n"
            f"✅ Custom price alerts\n"
            f"✅ Daily market score\n"
            f"✅ Gem of the day + exclusive quote\n"
            f"✅ Auto briefing 8h + weekly summary\n"
            f"✅ Learning mode (1 lesson/week)\n"
            f"✅ Live AI Wallet\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *Monthly:* {PRIX_MENSUEL}/month\n"
            f"💎 *Annual:* {PRIX_ANNUEL}/year\n"
            f"   ➜ _Save 2 months!_\n\n"
            f"1️⃣ Choose plan → 2️⃣ Pay → 3️⃣ Send confirmation\n"
            f"⚡ Near-instant access"
        ),
        "es": (
            f"👑 *IR A PREMIUM*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Señales BUY/SHORT — 14 activos\n"
            f"✅ RSI en tiempo real — 9 activos\n"
            f"✅ Paper Trading sin riesgo\n"
            f"✅ Alertas de precio personalizadas\n"
            f"✅ Puntuación diaria del mercado\n"
            f"✅ Joya del día + cita exclusiva\n"
            f"✅ Briefing auto 8h + resumen semanal\n"
            f"✅ Modo Aprendizaje (1 lección/semana)\n"
            f"✅ Wallet IA en vivo\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *Plan mensual:* {PRIX_MENSUEL}/mes\n"
            f"💎 *Plan anual:* {PRIX_ANNUEL}/año\n"
            f"   ➜ _¡Ahorra 2 meses!_\n\n"
            f"1️⃣ Elige plan → 2️⃣ Paga → 3️⃣ Envía confirmación\n"
            f"⚡ Acceso casi instantáneo"
        ),
    }
    send_message(chat_id, msgs.get(lang, msgs["fr"]), reply_markup={"inline_keyboard": [
        [{"text": f"💳 Mensuel — {PRIX_MENSUEL}/mois", "url": PAYMENT_LINK},
         {"text": f"💎 Annuel — {PRIX_ANNUEL}/an", "url": PAYMENT_LINK_ANNUEL}],
        [{"text": "🤝 Parrainer un ami", "callback_data": "/parrainage"}],
        [{"text": "🔙 Retour", "callback_data": "/menu_retour"}]
    ]})

def cmd_moncompte(chat_id):
    user = get_user(chat_id)
    lang = get_lang(chat_id)
    if is_admin(chat_id):
        send_message(chat_id, "🛡️ *COMPTE ADMIN*\nAccès illimité.",
            reply_markup={"inline_keyboard": [[{"text": tr(chat_id,"btn_back"), "callback_data": "/menu_retour"}]]})
    elif is_premium(chat_id):
        exp      = user.get("expiry", "Illimité")
        balance  = user.get("paper_balance", 10000)
        alertes  = len(user.get("alertes", []))
        titles   = {"fr":"━━━━━━━━━━━━━━━━━━━━\n💎 *CARTE MEMBRE PREMIUM*\n━━━━━━━━━━━━━━━━━━━━",
                    "en":"━━━━━━━━━━━━━━━━━━━━\n💎 *PREMIUM MEMBER CARD*\n━━━━━━━━━━━━━━━━━━━━",
                    "es":"━━━━━━━━━━━━━━━━━━━━\n💎 *TARJETA MIEMBRO PREMIUM*\n━━━━━━━━━━━━━━━━━━━━"}
        expiry_label = {"fr":f"📅 Valable jusqu'au : *{exp}*","en":f"📅 Valid until: *{exp}*","es":f"📅 Válido hasta: *{exp}*"}
        paper_label  = {"fr":f"💰 Paper Trading : *{balance:,.2f}$*","en":f"💰 Paper Trading: *{balance:,.2f}$*","es":f"💰 Paper Trading: *{balance:,.2f}$*"}
        alert_label  = {"fr":f"🔔 Alertes actives : *{alertes}*","en":f"🔔 Active alerts: *{alertes}*","es":f"🔔 Alertas activas: *{alertes}*"}
        send_message(chat_id,
            f"{titles.get(lang,titles['fr'])}\n\n"
            f"👤 *{user.get('name','Membre')}*\n"
            f"{tr(chat_id,'account_status')}\n"
            f"{expiry_label.get(lang,expiry_label['fr'])}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{paper_label.get(lang,paper_label['fr'])}\n"
            f"{alert_label.get(lang,alert_label['fr'])}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{tr(chat_id,'account_thanks')}",
            reply_markup={"inline_keyboard": [
                [{"text": tr(chat_id,"btn_sav"),  "callback_data": "/sav"}],
                [{"text": tr(chat_id,"btn_back"), "callback_data": "/menu_retour"}]
            ]}
        )
    else:
        msgs = {"fr":f"👤 *TON COMPTE*\n━━━━━━━━━━━━━━━━━━━━\n\nNom : *{user.get('name','Membre')}*\nStatut : 🆓 Gratuit\n\nPasse Premium pour tout débloquer ⚡",
                "en":f"👤 *YOUR ACCOUNT*\n━━━━━━━━━━━━━━━━━━━━\n\nName: *{user.get('name','Member')}*\nStatus: 🆓 Free\n\nGo Premium to unlock everything ⚡",
                "es":f"👤 *TU CUENTA*\n━━━━━━━━━━━━━━━━━━━━\n\nNombre: *{user.get('name','Miembro')}*\nEstado: 🆓 Gratuito\n\nPasa a Premium para desbloquear todo ⚡"}
        send_message(chat_id, msgs.get(lang, msgs["fr"]),
            reply_markup={"inline_keyboard": [
                [{"text": f"{tr(chat_id,'subscribe_btn')} {PRIX_MENSUEL}/mois", "url": PAYMENT_LINK}],
                [{"text": tr(chat_id,"btn_back"), "callback_data": "/menu_retour"}]
            ]}
        )

def cmd_actu(chat_id):
    lang = get_lang(chat_id)
    send_message(chat_id, tr(chat_id, "processing"))
    news_text, news_keyboard = get_news_with_buttons()
    news = get_news()
    market = get_market_data()
    summary = generate_summary(news, market, lang)
    titles = {"fr": "📊 *RÉSUMÉ MARCHÉ", "en": "📊 *MARKET SUMMARY", "es": "📊 *RESUMEN MERCADO"}
    if is_premium(chat_id):
        send_message(chat_id, f"{titles.get(lang,'📊 *RÉSUMÉ')} — {now_paris().strftime('%d/%m/%Y %H:%M')}*\n\n{summary}")
        deep_lbl = {"fr":"📰 *ACTUALITÉS*\n_Appuie sur une news pour l'analyse approfondie :_","en":"📰 *NEWS*\n_Tap a headline for in-depth analysis:_","es":"📰 *NOTICIAS*\n_Toca un titular para análisis profundo:_"}.get(lang,"📰 *ACTUALITÉS*")
        news_keyboard.append([{"text": "🔙 Menu", "callback_data": "/menu_retour"}])
        send_message(chat_id, deep_lbl, reply_markup={"inline_keyboard": news_keyboard})
    else:
        # Utilisateur gratuit : résumé + signal partiel FOMO + compteur
        send_message(chat_id, f"{titles.get(lang,'📊 *RÉSUMÉ')} — {now_paris().strftime('%d/%m/%Y %H:%M')}*\n\n{summary}")
        # Signal partiel — direction flouttée
        teaser = _generate_signal_teaser(news)
        if teaser:
            send_message(chat_id, teaser)
        # Compteur FOMO
        h = now_paris().hour
        signals_sent = 3 if 9 <= h < 14 else 2 if 14 <= h < 20 else 1
        fomo = {
            "fr": (
                f"🔒 *{signals_sent} signaux envoyés aux membres Premium ce matin*\n\n"
                f"Ils savent déjà sur quel actif trader — et dans quelle direction.\n\n"
                f"*Plan mensuel :* {PRIX_MENSUEL}/mois\n"
                f"*Plan annuel :* {PRIX_ANNUEL}/an _(2 mois offerts !)_\n\n"
                f"⚡ Accès quasi-instantané après paiement."
            ),
            "en": (
                f"🔒 *{signals_sent} signals sent to Premium members this morning*\n\n"
                f"They already know which asset to trade — and in which direction.\n\n"
                f"*Monthly:* {PRIX_MENSUEL}/month\n"
                f"*Annual:* {PRIX_ANNUEL}/year _(2 months free!)_\n\n"
                f"⚡ Near-instant access after payment."
            ),
            "es": (
                f"🔒 *{signals_sent} señales enviadas a miembros Premium esta mañana*\n\n"
                f"Ya saben en qué activo operar — y en qué dirección.\n\n"
                f"*Plan mensual:* {PRIX_MENSUEL}/mes\n"
                f"*Plan anual:* {PRIX_ANNUEL}/año _(2 meses gratis!)_\n\n"
                f"⚡ Acceso casi instantáneo tras el pago."
            ),
        }
        send_message(chat_id, fomo.get(lang, fomo["fr"]), reply_markup={"inline_keyboard": [
            [{"text": f"💳 {PRIX_MENSUEL}/mois", "url": PAYMENT_LINK},
             {"text": f"💎 {PRIX_ANNUEL}/an", "url": PAYMENT_LINK_ANNUEL}],
            [{"text": tr(chat_id,"btn_menu"), "callback_data": "/menu_retour"}]
        ]})

def _generate_signal_teaser(news_list):
    """Génère un signal partiel (direction + actif) sans la raison, pour créer du FOMO"""
    assets_teaser = [
        ("₿ Bitcoin",  "BUY 🟢"),  ("🟢 Nvidia",  "BUY 🟢"),
        ("📘 Meta",    "SHORT 🔴"), ("🚗 Tesla",   "BUY 🟢"),
        ("🔷 Ethereum","BUY 🟢"),  ("🍎 Apple",   "SHORT 🔴"),
    ]
    pick = random.choice(assets_teaser)
    asset_name, direction = pick
    blurred = "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
    return (
        f"📡 *APERÇU SIGNAL PREMIUM*\n\n"
        f"Actif : *{asset_name}*\n"
        f"Direction : *{direction}*\n"
        f"Raison : _{blurred}_\n"
        f"Prix cible : _{blurred}_\n"
        f"Stop loss : _{blurred}_\n\n"
        f"🔒 _Débloque l\'analyse complète avec Premium._"
    )

def cmd_signal(chat_id, asset_key):
    if not is_premium(chat_id): return premium_lock(chat_id)
    asset = SIGNAL_ASSETS.get(asset_key)
    if not asset:
        send_message(chat_id, tr(chat_id,"error"), reply_markup=menu_signaux()); return
    ticker, name = asset
    lang = get_lang(chat_id)
    send_message(chat_id, tr(chat_id, "signal_analyzing").format(name))
    news = get_news()
    signal = generate_trade_signal(name, ticker, news, lang)
    title = {"fr":"📈 *SIGNAL","en":"📈 *SIGNAL","es":"📈 *SEÑAL"}.get(lang,"📈 *SIGNAL")
    send_message(chat_id, f"{title} {name} — {now_paris().strftime('%d/%m/%Y %H:%M')}*\n\n{signal}")
    send_message(chat_id, tr(chat_id, "signal_other"), reply_markup=menu_signaux())

def cmd_rsi(chat_id, asset_key):
    if not is_premium(chat_id): return premium_lock(chat_id)
    asset = RSI_ASSETS.get(asset_key)
    if not asset:
        send_message(chat_id, tr(chat_id,"error"), reply_markup=menu_rsi()); return
    ticker, name = asset
    lang = get_lang(chat_id)
    send_message(chat_id, tr(chat_id,"rsi_analyzing").format(name))
    try:
        val = compute_rsi(ticker)
        if val is None:
            send_message(chat_id, tr(chat_id,"no_data"))
            send_message(chat_id, tr(chat_id,"rsi_other"), reply_markup=menu_rsi())
            return
        if val < 30:
            zone    = tr(chat_id, "rsi_oversold")
            bar     = "🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜"
            conseil = tr(chat_id, "rsi_buy_hint")
        elif val > 70:
            zone    = tr(chat_id, "rsi_overbought")
            bar     = "🟩🟩🟩🟩🟩🟩🟩🟥🟥🟥"
            conseil = tr(chat_id, "rsi_sell_hint")
        else:
            zone    = tr(chat_id, "rsi_neutral")
            bar     = "🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜"
            conseil = tr(chat_id, "rsi_wait_hint")
        val_label  = {"fr":"Valeur","en":"Value","es":"Valor"}.get(lang,"Valeur")
        zone_label = {"fr":"Zone","en":"Zone","es":"Zona"}.get(lang,"Zone")
        send_message(chat_id,
            f"*📊 RSI (14) — {name}*\n\n"
            f"{bar}\n"
            f"{val_label} : *{val:.1f} / 100*\n\n"
            f"{zone_label} : {zone}\n"
            f"💡 _{conseil}_\n\n"
            f"{tr(chat_id,'rsi_legend')}"
        )
        send_message(chat_id, tr(chat_id,"rsi_other"), reply_markup=menu_rsi())
    except Exception as e:
        print(f"Erreur RSI {ticker}: {e}")
        send_message(chat_id, tr(chat_id,"error"))
        send_message(chat_id, tr(chat_id,"rsi_other"), reply_markup=menu_rsi())

def cmd_top(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    send_message(chat_id, tr(chat_id, "top_loading"))
    try:
        send_message(chat_id, get_top5())
    except Exception as e:
        print(f"Erreur top5: {e}")
        send_message(chat_id, tr(chat_id, "error"))
    menu_retour_msg(chat_id)

def cmd_chance(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    send_message(chat_id, tr(chat_id, "gem_searching"))
    try:
        lang = get_lang(chat_id)
        gem = generate_hidden_gem(get_news(), lang)
        title = {"fr": "🎰 *PÉPITE DU JOUR", "en": "🎰 *GEM OF THE DAY", "es": "🎰 *JOYA DEL DÍA"}.get(lang, "🎰 *PÉPITE DU JOUR")
        send_message(chat_id, f"{title} — {now_paris().strftime('%d/%m/%Y %H:%M')}*\n\n{gem}")
    except Exception as e:
        print(e); send_message(chat_id, tr(chat_id, "error"))
    menu_retour_msg(chat_id)

def cmd_quote(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    title = {"fr": "💬 *CITATION DU JOUR", "en": "💬 *QUOTE OF THE DAY", "es": "💬 *CITA DEL DÍA"}.get(get_lang(chat_id), "💬 *CITATION DU JOUR")
    send_message(chat_id,
        f"{title} — {now_paris().strftime('%d/%m/%Y')}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n{get_daily_quote()}\n\n━━━━━━━━━━━━━━━━━━━━",
        reply_markup={"inline_keyboard": [[{"text": tr(chat_id,"btn_menu"), "callback_data": "/menu_retour"}]]}
    )

def cmd_score(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    lang = get_lang(chat_id)
    score, _, _, bar = generate_market_score()
    if score >= 70:
        sentiment = tr(chat_id, "score_bullish")
        conseil   = tr(chat_id, "score_bull_tip")
    elif score >= 45:
        sentiment = tr(chat_id, "score_neutral")
        conseil   = tr(chat_id, "score_neut_tip")
    else:
        sentiment = tr(chat_id, "score_bearish")
        conseil   = tr(chat_id, "score_bear_tip")
    title = {"fr":"📅 *SCORE MARCHÉ","en":"📅 *MARKET SCORE","es":"📅 *PUNTUACIÓN MERCADO"}.get(lang,"📅 *SCORE MARCHÉ")
    send_message(chat_id,
        f"{title} — {now_paris().strftime('%d/%m/%Y')}*\n\n"
        f"┌─────────────────┐\n"
        f"│  {bar}  │\n"
        f"│     *{score}/100*          │\n"
        f"└─────────────────┘\n\n"
        f"{tr(chat_id,'score_sentiment')} {sentiment}\n"
        f"💡 _{conseil}_",
        reply_markup={"inline_keyboard": [[{"text": tr(chat_id,"btn_back"), "callback_data": "/menu_outils"}]]}
    )

def cmd_performance(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    user = get_user(chat_id)
    joined = user.get("expiry")
    if joined:
        exp_date = datetime.strptime(joined, "%Y-%m-%d")
        start = exp_date - timedelta(days=30)
    else:
        start = now_paris() - timedelta(days=30)
    try:
        data_raw = _yf_safe(["BTC-USD","^GSPC","NVDA"], period="30d")
        if data_raw is None or data_raw.empty: return
        data = data_raw["Close"]
        chg = {}
        for tk in ["BTC-USD","^GSPC","NVDA"]:
            vals = data[tk].dropna().values
            if len(vals) >= 2:
                chg[tk] = ((vals[-1] - vals[0]) / vals[0]) * 100
        btc_chg = chg.get("BTC-USD", 0)
        sp_chg = chg.get("^GSPC", 0)
        nvda_chg = chg.get("NVDA", 0)
        e_btc = "🟢" if btc_chg >= 0 else "🔴"
        e_sp = "🟢" if sp_chg >= 0 else "🔴"
        e_nv = "🟢" if nvda_chg >= 0 else "🔴"
        balance = user.get("paper_balance", 10000)
        paper_pnl = ((balance - 10000) / 10000) * 100
        e_paper = "🟢" if paper_pnl >= 0 else "🔴"
        send_message(chat_id,
            f"📈 *PERFORMANCE 30 DERNIERS JOURS*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *MARCHÉS*\n"
            f"{e_btc} Bitcoin : *{btc_chg:+.1f}%*\n"
            f"{e_sp} S&P 500 : *{sp_chg:+.1f}%*\n"
            f"{e_nv} Nvidia : *{nvda_chg:+.1f}%*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *TON PAPER TRADING*\n"
            f"{e_paper} P&L : *{paper_pnl:+.1f}%*\n"
            f"💰 Solde : *{balance:,.2f}$* (départ 10 000$)\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup={"inline_keyboard": [[{"text": "🔙 Retour", "callback_data": "/menu_outils"}]]}
        )
    except Exception as e:
        print(e); send_message(chat_id, "❌ Erreur performance.")

def cmd_avis(chat_id, name=""):
    if not is_premium(chat_id): return premium_lock(chat_id)
    user = get_user(chat_id)
    if user.get("avis_done"):
        already = {"fr":"⭐ *Tu as déjà laissé un avis. Merci !* 🙏","en":"⭐ *You already left a review. Thank you!* 🙏","es":"⭐ *Ya dejaste una reseña. ¡Gracias!* 🙏"}
        send_message(chat_id, already.get(get_lang(chat_id), already["fr"]),
            reply_markup={"inline_keyboard": [[{"text": tr(chat_id,"btn_back"), "callback_data": "/menu_outils"}]]})
        return
    titles  = {"fr":"⭐ *DONNE TON AVIS*\n\nTon retour nous aide à améliorer le bot.\n\n*Comment notes-tu ton expérience ?*",
               "en":"⭐ *LEAVE A REVIEW*\n\nYour feedback helps us improve the bot.\n\n*How do you rate your experience?*",
               "es":"⭐ *DEJA TU RESEÑA*\n\nTu opinión nos ayuda a mejorar el bot.\n\n*¿Cómo valoras tu experiencia?*"}
    ratings = {"fr":[("⭐⭐⭐⭐⭐ Excellent","/avis_5"),("⭐⭐⭐⭐ Bien","/avis_4"),("⭐⭐⭐ Correct","/avis_3"),("⭐⭐ Peut mieux faire","/avis_2")],
               "en":[("⭐⭐⭐⭐⭐ Excellent","/avis_5"),("⭐⭐⭐⭐ Good","/avis_4"),("⭐⭐⭐ OK","/avis_3"),("⭐⭐ Needs work","/avis_2")],
               "es":[("⭐⭐⭐⭐⭐ Excelente","/avis_5"),("⭐⭐⭐⭐ Bueno","/avis_4"),("⭐⭐⭐ Correcto","/avis_3"),("⭐⭐ Mejorable","/avis_2")]}
    lang = get_lang(chat_id)
    rs = ratings.get(lang, ratings["fr"])
    send_message(chat_id, titles.get(lang, titles["fr"]), reply_markup={"inline_keyboard": [
        [{"text": rs[0][0], "callback_data": rs[0][1]}, {"text": rs[1][0], "callback_data": rs[1][1]}],
        [{"text": rs[2][0], "callback_data": rs[2][1]}, {"text": rs[3][0], "callback_data": rs[3][1]}],
        [{"text": tr(chat_id,"btn_back"), "callback_data": "/menu_outils"}],
    ]})

def cmd_avis_note(chat_id, name, note):
    stars = "⭐" * note
    set_user_field(chat_id, "avis_done", True)
    set_user_field(chat_id, "sav_motif", f"[AVIS {note}★]")
    msgs = {"fr":f"{stars} *Merci pour ton avis !*\n\n_Si tu as un commentaire, écris-le maintenant._\n_(ou Retour pour ignorer)_",
            "en":f"{stars} *Thank you for your review!*\n\n_Feel free to add a comment now._\n_(or Back to skip)_",
            "es":f"{stars} *¡Gracias por tu reseña!*\n\n_Puedes añadir un comentario ahora._\n_(o Volver para omitir)_"}
    send_message(chat_id, msgs.get(get_lang(chat_id), msgs["fr"]),
        reply_markup={"inline_keyboard": [[{"text": tr(chat_id,"btn_back"), "callback_data": "/menu_outils"}]]})
    send_message(TELEGRAM_CHAT_ID, f"⭐ *NOUVEL AVIS*\n👤 {name} | {stars}\n🆔 `{chat_id}`")

def cmd_alerte_new(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    send_message(chat_id,
        "🔔 *NOUVELLE ALERTE DE PRIX*\n\n"
        "Écris ton alerte dans ce format :\n\n"
        "`alerte btc 100000 above`\n"
        "_→ Préviens-moi quand BTC dépasse 100 000$_\n\n"
        "`alerte eth 2000 below`\n"
        "_→ Préviens-moi quand ETH passe sous 2 000$_\n\n"
        "Actifs disponibles : btc, eth, bnb, sol, xrp, gold, aapl, nvda, msft, tsla, amzn, googl, meta, amd",
        reply_markup={"inline_keyboard": [[{"text": "🔙 Retour", "callback_data": "/menu_alertes"}]]}
    )
    set_user_field(chat_id, "sav_motif", "[ALERTE_NEW]")

def cmd_alerte_del(chat_id, idx):
    users = load_users()
    uid = str(chat_id)
    alertes = users.get(uid, {}).get("alertes", [])
    if 0 <= idx < len(alertes):
        removed = alertes.pop(idx)
        users[uid]["alertes"] = alertes
        save_users(users)
        send_message(chat_id, f"✅ Alerte supprimée : *{removed['asset']}* @ {removed['price']:,.2f}$",
            reply_markup=menu_alertes(chat_id))
    else:
        send_message(chat_id, "❌ Alerte introuvable.", reply_markup=menu_alertes(chat_id))

def parse_alerte(chat_id, text):
    """Parse 'alerte btc 100000 above' -> add alert"""
    parts = text.strip().lower().split()
    if len(parts) < 3:
        return False
    asset_key = parts[1] if len(parts) > 1 else ""
    asset = SIGNAL_ASSETS.get(asset_key)
    if not asset:
        return False
    try:
        price = float(parts[2])
    except:
        return False
    cond = parts[3] if len(parts) > 3 else "above"
    if cond not in ["above", "below"]:
        cond = "above"
    ticker, name = asset
    users = load_users()
    uid = str(chat_id)
    if uid not in users:
        users[uid] = {}
    if "alertes" not in users[uid]:
        users[uid]["alertes"] = []
    users[uid]["alertes"].append({"asset": name, "ticker": ticker, "price": price, "cond": cond})
    save_users(users)
    cond_fr = "dépasse" if cond == "above" else "passe sous"
    send_message(chat_id,
        f"✅ *Alerte créée !*\n\n"
        f"🔔 {name} — Alerte quand le prix *{cond_fr} {price:,.2f}$*\n\n"
        f"Tu recevras une notification automatiquement.",
        reply_markup=menu_alertes(chat_id)
    )
    return True

def parse_paper_order(chat_id, text):
    """Parse 'buy btc 500' or 'sell btc 100'"""
    parts = text.strip().lower().split()
    if len(parts) < 3:
        return False
    action = parts[0]
    asset_key = parts[1]
    try:
        amount = float(parts[2])
    except:
        return False
    if action == "buy":
        ok, msg = paper_buy(chat_id, asset_key, amount)
        send_message(chat_id, msg, reply_markup=menu_paper(chat_id))
        return True
    elif action == "sell":
        ok, msg = paper_sell(chat_id, asset_key, int(amount) if amount <= 100 else 100)
        send_message(chat_id, msg, reply_markup=menu_paper(chat_id))
        return True
    return False

def cmd_paper_info(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    send_message(chat_id,
        "📊 *PAPER TRADING*\n\n"
        "Entraîne-toi à investir avec *10 000$ virtuels* — zéro risque réel.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*ACHETER*\n`buy btc 500` → Achète 500$ de Bitcoin\n"
        "`buy aapl 200` → Achète 200$ d'Apple\n\n"
        "*VENDRE*\n`sell btc 100` → Vend 100% de ta position BTC\n"
        "`sell nvda 50` → Vend 50% de ta position Nvidia\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Actifs : btc, eth, bnb, sol, xrp, gold, aapl, nvda, msft, tsla, amzn, googl, meta, amd",
        reply_markup=menu_paper(chat_id)
    )

# ================== SAV ==================
def cmd_sav(chat_id, name=""):
    send_message(chat_id,
        tr(chat_id, "sav_title"),
        reply_markup={"inline_keyboard": [
            [{"text": tr(chat_id, "sav_tech"),       "callback_data": "/sav_tech"}],
            [{"text": tr(chat_id, "sav_payment"),    "callback_data": "/sav_paiement"}],
            [{"text": tr(chat_id, "sav_suggestion"), "callback_data": "/sav_suggestion"}],
            [{"text": tr(chat_id, "sav_other"),      "callback_data": "/sav_autre"}],
            [{"text": tr(chat_id, "btn_back"),       "callback_data": "/menu_retour"}],
        ]}
    )

def cmd_sav_motif(chat_id, name, motif):
    titres = {
        "tech":       tr(chat_id, "sav_tech"),
        "paiement":   tr(chat_id, "sav_payment"),
        "suggestion": tr(chat_id, "sav_suggestion"),
        "autre":      tr(chat_id, "sav_other"),
    }
    titre = titres.get(motif, tr(chat_id, "sav_other"))
    set_user_field(chat_id, "sav_motif", titre)
    send_message(chat_id,
        f"{titre}{tr(chat_id,'sav_write')}",
        reply_markup={"inline_keyboard": [[{"text": tr(chat_id,"btn_back"), "callback_data": "/sav"}]]}
    )

def notify_admin_sav(chat_id, name, text):
    user = get_user(chat_id)
    motif = user.get("sav_motif", "Non précisé")
    plan = "👑 Premium" if is_premium(chat_id) else "🆓 Gratuit"
    send_message(TELEGRAM_CHAT_ID,
        f"🛎️ *NOUVEAU TICKET SAV*\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *{name}* | {plan}\n🆔 `{chat_id}`\n📂 {motif}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n💬 _{text}_\n\n"
        f"↩️ Répondre : `/repondre {chat_id} [message]`"
    )

# ================== ADMIN ==================
def cmd_admin(chat_id, text):
    if not is_admin(chat_id): return
    parts = text.strip().split()
    cmd = parts[0]
    if cmd == "/addpremium" and len(parts) >= 4:
        expiry = add_premium(parts[1], parts[2], int(parts[3]))
        apply_referral_bonus_on_premium(int(parts[1]))
        send_message(chat_id, f"✅ Premium activé : {parts[2]} ({parts[1]}) jusqu'au {expiry}")
        cmd_welcome_premium(int(parts[1]), parts[2])
    elif cmd == "/removepremium" and len(parts) >= 2:
        remove_premium(parts[1]); send_message(chat_id, f"✅ Premium supprimé pour {parts[1]}")
    elif cmd == "/repondre" and len(parts) >= 3:
        msg = " ".join(parts[2:])
        send_message(int(parts[1]), f"📩 *Réponse du Service Client*\n\n{msg}\n\n_Tape /sav pour nous recontacter._")
        send_message(chat_id, f"✅ Réponse envoyée à {parts[1]}")
    elif cmd == "/listusers":
        users = load_users()
        lines = [f"👥 *UTILISATEURS ({len(users)})*\n"]
        for uid, u in users.items():
            plan = "👑" if u.get("plan") == "premium" else "🆓"
            lines.append(f"{plan} {u.get('name','?')} | {uid} | exp: {u.get('expiry','—')}")
        send_message(chat_id, "\n".join(lines))
    elif cmd == "/stats":
        users = load_users()
        total = len(users)
        prem = sum(1 for u in users.values() if u.get("plan") == "premium")
        rev = prem * float(PRIX_MENSUEL.replace("€",""))
        send_message(chat_id,
            f"📈 *STATS BOT*\n\n👥 Total: {total}\n👑 Premium: {prem}\n🆓 Gratuit: {total-prem}\n💰 Revenus estimés: {rev:.2f}€/mois")
    else:
        send_message(chat_id,
            "🛠️ *COMMANDES ADMIN*\n\n"
            "`/addpremium [id] [nom] [jours]`\n`/removepremium [id]`\n"
            "`/repondre [id] [message]`\n`/listusers`\n`/stats`")

# ================== AI WALLET PUBLIC ==================
AI_WALLET_FILE   = "ai_wallet.json"
USER_WALLETS_FILE = "user_wallets.json"
UW_INITIAL        = 10000.0
AI_WALLET_INITIAL = 10000.0
AI_MAX_POSITION_PCT = 0.20
AI_STOP_LOSS_PCT    = 0.08
AI_TAKE_PROFIT_PCT  = 0.18
_wallet_lock = threading.Lock()  # Verrou pour eviter les race conditions

AI_TRADABLE = {
    "btc":   ("BTC-USD",  "₿ Bitcoin"),
    "eth":   ("ETH-USD",  "🔷 Ethereum"),
    "sol":   ("SOL-USD",  "🔵 Solana"),
    "nvda":  ("NVDA",     "🟢 Nvidia"),
    "aapl":  ("AAPL",     "🍎 Apple"),
    "msft":  ("MSFT",     "🔵 Microsoft"),
    "tsla":  ("TSLA",     "🚗 Tesla"),
    "meta":  ("META",     "📘 Meta"),
    "amzn":  ("AMZN",     "📦 Amazon"),
    "gold":  ("GC=F",     "🥇 Or"),
}

def load_ai_wallet():
    with _wallet_lock:
        if os.path.exists(AI_WALLET_FILE):
            try:
                with open(AI_WALLET_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        wallet = {
            "balance": AI_WALLET_INITIAL,
            "portfolio": {},
            "history": [],
            "created": now_paris().strftime("%d/%m/%Y"),
            "last_trade": None,
            "total_trades": 0,
            "winning_trades": 0,
        }
        save_ai_wallet_unsafe(wallet)
        return wallet

def save_ai_wallet_unsafe(wallet):
    """Sauvegarde sans verrou (appeler depuis un bloc _wallet_lock)"""
    with open(AI_WALLET_FILE, "w") as f:
        json.dump(wallet, f, indent=2)

def save_ai_wallet(wallet):
    with _wallet_lock:
        save_ai_wallet_unsafe(wallet)

def ai_wallet_total_value(wallet):
    total = wallet["balance"]
    for key, pos in wallet.get("portfolio", {}).items():
        price = get_asset_price(pos["ticker"]) or pos.get("buy_price", 0)
        is_short = pos.get("type") == "SHORT"
        if is_short:
            # SHORT: valeur = marge initiale + P&L
            # P&L short = (buy_price - current) * qty
            pnl = (pos["buy_price"] - price) * pos["qty"]
            total += pos["qty"] * pos["buy_price"] + pnl
        else:
            total += pos["qty"] * price
    return max(total, 0)  # ne peut pas être négatif

def ai_wallet_pnl(wallet):
    total = ai_wallet_total_value(wallet)
    pnl = total - AI_WALLET_INITIAL
    pnl_pct = (pnl / AI_WALLET_INITIAL) * 100
    return pnl, pnl_pct

def ai_get_technicals(ticker):
    """RSI, MACD, SMA20/50, volume, volatilité, support/résistance"""
    try:
        data = _yf_safe(ticker, period="60d", auto_adjust=True)
        if data.empty or len(data) < 20:
            return {}
        close = data["Close"]
        if hasattr(close, "columns"): close = close.iloc[:, 0]
        close = pd.Series([float(v) for v in close.values.flatten()]).dropna()
        volume = data["Volume"]
        if hasattr(volume, "columns"): volume = volume.iloc[:, 0]
        vol_s = pd.Series([float(v) for v in volume.values.flatten()]).dropna()

        # RSI 14
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = float((100 - 100/(1 + gain/loss)).iloc[-1])

        # SMA 20 / 50
        sma20 = float(close.rolling(20).mean().iloc[-1])
        sma50 = float(close.rolling(min(50,len(close))).mean().iloc[-1])

        # MACD 12/26/9
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_val = float((ema12 - ema26).iloc[-1])
        macd_sig = float((ema12 - ema26).ewm(span=9).mean().iloc[-1])

        # Volume ratio vs moyenne 20j
        avg_vol = float(vol_s.tail(20).mean())
        vol_ratio = float(vol_s.iloc[-1]) / avg_vol if avg_vol > 0 else 1.0

        # Volatilité 14j
        volatility = float(close.pct_change().dropna().tail(14).std() * 100)

        # Variations
        current = float(close.iloc[-1])
        chg1d  = (current - float(close.iloc[-2]))  / float(close.iloc[-2])  * 100 if len(close)>=2  else 0
        chg7d  = (current - float(close.iloc[-7]))  / float(close.iloc[-7])  * 100 if len(close)>=7  else 0
        chg30d = (current - float(close.iloc[-30])) / float(close.iloc[-30]) * 100 if len(close)>=30 else 0

        # Support / Résistance 20j
        high20 = float(close.tail(20).max())
        low20  = float(close.tail(20).min())

        return {
            "rsi": round(rsi, 1),
            "sma20": round(sma20, 2),
            "sma50": round(sma50, 2),
            "vs_sma20": "dessus" if current > sma20 else "dessous",
            "vs_sma50": "dessus" if current > sma50 else "dessous",
            "macd_cross": "haussier" if macd_val > macd_sig else "baissier",
            "vol_ratio": round(vol_ratio, 2),
            "volatility": round(volatility, 2),
            "chg1d": round(chg1d, 2),
            "chg7d": round(chg7d, 2),
            "chg30d": round(chg30d, 2),
            "resistance": round(high20, 2),
            "support": round(low20, 2),
            "dist_resist": round((high20 - current)/current*100, 2),
            "dist_support": round((current - low20)/current*100, 2),
        }
    except Exception as e:
        print(f"Erreur technicals {ticker}: {e}")
        return {}

def generate_ai_trade_decision(news_list, market_str, wallet):
    now = now_paris()

    # Résumé du portefeuille actuel
    portfolio_str = ""
    for key, pos in wallet.get("portfolio", {}).items():
        price = get_asset_price(pos["ticker"]) or pos.get("buy_price", 0)
        is_short = pos.get("type") == "SHORT"
        if is_short:
            pnl_pct = (pos["buy_price"] - price) / pos["buy_price"] * 100
        else:
            pnl_pct = (price - pos["buy_price"]) / pos["buy_price"] * 100
        portfolio_str += f"  - {pos['name']} ({pos.get('type','LONG')}): qty={pos['qty']:.4f} | entry={pos['buy_price']:,.2f}$ | actuel={price:,.2f}$ | P&L={pnl_pct:+.1f}%\n"

    # Indicateurs techniques pour tous les actifs
    tech_str = ""
    for key, (ticker, name) in AI_TRADABLE.items():
        t = ai_get_technicals(ticker)
        if t:
            tech_str += (
                f"  {name} [{key}]: RSI={t['rsi']} | MACD={t['macd_cross']} | "
                f"SMA20={t['vs_sma20']} | SMA50={t['vs_sma50']} | Vol x{t['vol_ratio']} | "
                f"1j={t['chg1d']:+.1f}% 7j={t['chg7d']:+.1f}% 30j={t['chg30d']:+.1f}% | "
                f"Support={t['support']} Résist={t['resistance']}\n"
            )

    total_val = ai_wallet_total_value(wallet)
    win_rate = (wallet["winning_trades"] / wallet["total_trades"] * 100) if wallet["total_trades"] > 0 else 0
    hist_str = "\n".join([
        f"  {h['date']} | {h['type']}{' SHORT' if h.get('short') else ''} | {h['asset']} | P&L={h.get('pnl_pct',0):+.1f}% | {h.get('reason','')}"
        for h in wallet.get("history", [])[-6:]
    ]) or "  Aucun"

    # Détermine la session
    session = "matin" if 5 <= now.hour < 12 else "après-midi" if 12 <= now.hour < 18 else "soir/nuit"
    has_cash = wallet["balance"] > 200
    has_positions = len(wallet.get("portfolio", {})) > 0

    prompt = f"""Tu es ARIA, une IA de trading autonome et DÉCISIVE. Tu gères un portefeuille virtuel public de 10 000$.
Heure Paris : {now.strftime('%d/%m/%Y %H:%M')} — Session : {session}
Cash disponible : {wallet['balance']:,.2f}$ | Valeur totale : {total_val:,.2f}$
Winrate : {win_rate:.0f}% sur {wallet['total_trades']} trades

=== POSITIONS ACTUELLES ===
{portfolio_str or "AUCUNE POSITION — Tu DOIS ouvrir au moins 1 position si le cash > 200$"}

=== HISTORIQUE RECENT ===
{hist_str}

=== ANALYSE TECHNIQUE ===
{tech_str}

=== PRIX MARCHES ===
{market_str}

=== ACTUALITES DU JOUR ===
{chr(10).join(news_list[:12])}

=== MISSION PRIORITAIRE ===
{"IMPORTANT: Tu n'as pas de position ouverte et tu as " + f"{wallet['balance']:,.2f}$ de cash. Tu DOIS trader maintenant." if not has_positions and has_cash else "Gere tes positions et cherche de nouvelles opportunites."}

=== REGLES DE TRADING ===
- Max 20% par actif (soit {total_val*0.20:,.0f}$ max par trade)
- Stop loss auto a -8%, take profit auto a +18%
- SHORT si RSI > 70 ET MACD baissier ET news negative
- VENTE URGENTE si news tres negative sur une position en profit (emergency_sell=true)
- COVER si un short est profitable ET signal inverse
- Conviction MINIMUM 45% pour trader (pas 60%!)
- Max 3 decisions par session
- BIAIS ACTION: Si tu hesites entre HOLD et BUY/SHORT avec conviction 45-60%, PRENDS LE TRADE

=== CONSIGNE SPECIALE ===
Analyse chaque actif. Trouve les opportunites. Un portefeuille qui ne trade pas est un portefeuille qui ne progresse pas.
Si RSI < 35 sur un actif = signal d'achat fort.
Si RSI > 65 sur un actif = surveiller pour short.
Si MACD haussier + prix au-dessus SMA20 = tendance haussiere = BUY.
News positives (ETF, adoption, partenariat, résultats) = opportunite BUY.
News negatives (regulation, fraude, resultats decevants) = SHORT ou SELL urgence.

=== FORMAT REPONSE (JSON pur, rien d'autre) ===
{{
  "decisions": [
    {{
      "action": "BUY" ou "SELL" ou "SHORT" ou "COVER" ou "HOLD",
      "asset_key": "btc",
      "amount_usd": 800,
      "sell_pct": 100,
      "emergency_sell": false,
      "reason": "Raison concise max 90 chars",
      "conviction": 72,
      "technical_basis": "RSI=32 zone survente, MACD croisement haussier",
      "fundamental_basis": "Afflux ETF Bitcoin record cette semaine"
    }}
  ],
  "analyse": "Synthese du contexte en 2 phrases"
}}"""
    try:
        raw = call_groq(prompt, max_tokens=800, temperature=0.35)
        raw = raw.strip()
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1].replace("json","").strip() if len(parts) > 1 else parts[0]
        # Cherche le premier { et le dernier }
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]
        return json.loads(raw)
    except Exception as e:
        print(f"Erreur JSON décision IA: {e}")
        return {"decisions": [{"action": "HOLD", "reason": "Parse error"}], "analyse": ""}

def ai_execute_trades(wallet, decisions):
    executed = []
    for d in decisions:
        action = d.get("action","HOLD").upper()
        if action == "HOLD": continue
        asset_key = d.get("asset_key","")
        asset = AI_TRADABLE.get(asset_key)
        if not asset: continue
        ticker, name = asset
        price = get_asset_price(ticker)
        if not price: continue
        reason    = d.get("reason","")
        conviction = d.get("conviction", 50)
        emergency = d.get("emergency_sell", False)
        tech      = d.get("technical_basis","")
        fund      = d.get("fundamental_basis","")
        portfolio = wallet.get("portfolio", {})
        total_val = ai_wallet_total_value(wallet)

        # ── BUY (LONG) ──
        if action == "BUY":
            amount = min(float(d.get("amount_usd", 500)), wallet["balance"])
            amount = min(amount, total_val * AI_MAX_POSITION_PCT)
            if amount < 10: continue
            qty = amount / price
            short_key = f"{asset_key}_short"
            # Ferme le short inverse automatiquement
            if short_key in portfolio:
                pos = portfolio.pop(short_key)
                short_pnl = (pos["buy_price"] - price) * pos["qty"]
                wallet["balance"] += pos["qty"] * pos["buy_price"] + short_pnl
                wallet["total_trades"] += 1
                if short_pnl >= 0: wallet["winning_trades"] += 1
                executed.append({"type":"COVER","asset":name,"amount":pos["qty"]*price,"price":price,"qty":pos["qty"],"pnl":short_pnl,"pnl_pct":(short_pnl/(pos["buy_price"]*pos["qty"]))*100,"reason":"Auto-cover","conviction":100,"short":True,"tech":"","fund":""})
                portfolio = wallet.get("portfolio",{})
            if asset_key in portfolio:
                tq = portfolio[asset_key]["qty"] + qty
                tc = portfolio[asset_key]["qty"] * portfolio[asset_key]["buy_price"] + amount
                portfolio[asset_key].update({"qty": tq, "buy_price": tc/tq})
            else:
                portfolio[asset_key] = {"qty":qty,"buy_price":price,"name":name,"ticker":ticker,"type":"LONG","date":now_paris().strftime("%d/%m/%Y %H:%M")}
            wallet["portfolio"] = portfolio
            wallet["balance"] -= amount
            wallet["total_trades"] += 1
            executed.append({"type":"BUY","asset":name,"amount":amount,"price":price,"qty":qty,"pnl":0,"pnl_pct":0,"reason":reason,"conviction":conviction,"emergency":False,"short":False,"tech":tech,"fund":fund})

        # ── SHORT ──
        elif action == "SHORT":
            amount = min(float(d.get("amount_usd", 500)), wallet["balance"])
            amount = min(amount, total_val * AI_MAX_POSITION_PCT)
            if amount < 10: continue
            short_key = f"{asset_key}_short"
            if short_key in portfolio: continue  # déjà short
            qty = amount / price
            portfolio[short_key] = {"qty":qty,"buy_price":price,"name":name,"ticker":ticker,"type":"SHORT","date":now_paris().strftime("%d/%m/%Y %H:%M")}
            wallet["portfolio"] = portfolio
            wallet["balance"] -= amount
            wallet["total_trades"] += 1
            executed.append({"type":"SHORT","asset":name,"amount":amount,"price":price,"qty":qty,"pnl":0,"pnl_pct":0,"reason":reason,"conviction":conviction,"emergency":False,"short":True,"tech":tech,"fund":fund})

        # ── COVER (clôture short) ──
        elif action == "COVER":
            short_key = f"{asset_key}_short"
            if short_key not in portfolio: continue
            pos = portfolio.pop(short_key)
            pnl = (pos["buy_price"] - price) * pos["qty"]
            proceeds = pos["qty"] * pos["buy_price"] + pnl
            pnl_pct = pnl / (pos["buy_price"] * pos["qty"]) * 100 if pos["qty"] > 0 else 0
            wallet["portfolio"] = portfolio
            wallet["balance"] += proceeds
            wallet["total_trades"] += 1
            if pnl >= 0: wallet["winning_trades"] += 1
            executed.append({"type":"COVER","asset":name,"amount":proceeds,"price":price,"qty":pos["qty"],"pnl":pnl,"pnl_pct":pnl_pct,"reason":reason,"conviction":conviction,"emergency":False,"short":True,"tech":tech,"fund":fund})

        # ── SELL (long, avec possible urgence news) ──
        elif action == "SELL":
            if asset_key not in portfolio: continue
            pos = portfolio[asset_key]
            sell_pct = min(100, max(1, int(d.get("sell_pct", 100))))
            qty_sell = pos["qty"] * (sell_pct / 100)
            proceeds = qty_sell * price
            pnl = proceeds - pos["buy_price"] * qty_sell
            pnl_pct = pnl / (pos["buy_price"] * qty_sell) * 100 if qty_sell > 0 else 0
            if sell_pct >= 100: del portfolio[asset_key]
            else: portfolio[asset_key]["qty"] -= qty_sell
            wallet["portfolio"] = portfolio
            wallet["balance"] += proceeds
            wallet["total_trades"] += 1
            if pnl >= 0: wallet["winning_trades"] += 1
            executed.append({"type":"SELL","asset":name,"amount":proceeds,"price":price,"qty":qty_sell,"pnl":pnl,"pnl_pct":pnl_pct,"reason":reason,"conviction":conviction,"emergency":emergency,"short":False,"tech":tech,"fund":fund})

    return executed

def ai_check_stops(wallet):
    """Stop loss -8% et take profit +18%, gère LONG et SHORT"""
    auto_closed = []
    portfolio = dict(wallet.get("portfolio", {}))
    for key, pos in list(portfolio.items()):
        price = get_asset_price(pos["ticker"])
        if not price: continue
        is_short = pos.get("type") == "SHORT"
        pnl_pct = ((pos["buy_price"] - price) if is_short else (price - pos["buy_price"])) / pos["buy_price"] * 100
        reason = None
        if pnl_pct <= -(AI_STOP_LOSS_PCT * 100):   reason = f"🛑 Stop loss {pnl_pct:.1f}%"
        elif pnl_pct >= (AI_TAKE_PROFIT_PCT * 100): reason = f"✅ Take profit +{pnl_pct:.1f}%"
        if reason:
            if is_short:
                pnl = (pos["buy_price"] - price) * pos["qty"]
                proceeds = pos["qty"] * pos["buy_price"] + pnl
            else:
                proceeds = pos["qty"] * price
                pnl = proceeds - pos["buy_price"] * pos["qty"]
            del portfolio[key]
            wallet["portfolio"] = portfolio
            wallet["balance"] += proceeds
            wallet["total_trades"] += 1
            if pnl >= 0: wallet["winning_trades"] += 1
            auto_closed.append({"type":"COVER" if is_short else "SELL","asset":pos["name"],"amount":proceeds,"price":price,"qty":pos["qty"],"pnl":pnl,"pnl_pct":pnl_pct,"reason":reason,"conviction":100,"emergency":False,"short":is_short,"tech":"","fund":""})
    return auto_closed

def ai_breaking_news_check():
    """Detects major breaking news every 2h and triggers trade if needed.
    Uses llama-3.1-8b-instant (faster, cheaper) for the detection step."""
    try:
        news = get_news()
        if not news:
            return
        # Utilise le modèle léger pour la détection (économise le quota)
        FAST_MODEL = "llama-3.1-8b-instant"
        news_str = "\n".join(news[:6])
        prompt = f"""Analyse these news headlines. Is there a MAJOR market-moving event?
MAJOR = Fed/ECB rate decision, crypto ETF approval/rejection, company bankruptcy, market crash >5%, geopolitical crisis.
NEWS: {news_str}
Reply ONLY in JSON: {{"breaking": true or false, "summary": "one sentence or empty", "asset": "btc/nvda/tsla/meta/aapl/msft/amzn/sp500 or null"}}"""
        raw = call_groq(prompt, max_tokens=100, temperature=0.1, model=FAST_MODEL)
        raw = raw.strip()
        start_idx = raw.find("{"); end_idx = raw.rfind("}") + 1
        if start_idx >= 0 and end_idx > start_idx:
            raw = raw[start_idx:end_idx]
        result = json.loads(raw)
        if result.get("breaking"):
            summary = result.get("summary","")
            print(f"BREAKING NEWS detectee: {summary}")
            # Lance l'analyse complète avec le modèle 70b
            ai_run_analysis(breaking_news=summary)
        else:
            print(f"News check OK — pas d'urgence ({now_paris().strftime('%H:%M')})")
    except Exception as e:
        print(f"Erreur breaking news check: {e}")


def ai_run_analysis(breaking_news=None):
    """Analyse + trade IA — sessions fixes + breaking news"""
    if not _ai_running.acquire(blocking=False):
        print("IA deja en cours, on skip")
        return
    try:
        tag = f" [BREAKING: {breaking_news[:50]}]" if breaking_news else ""
        print(f"IA Analyse {now_paris().strftime('%H:%M')}{tag}")
        wallet = load_ai_wallet()
        news = get_news()
        if breaking_news:
            news = [f"BREAKING NEWS URGENTE: {breaking_news}"] + news
        market = get_market_data()

        auto_closed = ai_check_stops(wallet)
        result = generate_ai_trade_decision(news, market, wallet)
        executed = ai_execute_trades(wallet, result.get("decisions", []))
        all_trades = auto_closed + executed
        analyse = result.get("analyse", "")

        now_str = now_paris().strftime("%d/%m/%Y %H:%M")
        for trade in all_trades:
            # Cap pnl_pct pour eviter les valeurs aberrantes
            raw_pnl = trade.get("pnl_pct", 0)
            capped_pnl = max(-99.9, min(999.0, raw_pnl))
            wallet["history"].append({
                "date": now_str, "type": trade["type"], "asset": trade["asset"],
                "price": trade["price"], "qty": trade["qty"], "amount": trade["amount"],
                "pnl": trade.get("pnl", 0), "pnl_pct": capped_pnl,
                "reason": trade["reason"], "conviction": trade.get("conviction", 50),
                "short": trade.get("short", False), "emergency": trade.get("emergency", False),
                "tech": trade.get("tech", ""), "fund": trade.get("fund", ""),
            })
        wallet["last_trade"] = now_str
        save_ai_wallet(wallet)

        # Copy trading — applique les trades aux users qui ont activé le copy
        if all_trades:
            aria_size = ai_wallet_total_value(wallet) + sum(t.get("amount",0) for t in all_trades if t["type"] in ["BUY","SHORT"])
            threading.Thread(target=run_copy_trading, args=(all_trades, aria_size), daemon=True).start()

        if not all_trades:
            print(f"IA HOLD — {analyse[:60] if analyse else 'RAS'}")
            return

        total_val = ai_wallet_total_value(wallet)
        pnl_total, pnl_pct = ai_wallet_pnl(wallet)
        # Cap le P&L total affiche
        pnl_pct_display = max(-99.9, min(9999.0, pnl_pct))
        e = "🟢" if pnl_total >= 0 else "🔴"
        icons = {"BUY": "📥", "SELL": "📤", "SHORT": "🔻", "COVER": "🔼"}
        lines_msg = [f"🤖 *WALLET IA — " + now_paris().strftime("%d/%m/%Y %H:%M") + "*\n"]
        if analyse:
            lines_msg.append("📊 _" + analyse + "_\n")
        for trade in all_trades:
            ic = icons.get(trade["type"], "•")
            short_tag = " _(short)_" if trade.get("short") else ""
            emerg_tag = " ⚠️ _urgence_" if trade.get("emergency") else ""
            capped = max(-99.9, min(999.0, trade.get("pnl_pct", 0)))
            pnl_str = f" | P&L *{capped:+.1f}%*" if trade["type"] in ["SELL", "COVER"] else ""
            lines_msg.append(f"{ic} *{trade['type']} {trade['asset']}*{short_tag} @ {trade['price']:,.2f}${pnl_str}{emerg_tag}")
            lines_msg.append(f"   💡 _{trade['reason']}_")
            if trade.get("tech"):
                lines_msg.append(f"   📊 _{trade['tech']}_")
            if trade.get("fund"):
                lines_msg.append(f"   📰 _{trade['fund']}_")
        lines_msg.append("\n" + f"{e} *Wallet : {total_val:,.2f}$* ({pnl_pct_display:+.1f}% depuis creation)")
        msg = "\n".join(lines_msg)

        users = load_users()
        for target in set([TELEGRAM_CHAT_ID] + list(users.keys())):
            try:
                send_message(int(target), msg, reply_markup={"inline_keyboard": [[{"text": "📊 Voir le Wallet IA", "callback_data": "/aiwallet"}]]})
            except:
                pass
        print(f"IA trades: {len(all_trades)} | Wallet: {total_val:,.2f}$")
    except Exception as e:
        print(f"Erreur ai_run_analysis: {e}")
        import traceback; traceback.print_exc()
    finally:
        _ai_running.release()

def ai_daily_trade():
    ai_run_analysis()


def cmd_ai_wallet(chat_id):
    """Affiche le wallet IA — accessible à TOUS"""
    wallet = load_ai_wallet()
    total = ai_wallet_total_value(wallet)
    pnl, pnl_pct = ai_wallet_pnl(wallet)
    e = "🟢" if pnl >= 0 else "🔴"
    win_rate = (wallet["winning_trades"] / wallet["total_trades"] * 100) if wallet["total_trades"] > 0 else 0

    lines = [
        f"🤖 *WALLET IA — PERFORMANCE PUBLIQUE*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📅 Créé le : *{wallet.get('created','—')}*",
        f"💰 Capital départ : *10 000$*",
        f"🕐 Dernier trade : *{wallet.get('last_trade','—')}*",
        f"",
        f"━━━ 📊 RÉSUMÉ ━━━",
        f"{e} Valeur actuelle : *{total:,.2f}$*",
        f"{e} P&L total : *{pnl:+,.2f}$ ({pnl_pct:+.1f}%)*",
        f"🎯 Winrate : *{win_rate:.0f}%* sur *{wallet['total_trades']} trades*",
        f"",
    ]

    portfolio = wallet.get("portfolio", {})
    if portfolio:
        lines.append("━━━ 💼 POSITIONS OUVERTES ━━━")
        for key, pos in portfolio.items():
            price = get_asset_price(pos["ticker"]) or pos["buy_price"]
            is_short = pos.get("type") == "SHORT"
            pos_pnl = ((pos["buy_price"] - price) if is_short else (price - pos["buy_price"])) / pos["buy_price"] * 100
            ep = "🟢" if pos_pnl >= 0 else "🔴"
            tag = " 🔻SHORT" if is_short else ""
            lines.append(f"{ep} *{pos['name']}*{tag} — {pos_pnl:+.1f}% (entrée {pos.get('date','—')})")
        lines.append("")

    history = wallet.get("history", [])
    if history:
        lines.append("━━━ 📋 DERNIERS TRADES ━━━")
        icons = {"BUY":"📥","SELL":"📤","SHORT":"🔻","COVER":"🔼"}
        for h in reversed(history[-8:]):
            ic = icons.get(h["type"],"•")
            short_tag = " _(short)_" if h.get("short") else ""
            emerg_tag = " ⚠️" if h.get("emergency") else ""
            pnl_str = f" ({h.get('pnl_pct',0):+.1f}%)" if h["type"] in ["SELL","COVER"] else ""
            lines.append(f"{ic} {h['date']} — *{h['asset']}*{short_tag}{pnl_str}{emerg_tag}")
            lines.append(f"   _{h.get('reason','')}_")
            if h.get("tech"):  lines.append(f"   📊 _{h['tech']}_")
            if h.get("fund"):  lines.append(f"   📰 _{h['fund']}_")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("_L'IA analyse les marchés 3x/jour et trade en autonomie._")
    lines.append("_Elle utilise RSI, MACD, SMA, volume et actualités._")
    lines.append("_Inspire-toi de ses trades — mais fais ta propre analyse !_")

    send_message(chat_id, "\n".join(lines), reply_markup={
        "inline_keyboard": [
            [{"text": "🔄 Actualiser", "callback_data": "/aiwallet"}],
            [{"text": "👑 Rejoindre Premium", "url": PAYMENT_LINK}] if not is_premium(chat_id)
             else [{"text": "🔙 Menu", "callback_data": "/menu_retour"}],
        ]
    })



auto_sent_today = None
weekly_sent_this_week = None

def check_auto_send():
    global auto_sent_today, weekly_sent_this_week
    now = now_paris()
    today = now.strftime('%Y-%m-%d')
    week = now.strftime('%Y-%W')

    # Briefing quotidien à 8h
    if now.hour == 8 and now.minute < 30 and auto_sent_today != today:
        auto_sent_today = today
        def _send_briefing():
            try:
                users = load_users()
                targets = [TELEGRAM_CHAT_ID] + [uid for uid, u in users.items() if u.get("plan") == "premium"]
                news = get_news(); market = get_market_data(); quote = get_daily_quote()
                summary = generate_summary(news, market)
                for target in set(targets):
                    try:
                        tid = int(target)
                        ud = users.get(str(target), {}); uname = ud.get("name", "")
                        lang = ud.get("lang", "fr")
                        sal = LANGS[lang]["morning"][0]
                        send_message(tid, f"{sal} *{uname}* 👋\n\n💬 _{quote}_\n\n━━━━━━━━━━━━━━━━━━━━\nTon briefing du matin 👇")
                        send_message(tid, f"📊 *RÉSUMÉ MARCHÉ — {now_paris().strftime('%d/%m/%Y')}*\n\n{summary}")
                        send_message(tid, "⬇️", reply_markup=main_menu(tid))
                    except Exception as eu: print(f"Erreur briefing {target}: {eu}")
            except Exception as e: print(f"Erreur 8h: {e}")
        threading.Thread(target=_send_briefing, daemon=True).start()
        print("Briefing 8h lancé en thread")
    if now.weekday() == 6 and now.hour == 19 and now.minute == 0 and weekly_sent_this_week != week:
        weekly_sent_this_week = week
        print("Envoi bilan hebdo dimanche...")
        try:
            users = load_users()
            targets = [TELEGRAM_CHAT_ID] + [uid for uid, u in users.items() if u.get("plan") == "premium"]
            news = get_news(); market = get_market_data()
            for target in set(targets):
                tid = int(target)
                ud = users.get(str(target), {}); lang = ud.get("lang","fr")
                report = generate_weekly_report(news, market, lang)
                send_message(tid, f"📅 *BILAN HEBDOMADAIRE — Semaine du {now.strftime('%d/%m/%Y')}*\n\n{report}")
                menu_retour_msg(tid)
        except Exception as e:
            print(f"Erreur bilan hebdo: {e}")

    # Trading IA : 3 sessions + rattrapage si bot redemarré + breaking news
    for session_name, h_start, h_end in [("morning",9,11),("afternoon",14,16),("evening",19,21)]:
        flag = f"ai_session_{session_name}_{today}"
        if h_start <= now.hour < h_end and not globals().get(flag):
            globals()[flag] = True
            print(f"IA session '{session_name}' ({now.strftime('%H:%M')})")
            try:
                threading.Thread(target=ai_run_analysis, daemon=True).start()
            except Exception as e:
                print(f"Erreur IA session {session_name}: {e}")

    # Breaking news : toutes les 2h (économise le quota Groq)
    news_flag = f"ai_news_{today}_{now.hour // 2}"
    if not globals().get(news_flag) and now.minute == 0 and now.second < 10:
        globals()[news_flag] = True
        try:
            threading.Thread(target=ai_breaking_news_check, daemon=True).start()
        except Exception as e:
            print(f"Erreur breaking news: {e}")


    # Alertes prix + pre-chauffe cache (toutes les 5 min)
    if now.second < 3 and now.minute % 5 == 0:
        try:
            check_alerts()
        except Exception as e:
            print(f"Erreur alertes: {e}")
        # Pre-chauffe le cache en arrière-plan
        threading.Thread(target=_do_refresh_cache, daemon=True).start()

    # Mouvements forts >5% (toutes les 30 min)
    if now.second < 5 and now.minute % 30 == 0:
        move_flag = f"moves_{today}_{now.hour}_{now.minute}"
        if not globals().get(move_flag):
            globals()[move_flag] = True
            try:
                threading.Thread(target=check_strong_moves, daemon=True).start()
            except Exception as e:
                print(f"Erreur mouvements forts: {e}")

    # Leçon hebdomadaire le lundi à 10h
    if now.weekday() == 0 and now.hour == 10 and now.minute == 0:
        lesson_flag = f"lesson_{week}"
        if not globals().get(lesson_flag):
            globals()[lesson_flag] = True
            try:
                sent_data = load_lesson_sent()
                if not sent_data.get(week):
                    lecon = get_this_week_lesson()
                    users = load_users()
                    targets = [TELEGRAM_CHAT_ID] + [uid for uid, u in users.items() if u.get("plan") == "premium"]
                    header = {"fr": "📚 *LEÇON DE LA SEMAINE*", "en": "📚 *LESSON OF THE WEEK*", "es": "📚 *LECCIÓN DE LA SEMANA*"}
                    for target in set(targets):
                        tid = int(target)
                        lang = users.get(str(target), {}).get("lang", "fr")
                        send_message(tid,
                            f"{header.get(lang, header['fr'])}\n\n{lecon['corps']}",
                            reply_markup={"inline_keyboard": [[{"text": "📚 Voir plus de leçons", "callback_data": "/lecon_next"}]]}
                        )
                    sent_data[week] = True
                    save_lesson_sent(sent_data)
                    print(f"Leçon envoyée: {lecon['titre']}")
            except Exception as e:
                print(f"Erreur lecon: {e}")


# ════════════════════════════════════════════════════════════════
# USER WALLET SYSTEM — copy trading + trades manuels
# ════════════════════════════════════════════════════════════════
_uw_lock = threading.Lock()
_ai_running = threading.Lock()   

def _uw_token(chat_id):
    import hashlib
    return hashlib.md5(f"uw_{chat_id}_aria".encode()).hexdigest()[:12].upper()

def load_user_wallets():
    if os.path.exists(USER_WALLETS_FILE):
        try:
            with open(USER_WALLETS_FILE) as f: return json.load(f)
        except: pass
    return {}

def save_user_wallets(data):
    with _uw_lock:
        with open(USER_WALLETS_FILE, "w") as f: json.dump(data, f)

def get_user_wallet(chat_id):
    wallets = load_user_wallets()
    sid = str(chat_id)
    if sid not in wallets:
        wallets[sid] = {
            "balance": UW_INITIAL, "portfolio": {}, "history": [],
            "copy_trading": False, "token": _uw_token(chat_id),
            "created": now_paris().strftime("%d/%m/%Y"),
            "total_trades": 0, "winning_trades": 0,
            "perf_history": [{"d": now_paris().strftime("%d/%m/%Y"), "v": UW_INITIAL}],
            "name": get_user(chat_id).get("name", "User"),
        }
        save_user_wallets(wallets)
    return wallets[sid]

def save_user_wallet(chat_id, wallet):
    wallets = load_user_wallets()
    wallets[str(chat_id)] = wallet
    save_user_wallets(wallets)

def uw_total_value(w):
    total = w.get("balance", 0)
    for key, pos in w.get("portfolio", {}).items():
        price = get_asset_price(pos["ticker"]) or pos.get("buy_price", 0)
        if pos.get("type") == "SHORT":
            total += pos["qty"] * pos["buy_price"] + (pos["buy_price"] - price) * pos["qty"]
        else:
            total += pos["qty"] * price
    return max(total, 0)

def uw_pnl(w):
    total = uw_total_value(w)
    pnl = total - UW_INITIAL
    return pnl, (pnl / UW_INITIAL * 100)

# ── Copy trading: called from ai_run_analysis after each trade ──
def _copy_trade_for_user(chat_id, uw, trade, aria_wallet_size):
    """Réplique proportionnellement un trade ARIA dans le wallet user"""
    try:
        action   = trade["type"]           # BUY / SELL / SHORT / COVER
        asset_key= trade["asset"].lower().replace(" ","").replace("₿","btc").split("(")[0].strip()
        # Normalise vers les clés AI_TRADABLE
        key_map  = {"bitcoin":"btc","ethereum":"eth","nvidia":"nvda","tesla":"tsla",
                    "apple":"aapl","meta":"meta","amazon":"amzn","microsoft":"msft",
                    "solana":"sol","binancecoin":"bnb","gold":"gold","sp500":"sp500"}
        for long_name, short_key in key_map.items():
            if long_name in asset_key or short_key == asset_key:
                asset_key = short_key; break
        # Retrouve le ticker via AI_TRADABLE
        asset_info = AI_TRADABLE.get(asset_key)
        if not asset_info: return
        ticker, name = asset_info
        price   = trade["price"]
        # Proportion: même % du wallet que ARIA
        pct     = trade["amount"] / aria_wallet_size if aria_wallet_size > 0 else 0.05
        amount  = uw_total_value(uw) * pct
        amount  = min(amount, uw["balance"])
        if amount < 5: return
        portfolio = uw.get("portfolio", {})
        now_str   = now_paris().strftime("%d/%m/%Y %H:%M")
        pnl = 0; pnl_pct = 0
        executed = None
        if action == "BUY":
            if asset_key in portfolio: return
            qty = amount / price
            portfolio[asset_key] = {"qty":qty,"buy_price":price,"name":name,"ticker":ticker,"type":"LONG","date":now_str}
            uw["balance"] -= amount
            executed = {"date":now_str,"type":"BUY","asset":name,"price":price,"qty":qty,"amount":amount,"pnl":0,"pnl_pct":0,"reason":f"📋 Copy ARIA","conviction":trade.get("conviction",50),"short":False}
        elif action == "SELL" and asset_key in portfolio:
            pos = portfolio.pop(asset_key)
            proceeds = pos["qty"] * price
            pnl = proceeds - pos["buy_price"] * pos["qty"]
            pnl_pct = pnl / (pos["buy_price"] * pos["qty"]) * 100 if pos["qty"] > 0 else 0
            uw["balance"] += proceeds
            uw["winning_trades"] += int(pnl >= 0)
            executed = {"date":now_str,"type":"SELL","asset":name,"price":price,"qty":pos["qty"],"amount":proceeds,"pnl":pnl,"pnl_pct":pnl_pct,"reason":"📋 Copy ARIA","conviction":100,"short":False}
        elif action == "SHORT":
            sk = f"{asset_key}_short"
            if sk in portfolio: return
            qty = amount / price
            portfolio[sk] = {"qty":qty,"buy_price":price,"name":name,"ticker":ticker,"type":"SHORT","date":now_str}
            uw["balance"] -= amount
            executed = {"date":now_str,"type":"SHORT","asset":name,"price":price,"qty":qty,"amount":amount,"pnl":0,"pnl_pct":0,"reason":"📋 Copy ARIA","conviction":trade.get("conviction",50),"short":True}
        elif action == "COVER":
            sk = f"{asset_key}_short"
            if sk not in portfolio: return
            pos = portfolio.pop(sk)
            pnl = (pos["buy_price"] - price) * pos["qty"]
            proceeds = pos["qty"] * pos["buy_price"] + pnl
            pnl_pct = pnl / (pos["buy_price"] * pos["qty"]) * 100 if pos["qty"] > 0 else 0
            uw["balance"] += proceeds
            uw["winning_trades"] += int(pnl >= 0)
            executed = {"date":now_str,"type":"COVER","asset":name,"price":price,"qty":pos["qty"],"amount":proceeds,"pnl":pnl,"pnl_pct":pnl_pct,"reason":"📋 Copy ARIA","conviction":100,"short":True}
        if executed:
            uw["portfolio"] = portfolio
            uw["total_trades"] = uw.get("total_trades",0) + 1
            uw["history"].append(executed)
            # snapshot perf
            tv = uw_total_value(uw)
            uw.setdefault("perf_history",[]).append({"d":now_str[:10],"v":round(tv,2)})
            if len(uw["perf_history"]) > 200: uw["perf_history"] = uw["perf_history"][-200:]
    except Exception as e:
        print(f"Copy trade error user {chat_id}: {e}")

def run_copy_trading(all_trades, aria_wallet_size):
    """Applique les trades ARIA à tous les users avec copy_trading=True"""
    if not all_trades: return
    try:
        wallets = load_user_wallets()
        changed = {}
        for sid, uw in wallets.items():
            if not uw.get("copy_trading"): continue
            if not is_premium(int(sid)): continue
            for trade in all_trades:
                _copy_trade_for_user(int(sid), uw, trade, aria_wallet_size)
            changed[sid] = uw
        for sid, uw in changed.items():
            wallets[sid] = uw
        if changed:
            save_user_wallets(wallets)
            print(f"Copy trading: {len(changed)} wallets mis à jour")
    except Exception as e:
        print(f"Copy trading global error: {e}")

# ── Telegram commands ──
def cmd_mon_wallet(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    uw    = get_user_wallet(chat_id)
    total = uw_total_value(uw)
    pnl, pnl_pct = uw_pnl(uw)
    e = "🟢" if pnl >= 0 else "🔴"
    copy_status = "✅ Activé" if uw.get("copy_trading") else "⏸️ Désactivé"
    win_rate = (uw["winning_trades"] / uw["total_trades"] * 100) if uw.get("total_trades",0) > 0 else 0

    lines = [
        "💼 *MON WALLET VIRTUEL*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"💰 Valeur totale : *{total:,.2f}$*",
        f"📈 P&L : {e} *{pnl:+,.2f}$ ({pnl_pct:+.1f}%)*",
        f"💵 Cash dispo : *{uw['balance']:,.2f}$*",
        f"📊 Trades : *{uw.get('total_trades',0)}* | WinRate : *{win_rate:.0f}%*",
        f"🤖 Copy ARIA : *{copy_status}*",
        "",
    ]

    portfolio = uw.get("portfolio", {})
    if portfolio:
        lines.append("*Positions ouvertes :*")
        for key, pos in portfolio.items():
            price = get_asset_price(pos["ticker"]) or pos["buy_price"]
            is_s  = pos.get("type") == "SHORT"
            pp    = ((pos["buy_price"] - price) if is_s else (price - pos["buy_price"])) / pos["buy_price"] * 100
            tag   = " _(short)_" if is_s else ""
            ep    = "🟢" if pp >= 0 else "🔴"
            lines.append(f"  {ep} *{pos['name']}*{tag} @ {pos['buy_price']:,.2f}$ → {pp:+.1f}%")
    else:
        lines.append("_Aucune position ouverte._")

    lines += ["", f"🔑 *Token dashboard :* `{uw['token']}`"]

    # ================== BOUTON MAGIQUE ==================
    dashboard_url = f"{DASHBOARD_BASE_URL}/?token={uw['token']}"
    send_message(chat_id, "\n".join(lines), reply_markup={
        "inline_keyboard": [
            [{"text": "🌐 OUVRIR MON DASHBOARD WALLET", "url": dashboard_url}],  # ← LE BOUTON !
            [{"text": "🤖 Copy ARIA ON/OFF", "callback_data": "/copytrade_toggle"}],
            [{"text": "📈 Acheter", "callback_data": "/uw_buy"},
             {"text": "📉 Vendre",  "callback_data": "/uw_sell"}],
            [{"text": "📜 Historique", "callback_data": "/uw_history"}],
            [{"text": "🔙 Menu", "callback_data": "/menu_retour"}],
        ]
    })

def cmd_copytrade_toggle(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    uw = get_user_wallet(chat_id)
    uw["copy_trading"] = not uw.get("copy_trading", False)
    save_user_wallet(chat_id, uw)
    status = "✅ *Copy trading ACTIVÉ !*\nTu copieras automatiquement chaque trade d'ARIA." \
             if uw["copy_trading"] else \
             "⏸️ *Copy trading désactivé.*\nTu ne copieras plus les trades d'ARIA."
    send_message(chat_id, status, reply_markup={"inline_keyboard": [
        [{"text": "💼 Mon wallet", "callback_data": "/mon_wallet"}],
        [{"text": "🔙 Menu", "callback_data": "/menu_retour"}],
    ]})

def cmd_uw_history(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    uw = get_user_wallet(chat_id)
    hist = uw.get("history", [])[-10:][::-1]
    if not hist:
        send_message(chat_id, "Aucun trade dans ton historique.", reply_markup={"inline_keyboard":[[{"text":"🔙","callback_data":"/mon_wallet"}]]})
        return
    icons = {"BUY":"📥","SELL":"📤","SHORT":"🔻","COVER":"🔼"}
    lines = ["📜 *MES 10 DERNIERS TRADES*\n"]
    for t in hist:
        ic = icons.get(t["type"],"•")
        pnl_str = f" | *{t['pnl_pct']:+.1f}%*" if t["type"] in ["SELL","COVER"] else ""
        lines.append(f"{ic} *{t['type']} {t['asset']}* @ {t['price']:,.2f}${pnl_str}")
        lines.append(f"   _{t.get('reason','')[:60]}_ — {t.get('date','')[:10]}")
    send_message(chat_id, "\n".join(lines), reply_markup={"inline_keyboard":[[{"text":"🔙 Wallet","callback_data":"/mon_wallet"}]]})

# Assets disponibles pour trades manuels (même univers que ARIA)
UW_ASSETS_MENU = [
    ("₿ BTC",  "btc"),  ("🔷 ETH",  "eth"),  ("🟢 NVDA", "nvda"),
    ("🚗 TSLA","tsla"), ("🍎 AAPL", "aapl"), ("📘 META", "meta"),
    ("📦 AMZN","amzn"), ("🔵 MSFT", "msft"), ("🥇 Gold", "gold"),
]

def cmd_uw_buy_menu(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    send_message(chat_id, "📈 *ACHETER — Quel actif ?*",
        reply_markup={"inline_keyboard":
            [[{"text":name,"callback_data":f"/uw_buy_asset {key}"}] for name,key in UW_ASSETS_MENU] +
            [[{"text":"🔙","callback_data":"/mon_wallet"}]]})

def cmd_uw_sell_menu(chat_id):
    if not is_premium(chat_id): return premium_lock(chat_id)
    uw = get_user_wallet(chat_id)
    portfolio = uw.get("portfolio",{})
    if not portfolio:
        send_message(chat_id,"Aucune position à vendre.",reply_markup={"inline_keyboard":[[{"text":"🔙","callback_data":"/mon_wallet"}]]})
        return
    btns = [[{"text":f"🔴 Vendre {pos['name']}","callback_data":f"/uw_sell_asset {k}"}] for k,pos in portfolio.items()]
    btns.append([{"text":"🔙","callback_data":"/mon_wallet"}])
    send_message(chat_id,"📉 *VENDRE — Quelle position ?*",reply_markup={"inline_keyboard":btns})

def cmd_uw_buy_asset(chat_id, asset_key):
    if not is_premium(chat_id): return premium_lock(chat_id)
    set_user_field(chat_id, "sav_motif", f"[UW_BUY_{asset_key.upper()}]")
    uw = get_user_wallet(chat_id)
    send_message(chat_id,
        f"💰 *Cash disponible :* {uw['balance']:,.2f}$\n\n"
        f"Combien veux-tu investir dans *{asset_key.upper()}* ? (en $)\n"
        f"_Ex: 500_ (min 10$)",
        reply_markup={"inline_keyboard":[[{"text":"Annuler","callback_data":"/mon_wallet"}]]})

def cmd_uw_sell_asset(chat_id, pos_key):
    if not is_premium(chat_id): return premium_lock(chat_id)
    uw = get_user_wallet(chat_id)
    portfolio = uw.get("portfolio",{})
    if pos_key not in portfolio:
        send_message(chat_id,"Position introuvable.",reply_markup={"inline_keyboard":[[{"text":"🔙","callback_data":"/mon_wallet"}]]})
        return
    pos = portfolio[pos_key]
    price = get_asset_price(pos["ticker"]) or pos["buy_price"]
    is_s  = pos.get("type")=="SHORT"
    pp    = ((pos["buy_price"]-price) if is_s else (price-pos["buy_price"])) / pos["buy_price"] * 100
    proceeds = pos["qty"] * pos["buy_price"] + (pos["buy_price"]-price)*pos["qty"] if is_s else pos["qty"]*price
    pnl      = proceeds - pos["buy_price"]*pos["qty"] if not is_s else (pos["buy_price"]-price)*pos["qty"]
    ep = "🟢" if pnl >= 0 else "🔴"
    portfolio.pop(pos_key)
    uw["portfolio"] = portfolio
    uw["balance"] += proceeds
    uw["total_trades"] = uw.get("total_trades",0)+1
    uw["winning_trades"] = uw.get("winning_trades",0)+int(pnl>=0)
    now_str = now_paris().strftime("%d/%m/%Y %H:%M")
    uw.setdefault("history",[]).append({"date":now_str,"type":"COVER" if is_s else "SELL","asset":pos["name"],"price":price,"qty":pos["qty"],"amount":proceeds,"pnl":pnl,"pnl_pct":pp,"reason":"Vente manuelle","conviction":100,"short":is_s})
    tv = uw_total_value(uw)
    uw.setdefault("perf_history",[]).append({"d":now_str[:10],"v":round(tv,2)})
    save_user_wallet(chat_id, uw)
    send_message(chat_id,
        f"{ep} *Vente exécutée !*\n\n"
        f"Actif : *{pos['name']}*\n"
        f"Prix : *{price:,.2f}$*\n"
        f"P&L : {ep} *{pnl:+,.2f}$ ({pp:+.1f}%)*\n"
        f"Cash : *{uw['balance']:,.2f}$*",
        reply_markup={"inline_keyboard":[[{"text":"💼 Mon wallet","callback_data":"/mon_wallet"}]]})

def parse_uw_buy(chat_id, text):
    """Parse le montant saisi après cmd_uw_buy_asset"""
    user = get_user(chat_id)
    motif = user.get("sav_motif","")
    if not motif.startswith("[UW_BUY_"): return False
    asset_key = motif.replace("[UW_BUY_","").replace("]","").lower()
    try: amount = float(text.strip().replace("$","").replace(",","."))
    except: send_message(chat_id,"Montant invalide. Entre un nombre ex: 500"); return True
    if amount < 10:
        send_message(chat_id,"Minimum 10$."); return True
    asset_info = AI_TRADABLE.get(asset_key)
    if not asset_info:
        send_message(chat_id,"Actif inconnu."); set_user_field(chat_id,"sav_motif",""); return True
    ticker, name = asset_info
    price = get_asset_price(ticker)
    if not price:
        send_message(chat_id,"Prix indisponible, réessaie."); set_user_field(chat_id,"sav_motif",""); return True
    uw = get_user_wallet(chat_id)
    if amount > uw["balance"]:
        send_message(chat_id,f"Solde insuffisant ({uw['balance']:,.2f}$ dispo)."); return True
    if asset_key in uw.get("portfolio",{}):
        send_message(chat_id,f"Tu as déjà une position sur {name}."); set_user_field(chat_id,"sav_motif",""); return True
    qty = amount / price
    now_str = now_paris().strftime("%d/%m/%Y %H:%M")
    uw.setdefault("portfolio",{})[asset_key] = {"qty":qty,"buy_price":price,"name":name,"ticker":ticker,"type":"LONG","date":now_str}
    uw["balance"] -= amount
    uw["total_trades"] = uw.get("total_trades",0)+1
    uw.setdefault("history",[]).append({"date":now_str,"type":"BUY","asset":name,"price":price,"qty":qty,"amount":amount,"pnl":0,"pnl_pct":0,"reason":"Achat manuel","conviction":50,"short":False})
    tv = uw_total_value(uw)
    uw.setdefault("perf_history",[]).append({"d":now_str[:10],"v":round(tv,2)})
    save_user_wallet(chat_id, uw)
    set_user_field(chat_id,"sav_motif","")
    send_message(chat_id,
        f"✅ *Achat exécuté !*\n\n"
        f"Actif : *{name}*\n"
        f"Prix d'entrée : *{price:,.2f}$*\n"
        f"Quantité : *{qty:.6f}*\n"
        f"Investi : *{amount:,.2f}$*\n"
        f"Cash restant : *{uw['balance']:,.2f}$*",
        reply_markup={"inline_keyboard":[[{"text":"💼 Mon wallet","callback_data":"/mon_wallet"}]]})
    return True

# ════════════════════════════════════════════════════════════════
# FLASK API — dashboard web
# ════════════════════════════════════════════════════════════════
def _start_api_server():
    try:
        from flask import Flask, jsonify, request
        from flask_cors import CORS
    except ImportError:
        try:
            import subprocess, sys
            subprocess.check_call([sys.executable,"-m","pip","install","flask","flask-cors","--break-system-packages","-q"])
            from flask import Flask, jsonify, request
            from flask_cors import CORS
        except Exception as e:
            print(f"Flask non disponible: {e}"); return

    app = Flask(__name__)
    CORS(app)
        # ─── DASHBOARD HTML (servi directement) ───
    
    @app.route("/")
    def dashboard():
        try:
            with open("dashboard.html", "r", encoding="utf-8") as f:
                return f.read(), 200, {"Content-Type": "text/html"}
        except FileNotFoundError:
            return "<h1>dashboard.html manquant dans le repo</h1>", 404

    @app.route("/api/aria")
    def api_aria():
        try:
            w = load_ai_wallet()
            total = ai_wallet_total_value(w)
            pnl, pnl_pct = ai_wallet_pnl(w)
            positions = []
            for key, pos in w.get("portfolio",{}).items():
                price = get_asset_price(pos["ticker"]) or pos["buy_price"]
                is_s  = pos.get("type")=="SHORT"
                pp    = ((pos["buy_price"]-price) if is_s else (price-pos["buy_price"])) / pos["buy_price"] * 100
                positions.append({"key":key,"name":pos["name"],"type":pos.get("type","LONG"),"qty":pos["qty"],"buy_price":pos["buy_price"],"current_price":price,"pnl_pct":round(pp,2),"value":round(pos["qty"]*price,2),"date":pos.get("date","")})
            return jsonify({
                "balance": round(w["balance"],2),
                "total_value": round(total,2),
                "pnl": round(pnl,2),
                "pnl_pct": round(pnl_pct,2),
                "total_trades": w.get("total_trades",0),
                "winning_trades": w.get("winning_trades",0),
                "win_rate": round(w["winning_trades"]/w["total_trades"]*100,1) if w.get("total_trades",0)>0 else 0,
                "created": w.get("created",""),
                "last_trade": w.get("last_trade",""),
                "positions": positions,
                "history": w.get("history",[])[-50:][::-1],
                "perf_history": _build_perf_history(w),
            })
        except Exception as e:
            return jsonify({"error":str(e)}), 500

    @app.route("/api/wallet")
    def api_wallet():
        try:
            token = request.args.get("token", "").upper().strip()
            print(f"[API WALLET] Token reçu: {token[:10]}...")

            if not token:
                return jsonify({"error": "token required"}), 400

            wallets = load_user_wallets()
            uw = next((w for w in wallets.values() if w.get("token","").upper() == token), None)

            if not uw:
                print(f"[API WALLET] Token non trouvé")
                return jsonify({"error": "wallet not found"}), 404

            total = uw_total_value(uw)
            pnl, pnl_pct = uw_pnl(uw)

            positions = []
            for key, pos in uw.get("portfolio", {}).items():
                price = get_asset_price(pos.get("ticker")) or pos.get("buy_price", 0)
                is_short = pos.get("type") == "SHORT"
                pnl_pos = ((pos["buy_price"] - price) if is_short else (price - pos["buy_price"])) / pos["buy_price"] * 100 if pos["buy_price"] > 0 else 0
                positions.append({
                    "name": pos.get("name", key),
                    "type": pos.get("type", "LONG"),
                    "buy_price": round(pos.get("buy_price",0),2),
                    "current_price": round(price,2),
                    "pnl_pct": round(pnl_pos,2),
                    "value": round(pos.get("qty",0) * price, 2)
                })

            response = {
                "name": uw.get("name", "Mon Wallet"),
                "balance": round(uw.get("balance",0),2),
                "total_value": round(total,2),
                "pnl": round(pnl,2),
                "pnl_pct": round(pnl_pct,2),
                "copy_trading": uw.get("copy_trading", False),
                "total_trades": uw.get("total_trades",0),
                "win_rate": round(uw.get("winning_trades",0) / max(uw.get("total_trades",1),1) * 100, 1),
                "positions": positions,
                "history": uw.get("history", [])[-30:],
                "perf_history": uw.get("perf_history", [])
            }
            print(f"[API WALLET] Succès - Valeur totale: {total}$")
            return jsonify(response)

        except Exception as e:
            import traceback
            print(f"[API WALLET CRASH] {str(e)}")
            print(traceback.format_exc())
            return jsonify({"error": "internal server error"}), 500

    @app.route("/api/leaderboard")
    def api_leaderboard():
        wallets = load_user_wallets()
        board = []
        for sid, uw in wallets.items():
            total = uw_total_value(uw)
            pnl_pct = (total - UW_INITIAL) / UW_INITIAL * 100
            board.append({"name": uw.get("name","User")[:12], "pnl_pct": round(pnl_pct,2), "total_value": round(total,2), "copy_trading": uw.get("copy_trading",False)})
        board.sort(key=lambda x: x["pnl_pct"], reverse=True)
        return jsonify(board[:20])

    @app.route("/health")
    def health(): return "ok"

    # Sur Railway, PORT est utilisé par le reverse proxy.
    # On bind Flask sur FLASK_PORT (défaut 5000) pour éviter les conflits.
    port = int(os.environ.get("FLASK_PORT", os.environ.get("PORT", 5000)))
    print(f"🌐 API Flask démarrée sur le port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def _build_perf_history(w):
    """Reconstruit l'historique de perf ARIA depuis l'historique des trades"""
    h = w.get("history",[])
    if not h: return [{"d": w.get("created","today"), "v": AI_WALLET_INITIAL}]
    points = [{"d": w.get("created",""), "v": AI_WALLET_INITIAL}]
    balance = AI_WALLET_INITIAL
    for t in h:
        if t["type"] in ["SELL","COVER"]:
            balance += t.get("pnl",0)
        points.append({"d": t.get("date","")[:10], "v": round(balance,2)})
    return points[-100:]

# ================== ROUTING ==================
def handle_command(chat_id, text, user_name=""):
    t_low = text.strip().lower()

    # Admin
    if any(text.startswith(c) for c in ["/addpremium","/removepremium","/listusers","/stats","/repondre","/admin"]):
        cmd_admin(chat_id, text); return

    # Commandes principales
    if t_low == "/start" or t_low.startswith("/start "):
        # Vérifie si code de parrainage dans le start
        parts = text.strip().split()
        ref_code = parts[1] if len(parts) > 1 else None
        if ref_code and ref_code.startswith("REF"):
            apply_referral(chat_id, ref_code, user_name)
        cmd_start(chat_id, user_name)
    elif t_low in ["/help","/accueil"]:      cmd_accueil(chat_id, user_name)
    elif t_low == "/actu":                   threading.Thread(target=cmd_actu, args=(chat_id,), daemon=True).start()
    elif t_low.startswith("/news_deep"):
        idx = t_low.replace("/news_deep", "").strip()
        threading.Thread(target=cmd_news_deep, args=(chat_id, idx), daemon=True).start()
    elif t_low == "/top":                    cmd_top(chat_id)
    elif t_low == "/chance":                 cmd_chance(chat_id)
    elif t_low == "/quote":                  cmd_quote(chat_id)
    elif t_low == "/aiwallet":                cmd_ai_wallet(chat_id)
    elif t_low in ["/mon_wallet", "/mywallet"]:
        threading.Thread(target=cmd_mon_wallet, args=(chat_id,), daemon=True).start()
    elif t_low == "/copytrade_toggle":
        cmd_copytrade_toggle(chat_id)
    elif t_low == "/uw_history":
        cmd_uw_history(chat_id)
    elif t_low == "/uw_buy":
        cmd_uw_buy_menu(chat_id)
    elif t_low == "/uw_sell":
        cmd_uw_sell_menu(chat_id)
    elif t_low.startswith("/uw_buy_asset"):
        ak = t_low.replace("/uw_buy_asset", "").strip()
        cmd_uw_buy_asset(chat_id, ak)
    elif t_low.startswith("/uw_sell_asset"):
        pk = t_low.replace("/uw_sell_asset", "").strip()
        threading.Thread(target=cmd_uw_sell_asset, args=(chat_id, pk), daemon=True).start()
    elif t_low == "/score":                  cmd_score(chat_id)
    elif t_low == "/performance":            cmd_performance(chat_id)
    elif t_low == "/avis":                   cmd_avis(chat_id, user_name)
    elif t_low == "/moncompte":              cmd_moncompte(chat_id)
    elif t_low in ["/premium", "/upgrade"]:
        cmd_premium_page(chat_id)
    elif t_low == "/parrainage":
        cmd_parrainage(chat_id, user_name)
    elif t_low == "/lecon":
        cmd_lecon(chat_id)
    elif t_low == "/lecon_next":
        cmd_lecon_next(chat_id)
    # Menus
    elif t_low == "/menu_signaux":           send_message(chat_id, "📈 *Choisis un actif :*", reply_markup=menu_signaux())
    elif t_low == "/menu_rsi":               send_message(chat_id, "📊 *Choisis un actif :*", reply_markup=menu_rsi())
    elif t_low == "/menu_outils":            send_message(chat_id, "🧰 *Tes outils :*", reply_markup=menu_outils())
    elif t_low == "/menu_compte":            send_message(chat_id, "⚙️ *Ton compte :*", reply_markup=menu_compte())
    elif t_low == "/menu_langue":            send_message(chat_id, "🌐 *Choisis ta langue :*", reply_markup=menu_langue())
    elif t_low == "/menu_alertes":           send_message(chat_id, "🔔 *Tes alertes :*", reply_markup=menu_alertes(chat_id))
    elif t_low == "/menu_paper":             cmd_paper_info(chat_id)
    elif t_low == "/menu_retour":            menu_retour_msg(chat_id)
    elif t_low == "/noop":                   pass
    # Signaux
    elif t_low.startswith("/signal "):       threading.Thread(target=cmd_signal, args=(chat_id, t_low.replace("/signal ","").strip()), daemon=True).start()
    # RSI
    elif t_low.startswith("/rsi"):
        parts = t_low.split()
        threading.Thread(target=cmd_rsi, args=(chat_id, parts[1] if len(parts) > 1 else "btc"), daemon=True).start()
    # Paper trading
    elif t_low == "/paper_portfolio":
        if not is_premium(chat_id): return premium_lock(chat_id)
        send_message(chat_id, paper_portfolio_summary(chat_id), reply_markup=menu_paper(chat_id))
    elif t_low == "/paper_buy":
        if not is_premium(chat_id): return premium_lock(chat_id)
        send_message(chat_id, "📥 *ACHETER*\n\nFormat : `buy [actif] [montant$]`\nEx : `buy btc 500`\nEx : `buy nvda 200`",
            reply_markup={"inline_keyboard": [[{"text": "🔙 Retour", "callback_data": "/menu_paper"}]]})
        set_user_field(chat_id, "sav_motif", "[PAPER_BUY]")
    elif t_low == "/paper_sell":
        if not is_premium(chat_id): return premium_lock(chat_id)
        send_message(chat_id, "📤 *VENDRE*\n\nFormat : `sell [actif] [%]`\nEx : `sell btc 100` (vend 100%)\nEx : `sell tsla 50` (vend 50%)",
            reply_markup={"inline_keyboard": [[{"text": "🔙 Retour", "callback_data": "/menu_paper"}]]})
        set_user_field(chat_id, "sav_motif", "[PAPER_SELL]")
    elif t_low == "/paper_perf":
        if not is_premium(chat_id): return premium_lock(chat_id)
        cmd_performance(chat_id)
    elif t_low == "/paper_reset":
        if not is_premium(chat_id): return premium_lock(chat_id)
        set_user_field(chat_id, "paper_balance", 10000.0)
        set_user_field(chat_id, "paper_portfolio", {})
        set_user_field(chat_id, "paper_history", [])
        send_message(chat_id, "🔄 *Paper Trading réinitialisé à 10 000$*", reply_markup=menu_paper(chat_id))
    # Alertes
    elif t_low == "/alerte_new":             cmd_alerte_new(chat_id)
    elif t_low.startswith("/alerte_del "):
        try:
            idx = int(t_low.split()[1])
            cmd_alerte_del(chat_id, idx)
        except: send_message(chat_id, "❌ Erreur.", reply_markup=menu_alertes(chat_id))
    # SAV
    elif t_low == "/sav":                    cmd_sav(chat_id, user_name)
    elif t_low in ["/sav_tech","/sav_paiement","/sav_suggestion","/sav_autre"]:
        cmd_sav_motif(chat_id, user_name, t_low.replace("/sav_",""))
    # Avis
    elif t_low.startswith("/avis_"):
        try:
            note = int(t_low.replace("/avis_",""))
            cmd_avis_note(chat_id, user_name, note)
        except: pass
    # Langue
    elif t_low.startswith("/lang "):
        lang = t_low.replace("/lang ","").strip()
        if lang in LANGS:
            set_user_field(chat_id, "lang", lang)
            flags = {"fr":"🇫🇷 Français","en":"🇬🇧 English","es":"🇪🇸 Español"}
            # tr() now uses the NEW lang since we just saved it
            send_message(chat_id,
                f"{tr(chat_id,'lang_changed')} *{flags[lang]}*",
                reply_markup=main_menu(chat_id))
    # Messages libres
    else:
        user = get_user(chat_id)
        motif = user.get("sav_motif", "")

        # User wallet buy order
        if motif.startswith("[UW_BUY_"):
            if parse_uw_buy(chat_id, text):
                return

        # Paper trading orders
        if motif in ["[PAPER_BUY]", "[PAPER_SELL]"] or t_low.startswith(("buy ","sell ")):
            if parse_paper_order(chat_id, text):
                set_user_field(chat_id, "sav_motif", "")
                return

        # Alertes
        if motif == "[ALERTE_NEW]" or t_low.startswith("alerte ") or t_low.startswith("alert ") or t_low.startswith("alerta "):
            if parse_alerte(chat_id, text):
                set_user_field(chat_id, "sav_motif", "")
                return

        # SAV / paiement — confirmation dans la bonne langue
        notify_admin_sav(chat_id, user_name, text)
        set_user_field(chat_id, "sav_motif", "")
        if not is_premium(chat_id):
            send_message(chat_id, tr(chat_id, "payment_received"), reply_markup=main_menu(chat_id))
        else:
            send_message(chat_id, tr(chat_id, "sav_sent"), reply_markup=main_menu(chat_id))

# ================== BOUCLE PRINCIPALE ==================
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset: params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=35)
        return r.json().get("result", [])
    except:
        return []

print("🤖 Bot démarré !")
print("Fonctionnalités : Signaux(14) • RSI(9) • Paper Trading • Alertes • Score • Hebdo • Langues(FR/EN/ES)")

# Préchauffage du cache + démarrage API web
threading.Thread(target=_start_api_server, daemon=True).start()
# Préchauffage du cache au démarrage (en arrière-plan — bot réactif immédiatement)
print("Préchauffage cache news+marché en arrière-plan...")
threading.Thread(target=_do_refresh_cache, daemon=True).start()

offset = None
while True:
    try:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "callback_query" in update:
                cq = update["callback_query"]
                answer_callback(cq["id"])
                cid = cq["message"]["chat"]["id"]
                uname = cq["message"]["chat"].get("first_name", "")
                print(f"Bouton: {cq['data'][:30]} | {cid}")
                handle_command(cid, cq["data"], uname)
            elif "message" in update:
                msg = update["message"]
                txt = msg.get("text", "")
                cid = msg["chat"]["id"]
                uname = msg["chat"].get("first_name", "")
                if txt:
                    print(f"Message: {txt[:30]} | {cid}")
                    handle_command(cid, txt, uname)
        check_auto_send()
        time.sleep(1)
    except Exception as e:
        print(f"Erreur boucle: {e}")
        time.sleep(5)
