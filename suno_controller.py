#!/usr/bin/env python3
"""
VLTRN SUNO Controller
Main orchestrator for the SUNO automation suite
"""
import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add agents to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.session_manager import SessionManager
from agents.prompt_engineer import PromptEngineer, GenreTemplates
from agents.generation_queue import GenerationQueue
from agents.download_manager import DownloadManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SUNOController")


class VLTRNSunoController:
    """
    VLTRN SUNO Automation Controller
    Orchestrates all agents for end-to-end music generation
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.downloads_dir = self.base_dir / "downloads"
        self.logs_dir = self.base_dir / "logs"
        self.templates_dir = self.base_dir / "templates"

        # Create directories
        for d in [self.downloads_dir, self.logs_dir, self.templates_dir]:
            d.mkdir(exist_ok=True)

        # Initialize agents
        self.session = SessionManager()
        self.prompt_engineer = PromptEngineer()
        self.queue = GenerationQueue()
        self.downloader = DownloadManager(str(self.downloads_dir))

        self.is_connected = False

    def connect(self, debug_port: int = 9222) -> bool:
        """Connect to Chrome and SUNO"""
        print("\n" + "=" * 60)
        print("VLTRN SUNO Controller - Connecting")
        print("=" * 60)

        # Try to connect to existing Chrome
        print("\n[1] Connecting to Chrome...")
        self.session.debug_port = debug_port

        if self.session.connect_to_existing_chrome():
            print("    Connected to existing Chrome session")
        else:
            print("    Could not connect. Starting Chrome with debugging...")
            print(f"\n    Run this command first, then try again:")
            print(f'    /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={debug_port}')
            return False

        # Find SUNO tab
        print("\n[2] Finding SUNO tab...")
        if self.session.attach_to_suno_tab():
            print(f"    Found: {self.session.driver.current_url}")
        else:
            print("    No SUNO tab found - navigating to suno.com")

        # Extract cookies
        print("\n[3] Extracting session cookies...")
        cookies = self.session.extract_cookies()
        print(f"    Extracted {len(cookies)} cookies")

        # Check login status
        print("\n[4] Checking login status...")
        if self.session.check_login_status():
            print("    Logged in to SUNO")
            self.is_connected = True

            # Set up other agents
            self.queue.set_driver(self.session.driver)
            self.downloader.set_cookies(cookies)

            # Save session
            session_file = self.base_dir / "session.json"
            self.session.save_session(str(session_file))
            print(f"    Session saved to {session_file}")

            return True
        else:
            print("    NOT logged in - please log in to SUNO first")
            return False

    def generate_song(
        self,
        title: str,
        theme: str,
        genre: str = "pop",
        mood: str = "happy",
        vocal: str = "female_pop",
        instrumental: bool = False
    ) -> Optional[str]:
        """Generate a single song"""
        if not self.is_connected:
            logger.error("Not connected to SUNO")
            return None

        print(f"\n[Generating] {title}")
        print(f"  Theme: {theme}")
        print(f"  Genre: {genre}, Mood: {mood}")

        # Create prompt
        prompt = self.prompt_engineer.create_prompt(
            title=title,
            theme=theme,
            genre=genre,
            mood=mood,
            vocal_profile=vocal,
            instrumental=instrumental
        )

        print(f"  Tags: {prompt.get_tags_string()}")

        # Add to queue and process
        job = self.queue.add_job(
            title=prompt.title,
            lyrics=prompt.lyrics,
            style_tags=prompt.get_tags_string(),
            instrumental=prompt.instrumental
        )

        # Process the single job
        success = self.queue.process_job(job)

        if success:
            print(f"  Song ID: {job.suno_id}")
            print(f"  URL: {job.audio_url}")
            return job.suno_id
        else:
            print(f"  FAILED: {job.error}")
            return None

    def batch_generate(
        self,
        themes: List[Dict[str, Any]],
        delay: int = 30
    ) -> Dict[str, Any]:
        """Generate multiple songs from a list of themes"""
        if not self.is_connected:
            logger.error("Not connected to SUNO")
            return {"error": "Not connected"}

        print(f"\n[Batch Generation] {len(themes)} songs")

        # Create prompts
        prompts = self.prompt_engineer.create_batch_prompts(themes)

        # Add to queue
        self.queue.add_jobs_from_prompts(prompts)

        # Process queue
        results = self.queue.process_queue()

        # Save status
        status_file = self.logs_dir / f"batch_{int(time.time())}.json"
        self.queue.save_status(str(status_file))

        return results

    def download_song(self, suno_id: str, title: str, genre: Optional[str] = None):
        """Download a single song"""
        return self.downloader.download_song(suno_id, title, genre)

    def download_completed(self) -> List[Any]:
        """Download all completed songs from the queue"""
        songs = []
        for job in self.queue.completed:
            if job.suno_id:
                song = self.downloader.download_song(
                    suno_id=job.suno_id,
                    title=job.title
                )
                if song:
                    songs.append(song)
        return songs

    def status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            "connected": self.is_connected,
            "queue": self.queue.get_status(),
            "library": self.downloader.get_library_stats()
        }

    def interactive_mode(self):
        """Run in interactive mode"""
        print("\n" + "=" * 60)
        print("VLTRN SUNO Controller - Interactive Mode")
        print("=" * 60)
        print("\nCommands:")
        print("  generate <title> - Generate a song with prompts")
        print("  quick <theme>    - Quick generate with defaults")
        print("  download <id>    - Download a song by ID")
        print("  status           - Show status")
        print("  genres           - List available genres")
        print("  quit             - Exit")

        while True:
            try:
                cmd = input("\n> ").strip()

                if not cmd:
                    continue

                parts = cmd.split(maxsplit=1)
                action = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if action == "quit" or action == "exit":
                    break

                elif action == "status":
                    status = self.status()
                    print(json.dumps(status, indent=2))

                elif action == "genres":
                    print("\nAvailable genres:")
                    for g in GenreTemplates.list_genres():
                        print(f"  - {g}")

                elif action == "quick":
                    if not args:
                        print("Usage: quick <theme>")
                        continue
                    title = f"Song_{int(time.time())}"
                    self.generate_song(title=title, theme=args)

                elif action == "generate":
                    if not args:
                        print("Usage: generate <title>")
                        continue
                    title = args
                    theme = input("  Theme: ").strip()
                    genre = input("  Genre [pop]: ").strip() or "pop"
                    mood = input("  Mood [happy]: ").strip() or "happy"
                    self.generate_song(title=title, theme=theme, genre=genre, mood=mood)

                elif action == "download":
                    if not args:
                        print("Usage: download <suno_id>")
                        continue
                    title = input("  Title: ").strip() or "Downloaded Song"
                    self.download_song(args, title)

                else:
                    print(f"Unknown command: {action}")

            except KeyboardInterrupt:
                print("\nInterrupted")
                break
            except Exception as e:
                print(f"Error: {e}")

    def close(self):
        """Clean up and close connections"""
        self.session.close()
        logger.info("Controller closed")


def main():
    parser = argparse.ArgumentParser(description="VLTRN SUNO Automation Controller")
    parser.add_argument("--port", type=int, default=9222, help="Chrome debug port")
    parser.add_argument("--connect", action="store_true", help="Connect to Chrome")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--generate", type=str, help="Generate a song with given theme")
    parser.add_argument("--title", type=str, default="VLTRN Song", help="Song title")
    parser.add_argument("--genre", type=str, default="pop", help="Genre")
    parser.add_argument("--mood", type=str, default="happy", help="Mood")

    args = parser.parse_args()

    controller = VLTRNSunoController()

    try:
        # Connect if requested or if generating
        if args.connect or args.generate or args.interactive:
            if not controller.connect(args.port):
                print("\nFailed to connect. Make sure:")
                print("1. Chrome is running with --remote-debugging-port=9222")
                print("2. You are logged into suno.com")
                sys.exit(1)

        if args.generate:
            controller.generate_song(
                title=args.title,
                theme=args.generate,
                genre=args.genre,
                mood=args.mood
            )

        if args.interactive:
            controller.interactive_mode()

        if not any([args.connect, args.generate, args.interactive]):
            # Show help
            parser.print_help()

    finally:
        controller.close()


if __name__ == "__main__":
    main()
