import logging
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, InputMediaPhoto
from telegram.ext import ContextTypes, CallbackContext
from telegram.error import TelegramError
from persona import SisyphePersona
from admin import AdminManager
from perplexity_client import PerplexityClient
from media_handler import MediaHandler
import re
from scraper import GoogleImageScraper  # Changed import
from fiche import FicheClient

logger = logging.getLogger(__name__)

sisyphe = SisyphePersona()
admin_manager = AdminManager()
perplexity_client = PerplexityClient()
media_handler = MediaHandler()
fiche_client = FicheClient()

# Liste des commandes et leurs descriptions pour le menu
COMMANDS = {
    'start': 'Débuter une conversation avec Sisyphe',
    'help': 'Obtenir de l\'aide sur l\'utilisation du bot',
    'search': 'Rechercher des informations (ex: /search philosophie grecque)',
    'image': 'Rechercher des images (ex: /image paysage montagne)',
    'yt': 'Rechercher et télécharger une vidéo YouTube',
    'fiche': 'Créer une fiche détaillée d\'anime/série (ex: /fiche Naruto)',
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
    """Gère la commande /search avec un meilleur feedback"""
    progress_message = None
    try:
        query = ' '.join(context.args) if context.args else None
        if not query:
            if update.message.reply_to_message and update.message.reply_to_message.text:
                query = update.message.reply_to_message.text
            else:
                await update.message.reply_text("*lève un sourcil* Que souhaites-tu rechercher ?", parse_mode='Markdown')
                return

        user_id = update.effective_user.id
        logger.info(f"Recherche demandée par l'utilisateur {user_id}: {query}")

        # Message de recherche en cours
        progress_message = await update.message.reply_text(
            "*consulte ses sources*\n_Recherche en cours..._",
            parse_mode='Markdown'
        )

        # Indiquer que le bot est en train d'écrire
        await update.message.chat.send_action(action="typing")

        try:
            # Limite de temps pour la recherche
            result = await asyncio.wait_for(
                perplexity_client.search(query),
                timeout=25.0
            )

            if isinstance(result, dict) and "error" in result:
                error_msg = result["error"]
                logger.error(f"Erreur retournée par l'API: {error_msg}")
                if "quota" in error_msg.lower():
                    response = "*ferme son livre* J'ai besoin d'une pause, mes ressources sont épuisées."
                elif "timeout" in error_msg.lower():
                    response = "*fronce les sourcils* La recherche prend trop de temps. Essaie une requête plus simple."
                else:
                    response = f"*semble contrarié* {error_msg}"

                await progress_message.edit_text(response, parse_mode='Markdown')
                return

            response_text = result.get("response", "")
            sources = result.get("sources", [])
            is_media = result.get("is_media", False)

            logger.info(f"Nombre de sources trouvées: {len(sources)}")
            logger.info(f"Longueur de la réponse: {len(response_text)}")

            if not response_text:
                logger.error("Réponse vide reçue de l'API")
                await progress_message.edit_text(
                    "*fronce les sourcils* Je n'ai pas trouvé d'information pertinente.",
                    parse_mode='Markdown'
                )
                return

            formatted_response = ""

            if is_media:
                # Pour les médias, utiliser Gemini pour formater la réponse
                context_message = f"""Tu es un assistant sophistiqué qui doit créer une fiche détaillée pour ce contenu média.

Information brute à organiser dans le format exact suivant :
{response_text}

Format exact à utiliser (conserve tous les caractères spéciaux) :

┌───────────────────────────────────────────────┐
│               ✦ [TITRE] ✦                    │
│              *[TITRE EN JAPONAIS]*            │
└───────────────────────────────────────────────┘

◈ **Type** : [Type]  
◈ **Créateur** : [Créateur]  
◈ **Studio** : [Studio]  
◈ **Année** : [Année]  
◈ **Genres** : [Genres]  
◈ **Épisodes** : [Nombre d'épisodes]  
◈ **Univers** : [Description de l'univers]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **SYNOPSIS** ✦  
▪ [Résumé du synopsis]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **PERSONNAGES PRINCIPAUX** ✦  
🔹 **[Nom du personnage]** – [Description]  
🔹 **[Nom du personnage]** – [Description]  
🔹 **[Nom du personnage]** – [Description]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **THÈMES MAJEURS** ✦  
◈ [Thème 1]  
◈ [Thème 2]  
◈ [Thème 3]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **ADAPTATIONS & ŒUVRES ANNEXES** ✦  
▪ [Manga/Anime/etc.]  
▪ [Manga/Anime/etc.]  

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  
✦ **LIENS & RÉFÉRENCES** ✦  
{chr(10).join([f"🔗 {source}" for source in sources])}

Instructions de formatage :
1. Utilise exactement ce format avec les mêmes caractères spéciaux et emojis
2. Remplace les crochets par les informations appropriées
3. Conserve la mise en forme Markdown (**, *, etc.)
4. Laisse les sections vides si l'information n'est pas disponible"""

                logger.info("Envoi à Gemini pour formatage")
                formatted_response = await sisyphe.get_response(context_message)
                logger.info("Réponse reçue de Gemini")

            else:
                # Pour les autres recherches, utiliser directement la réponse de Perplexity
                formatted_response = f"{response_text}\n\n"
                formatted_response += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                formatted_response += "✦ **LIENS & RÉFÉRENCES** ✦\n"
                for source in sources:
                    formatted_response += f"🔗 {source}\n"

            if not formatted_response or not formatted_response.strip():
                logger.warning("Réponse vide après formatage, utilisation du format par défaut")
                formatted_response = f"""*Résultat de la recherche*

{response_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✦ **LIENS & RÉFÉRENCES** ✦
{chr(10).join([f"🔗 {source}" for source in sources])}"""

            # Envoi de la réponse formatée
            await progress_message.edit_text(
                formatted_response,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

        except asyncio.TimeoutError:
            logger.error("Timeout lors de la recherche")
            await progress_message.edit_text(
                "*fronce les sourcils* La recherche prend trop de temps. Essaie une requête plus simple.",
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Erreur dans search_command: {e}")
        logger.exception("Détails de l'erreur:")
        error_message = "*semble perplexe* Je ne peux pas effectuer cette recherche pour le moment."

        if progress_message:
            await progress_message.edit_text(error_message, parse_mode='Markdown')
        else:
            await update.message.reply_text(error_message, parse_mode='Markdown')

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /image avec une meilleure gestion des images de couverture"""
    progress_message = None
    try:
        query = ' '.join(context.args) if context.args else None
        if not query:
            await update.message.reply_text(
                "*lève un sourcil* Quelle image cherches-tu ?",
                parse_mode='Markdown'
            )
            return

        logger.info(f"Début de la recherche d'images pour la requête: {query}")

        # Message de progression initial
        progress_message = await update.message.reply_text(
            "*parcourt sa collection*\n_Recherche d'images en cours..._",
            parse_mode='Markdown'
        )

        # Recherche d'images
        scraper = GoogleImageScraper()
        logger.info(f"[DEBUG] Début de la recherche avec GoogleImageScraper pour query: {query}")
        image_urls = await scraper.search_images(query, max_results=10)
        logger.info(f"[DEBUG] URLs trouvées ({len(image_urls)}): {image_urls}")

        if not image_urls:
            logger.warning("[DEBUG] Aucune URL d'image trouvée, arrêt du processus")
            await progress_message.edit_text(
                "*fronce les sourcils* Je n'ai pas trouvé d'images correspondant à ta recherche.",
                parse_mode='Markdown'
            )
            return

        # Préparer l'album d'images
        media_group = []
        temp_files = []  # Pour garder une trace des fichiers à nettoyer
        quality_images = []  # Liste pour trier les images par qualité

        # Télécharger et vérifier la qualité de toutes les images
        for url in image_urls:
            try:
                logger.info(f"[DEBUG] Tentative de téléchargement pour URL: {url}")
                image_path = await media_handler.download_image(url)

                if image_path and os.path.exists(image_path):
                    # Vérifier la taille du fichier
                    file_size = os.path.getsize(image_path)
                    # Premier niveau de filtre : ignorer uniquement les images vraiment trop petites ou trop grandes
                    if file_size < 20 * 1024:  # 20KB (seuil plus bas)
                        logger.warning(f"[DEBUG] Image de trop faible qualité ({file_size/1024:.1f}KB): {image_path}")
                        continue
                    if file_size > 5 * 1024 * 1024:  # 5MB
                        logger.warning(f"[DEBUG] Image trop volumineuse ({file_size/1024/1024:.1f}MB): {image_path}")
                        continue

                    # Ajouter l'image à la liste de qualité avec sa taille
                    quality_images.append((file_size, image_path))
                    logger.info(f"[DEBUG] Image qualifiée: {image_path} ({file_size/1024:.1f}KB)")
                else:
                    logger.warning(f"[DEBUG] Échec du téléchargement pour {url}")
            except Exception as e:
                logger.error(f"[DEBUG] Erreur lors du téléchargement de {url}: {str(e)}")
                continue

        # Trier les images par taille (qualité)
        quality_images.sort(reverse=True)  # Tri par taille décroissante

        # Si nous avons moins de 5 images mais au moins une, on les utilise toutes
        best_images = quality_images[:5]  # Prendre jusqu'à 5 meilleures images

        # Si nous n'avons pas assez d'images, réessayer avec un seuil plus bas
        if len(best_images) < 3:
            logger.info("[DEBUG] Pas assez d'images trouvées, abaissement du seuil de qualité")
            quality_images = []  # Réinitialiser la liste
            for url in image_urls:
                try:
                    image_path = await media_handler.download_image(url)
                    if image_path and os.path.exists(image_path):
                        file_size = os.path.getsize(image_path)
                        # Seuil plus bas pour le second essai
                        if file_size < 10 * 1024:  # 10KB
                            continue
                        quality_images.append((file_size, image_path))
                except Exception as e:
                    logger.error(f"[DEBUG] Erreur lors du second essai: {str(e)}")
                    continue

            quality_images.sort(reverse=True)
            best_images = quality_images[:5]

        # Créer le groupe média avec les meilleures images
        for _, image_path in best_images:
            try:
                with open(image_path, 'rb') as photo_file:
                    media_group.append(
                        InputMediaPhoto(media=InputFile(photo_file))
                    )
                    temp_files.append(image_path)
                logger.info(f"[DEBUG] Image de haute qualité ajoutée à l'album: {image_path}")
            except Exception as e:
                logger.error(f"[DEBUG] Erreur lors de la lecture du fichier {image_path}: {str(e)}")
                continue

        if not media_group:
            logger.warning("[DEBUG] Aucune image de qualité suffisante n'a pu être préparée")
            await progress_message.edit_text(
                "*semble déçu* Je n'ai pas trouvé d'images de qualité suffisante.",
                parse_mode='Markdown'
            )
            return

        # Envoyer l'album complet
        try:
            logger.info(f"[DEBUG] Envoi de l'album avec {len(media_group)} images de haute qualité")
            await update.message.reply_media_group(media=media_group)  # Déjà limité à 5 images
            message_text = (
                "*range ses documents* Voici les meilleures images que j'ai trouvées "
                f"({len(media_group)} image{'s' if len(media_group) > 1 else ''})."
            )
            await progress_message.edit_text(
                message_text,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"[DEBUG] Erreur lors de l'envoi de l'album: {str(e)}")
            await progress_message.edit_text(
                "*semble troublé* Je n'ai pas pu envoyer les images.",
                parse_mode='Markdown'
            )
        finally:
            # Nettoyage des fichiers
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.info(f"[DEBUG] Fichier nettoyé: {temp_file}")
                except Exception as e:
                    logger.error(f"[DEBUG] Erreur lors du nettoyage de {temp_file}: {str(e)}")
            media_handler.cleanup()

    except Exception as e:
        logger.error(f"Erreur générale dans image_command: {e}", exc_info=True)
        error_message = "*semble perplexe* Je ne peux pas traiter ces images pour le moment."
        if progress_message:
            await progress_message.edit_text(error_message, parse_mode='Markdown')
        else:
            await update.message.reply_text(error_message, parse_mode='Markdown')
    finally:
        # Nettoyage final
        logger.info("Nettoyage final des ressources")
        media_handler.cleanup()

async def yt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /yt"""
    try:
        query = ' '.join(context.args) if context.args else None
        if not query:
            await update.message.reply_text("*lève un sourcil* Quelle vidéo cherches-tu ?", parse_mode='Markdown')
            return

        # Indiquer que le bot est en train d'écrire
        await update.message.chat.send_action(action="typing")

        # Rechercher les vidéos avec yt-dlp
        videos = await media_handler.search_youtube(query)
        if not videos:
            await update.message.reply_text("*fronce les sourcils* Je n'ai pas trouvé de vidéos correspondant à ta recherche.", parse_mode='Markdown')
            return

        # Créer les boutons pour chaque vidéo avec des titres plus clairs
        keyboard = []
        for i, video in enumerate(videos):
            title = video['title']
            # Limiter la longueur du titre si nécessaire
            if len(title) > 35:
                title = title[:32] + "..."

            # Ajouter la durée si disponible
            if 'duration_str' in video:
                title = f"{title} ({video['duration_str']})"

            # Créer un callback_data sécurisé
            video_id = video['url'].split('watch?v=')[-1].split('&')[0]
            callback_data = f"yt_{i}_{video_id}"
            keyboard.append([InlineKeyboardButton(title, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Créer un message de réponse détaillé
        message = "*consulte son catalogue* Voici les vidéos trouvées :\n\n"
        for i, video in enumerate(videos, 1):
            duration = video.get('duration_str', 'Durée inconnue')
            message += f"{i}. {video['title']} ({duration})\n"

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Erreur dans yt_command: {e}")
        logger.exception("Détails de l'erreur:")
        await update.message.reply_text("*semble troublé* Je ne peux pas rechercher de vidéos pour le moment.", parse_mode='Markdown')

async def handle_callback(update: Update, context: CallbackContext):
    """Gère les callbacks des boutons inline avec une meilleure gestion des fichiers"""
    query = update.callback_query
    try:
        await query.answer()

        if query.data.startswith('yt_'):
            parts = query.data.split('_', 2)
            if len(parts) != 3:
                raise ValueError("Format de callback incorrect")

            _, index, video_id = parts
            url = f"https://www.youtube.com/watch?v={video_id}"

            keyboard = [
                [InlineKeyboardButton("MP3 (Audio)", callback_data=f"format_mp3_{video_id}")],
                [InlineKeyboardButton("MP4 (Vidéo)", callback_data=f"format_mp4_{video_id}")]
            ]
            await query.edit_message_text(
                "*réfléchit* Dans quel format souhaites-tu cette vidéo ?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        elif query.data.startswith('format_'):
            parts = query.data.split('_', 2)
            if len(parts) != 3:
                raise ValueError("Format de callback incorrect")

            _, format_type, video_id = parts
            if format_type not in ['mp3', 'mp4']:
                raise ValueError("Format non supporté")

            url = f"https://www.youtube.com/watch?v={video_id}"

            # Message de progression
            progress_msg = await query.edit_message_text(
                "*commence le téléchargement* Préparation...",
                parse_mode='Markdown'
            )

            try:
                # Téléchargement avec timeout
                file_path = await asyncio.wait_for(
                    media_handler.download_youtube_video(url, format_type),
                    timeout=300  # 5 minutes maximum
                )

                if not file_path:
                    await progress_msg.edit_text(
                        "*fronce les sourcils* La vidéo n'est pas accessible. Essayez une vidéo plus courte ou de qualité inférieure.",
                        parse_mode='Markdown'
                    )
                    return

                await progress_msg.edit_message_text(
                    "*prépare l'envoi* Fichier téléchargé, vérification de la taille...",
                    parse_mode='Markdown'
                )

                try:
                    with open(file_path, 'rb') as f:
                        file_size = os.path.getsize(file_path)
                        size_mb = file_size / (1024 * 1024)

                        if size_mb > 50:  # 50MB
                            error_msg = f"Le fichier est trop volumineux pour Telegram ({size_mb:.1f}MB > 50MB). Essayez une vidéo plus courte."
                            await progress_msg.edit_text(
                                f"*semble désolé* {error_msg}",
                                parse_mode='Markdown'
                            )
                            return

                        if format_type == 'mp3':
                            await query.message.reply_audio(
                                audio=f,
                                caption=f"*range le fichier* Voici ton audio. (Taille: {size_mb:.1f}MB)",
                                parse_mode='Markdown'
                            )
                        else:
                            await query.message.reply_video(
                                video=f,
                                caption=f"*range le fichier* Voici ta vidéo. (Taille: {size_mb:.1f}MB)",
                                supports_streaming=True,
                                parse_mode='Markdown'
                            )

                    await progress_msg.edit_text(
                        "*termine le processus* Envoi terminé.",
                        parse_mode='Markdown'
                    )

                except TelegramError as te:
                    logger.error(f"Erreur Telegram lors de l'envoi du fichier: {te}")
                    await progress_msg.edit_text(
                        "*semble désolé* Impossible d'envoyer le fichier. Essayez une autre vidéo.",
                        parse_mode='Markdown'
                    )

                finally:
                    # Nettoyage des fichiers
                    media_handler.cleanup(os.path.dirname(file_path))

            except asyncio.TimeoutError:
                await progress_msg.edit_text(
                    "*semble frustré* Le téléchargement prend trop de temps. Essayez une vidéo plus courte.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                error_msg = str(e)
                if "trop volumineux" in error_msg.lower():
                    await progress_msg.edit_text(
                        f"*ajuste ses lunettes* {error_msg}. Essayez une vidéo plus courte ou de qualité inférieure.",
                        parse_mode='Markdown'
                    )
                else:
                    logger.error(f"Erreur lors du téléchargement/envoi: {e}")
                    await progress_msg.edit_text(
                        "*semble troublé* Une erreur est survenue lors du traitement du fichier.",
                        parse_mode='Markdown'
                    )

    except ValueError as ve:
        logger.error(f"Erreur de format dans handle_callback: {ve}")
        await query.message.reply_text(
            "*fronce les sourcils* Je ne comprends pas cette requête.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Erreur dans handle_callback: {e}")
        logger.exception("Détails de l'erreur:")
        await query.message.reply_text(
            "*semble troublé* Je ne peux pas traiter cette requête pour le moment.",
            parse_mode='Markdown'
        )

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
        context_message = f"[L'utilisateur s'appelle {nickname}."
        if admin_manager.is_admin(user_id):
            context_message += "C'est une personne familière avec la philosophie."
        context_message += f"]\n\n{message_text}"

        response = await sisyphe.get_response(context_message)
        await update.message.reply_text(response, parse_mode='Markdown')

    except TelegramError as e:
        logger.error(f"Erreur Telegram dans handle_message: {e}")
        await update.message.reply_text("*semble distrait*", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Erreur inattendue dans handle_message: {e}")
        logger.exception("Détails de l'erreur:")
        await update.message.reply_text("*fronce les sourcils* Une pensée m'échappe...", parse_mode='Markdown')

async def fiche_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la commande /fiche avec une meilleure gestion des images de couverture"""
    progress_message = None
    try:
        # Récupérer le titre
        titre = ' '.join(context.args) if context.args else None
        if not titre:
            if update.message.reply_to_message and update.message.reply_to_message.text:
                titre = update.message.reply_to_message.text
            else:
                await update.message.reply_text(
                    "*lève un sourcil* Quel anime/série souhaites-tu découvrir ?",
                    parse_mode='Markdown'
                )
                return

        user_id = update.effective_user.id
        logger.info(f"Fiche demandée par l'utilisateur {user_id}: {titre}")

        # Message de recherche en cours
        progress_message = await update.message.reply_text(
            "*consulte son catalogue*\n_Création de la fiche en cours..._",
            parse_mode='Markdown'
        )

        # Indiquer que le bot est en train d'écrire
        await update.message.chat.send_action(action="typing")

        try:
            # Limite de temps pour la création de la fiche
            result = await asyncio.wait_for(
                fiche_client.create_fiche(titre),
                timeout=45.0
            )

            if isinstance(result, dict) and "error" in result:
                error_msg = result["error"]
                logger.error(f"Erreur retournée par l'API: {error_msg}")
                await progress_message.edit_text(
                    f"*semble contrarié* {error_msg}",
                    parse_mode='Markdown'
                )
                return

            fiche = result.get("fiche", "")
            image_url = result.get("image_url")

            if not fiche or not fiche.strip():
                logger.error("Fiche vide reçue de l'API")
                await progress_message.edit_text(
                    "*fronce les sourcils* Je n'ai pas trouvé d'information sur ce titre.",
                    parse_mode='Markdown'
                )
                return

            # Envoi de la fiche
            await progress_message.edit_text(
                fiche,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

            # Gestion des images améliorée
            if image_url:
                try:
                    logger.info(f"Téléchargement de l'image de couverture: {image_url}")
                    image_paths = await media_handler.download_images([image_url])

                    if image_paths and len(image_paths) > 0:
                        image_path = image_paths[0]
                        try:
                            with open(image_path, 'rb') as f:
                                await update.message.reply_photo(
                                    photo=f,
                                    caption="*présente la couverture avec élégance*",
                                    parse_mode='Markdown'
                                )
                        except Exception as photo_error:
                            logger.error(f"Erreur lors de l'envoi de la photo: {photo_error}")
                except Exception as image_error:
                    logger.error(f"Erreur lors du traitement de l'image: {image_error}")

        except asyncio.TimeoutError:
            logger.error("Timeout lors de la création de la fiche")
            await progress_message.edit_text(
                "*fronce les sourcils* La création de la fiche prend trop de temps. Essaie une autre requête.",
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Erreur dans fiche_command: {e}")
        logger.exception("Détails de l'erreur:")
        error_message = "*semble perplexe* Je ne peux pas créer cette fiche pour le moment."

        if progress_message:
            await progress_message.edit_text(error_message, parse_mode='Markdown')
        else:
            await update.message.reply_text(error_message, parse_mode='Markdown')

    finally:
        # Nettoyer les fichiers temporaires si nécessaire
        if 'image_paths' in locals():
            media_handler.cleanup()