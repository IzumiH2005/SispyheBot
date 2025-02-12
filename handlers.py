import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from persona import SisyphePersona
from admin import AdminManager

logger = logging.getLogger(__name__)

sisyphe = SisyphePersona()
admin_manager = AdminManager()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /start"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.first_name
        nickname = admin_manager.get_nickname(user_id, username)

        logger.info(f"Commande /start reçue de {nickname} (ID: {user_id})")

        if admin_manager.is_admin(user_id):
            response = f"*pose son livre et esquisse un léger sourire* Ah, {nickname}. Que puis-je pour toi ?"
        else:
            response = "*lève brièvement les yeux de son livre* Bienvenue. Que veux-tu savoir ?"

        await update.message.reply_text(response, parse_mode='Markdown')
    except TelegramError as e:
        logger.error(f"Erreur Telegram dans start_command: {e}")
        await update.message.reply_text("*semble distrait*")
    except Exception as e:
        logger.error(f"Erreur inattendue dans start_command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /help"""
    try:
        user_id = update.effective_user.id
        username = update.effective_user.first_name
        nickname = admin_manager.get_nickname(user_id, username)

        logger.info(f"Commande /help reçue de {nickname} (ID: {user_id})")

        if admin_manager.is_admin(user_id):
            help_text = f"*marque sa page* Dis-moi ce qui t'intrigue, {nickname}."
        else:
            help_text = """*sans quitter son livre des yeux*

Je peux discuter de philosophie, sciences, ou littérature.
Pose ta question simplement."""

        await update.message.reply_text(help_text, parse_mode='Markdown')
    except TelegramError as e:
        logger.error(f"Erreur Telegram dans help_command: {e}")
        await update.message.reply_text("*semble distrait*")
    except Exception as e:
        logger.error(f"Erreur inattendue dans help_command: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages reçus"""
    try:
        message_text = update.message.text

        if not message_text or message_text.isspace():
            return

        user_id = update.effective_user.id
        username = update.effective_user.first_name
        nickname = admin_manager.get_nickname(user_id, username)

        logger.info(f"Message reçu de {nickname} (ID: {user_id}): {message_text[:50]}...")

        # Ajoute le contexte de l'utilisateur au message pour Gemini
        context_message = f"[L'utilisateur s'appelle {nickname}. "
        if admin_manager.is_admin(user_id):
            if user_id == 580187559:
                context_message += "C'est Marceline, la personne avec qui tu aimes le plus discuter même si tu restes impassible. "
            else:
                context_message += "C'est ton créateur. "
        context_message += f"]\n\n{message_text}"

        response = await sisyphe.get_response(context_message)
        await update.message.reply_text(response, parse_mode='Markdown')

    except TelegramError as e:
        logger.error(f"Erreur Telegram dans handle_message: {e}")
        await update.message.reply_text("*semble distrait*")
    except Exception as e:
        logger.error(f"Erreur inattendue dans handle_message: {e}")
        logger.exception("Détails de l'erreur:")
        await update.message.reply_text("*fronce les sourcils* Une pensée m'échappe...")