"""
VLTRN SUNO - Download Manager Agent
Handles downloading, organizing, and tagging generated songs
"""
import os
import re
import time
import json
import logging
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DownloadManager")

# Try to import mutagen for ID3 tagging
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TBPM, TKEY
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logger.warning("mutagen not installed - ID3 tagging disabled")

# Try to import librosa for audio analysis
try:
    import librosa
    import numpy as np
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logger.warning("librosa not installed - audio analysis disabled")


@dataclass
class DownloadedSong:
    """Represents a downloaded song with metadata"""
    suno_id: str
    title: str
    filepath: str
    genre: Optional[str] = None
    bpm: Optional[float] = None
    key: Optional[str] = None
    duration: Optional[float] = None
    quality_score: Optional[float] = None
    tier: str = "B"  # A, B, or C
    downloaded_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suno_id": self.suno_id,
            "title": self.title,
            "filepath": self.filepath,
            "genre": self.genre,
            "bpm": self.bpm,
            "key": self.key,
            "duration": self.duration,
            "quality_score": self.quality_score,
            "tier": self.tier,
            "downloaded_at": self.downloaded_at
        }


class DownloadManager:
    """
    VLTRN SUNO Download Manager
    Downloads, organizes, and tags SUNO-generated songs
    """

    def __init__(
        self,
        downloads_dir: str = "downloads",
        organize_by_date: bool = True,
        organize_by_genre: bool = True,
        organize_by_tier: bool = True
    ):
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.organize_by_date = organize_by_date
        self.organize_by_genre = organize_by_genre
        self.organize_by_tier = organize_by_tier
        self.downloaded: List[DownloadedSong] = []
        self.cookies: Dict[str, str] = {}

    def set_cookies(self, cookies: Dict[str, str]):
        """Set cookies for authenticated downloads"""
        self.cookies = cookies

    def get_audio_url(self, suno_id: str) -> Optional[str]:
        """Get the audio URL for a SUNO song"""
        # SUNO audio URLs follow a pattern
        possible_urls = [
            f"https://cdn1.suno.ai/{suno_id}.mp3",
            f"https://cdn2.suno.ai/{suno_id}.mp3",
            f"https://audiopipe.suno.ai/?item_id={suno_id}",
        ]

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://suno.com/"
        }

        for url in possible_urls:
            try:
                response = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
                if response.status_code == 200:
                    logger.info(f"Found audio URL: {url}")
                    return url
            except:
                continue

        return None

    def download_song(
        self,
        suno_id: str,
        title: str,
        genre: Optional[str] = None
    ) -> Optional[DownloadedSong]:
        """Download a single song from SUNO"""
        logger.info(f"Downloading: {title} (ID: {suno_id})")

        # Get audio URL
        audio_url = self.get_audio_url(suno_id)
        if not audio_url:
            logger.error(f"Could not find audio URL for {suno_id}")
            return None

        # Determine output path
        output_path = self._get_output_path(suno_id, title, genre)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Download the file
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://suno.com/"
            }

            response = requests.get(audio_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded to: {output_path}")

            # Create song record
            song = DownloadedSong(
                suno_id=suno_id,
                title=title,
                filepath=str(output_path),
                genre=genre,
                downloaded_at=datetime.now().isoformat()
            )

            # Analyze audio
            if LIBROSA_AVAILABLE:
                self._analyze_audio(song)

            # Apply ID3 tags
            if MUTAGEN_AVAILABLE:
                self._apply_id3_tags(song)

            # Calculate quality and tier
            self._calculate_quality(song)

            # Move to appropriate tier folder if organizing by tier
            if self.organize_by_tier and song.tier != "B":
                song = self._move_to_tier_folder(song)

            self.downloaded.append(song)
            return song

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    def _get_output_path(self, suno_id: str, title: str, genre: Optional[str]) -> Path:
        """Generate output path based on organization settings"""
        # Clean title for filename
        clean_title = re.sub(r'[^\w\s-]', '', title)[:50]
        clean_title = clean_title.replace(' ', '_')

        # Build path components
        path_parts = [self.downloads_dir]

        if self.organize_by_date:
            now = datetime.now()
            path_parts.append(str(now.year))
            path_parts.append(f"{now.month:02d}-{now.strftime('%B')}")

        if self.organize_by_genre and genre:
            clean_genre = re.sub(r'[^\w\s-]', '', genre)
            path_parts.append(clean_genre)

        # Build final path
        base_path = Path(*path_parts)
        filename = f"{clean_title}_{suno_id[:8]}.mp3"

        return base_path / filename

    def _analyze_audio(self, song: DownloadedSong):
        """Analyze audio using librosa"""
        try:
            y, sr = librosa.load(song.filepath, duration=120)  # Load first 2 minutes

            # Duration
            song.duration = librosa.get_duration(y=y, sr=sr)

            # BPM
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            song.bpm = float(tempo) if isinstance(tempo, (int, float)) else float(tempo[0])

            # Key estimation (simplified)
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            key_idx = np.argmax(np.mean(chroma, axis=1))
            keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            song.key = keys[key_idx]

            logger.info(f"Audio analysis: {song.duration:.1f}s, {song.bpm:.0f} BPM, {song.key}")

        except Exception as e:
            logger.warning(f"Audio analysis failed: {e}")

    def _apply_id3_tags(self, song: DownloadedSong):
        """Apply ID3 tags to the MP3 file"""
        try:
            audio = MP3(song.filepath, ID3=ID3)

            # Add ID3 tag if not present
            try:
                audio.add_tags()
            except:
                pass

            # Set tags
            audio.tags.add(TIT2(encoding=3, text=song.title))
            audio.tags.add(TPE1(encoding=3, text="VLTRN x SUNO"))
            audio.tags.add(TALB(encoding=3, text="VLTRN Generated"))

            if song.genre:
                audio.tags.add(TCON(encoding=3, text=song.genre))
            if song.bpm:
                audio.tags.add(TBPM(encoding=3, text=str(int(song.bpm))))
            if song.key:
                audio.tags.add(TKEY(encoding=3, text=song.key))

            audio.save()
            logger.info(f"Applied ID3 tags to {song.title}")

        except Exception as e:
            logger.warning(f"ID3 tagging failed: {e}")

    def _calculate_quality(self, song: DownloadedSong):
        """Calculate quality score and assign tier"""
        score = 50.0  # Base score

        # Duration scoring
        if song.duration:
            if song.duration >= 120:
                score += 20
            elif song.duration >= 60:
                score += 10
            elif song.duration < 30:
                score -= 20

        # BPM scoring (reasonable range)
        if song.bpm:
            if 80 <= song.bpm <= 180:
                score += 10
            else:
                score -= 5

        song.quality_score = score

        # Assign tier
        if score >= 70:
            song.tier = "A"
        elif score >= 40:
            song.tier = "B"
        else:
            song.tier = "C"

        logger.info(f"Quality: {score:.0f} -> Tier {song.tier}")

    def _move_to_tier_folder(self, song: DownloadedSong) -> DownloadedSong:
        """Move song to appropriate tier folder"""
        try:
            current_path = Path(song.filepath)
            tier_folder = current_path.parent / f"Tier{song.tier}"
            tier_folder.mkdir(exist_ok=True)

            new_path = tier_folder / current_path.name
            current_path.rename(new_path)

            song.filepath = str(new_path)
            logger.info(f"Moved to Tier {song.tier} folder")

        except Exception as e:
            logger.warning(f"Could not move to tier folder: {e}")

        return song

    def download_batch(self, songs: List[Dict[str, str]], delay: int = 5) -> List[DownloadedSong]:
        """Download multiple songs"""
        results = []
        total = len(songs)

        for i, song_info in enumerate(songs):
            logger.info(f"Downloading {i + 1}/{total}...")

            result = self.download_song(
                suno_id=song_info.get("suno_id", ""),
                title=song_info.get("title", "Untitled"),
                genre=song_info.get("genre")
            )

            if result:
                results.append(result)

            if i < total - 1:
                time.sleep(delay)

        return results

    def get_library_stats(self) -> Dict[str, Any]:
        """Get statistics about downloaded library"""
        stats = {
            "total_songs": len(self.downloaded),
            "tier_a": sum(1 for s in self.downloaded if s.tier == "A"),
            "tier_b": sum(1 for s in self.downloaded if s.tier == "B"),
            "tier_c": sum(1 for s in self.downloaded if s.tier == "C"),
            "genres": {},
            "total_duration_minutes": 0
        }

        for song in self.downloaded:
            if song.genre:
                stats["genres"][song.genre] = stats["genres"].get(song.genre, 0) + 1
            if song.duration:
                stats["total_duration_minutes"] += song.duration / 60

        return stats

    def save_library(self, filepath: str):
        """Save library metadata to file"""
        data = {
            "songs": [s.to_dict() for s in self.downloaded],
            "stats": self.get_library_stats()
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Library saved to {filepath}")

    def load_library(self, filepath: str):
        """Load library metadata from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for song_data in data.get("songs", []):
                song = DownloadedSong(**song_data)
                self.downloaded.append(song)
            logger.info(f"Loaded {len(self.downloaded)} songs from library")
        except Exception as e:
            logger.error(f"Error loading library: {e}")


def main():
    """Test the Download Manager"""
    print("=" * 60)
    print("VLTRN SUNO Download Manager - Test")
    print("=" * 60)

    manager = DownloadManager(
        downloads_dir=str(Path(__file__).parent.parent / "downloads")
    )

    print(f"\n[1] Downloads directory: {manager.downloads_dir}")
    print(f"    Librosa available: {LIBROSA_AVAILABLE}")
    print(f"    Mutagen available: {MUTAGEN_AVAILABLE}")

    # Show organization settings
    print("\n[2] Organization settings:")
    print(f"    By date: {manager.organize_by_date}")
    print(f"    By genre: {manager.organize_by_genre}")
    print(f"    By tier: {manager.organize_by_tier}")

    print("\n" + "=" * 60)
    print("Download Manager test complete!")
    print("Note: Actual downloads require valid SUNO song IDs")
    print("=" * 60)


if __name__ == "__main__":
    main()
