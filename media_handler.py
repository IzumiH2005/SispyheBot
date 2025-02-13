import os
import asyncio
import logging
import httpx
from typing import List, Optional
import tempfile
import time
from PIL import Image
import io

logger = logging.getLogger(__name__)

class MediaHandler:
    def __init__(self):
        """Initialise le gestionnaire de médias"""
        self.temp_dir = tempfile.mkdtemp(prefix='sisyphe_media_')
        logger.info(f"[DEBUG] Dossier temporaire créé: {self.temp_dir}")

        # Formats supportés
        self.supported_formats = {'JPEG', 'JPG', 'PNG', 'GIF', 'WEBP'}
        self.max_size = 5 * 1024 * 1024  # 5MB
        self.target_size = 1600  # px

        # Domaines autorisés pour les images
        self.allowed_domains = {'zerochan.net', 'pinterest.com', 'pinimg.com'}

    async def download_image(self, url: str) -> Optional[str]:
        """Télécharge et traite une image"""
        try:
            logger.info(f"[DEBUG] Téléchargement depuis: {url}")

            # Vérifier le domaine
            domain = url.split('/')[2].lower()
            if not any(allowed in domain for allowed in self.allowed_domains):
                logger.warning(f"[DEBUG] Domaine non autorisé: {domain}")
                return None

            # Télécharger l'image
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Créer l'objet Image
                img = Image.open(io.BytesIO(response.content))

                # Vérifier le format
                if not img.format:
                    logger.warning("[DEBUG] Format non détecté")
                    return None

                format_name = img.format.upper()
                if format_name not in self.supported_formats:
                    if format_name == 'WEBP':
                        img = img.convert('RGB')
                        format_name = 'JPEG'
                    else:
                        logger.warning(f"[DEBUG] Format non supporté: {format_name}")
                        return None

                # Redimensionner si nécessaire
                if max(img.size) > self.target_size:
                    ratio = self.target_size / max(img.size)
                    new_size = tuple(int(dim * ratio) for dim in img.size)
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"[DEBUG] Redimensionné à: {new_size}")

                # Sauvegarder l'image
                ext = '.jpg' if format_name == 'JPEG' else f'.{format_name.lower()}'
                temp_path = os.path.join(self.temp_dir, f"img_{int(time.time())}_{os.urandom(4).hex()}{ext}")

                # Optimiser selon le format
                save_opts = {}
                if format_name in ('JPEG', 'JPG'):
                    save_opts = {'quality': 85, 'optimize': True}
                elif format_name == 'PNG':
                    save_opts = {'optimize': True}
                else:
                    save_opts = {}

                img.save(temp_path, format=format_name, **save_opts)

                # Vérifier la taille finale
                if os.path.getsize(temp_path) > self.max_size:
                    logger.warning("[DEBUG] Image trop volumineuse après optimisation")
                    os.remove(temp_path)
                    return None

                logger.info(f"[DEBUG] Image sauvegardée: {temp_path}")
                return temp_path

        except Exception as e:
            logger.error(f"[DEBUG] Erreur téléchargement: {str(e)}")
            return None

    async def download_images(self, urls: List[str]) -> List[str]:
        """Télécharge plusieurs images"""
        if not urls:
            return []

        valid_paths = []
        for url in urls:
            try:
                if path := await self.download_image(url):
                    valid_paths.append(path)
                await asyncio.sleep(0.5)  # Délai entre les téléchargements
            except Exception as e:
                logger.error(f"[DEBUG] Erreur: {str(e)}")
                continue

        return valid_paths

    def cleanup(self, specific_path: Optional[str] = None):
        """Nettoie les fichiers temporaires"""
        try:
            if specific_path and os.path.exists(specific_path):
                os.remove(specific_path)
                logger.info(f"[DEBUG] Supprimé: {specific_path}")
            elif os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        path = os.path.join(self.temp_dir, file)
                        if os.path.isfile(path):
                            os.remove(path)
                            logger.info(f"[DEBUG] Supprimé: {path}")
                    except Exception as e:
                        logger.error(f"[DEBUG] Erreur nettoyage {path}: {str(e)}")
        except Exception as e:
            logger.error(f"[DEBUG] Erreur nettoyage: {str(e)}")