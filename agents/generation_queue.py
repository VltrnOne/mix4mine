"""
VLTRN SUNO - Generation Queue Agent
Handles batch song generation with SUNO via browser automation
"""
import time
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GenerationQueue")


@dataclass
class GenerationJob:
    """A single song generation job"""
    id: str
    title: str
    lyrics: str
    style_tags: str
    instrumental: bool = False
    status: str = "pending"  # pending, generating, completed, failed
    suno_id: Optional[str] = None
    audio_url: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None
    retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "lyrics": self.lyrics,
            "style_tags": self.style_tags,
            "instrumental": self.instrumental,
            "status": self.status,
            "suno_id": self.suno_id,
            "audio_url": self.audio_url,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "retries": self.retries
        }


class GenerationQueue:
    """
    VLTRN SUNO Generation Queue
    Manages batch song generation through browser automation
    """

    def __init__(self, driver=None, max_retries: int = 3, delay_between_jobs: int = 30):
        self.driver = driver
        self.max_retries = max_retries
        self.delay = delay_between_jobs
        self.queue: List[GenerationJob] = []
        self.completed: List[GenerationJob] = []
        self.failed: List[GenerationJob] = []

    def set_driver(self, driver):
        """Set the Selenium WebDriver"""
        self.driver = driver

    def add_job(self, title: str, lyrics: str, style_tags: str, instrumental: bool = False) -> GenerationJob:
        """Add a new job to the queue"""
        job_id = f"job_{len(self.queue) + len(self.completed) + 1}_{int(time.time())}"
        job = GenerationJob(
            id=job_id,
            title=title,
            lyrics=lyrics,
            style_tags=style_tags,
            instrumental=instrumental
        )
        self.queue.append(job)
        logger.info(f"Added job to queue: {job.title} (ID: {job_id})")
        return job

    def add_jobs_from_prompts(self, prompts: List[Any]) -> List[GenerationJob]:
        """Add multiple jobs from SongPrompt objects"""
        jobs = []
        for prompt in prompts:
            job = self.add_job(
                title=prompt.title,
                lyrics=prompt.lyrics,
                style_tags=prompt.get_tags_string(),
                instrumental=prompt.instrumental
            )
            jobs.append(job)
        return jobs

    def navigate_to_create(self) -> bool:
        """Navigate to SUNO create page"""
        if not self.driver:
            logger.error("No driver connected")
            return False

        try:
            self.driver.get("https://suno.com/create")
            time.sleep(3)
            logger.info("Navigated to create page")
            return True
        except Exception as e:
            logger.error(f"Error navigating to create page: {e}")
            return False

    def fill_generation_form(self, job: GenerationJob) -> bool:
        """Fill in the SUNO generation form"""
        if not self.driver:
            return False

        try:
            # Wait for the form to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "textarea"))
            )

            # Try to find and click "Custom" mode if available
            try:
                custom_buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Custom')]")
                for btn in custom_buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        time.sleep(1)
                        break
            except:
                pass

            # Find lyrics textarea
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            lyrics_textarea = None

            for textarea in textareas:
                placeholder = textarea.get_attribute("placeholder") or ""
                if "lyrics" in placeholder.lower() or "write" in placeholder.lower():
                    lyrics_textarea = textarea
                    break

            if not lyrics_textarea and textareas:
                lyrics_textarea = textareas[0]

            if lyrics_textarea:
                lyrics_textarea.clear()
                # Send lyrics in chunks to avoid issues
                for line in job.lyrics.split('\n'):
                    lyrics_textarea.send_keys(line)
                    lyrics_textarea.send_keys(Keys.ENTER)
                logger.info("Filled lyrics textarea")

            # Find and fill style/tags input
            try:
                style_inputs = self.driver.find_elements(By.XPATH,
                    "//input[contains(@placeholder, 'style') or contains(@placeholder, 'Style') or contains(@placeholder, 'genre')]")
                if style_inputs:
                    style_inputs[0].clear()
                    style_inputs[0].send_keys(job.style_tags)
                    logger.info("Filled style tags")
            except:
                pass

            # Find and fill title input
            try:
                title_inputs = self.driver.find_elements(By.XPATH,
                    "//input[contains(@placeholder, 'title') or contains(@placeholder, 'Title') or contains(@placeholder, 'name')]")
                if title_inputs:
                    title_inputs[0].clear()
                    title_inputs[0].send_keys(job.title)
                    logger.info("Filled title")
            except:
                pass

            # Handle instrumental toggle if needed
            if job.instrumental:
                try:
                    instrumental_toggles = self.driver.find_elements(By.XPATH,
                        "//*[contains(text(), 'Instrumental') or contains(text(), 'instrumental')]")
                    for toggle in instrumental_toggles:
                        if toggle.is_displayed():
                            toggle.click()
                            logger.info("Toggled instrumental mode")
                            break
                except:
                    pass

            return True

        except Exception as e:
            logger.error(f"Error filling form: {e}")
            return False

    def click_generate(self) -> bool:
        """Click the generate/create button"""
        if not self.driver:
            return False

        try:
            # Look for various button texts
            button_texts = ["Create", "Generate", "Make", "Submit"]

            for text in button_texts:
                try:
                    buttons = self.driver.find_elements(By.XPATH,
                        f"//button[contains(text(), '{text}')]")
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            btn.click()
                            logger.info(f"Clicked '{text}' button")
                            return True
                except:
                    continue

            # Try finding button by class
            try:
                submit_btns = self.driver.find_elements(By.CSS_SELECTOR,
                    "button[type='submit'], button.primary, button.create-btn")
                for btn in submit_btns:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        logger.info("Clicked submit button")
                        return True
            except:
                pass

            logger.warning("Could not find generate button")
            return False

        except Exception as e:
            logger.error(f"Error clicking generate: {e}")
            return False

    def wait_for_generation(self, timeout: int = 180) -> Optional[str]:
        """Wait for song generation to complete and return song ID"""
        if not self.driver:
            return None

        start_time = time.time()
        logger.info(f"Waiting for generation (timeout: {timeout}s)...")

        while time.time() - start_time < timeout:
            try:
                # Check for completed song
                # Look for audio player or song card that appeared
                current_url = self.driver.current_url

                # If URL contains a song ID, generation completed
                if "/song/" in current_url:
                    song_id = current_url.split("/song/")[-1].split("?")[0]
                    logger.info(f"Generation completed! Song ID: {song_id}")
                    return song_id

                # Look for song cards with play buttons
                try:
                    song_cards = self.driver.find_elements(By.CSS_SELECTOR,
                        "[data-testid='song-card'], .song-card, [class*='song']")
                    if song_cards:
                        # Check if it's a new song
                        for card in song_cards:
                            # Try to find song ID in card attributes or links
                            links = card.find_elements(By.TAG_NAME, "a")
                            for link in links:
                                href = link.get_attribute("href") or ""
                                if "/song/" in href:
                                    song_id = href.split("/song/")[-1].split("?")[0]
                                    logger.info(f"Found song ID: {song_id}")
                                    return song_id
                except:
                    pass

                # Check for loading indicators
                try:
                    loading = self.driver.find_elements(By.CSS_SELECTOR,
                        "[class*='loading'], [class*='spinner'], [class*='progress']")
                    if loading:
                        logger.debug("Still generating...")
                except:
                    pass

                time.sleep(5)

            except Exception as e:
                logger.debug(f"Waiting... ({e})")
                time.sleep(5)

        logger.warning("Generation timed out")
        return None

    def process_job(self, job: GenerationJob) -> bool:
        """Process a single generation job"""
        logger.info(f"Processing job: {job.title}")
        job.status = "generating"

        # Navigate to create page
        if not self.navigate_to_create():
            job.status = "failed"
            job.error = "Failed to navigate to create page"
            return False

        time.sleep(2)

        # Fill the form
        if not self.fill_generation_form(job):
            job.status = "failed"
            job.error = "Failed to fill generation form"
            return False

        time.sleep(1)

        # Click generate
        if not self.click_generate():
            job.status = "failed"
            job.error = "Failed to click generate button"
            return False

        # Wait for generation
        song_id = self.wait_for_generation()

        if song_id:
            job.status = "completed"
            job.suno_id = song_id
            job.audio_url = f"https://suno.com/song/{song_id}"
            job.completed_at = datetime.now().isoformat()
            logger.info(f"Job completed: {job.title} -> {song_id}")
            return True
        else:
            job.status = "failed"
            job.error = "Generation timed out"
            return False

    def process_queue(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Process all jobs in the queue"""
        results = {"completed": 0, "failed": 0, "remaining": 0}

        jobs_to_process = self.queue[:limit] if limit else self.queue[:]

        for i, job in enumerate(jobs_to_process):
            logger.info(f"Processing job {i + 1}/{len(jobs_to_process)}")

            success = False
            while job.retries < self.max_retries and not success:
                success = self.process_job(job)
                if not success:
                    job.retries += 1
                    logger.warning(f"Retry {job.retries}/{self.max_retries} for {job.title}")
                    time.sleep(10)

            if success:
                self.completed.append(job)
                results["completed"] += 1
            else:
                self.failed.append(job)
                results["failed"] += 1

            # Remove from queue
            if job in self.queue:
                self.queue.remove(job)

            # Delay between jobs
            if i < len(jobs_to_process) - 1:
                logger.info(f"Waiting {self.delay}s before next job...")
                time.sleep(self.delay)

        results["remaining"] = len(self.queue)
        return results

    def get_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            "pending": len(self.queue),
            "completed": len(self.completed),
            "failed": len(self.failed),
            "queue": [j.to_dict() for j in self.queue],
            "completed_jobs": [j.to_dict() for j in self.completed],
            "failed_jobs": [j.to_dict() for j in self.failed]
        }

    def save_status(self, filepath: str):
        """Save queue status to file"""
        with open(filepath, 'w') as f:
            json.dump(self.get_status(), f, indent=2)
        logger.info(f"Status saved to {filepath}")

    def load_queue(self, filepath: str):
        """Load queue from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for job_data in data.get("queue", []):
                job = GenerationJob(**job_data)
                self.queue.append(job)
            logger.info(f"Loaded {len(self.queue)} jobs from {filepath}")
        except Exception as e:
            logger.error(f"Error loading queue: {e}")


def main():
    """Test the Generation Queue (requires Session Manager)"""
    print("=" * 60)
    print("VLTRN SUNO Generation Queue - Test")
    print("=" * 60)

    queue = GenerationQueue()

    # Add a test job
    print("\n[1] Adding test job...")
    job = queue.add_job(
        title="Test Song",
        lyrics="[Verse 1]\nThis is a test song\nGenerated by VLTRN\n\n[Chorus]\nAutomation is great\nWe don't have to wait",
        style_tags="[pop, upbeat, test]",
        instrumental=False
    )
    print(f"    Added: {job.title} (ID: {job.id})")

    # Show status
    print("\n[2] Queue status:")
    status = queue.get_status()
    print(f"    Pending: {status['pending']}")
    print(f"    Completed: {status['completed']}")
    print(f"    Failed: {status['failed']}")

    print("\n" + "=" * 60)
    print("Generation Queue test complete!")
    print("Note: Actual generation requires Session Manager connection")
    print("=" * 60)


if __name__ == "__main__":
    main()
