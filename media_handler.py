import os
import asyncio
import logging
import httpx
from typing import List, Dict, Optional, Tuple
import tempfile
import shutil
import time
import mimetypes

logger = logging.getLogger(__name__)

class MediaHandler:
    def __init__(self):
        """Initialise les répertoires temporaires pour les médias"""
        self.temp_dir = tempfile.mkdtemp(prefix='sisyphe_media_')

        # Créer des sous-dossiers spécifiques
        self.images_dir = os.path.join(self.temp_dir, 'images')
        os.makedirs(self.images_dir, exist_ok=True)
        os.chmod(self.images_dir, 0o755)

        logger.info(f"Dossiers temporaires créés dans: {self.temp_dir}")

    async def download_image(self, url: str) -> Optional[str]:
        """Télécharge une image depuis une URL avec plus de vérifications"""
        try:
            if not url or not isinstance(url, str):
                logger.warning("URL invalide")
                return None

            if not url.startswith(('http://', 'https://')):
                logger.warning(f"Protocole non supporté: {url}")
                return None

            logger.info(f"Tentative de téléchargement depuis: {url}")

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # Vérifier d'abord les en-têtes
                head_response = await client.head(url)
                content_type = head_response.headers.get('content-type', '').lower()
                content_length = int(head_response.headers.get('content-length', 0))

                # Vérification du type MIME
                if not content_type.startswith('image/'):
                    logger.warning(f"Type de contenu non supporté: {content_type}")
                    return None

                # Vérification de la taille avant téléchargement
                if content_length > 5 * 1024 * 1024:  # 5MB
                    logger.warning(f"Fichier trop volumineux: {content_length/1024/1024:.2f}MB")
                    return None

                # Téléchargement du contenu
                response = await client.get(url)
                response.raise_for_status()

                # Vérification finale du type MIME
                extension = mimetypes.guess_extension(content_type) or '.jpg'
                if extension not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    logger.warning(f"Extension non supportée: {extension}")
                    return None

                # Génération du nom de fichier unique
                filename = f"image_{int(time.time())}_{os.urandom(4).hex()}{extension}"
                temp_path = os.path.join(self.images_dir, filename)

                # Écriture du fichier
                with open(temp_path, 'wb') as f:
                    f.write(response.content)

                logger.info(f"Image téléchargée avec succès: {temp_path}")
                return temp_path

        except httpx.HTTPError as e:
            logger.error(f"Erreur HTTP lors du téléchargement: {e}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement: {e}")
            return None

    async def download_images(self, urls: List[str]) -> List[str]:
        """Télécharge plusieurs images en parallèle avec gestion d'erreurs améliorée"""
        if not urls:
            logger.warning("Aucune URL fournie pour le téléchargement")
            return []

        valid_urls = [url for url in urls if url and isinstance(url, str) and 
                     url.startswith(('http://', 'https://'))]

        if not valid_urls:
            logger.warning("Aucune URL valide trouvée")
            return []

        logger.info(f"Début du téléchargement de {len(valid_urls)} images")
        tasks = [self.download_image(url) for url in valid_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_paths = []
        for i, result in enumerate(results):
            if isinstance(result, str) and os.path.exists(result):
                valid_paths.append(result)
            else:
                logger.error(f"Échec du téléchargement pour l'URL {valid_urls[i]}: {result}")

        logger.info(f"Téléchargement terminé. {len(valid_paths)}/{len(valid_urls)} images réussies")
        return valid_paths

    def cleanup(self, specific_path: Optional[str] = None):
        """Nettoie les fichiers temporaires avec plus de logs"""
        try:
            if specific_path and os.path.exists(specific_path):
                logger.info(f"Nettoyage du fichier spécifique: {specific_path}")
                os.remove(specific_path)
                logger.info("Fichier supprimé avec succès")
            else:
                logger.info(f"Nettoyage du répertoire temporaire: {self.temp_dir}")
                for root, dirs, files in os.walk(self.temp_dir):
                    for file in files:
                        try:
                            file_path = os.path.join(root, file)
                            os.remove(file_path)
                            logger.info(f"Fichier supprimé: {file_path}")
                        except Exception as e:
                            logger.error(f"Erreur lors de la suppression de {file_path}: {e}")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {e}")