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
        """Initialise le gestionnaire de médias avec des dossiers temporaires dédiés"""
        self.base_temp_dir = tempfile.mkdtemp(prefix='sisyphe_media_')
        self.images_dir = os.path.join(self.base_temp_dir, 'images')
        self.videos_dir = os.path.join(self.base_temp_dir, 'videos')
        self.audio_dir = os.path.join(self.base_temp_dir, 'audio')

        # Créer les sous-dossiers
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

        self.last_youtube_request = 0
        logger.info(f"Dossiers temporaires créés dans: {self.base_temp_dir}")

    async def download_image(self, url: str) -> Optional[str]:
        """Télécharge une image depuis une URL avec des vérifications améliorées"""
        try:
            logger.info(f"Tentative de téléchargement de l'image: {url}")
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Vérifier le type de contenu
                content_type = response.headers.get('content-type', '').lower()
                logger.info(f"Type de contenu détecté: {content_type}")

                if not any(mime in content_type for mime in ['image/jpeg', 'image/png', 'image/gif', 'image/webp']):
                    logger.warning(f"Type de contenu non supporté: {content_type}")
                    return None

                # Vérifier la taille avant de télécharger (limite à 10MB)
                content_length = len(response.content)
                if content_length > 10 * 1024 * 1024:  # 10MB
                    logger.warning(f"Image trop grande: {content_length / 1024 / 1024:.2f}MB")
                    return None

                # Déterminer l'extension
                ext_map = {
                    'image/jpeg': 'jpg',
                    'image/png': 'png',
                    'image/gif': 'gif',
                    'image/webp': 'webp'
                }
                ext = ext_map.get(content_type, 'jpg')

                # Créer un nom de fichier unique
                temp_path = os.path.join(self.images_dir, f"image_{os.urandom(8).hex()}.{ext}")

                # Sauvegarder l'image
                with open(temp_path, 'wb') as f:
                    f.write(response.content)

                logger.info(f"Image téléchargée avec succès: {temp_path}")
                return temp_path

        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de {url}: {e}")
            logger.exception("Détails de l'erreur:")
            return None

    async def download_youtube_video(self, url: str, format_type: str = 'mp4', max_size_mb: int = 70) -> Optional[str]:
        """Télécharge une vidéo YouTube dans le format spécifié avec gestion améliorée"""
        try:
            output_dir = self.audio_dir if format_type == 'mp3' else self.videos_dir
            output_template = os.path.join(output_dir, f'%(title)s.%(ext)s')

            # Options de base communes
            ydl_opts = {
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'writethumbnail': False,
                'writeinfojson': False,
                'ffmpeg_location': 'ffmpeg',
                'max_filesize': max_size_mb * 1024 * 1024,  # Limite à 70MB
            }

            # Options spécifiques au format
            if format_type == 'mp3':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:  # mp4
                ydl_opts.update({
                    'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[ext=mp4]',
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
                # Extraire les informations avant le téléchargement
                info = ydl.extract_info(url, download=False)
                logger.info(f"Informations vidéo extraites: {info.get('title')}")

                # Vérifier la taille estimée si disponible
                filesize = info.get('filesize') or info.get('filesize_approx')
                if filesize and filesize > max_size_mb * 1024 * 1024:
                    raise Exception(f"Fichier trop volumineux: {filesize / 1024 / 1024:.2f}MB")

                # Télécharger la vidéo
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                # Ajuster l'extension si nécessaire
                if format_type == 'mp3':
                    filename = filename.rsplit('.', 1)[0] + '.mp3'
                elif not filename.endswith('.mp4'):
                    filename = filename.rsplit('.', 1)[0] + '.mp4'

                # Vérifier le fichier final
                if not os.path.exists(filename):
                    raise Exception("Le fichier n'a pas été créé")

                if os.path.getsize(filename) == 0:
                    os.remove(filename)
                    raise Exception("Le fichier téléchargé est vide")

                logger.info(f"Téléchargement réussi: {filename}")
                return filename

        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de la vidéo {url}: {e}")
            logger.exception("Détails de l'erreur:")
            return None

    async def download_images(self, urls: List[str]) -> List[str]:
        """Télécharge plusieurs images en parallèle avec une limite de concurrence"""
        # Limiter le nombre de téléchargements simultanés à 5
        semaphore = asyncio.Semaphore(5)

        async def download_with_semaphore(url):
            async with semaphore:
                return await self.download_image(url)

        tasks = [download_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return [path for path in results if path is not None]

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
                'extract_flat': True,
                'default_search': 'ytsearch5'
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch5:{query}", download=False)
                videos = []

                if 'entries' in results:
                    for entry in results['entries'][:5]:
                        if entry:
                            duration = entry.get('duration', 0)
                            minutes = duration // 60
                            seconds = duration % 60

                            videos.append({
                                'title': entry.get('title', ''),
                                'url': entry.get('webpage_url', ''),
                                'duration': duration,
                                'duration_str': f"{minutes}:{seconds:02d}",
                                'thumbnail': entry.get('thumbnail', '')
                            })

                return videos

        except Exception as e:
            logger.error(f"Erreur lors de la recherche YouTube: {e}")
            logger.exception("Détails de l'erreur:")
            return []

    def cleanup(self):
        """Nettoie tous les fichiers temporaires"""
        try:
            shutil.rmtree(self.base_temp_dir)
            logger.info("Nettoyage des fichiers temporaires effectué")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des fichiers temporaires: {e}")