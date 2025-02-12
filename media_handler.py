import os
import asyncio
import logging
import yt_dlp
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
import tempfile
import shutil
import time

logger = logging.getLogger(__name__)

class MediaHandler:
    def __init__(self):
        """Initialise les répertoires temporaires pour les médias"""
        self.temp_dir = tempfile.mkdtemp(prefix='sisyphe_media_')
        self.images_dir = os.path.join(self.temp_dir, 'images')
        self.videos_dir = os.path.join(self.temp_dir, 'videos')
        self.audio_dir = os.path.join(self.temp_dir, 'audio')

        # Créer les sous-répertoires s'ils n'existent pas
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)
        logger.info(f"Répertoires temporaires créés: {self.temp_dir}")
        logger.debug(f"Répertoire images: {self.images_dir}")
        logger.debug(f"Répertoire videos: {self.videos_dir}")
        logger.debug(f"Répertoire audio: {self.audio_dir}")

        # Vérifier les permissions
        if not os.access(self.images_dir, os.W_OK):
            logger.error(f"Pas de permission d'écriture sur {self.images_dir}")
        if not os.access(self.videos_dir, os.W_OK):
            logger.error(f"Pas de permission d'écriture sur {self.videos_dir}")
        if not os.access(self.audio_dir, os.W_OK):
            logger.error(f"Pas de permission d'écriture sur {self.audio_dir}")

        self.last_youtube_request = 0
        logger.info(f"Dossiers temporaires créés dans: {self.temp_dir}")


    async def download_image(self, url: str) -> Optional[str]:
        """Télécharge une image depuis une URL avec des vérifications améliorées"""
        try:
            # Validation basique de l'URL
            if not url or not isinstance(url, str):
                logger.error(f"URL invalide: {url}")
                return None

            # Vérifier que l'URL commence par http:// ou https:// et a un domaine valide
            if not url.startswith(('http://', 'https://')) or len(url.split('/')) < 3:
                logger.error(f"Format d'URL invalide: {url}")
                return None

            logger.info(f"Tentative de téléchargement de l'image: {url}")
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                try:
                    logger.debug(f"Envoi de la requête GET à {url}")
                    response = await client.get(url)
                    response.raise_for_status()
                    logger.debug(f"Réponse reçue avec statut: {response.status_code}")
                except httpx.ConnectError as e:
                    logger.error(f"Erreur de connexion pour {url}: {e}")
                    return None
                except httpx.HTTPError as e:
                    logger.error(f"Erreur HTTP pour {url}: {e}")
                    return None

                # Vérifier la taille avant de télécharger (limite à 10MB)
                content_length = len(response.content)
                logger.debug(f"Taille du contenu: {content_length / 1024 / 1024:.2f}MB")
                if content_length > 10 * 1024 * 1024:  # 10MB
                    logger.warning(f"Image trop grande: {content_length / 1024 / 1024:.2f}MB")
                    return None

                # Créer un nom de fichier unique
                filename = f"image_{os.urandom(8).hex()}"
                temp_path = os.path.join(self.images_dir, filename)
                logger.debug(f"Chemin du fichier temporaire: {temp_path}")

                try:
                    # Sauvegarder l'image
                    with open(temp_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"Image téléchargée avec succès: {temp_path}")

                    # Vérifier que le fichier existe et est accessible
                    if not os.path.exists(temp_path):
                        logger.error(f"Le fichier n'existe pas après l'écriture: {temp_path}")
                        return None
                    if not os.path.getsize(temp_path) > 0:
                        logger.error(f"Le fichier est vide après l'écriture: {temp_path}")
                        return None

                    return temp_path
                except IOError as e:
                    logger.error(f"Erreur lors de l'écriture du fichier {temp_path}: {e}")
                    return None

        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de {url}: {e}")
            return None

    async def download_youtube_video(self, url: str, format_type: str = 'mp4', max_size_mb: int = 75) -> Optional[str]:
        """Télécharge une vidéo YouTube dans le format spécifié avec gestion améliorée"""
        try:
            # Créer un sous-dossier unique pour ce téléchargement
            download_id = os.urandom(8).hex()
            output_dir = os.path.join(self.audio_dir if format_type == 'mp3' else self.videos_dir, download_id)
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Dossier de téléchargement créé: {output_dir}")

            output_template = os.path.join(output_dir, f'%(title)s.%(ext)s')

            # Options de base communes
            ydl_opts = {
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'writethumbnail': False,
                'writeinfojson': False,
                'ffmpeg_location': shutil.which('ffmpeg'),
                'max_filesize': max_size_mb * 1024 * 1024,  # Limite à 75MB
            }

            # Options spécifiques au format
            if format_type == 'mp3':
                ydl_opts.update({
                    'format': 'worstaudio/worst',  # Prend la qualité audio la plus basse
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '64',  # Réduit encore plus la qualité à 64kbps
                    }],
                })
            else:  # mp4
                ydl_opts.update({
                    # Essaie d'abord 240p, puis 360p si non disponible, puis la plus basse qualité
                    'format': 'worst[height<=240][ext=mp4]/worst[height<=360][ext=mp4]/worst[ext=mp4]',
                    'merge_output_format': 'mp4',
                })

            logger.info(f"Début du téléchargement depuis {url} en format {format_type}")
            logger.debug(f"Options yt-dlp: {ydl_opts}")

            # Respecter le rate limit
            current_time = time.time()
            if current_time - self.last_youtube_request < 2:
                await asyncio.sleep(2 - (current_time - self.last_youtube_request))
            self.last_youtube_request = time.time()

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # Extraire les informations avant le téléchargement
                    info = ydl.extract_info(url, download=False)
                    logger.info(f"Informations vidéo extraites: {info.get('title')}")

                    # Vérifier la taille estimée si disponible
                    filesize = info.get('filesize') or info.get('filesize_approx')
                    if filesize:
                        size_mb = filesize / (1024 * 1024)
                        logger.info(f"Taille estimée du fichier: {size_mb:.1f}MB")
                        if size_mb > max_size_mb:
                            raise Exception(f"Fichier trop volumineux ({size_mb:.1f}MB > {max_size_mb}MB)")

                    # Télécharger la vidéo
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)

                    # Ajuster l'extension si nécessaire
                    if format_type == 'mp3':
                        filename = filename.rsplit('.', 1)[0] + '.mp3'
                    elif not filename.endswith('.mp4'):
                        filename = filename.rsplit('.', 1)[0] + '.mp4'

                    logger.info(f"Téléchargement réussi: {filename}")

                    # Vérifier si le fichier existe et sa taille
                    if not os.path.exists(filename):
                        raise Exception("Le fichier n'a pas été créé")

                    actual_size = os.path.getsize(filename)
                    actual_size_mb = actual_size / (1024 * 1024)
                    logger.info(f"Taille réelle du fichier: {actual_size_mb:.1f}MB")

                    if actual_size > max_size_mb * 1024 * 1024:
                        # Nettoyer le fichier avant de lever l'exception
                        os.remove(filename)
                        raise Exception(f"Fichier final trop volumineux: {actual_size_mb:.1f}MB")

                    return filename

                except Exception as e:
                    logger.error(f"Erreur lors du téléchargement/traitement: {e}")
                    # Nettoyer en cas d'erreur
                    if 'filename' in locals() and os.path.exists(filename):
                        os.remove(filename)
                    raise

        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de la vidéo {url}: {e}")
            logger.exception("Détails de l'erreur:")
            # Nettoyer le dossier en cas d'erreur
            if 'output_dir' in locals():
                shutil.rmtree(output_dir, ignore_errors=True)
            return None

    async def download_images(self, urls: List[str]) -> List[str]:
        """Télécharge plusieurs images en parallèle avec une limite de concurrence et meilleure gestion des erreurs"""
        # Limiter le nombre de téléchargements simultanés à 3 pour éviter la surcharge
        semaphore = asyncio.Semaphore(3)

        async def download_with_semaphore(url):
            try:
                async with semaphore:
                    return await self.download_image(url)
            except Exception as e:
                logger.error(f"Erreur lors du téléchargement de {url}: {e}")
                return None

        # Filtrer les URLs invalides
        valid_urls = [url for url in urls if url and isinstance(url, str) and url.startswith(('http://', 'https://'))]

        if not valid_urls:
            logger.warning("Aucune URL valide fournie pour le téléchargement")
            return []

        tasks = [download_with_semaphore(url) for url in valid_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtrer les résultats pour ne garder que les chemins valides
        successful_downloads = [path for path in results if path and isinstance(path, str) and os.path.exists(path)]

        if not successful_downloads:
            logger.warning("Aucune image n'a pu être téléchargée avec succès")
        else:
            logger.info(f"Téléchargement réussi de {len(successful_downloads)} images sur {len(urls)} tentatives")

        return successful_downloads

    async def search_youtube(self, query: str) -> List[Dict[str, str]]:
        """Recherche des vidéos YouTube avec gestion améliorée du rate limiting"""
        try:
            # Respecter le rate limit
            current_time = time.time()
            if current_time - self.last_youtube_request < 2:
                await asyncio.sleep(2 - (current_time - self.last_youtube_request))
            self.last_youtube_request = time.time()

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': 'in_playlist',
                'default_search': 'ytsearch5'
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch5:{query}", download=False)
                videos = []

                if 'entries' in results:
                    for entry in results['entries'][:5]:
                        if entry:
                            try:
                                duration = int(float(entry.get('duration', 0)))
                                minutes = duration // 60
                                seconds = duration % 60
                                duration_str = f"{minutes}:{seconds:02d}"
                            except (ValueError, TypeError):
                                duration_str = "??:??"

                            # S'assurer que l'URL est valide
                            url = entry.get('url') or entry.get('webpage_url', '')
                            if not url.startswith('http'):
                                video_id = entry.get('id', '')
                                url = f"https://www.youtube.com/watch?v={video_id}"

                            videos.append({
                                'title': entry.get('title', 'Sans titre'),
                                'url': url,
                                'duration': duration,
                                'duration_str': duration_str,
                                'thumbnail': entry.get('thumbnail', '')
                            })

                logger.info(f"Recherche YouTube réussie: {len(videos)} vidéos trouvées")
                return videos

        except Exception as e:
            logger.error(f"Erreur lors de la recherche YouTube: {e}")
            logger.exception("Détails de l'erreur:")
            return []

    def cleanup(self, specific_path: Optional[str] = None):
        """Nettoie les fichiers temporaires
        Args:
            specific_path: Chemin spécifique à nettoyer. Si None, nettoie tous les dossiers temporaires.
        """
        try:
            if specific_path and os.path.exists(specific_path):
                if os.path.isfile(specific_path):
                    os.remove(specific_path)
                    logger.info(f"Fichier temporaire supprimé: {specific_path}")
                else:
                    shutil.rmtree(specific_path, ignore_errors=True)
                    logger.info(f"Dossier temporaire supprimé: {specific_path}")
            else:
                # Nettoyer tous les dossiers temporaires
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                # Recréer les dossiers de base
                os.makedirs(self.images_dir, exist_ok=True)
                os.makedirs(self.videos_dir, exist_ok=True)
                os.makedirs(self.audio_dir, exist_ok=True)
                logger.info("Nettoyage complet des fichiers temporaires effectué")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des fichiers temporaires: {e}")
            logger.exception("Détails de l'erreur:")