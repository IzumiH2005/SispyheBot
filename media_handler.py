import os
import asyncio
import logging
import tempfile
import time
import requests
from typing import List, Dict, Optional, Any
import yt_dlp

logger = logging.getLogger(__name__)

class MediaHandler:
    def __init__(self):
        """Initialize the media handler with a temporary directory"""
        self.temp_dir = tempfile.mkdtemp(prefix='sisyphe_media_')
        logger.info(f"Temp directory created: {self.temp_dir}")

    async def download_images(self, urls: List[str]) -> List[str]:
        """Download images from URLs and return their local file paths"""
        downloaded_paths = []
        for url in urls:
            try:
                response = requests.get(url, stream=True, timeout=30)
                if response.status_code == 200:
                    # Get file extension from URL or content type
                    content_type = response.headers.get('content-type', '')
                    ext = self._get_extension_from_content_type(content_type)
                    if not ext and '.' in url:
                        ext = url.split('.')[-1].lower()
                    if not ext:
                        ext = 'jpg'  # Default extension

                    # Create temporary file with proper extension
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}', dir=self.temp_dir) as tmp_file:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                tmp_file.write(chunk)
                        downloaded_paths.append(tmp_file.name)
                        logger.info(f"Image downloaded to {tmp_file.name}")
            except Exception as e:
                logger.error(f"Error downloading image from {url}: {str(e)}")

        return downloaded_paths

    def _get_extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from content type"""
        content_type = content_type.lower()
        if 'jpeg' in content_type or 'jpg' in content_type:
            return 'jpg'
        elif 'png' in content_type:
            return 'png'
        elif 'gif' in content_type:
            return 'gif'
        elif 'webp' in content_type:
            return 'webp'
        return ''

    async def search_youtube(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search YouTube videos with yt-dlp"""
        try:
            logger.info(f"Searching YouTube for: {query}")

            ydl_opts = {
                'quiet': True,
                'extract_flat': 'in_playlist',
                'default_search': 'ytsearch',
                'ignoreerrors': True,
                'no_warnings': True
            }

            try:
                # Construct the search URL
                search_url = f"ytsearch{max_results}:{query}"
                logger.debug(f"Search URL: {search_url}")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.debug("Starting YouTube search...")
                    results = await asyncio.to_thread(
                        ydl.extract_info,
                        search_url,
                        download=False
                    )

                    if not results:
                        logger.warning("No results found")
                        return []

                    videos = []
                    entries = results.get('entries', [])
                    logger.info(f"Found {len(entries)} entries")

                    for entry in entries:
                        if not entry:
                            continue

                        try:
                            video_info = {
                                'title': entry.get('title', 'Unknown Title'),
                                'url': entry.get('webpage_url', entry.get('url', '')),
                                'duration': entry.get('duration'),
                                'duration_str': self._format_duration(entry.get('duration', 0))
                            }
                            logger.debug(f"Processed video: {video_info['title']}")
                            videos.append(video_info)

                        except Exception as e:
                            logger.error(f"Error processing video entry: {str(e)}")
                            continue

                    return videos[:max_results]

            except Exception as e:
                logger.error(f"Error during YouTube search operation: {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Error in search_youtube: {str(e)}")
            return []

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information using yt-dlp"""
        try:
            logger.info(f"Getting info for video: {url}")

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'format': info.get('format', '')
                }

        except Exception as e:
            logger.error(f"Error getting video info: {str(e)}")
            return {}

    async def download_youtube_video(self, url: str, format_type: str, resolution: Optional[str] = None) -> Optional[str]:
        """Download YouTube video in specified format and resolution"""
        try:
            logger.info(f"Downloading {url} in {format_type} format")

            # Get video info first to get the title
            info = await self.get_video_info(url)
            title = info.get('title', 'video')

            # Clean the title to make it filesystem-friendly
            clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if len(clean_title) > 100:  # Limit title length
                clean_title = clean_title[:100]

            timestamp = int(time.time())
            temp_path = os.path.join(self.temp_dir, f"{clean_title}_{timestamp}")

            if format_type == 'mp3':
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': f"{temp_path}.%(ext)s",
                    'quiet': True,
                    'no_warnings': True
                }
                final_path = f"{temp_path}.mp3"
            else:  # mp4
                if resolution:
                    video_format = f"bestvideo[height<={resolution[:-1]}]+bestaudio/best[height<={resolution[:-1]}]"
                else:
                    video_format = 'best'

                ydl_opts = {
                    'format': video_format,
                    'merge_output_format': 'mp4',
                    'outtmpl': f"{temp_path}.%(ext)s",
                    'quiet': True,
                    'no_warnings': True
                }
                final_path = f"{temp_path}.mp4"

            logger.debug(f"Download options: {ydl_opts}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.to_thread(ydl.download, [url])

            if os.path.exists(final_path):
                logger.info(f"Download successful: {final_path}")
                return final_path

            logger.error("Download failed: File not found")
            return None

        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")
            return None

    def cleanup(self, specific_path: Optional[str] = None):
        """Clean up temporary files"""
        try:
            if specific_path and os.path.exists(specific_path):
                os.remove(specific_path)
                logger.info(f"Removed file: {specific_path}")
            elif os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    file_path = os.path.join(self.temp_dir, file)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            logger.info(f"Removed file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error cleaning up {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")

    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to HH:MM:SS"""
        try:
            if not seconds or not isinstance(seconds, (int, float)):
                return "Unknown"

            seconds = int(seconds)
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60

            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            return f"{minutes:02d}:{secs:02d}"

        except Exception as e:
            logger.error(f"Error formatting duration: {e}")
            return "Unknown"