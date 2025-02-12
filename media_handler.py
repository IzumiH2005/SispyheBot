<replit_final_file>
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
        # Créer un dossier temporaire principal avec un nom unique
        self.temp_dir = tempfile.mkdtemp(prefix='sisyphe_media_')

        # Créer des sous-dossiers spécifiques
        self.images_dir = os.path.join(self.temp_dir, 'images')
        self.videos_dir = os.path.join(self.temp_dir, 'videos')
        self.audio_dir = os.path.join(self.temp_dir, 'audio')

        # Créer tous les sous-dossiers
        for directory in [self.images_dir, self.videos_dir, self.audio_dir]:
            os.makedirs(directory, exist_ok=True)
            # S'assurer que les permissions sont correctes (lecture et écriture)
            os.chmod(directory, 0o755)

        logger.info(f"Dossiers temporaires créés dans: {self.temp_dir}")
        logger.debug(f"Dossier images: {self.images_dir}")
        logger.debug(f"Dossier vidéos: {self.videos_dir}")
        logger.debug(f"Dossier audio: {self.audio_dir}")

        # Vérifier les permissions
        for directory in [self.images_dir, self.videos_dir, self.audio_dir]:
            if not os.access(directory, os.W_OK):
                logger.error(f"Pas de permission d'écriture sur {directory}")
            if not os.access(directory, os.R_OK):
                logger.error(f"Pas de permission de lecture sur {directory}")

        self.last_youtube_request = 0

    async def download_image(self, url: str) -> Optional[str]:
        """Télécharge une image depuis une URL avec une meilleure gestion des fichiers temporaires"""
        try:
            if not url or not isinstance(url, str):
                logger.error(f"URL invalide: {url}")
                return None

            if not url.startswith(('http://', 'https://')):
                logger.error(f"Format d'URL invalide: {url}")
                return None

            logger.info(f"Téléchargement de l'image depuis: {url}")

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    logger.debug(f"Statut de la réponse: {response.status_code}")
                except httpx.HTTPError as e:
                    logger.error(f"Erreur HTTP lors du téléchargement: {e}")
                    return None

                # Vérifier le content-type
                content_type = response.headers.get('content-type', '').lower()
                if not content_type.startswith('image/'):
                    logger.error(f"Content-type non valide: {content_type}")
                    return None

                # Créer un nom de fichier unique avec l'extension appropriée
                extension = content_type.split('/')[-1].split(';')[0]
                if not extension or extension not in ['jpeg', 'jpg', 'png', 'gif', 'webp']:
                    extension = 'jpg'  # Extension par défaut
                filename = f"image_{os.urandom(8).hex()}.{extension}"
                temp_path = os.path.join(self.images_dir, filename)

                logger.debug(f"Sauvegarde de l'image dans: {temp_path}")

                try:
                    # Écrire le fichier
                    with open(temp_path, 'wb') as f:
                        f.write(response.content)

                    # S'assurer que les permissions sont correctes
                    os.chmod(temp_path, 0o644)

                    # Vérifications post-téléchargement
                    if not os.path.exists(temp_path):
                        logger.error("Le fichier n'a pas été créé")
                        return None

                    file_size = os.path.getsize(temp_path)
                    logger.debug(f"Taille du fichier téléchargé: {file_size/1024:.1f}KB")

                    if file_size == 0:
                        logger.error("Le fichier téléchargé est vide")
                        os.remove(temp_path)
                        return None

                    if file_size > 10 * 1024 * 1024:  # 10MB
                        logger.error(f"Fichier trop volumineux: {file_size/1024/1024:.2f}MB")
                        os.remove(temp_path)
                        return None

                    # Vérifier que le fichier est bien une image valide
                    try:
                        with open(temp_path, 'rb') as f:
                            magic_number = f.read(4)
                            if not any(magic_number.startswith(sig) for sig in [
                                b'\xFF\xD8\xFF',  # JPEG
                                b'\x89PNG',       # PNG
                                b'GIF8',          # GIF
                                b'RIFF'           # WEBP
                            ]):
                                logger.error("Format de fichier non valide")
                                os.remove(temp_path)
                                return None
                    except Exception as e:
                        logger.error(f"Erreur lors de la vérification du format: {e}")
                        os.remove(temp_path)
                        return None

                    logger.info(f"Image téléchargée avec succès: {temp_path} ({file_size/1024:.1f}KB)")
                    return temp_path

                except IOError as e:
                    logger.error(f"Erreur lors de l'écriture du fichier: {e}")
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return None

        except Exception as e:
            logger.error(f"Erreur inattendue lors du téléchargement: {e}")
            return None

    def cleanup(self, specific_path: Optional[str] = None):
        """Nettoie les fichiers temporaires"""
        try:
            if specific_path and os.path.exists(specific_path):
                # Nettoyer un fichier ou dossier spécifique
                try:
                    if os.path.isfile(specific_path):
                        os.remove(specific_path)
                        logger.info(f"Fichier supprimé: {specific_path}")
                    else:
                        shutil.rmtree(specific_path, ignore_errors=True)
                        logger.info(f"Dossier supprimé: {specific_path}")
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression de {specific_path}: {e}")
            else:
                # Nettoyer tous les dossiers temporaires
                cleaned_files = 0
                for dir_path in [self.images_dir, self.videos_dir, self.audio_dir]:
                    if os.path.exists(dir_path):
                        for filename in os.listdir(dir_path):
                            file_path = os.path.join(dir_path, filename)
                            try:
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                                    cleaned_files += 1
                                    logger.debug(f"Fichier supprimé: {file_path}")
                                else:
                                    shutil.rmtree(file_path)
                                    cleaned_files += 1
                                    logger.debug(f"Dossier supprimé: {file_path}")
                            except Exception as e:
                                logger.error(f"Erreur lors de la suppression de {file_path}: {e}")
                logger.info(f"Nettoyage terminé: {cleaned_files} fichiers/dossiers supprimés")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {e}")

    async def download_images(self, urls: List[str]) -> List[str]:
        """Télécharge plusieurs images en parallèle avec une meilleure gestion des erreurs"""
        if not urls:
            logger.warning("Aucune URL fournie")
            return []

        # Filtrer les URLs invalides
        valid_urls = [url for url in urls if url and isinstance(url, str) and url.startswith(('http://', 'https://'))]
        if not valid_urls:
            logger.warning("Aucune URL valide trouvée")
            return []

        logger.info(f"Début du téléchargement de {len(valid_urls)} images")

        # Limiter les téléchargements simultanés
        semaphore = asyncio.Semaphore(3)

        async def download_with_semaphore(url: str) -> Optional[str]:
            async with semaphore:
                return await self.download_image(url)

        # Télécharger toutes les images
        tasks = [download_with_semaphore(url) for url in valid_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtrer les résultats valides
        valid_paths = []
        for path in results:
            if isinstance(path, str) and os.path.exists(path):
                file_size = os.path.getsize(path)
                logger.debug(f"Image valide: {path} ({file_size/1024:.1f}KB)")
                valid_paths.append(path)
            elif isinstance(path, Exception):
                logger.error(f"Erreur lors du téléchargement: {path}")

        logger.info(f"Téléchargement terminé: {len(valid_paths)}/{len(urls)} images réussies")
        return valid_paths
    
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