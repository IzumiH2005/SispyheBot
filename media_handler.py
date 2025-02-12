import os
import asyncio
import logging
import yt_dlp
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
import tempfile
import shutil

logger = logging.getLogger(__name__)

class MediaHandler:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Dossier temporaire créé: {self.temp_dir}")

    async def download_image(self, url: str) -> Optional[str]:
        """Télécharge une image depuis une URL"""
        try:
            logger.info(f"Tentative de téléchargement de l'image: {url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

                # Vérifier le type de contenu
                content_type = response.headers.get('content-type', '')
                logger.info(f"Type de contenu détecté: {content_type}")

                if not content_type.startswith('image/'):
                    logger.warning(f"Le contenu n'est pas une image: {content_type}")
                    return None

                # Créer un nom de fichier unique avec la bonne extension
                file_ext = content_type.split('/')[-1].lower()
                if file_ext not in ['jpeg', 'jpg', 'png', 'gif', 'webp']:
                    file_ext = 'jpg'

                temp_path = os.path.join(self.temp_dir, f"image_{os.urandom(8).hex()}.{file_ext}")

                # Vérifier la taille du fichier (limite à 10MB)
                content_length = len(response.content)
                if content_length > 10 * 1024 * 1024:
                    logger.warning(f"Image trop grande: {content_length / 1024 / 1024:.2f}MB")
                    return None

                with open(temp_path, 'wb') as f:
                    f.write(response.content)

                logger.info(f"Image téléchargée avec succès: {temp_path}")
                return temp_path

        except httpx.TimeoutException:
            logger.error(f"Timeout lors du téléchargement de {url}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP lors du téléchargement de {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur inattendue lors du téléchargement de {url}: {e}")
            return None

    async def download_images(self, urls: List[str]) -> List[str]:
        """Télécharge plusieurs images en parallèle"""
        tasks = [self.download_image(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return [path for path in results if path is not None]

    async def download_youtube_video(self, url: str, format_type: str = 'mp4', max_size_mb: int = 75) -> Optional[str]:
        """Télécharge une vidéo YouTube dans le format spécifié"""
        try:
            output_template = os.path.join(self.temp_dir, f'%(title)s.%(ext)s')

            ydl_opts = {
                'format': 'ba' if format_type == 'mp3' else 'bv*[height<=720]+ba/b[height<=720]',
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }] if format_type == 'mp3' else [],
                'max_filesize': max_size_mb * 1024 * 1024,  # Convertir en bytes
                'writethumbnail': False,
                'writeinfojson': False,
            }

            logger.info(f"Début du téléchargement de {url} en format {format_type}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Vérifier la taille avant le téléchargement
                info = ydl.extract_info(url, download=False)
                logger.info(f"Informations vidéo extraites: {info.get('title')}")

                # Télécharger la vidéo
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                if format_type == 'mp3':
                    filename = filename.rsplit('.', 1)[0] + '.mp3'

                logger.info(f"Téléchargement réussi: {filename}")
                return filename

        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de la vidéo {url}: {e}")
            return None

    def cleanup(self):
        """Nettoie les fichiers temporaires"""
        try:
            shutil.rmtree(self.temp_dir)
            logger.info("Nettoyage des fichiers temporaires effectué")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des fichiers temporaires: {e}")