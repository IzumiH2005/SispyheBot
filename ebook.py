import os
import logging
import asyncio
import tempfile
import requests
from openai import OpenAI
from typing import Dict, Any, Optional, Tuple
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

    def _extract_urls(self, text: str) -> list:
        """Extrait les URLs des résultats de recherche"""
        words = text.split()
        urls = [word for word in words if word.startswith(('http://', 'https://'))]
        return urls

    def _parse_command(self, command: str) -> Tuple[str, str]:
        """Parse la commande /ebook pour extraire le titre et la langue"""
        parts = command.strip().split()
        if len(parts) < 2:
            return "", "fr"  # Langue par défaut: français

        # Si la dernière partie est un code de langue de 2-3 caractères
        if len(parts[-1]) in [2, 3] and parts[-1].isalpha():
            return " ".join(parts[:-1]), parts[-1].lower()

        return " ".join(parts), "fr"

    async def search_and_download_ebook(self, command: str) -> Dict[str, Any]:
        """Recherche et télécharge un ebook"""
        try:
            title, lang = self._parse_command(command)
            if not title:
                return {"error": "Veuillez spécifier un titre de livre"}

            logger.info(f"Recherche de l'ebook: {title} en {lang}")

            # Construire la requête en fonction de la langue
            lang_terms = {
                "fr": "livre ebook gratuit français",
                "en": "free ebook book english",
                "es": "libro ebook gratis español",
                "de": "kostenloses ebook deutsch",
                # Ajoutez d'autres langues selon les besoins
            }
            lang_term = lang_terms.get(lang, lang_terms["fr"])

            messages = [
                {
                    "role": "system",
                    "content": f"""Recherchez des liens de téléchargement gratuits et légaux pour le livre "{title}" en {lang}.
                    Retournez UNIQUEMENT les URLs trouvées, une par ligne.
                    Ne retournez PAS de texte explicatif, seulement les URLs."""
                },
                {
                    "role": "user",
                    "content": f'Trouve des liens de téléchargement pour "{title}" {lang_term}'
                }
            ]

            logger.info("Envoi de la requête à l'API Perplexity")
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="claude-2",  # Changé pour utiliser claude-2 au lieu de sonar-pro
                    messages=messages,
                    temperature=0.1,
                    stream=False
                ),
                timeout=45.0
            )

            content = response.choices[0].message.content
            urls = self._extract_urls(content)

            if not urls:
                return {"error": f"Aucun lien de téléchargement trouvé pour '{title}'"}

            # Essayer de télécharger depuis chaque URL jusqu'à ce qu'un téléchargement réussisse
            for url in urls:
                try:
                    response = requests.get(url, stream=True, timeout=30)
                    if response.status_code == 200:
                        # Créer un fichier temporaire avec une extension appropriée
                        ext = url.split('.')[-1].lower()
                        if ext not in ['pdf', 'epub', 'mobi', 'txt']:
                            ext = 'pdf'  # Extension par défaut

                        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as temp_file:
                            for chunk in response.iter_content(chunk_size=8192):
                                temp_file.write(chunk)

                            # Renommer le fichier avec le titre
                            final_path = temp_file.name
                            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
                            new_path = os.path.join(os.path.dirname(final_path), f"{safe_title}.{ext}")
                            os.rename(final_path, new_path)
                            return {
                                "success": True,
                                "file_path": new_path,
                                "title": title,
                                "original_url": url
                            }
                except Exception as e:
                    logger.error(f"Erreur lors du téléchargement depuis {url}: {str(e)}")
                    continue

            return {"error": "Impossible de télécharger l'ebook depuis les liens trouvés"}

        except asyncio.TimeoutError:
            logger.error("Timeout lors de la recherche de l'ebook")
            return {"error": "La recherche prend trop de temps. Veuillez réessayer."}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erreur lors de la recherche de l'ebook: {error_msg}")
            logger.exception("Détails complets de l'erreur:")

            if "quota" in error_msg.lower():
                return {"error": "Limite de requêtes atteinte"}
            elif "unauthorized" in error_msg.lower():
                return {"error": "Erreur d'authentification avec l'API"}

            return {"error": f"Une erreur est survenue: {error_msg}"}