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

        # Créer des sous-dossiers spécifiques
        self.images_dir = os.path.join(self.temp_dir, 'images')
        self.videos_dir = os.path.join(self.temp_dir, 'videos')
        self.audio_dir = os.path.join(self.temp_dir, 'audio')

        # Créer tous les sous-dossiers avec les bonnes permissions
        for directory in [self.images_dir, self.videos_dir, self.audio_dir]:
            os.makedirs(directory, exist_ok=True)
            os.chmod(directory, 0o755)

        self.last_youtube_request = 0
        logger.info(f"Dossiers temporaires créés dans: {self.temp_dir}")

    async def download_image(self, url: str) -> Optional[str]:
        """Télécharge une image depuis une URL"""
        try:
            if not url or not isinstance(url, str):
                logger.error(f"URL invalide: {url}")
                return None

            if not url.startswith(('http://', 'https://')):
                logger.error(f"Format d'URL invalide: {url}")
                return None

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

                content_type = response.headers.get('content-type', '').lower()
                if not content_type.startswith('image/'):
                    logger.error(f"Content-type non valide: {content_type}")
                    return None

                extension = content_type.split('/')[-1].split(';')[0]
                if extension not in ['jpeg', 'jpg', 'png', 'gif', 'webp']:
                    extension = 'jpg'

                filename = f"image_{os.urandom(8).hex()}.{extension}"
                temp_path = os.path.join(self.images_dir, filename)

                with open(temp_path, 'wb') as f:
                    f.write(response.content)
                os.chmod(temp_path, 0o644)

                file_size = os.path.getsize(temp_path)
                if file_size == 0 or file_size > 10 * 1024 * 1024:  # Max 10MB
                    os.remove(temp_path)
                    return None

                return temp_path

        except Exception as e:
            logger.error(f"Erreur lors du téléchargement: {e}")
            return None

    async def download_images(self, urls: List[str]) -> List[str]:
        """Télécharge plusieurs images en parallèle"""
        if not urls:
            return []

        valid_urls = [url for url in urls if url and isinstance(url, str) and 
                     url.startswith(('http://', 'https://'))]

        semaphore = asyncio.Semaphore(3)
        async def download_with_semaphore(url: str) -> Optional[str]:
            async with semaphore:
                return await self.download_image(url)

        tasks = [download_with_semaphore(url) for url in valid_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_paths = [path for path in results if isinstance(path, str) and os.path.exists(path)]
        return valid_paths

    def cleanup(self, specific_path: Optional[str] = None):
        """Nettoie les fichiers temporaires"""
        try:
            if specific_path and os.path.exists(specific_path):
                if os.path.isfile(specific_path):
                    os.remove(specific_path)
                else:
                    shutil.rmtree(specific_path, ignore_errors=True)
            else:
                for dir_path in [self.images_dir, self.videos_dir, self.audio_dir]:
                    if os.path.exists(dir_path):
                        shutil.rmtree(dir_path, ignore_errors=True)
                        os.makedirs(dir_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {e}")

    async def download_youtube_video(self, url: str, format_type: str = 'mp4', max_size_mb: int = 75) -> Optional[str]:
        """Télécharge une vidéo YouTube"""
        try:
            download_id = os.urandom(8).hex()
            output_dir = os.path.join(self.audio_dir if format_type == 'mp3' else self.videos_dir, download_id)
            os.makedirs(output_dir, exist_ok=True)

            output_template = os.path.join(output_dir, f'%(title)s.%(ext)s')
            ydl_opts = {
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'max_filesize': max_size_mb * 1024 * 1024,
                'format': 'worstaudio/worst' if format_type == 'mp3' else 'worst[ext=mp4]',
            }

            if format_type == 'mp3':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '64',
                }]

            # Rate limiting
            await asyncio.sleep(max(0, 2 - (time.time() - self.last_youtube_request)))
            self.last_youtube_request = time.time()

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                if format_type == 'mp3':
                    filename = os.path.splitext(filename)[0] + '.mp3'
                elif not filename.endswith('.mp4'):
                    filename = os.path.splitext(filename)[0] + '.mp4'

                if os.path.exists(filename) and os.path.getsize(filename) <= max_size_mb * 1024 * 1024:
                    return filename
                else:
                    if os.path.exists(filename):
                        os.remove(filename)
                    return None

        except Exception as e:
            logger.error(f"Erreur téléchargement YouTube: {e}")
            if 'output_dir' in locals() and os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            return None

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