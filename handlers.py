import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackContext
from telegram.error import TelegramError
from persona import SisyphePersona
from admin import AdminManager
from perplexity_client import PerplexityClient
from media_handler import MediaHandler
import re

logger = logging.getLogger(__name__)

sisyphe = SisyphePersona()
admin_manager = AdminManager()
perplexity_client = PerplexityClient()
media_handler = MediaHandler()

# Liste des commandes et leurs descriptions pour le menu
COMMANDS = {
    'start': 'Débuter une conversation avec Sisyphe',
    'help': 'Obtenir de l\'aide sur l\'utilisation du bot',
    'search': 'Rechercher des informations (ex: /search philosophie grecque)',
    'image': 'Rechercher des images (ex: /image paysage montagne)',
    'yt': 'Rechercher et télécharger une vidéo YouTube',
    'menu': 'Afficher ce menu d\'aide'
}

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

        help_text = """*marque sa page et lève les yeux*

Je peux t'aider de plusieurs façons :

🔍 /search + ta question
   Pour des recherches précises et sourcées

🖼 /image + description
   Pour trouver des images spécifiques

🎥 /yt + titre
   Pour télécharger des vidéos YouTube

📖 /menu
   Pour voir toutes les commandes disponibles

*reprend sa lecture*"""

        await update.message.reply_text(help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erreur dans help_command: {e}")
        await update.message.reply_text("*semble distrait*")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche un menu sophistiqué des commandes disponibles"""
    try:
        menu_text = """*pose délicatement son livre et ajuste ses lunettes*

📚 **Guide d'utilisation de Sisyphe** 📚

Je suis Sisyphe, votre compagnon philosophique et érudit. Je peux vous aider de plusieurs manières :

🤝 **Interaction Basique**
• Mentionnez mon nom ou répondez à mes messages pour engager la conversation
• Je répondrai avec concision et précision

📜 **Commandes Principales**
"""
        for cmd, desc in COMMANDS.items():
            menu_text += f"• /{cmd} - {desc}\n"

        menu_text += """

🔍 **Fonctionnalités de Recherche**
• Pour la commande /search :
  - Utilisez des mots-clés précis
  - Les résultats seront sourcés et vérifiés
  - Format : /search votre question

🖼 **Recherche d'Images**
• Pour la commande /image :
  - Décrivez l'image souhaitée
  - Format : /image description détaillée

🎥 **Téléchargement YouTube**
• Pour la commande /yt :
  - Indiquez le titre ou les mots-clés
  - Choisissez le format (MP3/MP4)
  - Limite : 75MB

💡 **Astuces**
• Soyez précis dans vos requêtes
• Préférez des questions clairement formulées
• Attendez ma réponse avant d'envoyer une nouvelle demande

*reprend son livre*"""

        await update.message.reply_text(menu_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erreur dans menu_command: {e}")
        await update.message.reply_text("*fronce les sourcils* Un moment d'égarement...")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /search"""
    try:
        query = ' '.join(context.args) if context.args else None
        if not query:
            # Vérifier si le message est une réponse à un autre message
            if update.message.reply_to_message and update.message.reply_to_message.text:
                query = update.message.reply_to_message.text
            else:
                await update.message.reply_text("*lève un sourcil* Que souhaites-tu rechercher ?")
                return

        # Indiquer que le bot est en train d'écrire
        await update.message.chat.send_action(action="typing")

        # Effectuer la recherche
        result = await perplexity_client.search(query)

        if "error" in result:
            await update.message.reply_text("*fronce les sourcils* Je ne peux pas accéder à cette information pour le moment.")
            return

        response = result["response"]
        await update.message.reply_text(f"*consulte ses sources*\n\n{response}", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Erreur dans search_command: {e}")
        await update.message.reply_text("*semble perplexe* Je ne peux pas effectuer cette recherche pour le moment.")

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /image"""
    try:
        query = ' '.join(context.args) if context.args else None
        if not query:
            await update.message.reply_text("*lève un sourcil* Quelle image cherches-tu ?")
            return

        # Indiquer que le bot est en train d'écrire
        await update.message.chat.send_action(action="typing")

        # Rechercher sur Pinterest et Zerochan
        pinterest_urls = await perplexity_client.search_images(query, "Pinterest")
        zerochan_urls = await perplexity_client.search_images(query, "Zerochan")

        # Télécharger les images
        all_urls = pinterest_urls + zerochan_urls
        if not all_urls:
            await update.message.reply_text("*fronce les sourcils* Je n'ai pas trouvé d'images correspondant à ta recherche.")
            return

        image_paths = await media_handler.download_images(all_urls)

        if not image_paths:
            await update.message.reply_text("*semble confus* Je n'ai pas pu télécharger les images.")
            return

        # Envoyer les images
        await update.message.reply_text("*parcourt sa collection* Voici ce que j'ai trouvé :")
        for path in image_paths:
            with open(path, 'rb') as f:
                await update.message.reply_photo(photo=f)

        # Nettoyer les fichiers
        media_handler.cleanup()

    except Exception as e:
        logger.error(f"Erreur dans image_command: {e}")
        await update.message.reply_text("*semble troublé* Je ne peux pas traiter ces images pour le moment.")

async def yt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /yt"""
    try:
        query = ' '.join(context.args) if context.args else None
        if not query:
            await update.message.reply_text("*lève un sourcil* Quelle vidéo cherches-tu ?")
            return

        # Indiquer que le bot est en train d'écrire
        await update.message.chat.send_action(action="typing")

        # Rechercher les vidéos avec yt-dlp
        videos = await media_handler.search_youtube(query)
        if not videos:
            await update.message.reply_text("*fronce les sourcils* Je n'ai pas trouvé de vidéos correspondant à ta recherche.")
            return

        # Créer les boutons pour chaque vidéo avec des titres plus clairs
        keyboard = []
        for i, video in enumerate(videos):
            title = video['title']
            # Limiter la longueur du titre si nécessaire
            if len(title) > 35:
                title = title[:32] + "..."

            # Ajouter la durée si disponible
            if video.get('duration'):
                duration = int(video['duration'])  # Convert to int for division
                minutes = duration // 60
                seconds = duration % 60
                title = f"{title} ({minutes}:{seconds:02d})"

            callback_data = f"yt_{i}_{video['url']}"
            if len(callback_data) > 64:  # Limite Telegram pour callback_data
                video_id = video['url'].split('watch?v=')[-1].split('&')[0]
                callback_data = f"yt_{i}_{video_id}"
            keyboard.append([InlineKeyboardButton(title, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "*consulte son catalogue* Voici les vidéos trouvées :\n\n" + 
            "\n".join([f"• {video['title']}" for video in videos]),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Erreur dans yt_command: {e}")
        await update.message.reply_text("*semble troublé* Je ne peux pas rechercher de vidéos pour le moment.")

async def handle_callback(update: Update, context: CallbackContext):
    """Gère les callbacks des boutons inline"""
    query = update.callback_query
    try:
        await query.answer()

        if query.data.startswith('yt_'):
            # Format: yt_index_url
            parts = query.data.split('_', 2)
            if len(parts) != 3:
                raise ValueError("Format de callback incorrect")

            _, index, url_or_id = parts

            # Reconstruire l'URL complète si nécessaire
            if not url_or_id.startswith('http'):
                url = f"https://www.youtube.com/watch?v={url_or_id}"
            else:
                url = url_or_id

            # Demander le format
            keyboard = [
                [InlineKeyboardButton("MP3 (Audio)", callback_data=f"format_mp3_{url}")],
                [InlineKeyboardButton("MP4 (Vidéo)", callback_data=f"format_mp4_{url}")]
            ]
            await query.edit_message_text(
                "*réfléchit* Dans quel format souhaites-tu cette vidéo ?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        elif query.data.startswith('format_'):
            # Format: format_type_url
            parts = query.data.split('_', 2)
            if len(parts) != 3:
                raise ValueError("Format de callback incorrect")

            _, format_type, url = parts

            if format_type not in ['mp3', 'mp4']:
                raise ValueError("Format non supporté")

            await query.edit_message_text("*commence le téléchargement* Un moment...")

            # Télécharger la vidéo
            file_path = await media_handler.download_youtube_video(url, format_type)

            if not file_path:
                await query.message.reply_text("*fronce les sourcils* La vidéo est trop volumineuse ou n'est pas accessible.")
                return

            try:
                # Envoyer le fichier
                with open(file_path, 'rb') as f:
                    if format_type == 'mp3':
                        await query.message.reply_audio(audio=f)
                    else:
                        await query.message.reply_video(video=f)

                # Nettoyer
                media_handler.cleanup()
                await query.message.reply_text("*range le fichier* Voici ta vidéo.")
            except Exception as send_error:
                logger.error(f"Erreur lors de l'envoi du fichier: {send_error}")
                await query.message.reply_text("*semble confus* Je n'arrive pas à t'envoyer le fichier.")
                media_handler.cleanup()

    except ValueError as ve:
        logger.error(f"Erreur de format dans handle_callback: {ve}")
        await query.message.reply_text("*fronce les sourcils* Je ne comprends pas cette requête.")
    except Exception as e:
        logger.error(f"Erreur dans handle_callback: {e}")
        logger.exception("Détails de l'erreur:")
        await query.message.reply_text("*semble troublé* Je ne peux pas traiter cette requête pour le moment.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère les messages reçus"""
    try:
        message_text = update.message.text

        if not message_text or message_text.isspace():
            return

        # Vérifier si le message est dans un groupe et si Sisyphe doit répondre
        if update.message.chat.type in ['group', 'supergroup']:
            # Vérifier si le message est une réponse à un message de Sisyphe
            is_reply_to_bot = (
                update.message.reply_to_message and 
                update.message.reply_to_message.from_user.id == context.bot.id
            )

            # Vérifier si Sisyphe est mentionné
            bot_username = context.bot.username
            mentions_bot = (
                f"@{bot_username}" in message_text or 
                "Sisyphe" in message_text or 
                "sisyphe" in message_text
            )

            # Ne pas répondre si ce n'est ni une réponse ni une mention
            if not (is_reply_to_bot or mentions_bot):
                return

        # Détecter les mots-clés de recherche
        search_keywords = ["recherche", "trouve", "cherche"]
        if any(keyword in message_text.lower() for keyword in search_keywords):
            # Extraire la requête après le mot-clé
            for keyword in search_keywords:
                if keyword in message_text.lower():
                    query = re.split(f"{keyword}\\s+", message_text, flags=re.IGNORECASE)[1]
                    # Simuler la commande search
                    context.args = query.split()
                    await search_command(update, context)
                    return

        # Traitement normal du message
        user_id = update.effective_user.id
        username = update.effective_user.first_name
        nickname = admin_manager.get_nickname(user_id, username)

        logger.info(f"Message reçu de {nickname} (ID: {user_id}): {message_text[:50]}...")

        # Indiquer que le bot est en train d'écrire
        await update.message.chat.send_action(action="typing")

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