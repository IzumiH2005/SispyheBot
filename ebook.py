import os
import logging
import asyncio
import tempfile
import requests
from openai import OpenAI
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import unquote

logger = logging.getLogger(__name__)

class EbookClient:
    def __init__(self):
        """Initialise le client pour la recherche et le téléchargement d'ebooks"""
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY non trouvée dans les variables d'environnement")

        logger.info("Initialisation du client pour les ebooks")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.perplexity.ai"
        )

    async def extract_book_links(self, title: str, lang: str) -> Dict[str, Any]:
        """Recherche des liens de téléchargement pour un livre donné"""
        try:
            if not title.strip():
                return []

            logger.info(f"Recherche du livre: {title} en {lang}")

            # Construction d'une requête plus précise en fonction de la langue
            lang_query = "français" if lang.lower() == "fr" else "english" if lang.lower() == "en" else lang
            query = f"""Recherche exhaustive pour trouver des liens de téléchargement du livre '{title}' en {lang_query}.

            Instructions spécifiques :
            1. Cherche sur les sites suivants:
               - Project Gutenberg (gutenberg.org)
               - Internet Archive (archive.org)
               - Bibliothèque nationale de France (gallica.bnf.fr)
               - Wikisource
               - OpenLibrary (openlibrary.org)
               - LibGen (si disponible)
               - Z-Library (si disponible)
            2. Trouve des liens pour TOUS les formats disponibles (.pdf, .epub, .mobi)
            3. Vérifie que les liens mènent directement aux fichiers
            4. Ne retourne QUE les URLs, une par ligne
            5. Pour les livres français :
               - Priorité à Gallica et Wikisource
               - Vérifie aussi sur BNF et OpenLibrary
            6. Pour les livres anglais :
               - Priorité à Project Gutenberg et Internet Archive
               - Vérifie aussi sur OpenLibrary et Wikisource
            7. Si aucun lien n'est trouvé dans les sources principales,
               cherche dans d'autres bibliothèques numériques légales

            Format de réponse souhaité :
            - Une URL par ligne
            - Uniquement les liens directs vers les fichiers .pdf, .epub, ou .mobi
            - Pas de texte explicatif, uniquement les URLs"""

            messages = [
                {
                    "role": "system",
                    "content": """Tu es un expert en recherche de livres numériques qui :
                    - Utilise des sources fiables et légales
                    - Vérifie chaque lien pour s'assurer qu'il mène à un fichier
                    - Retourne uniquement des URLs directes
                    - S'assure de trouver tous les formats disponibles
                    - Adapte ses sources en fonction de la langue
                    - Priorise les sources appropriées selon la langue"""
                },
                {
                    "role": "user",
                    "content": query
                }
            ]

            logger.info("Envoi de la requête à l'API Perplexity")
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="sonar-pro-research",
                    messages=messages,
                    temperature=0.3,
                    stream=False
                ),
                timeout=45.0
            )

            content = response.choices[0].message.content
            logger.info("Réponse reçue de l'API, analyse des URLs...")

            # Extraction et validation des URLs par format
            book_links = []
            for line in content.split('\n'):
                url = line.strip()
                if url.startswith(('http://', 'https://')):
                    for ext in ['.pdf', '.epub', '.mobi']:
                        if url.lower().endswith(ext):
                            logger.info(f"URL trouvée pour le format {ext}: {url}")
                            book_info = {
                                'url': url,
                                'format': ext[1:],
                                'filename': self.get_filename_from_url(url, title, lang),
                                'size': None
                            }
                            # Vérifier la validité de l'URL
                            if await self.verify_url(url):
                                book_links.append(book_info)
                                logger.info(f"URL validée: {url}")
                            else:
                                logger.warning(f"URL invalide: {url}")
                            break

            # Regrouper les liens par format
            formats_available = {}
            for link in book_links:
                format_type = link['format']
                if format_type not in formats_available:
                    formats_available[format_type] = []
                formats_available[format_type].append(link)

            logger.info(f"Formats trouvés: {list(formats_available.keys())}")
            return formats_available

        except asyncio.TimeoutError:
            logger.error("Timeout lors de la recherche du livre")
            raise TimeoutError("La recherche du livre prend trop de temps")
        except Exception as e:
            logger.error(f"Erreur lors de la recherche du livre: {str(e)}")
            raise

    async def verify_url(self, url: str) -> bool:
        """Vérifie si l'URL est valide et pointe vers un fichier"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.head(url, headers=headers, timeout=10)
            content_type = response.headers.get('content-type', '').lower()
            content_length = response.headers.get('content-length')

            # Vérifier le type de contenu
            valid_types = ['pdf', 'epub', 'mobi', 'octet-stream', 'application']
            if not any(t in content_type for t in valid_types):
                return False

            # Vérifier la taille (si disponible)
            if content_length and int(content_length) < 1024:  # Moins de 1KB
                return False

            return True
        except Exception:
            return False

    def get_filename_from_url(self, url: str, title: str, lang: str) -> str:
        """Génère un nom de fichier approprié pour l'ebook"""
        try:
            # Extraire l'extension
            extension = ''
            for ext in ['.pdf', '.epub', '.mobi']:
                if url.lower().endswith(ext):
                    extension = ext
                    break

            if not extension:
                extension = '.pdf'  # Extension par défaut

            # Nettoyer le titre
            clean_title = title.strip()
            clean_title = ''.join(c for c in clean_title if c.isalnum() or c.isspace())
            clean_title = clean_title.replace(' ', '_')

            # Construire le nom final
            final_filename = f"{clean_title}_{lang}{extension}"

            return final_filename

        except Exception as e:
            logger.error(f"Erreur lors de la génération du nom de fichier: {str(e)}")
            return f"book_{lang}.pdf"

    async def download_ebook(self, url: str, filename: str) -> str:
        """Télécharge l'ebook et retourne le chemin du fichier temporaire"""
        try:
            logger.info(f"Téléchargement de l'ebook depuis: {url}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            # Création d'un fichier temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='_' + filename) as temp_file:
                response = requests.get(url, stream=True, headers=headers, timeout=30)
                response.raise_for_status()

                # Vérifier le type de contenu
                content_type = response.headers.get('content-type', '').lower()
                if not any(t in content_type for t in ['pdf', 'epub', 'mobi', 'octet-stream', 'application']):
                    raise ValueError(f"Type de contenu non valide: {content_type}")

                # Téléchargement par morceaux
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)

                # Vérifier la taille finale
                temp_file.seek(0, 2)
                file_size = temp_file.tell()
                if file_size < 1024:
                    raise ValueError("Fichier trop petit pour être un ebook valide")

                return temp_file.name

        except Exception as e:
            logger.error(f"Erreur lors du téléchargement: {e}")
            raise

    async def search_and_download(self, title: str, lang: str = "fr") -> Dict[str, Any]:
        """Recherche et télécharge un ebook"""
        try:
            # Recherche des formats disponibles
            result = await self.extract_book_links(title, lang)

            if not result:
                return {"error": "Aucun lien de téléchargement trouvé pour ce livre"}

            # Retourner les formats disponibles
            return {
                "success": True,
                "formats": result
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erreur lors de la recherche: {error_msg}")

            if "quota" in error_msg.lower():
                return {"error": "Limite de requêtes atteinte"}
            elif "unauthorized" in error_msg.lower():
                return {"error": "Erreur d'authentification avec l'API"}

            return {"error": f"Une erreur est survenue: {error_msg}"}

    async def download_selected_format(self, book_info: Dict[str, Any]) -> Dict[str, Any]:
        """Télécharge le format sélectionné par l'utilisateur"""
        try:
            file_path = await self.download_ebook(book_info['url'], book_info['filename'])

            if os.path.exists(file_path) and os.path.getsize(file_path) > 1024:
                return {
                    "success": True,
                    "file_path": file_path,
                    "filename": book_info['filename']
                }
            else:
                return {"error": "Le fichier téléchargé n'est pas valide"}

        except Exception as e:
            return {"error": f"Erreur lors du téléchargement: {str(e)}"}