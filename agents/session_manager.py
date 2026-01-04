"""
VLTRN SUNO - Session Manager Agent
Handles Chrome connection, cookie extraction, and session management
"""
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SessionManager")


class SessionManager:
    """
    VLTRN SUNO Session Manager
    Connects to existing Chrome session or launches new one
    """

    def __init__(self, debug_port: int = 9222):
        self.debug_port = debug_port
        self.driver: Optional[webdriver.Chrome] = None
        self.cookies: Dict[str, str] = {}
        self.session_token: Optional[str] = None
        self.is_connected = False

    def connect_to_existing_chrome(self) -> bool:
        """Connect to an already running Chrome instance with remote debugging"""
        try:
            options = Options()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.debug_port}")

            self.driver = webdriver.Chrome(options=options)
            self.is_connected = True
            logger.info(f"Connected to existing Chrome on port {self.debug_port}")
            return True
        except WebDriverException as e:
            logger.warning(f"Could not connect to existing Chrome: {e}")
            return False

    def launch_chrome_with_debugging(self) -> bool:
        """Launch a new Chrome instance with remote debugging enabled"""
        try:
            options = Options()
            options.add_argument(f"--remote-debugging-port={self.debug_port}")
            options.add_argument("--user-data-dir=/tmp/vltrn-suno-chrome")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")

            self.driver = webdriver.Chrome(options=options)
            self.is_connected = True
            logger.info(f"Launched Chrome with debugging on port {self.debug_port}")
            return True
        except WebDriverException as e:
            logger.error(f"Failed to launch Chrome: {e}")
            return False

    def attach_to_suno_tab(self) -> bool:
        """Find and attach to the SUNO tab in the browser"""
        if not self.driver:
            logger.error("No driver connected")
            return False

        try:
            # Get all window handles
            handles = self.driver.window_handles
            logger.info(f"Found {len(handles)} browser tabs")

            for handle in handles:
                self.driver.switch_to.window(handle)
                current_url = self.driver.current_url
                logger.info(f"Checking tab: {current_url}")

                if "suno.com" in current_url or "suno.ai" in current_url:
                    logger.info(f"Found SUNO tab: {current_url}")
                    return True

            # If no SUNO tab found, navigate to it
            logger.info("No SUNO tab found, navigating to suno.com")
            self.driver.get("https://suno.com")
            time.sleep(3)
            return True

        except Exception as e:
            logger.error(f"Error attaching to SUNO tab: {e}")
            return False

    def extract_cookies(self) -> Dict[str, str]:
        """Extract all cookies from the current session"""
        if not self.driver:
            return {}

        try:
            cookies = self.driver.get_cookies()
            self.cookies = {c['name']: c['value'] for c in cookies}
            logger.info(f"Extracted {len(self.cookies)} cookies")

            # Look for session token
            for name in ['__session', 'session', '__clerk_db_jwt', 'token']:
                if name in self.cookies:
                    self.session_token = self.cookies[name]
                    logger.info(f"Found session token: {name}")
                    break

            return self.cookies
        except Exception as e:
            logger.error(f"Error extracting cookies: {e}")
            return {}

    def get_cookie_string(self) -> str:
        """Get cookies as a single string for API requests"""
        return "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

    def check_login_status(self) -> bool:
        """Check if user is logged into SUNO"""
        if not self.driver:
            return False

        try:
            # Look for indicators of logged-in state
            self.driver.get("https://suno.com/me")
            time.sleep(2)

            # Check URL - if redirected to login, not authenticated
            current_url = self.driver.current_url
            if "sign-in" in current_url or "login" in current_url:
                logger.warning("Not logged in - redirected to login page")
                return False

            # Check for user menu or profile elements
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='user-menu'], .user-avatar, [class*='avatar']"))
                )
                logger.info("User is logged in")
                return True
            except TimeoutException:
                pass

            # Alternative: check for create button (only visible when logged in)
            try:
                create_btn = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Create')]")
                if create_btn:
                    logger.info("User is logged in (found Create button)")
                    return True
            except:
                pass

            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    def get_credit_balance(self) -> Optional[int]:
        """Get the user's current credit balance"""
        if not self.driver:
            return None

        try:
            # Navigate to account or look for credit display
            self.driver.get("https://suno.com/account")
            time.sleep(2)

            # Look for credit display
            credit_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'credits') or contains(text(), 'Credits')]")
            for elem in credit_elements:
                text = elem.text
                # Extract number from text like "500 credits"
                import re
                match = re.search(r'(\d+)\s*credits?', text, re.IGNORECASE)
                if match:
                    credits = int(match.group(1))
                    logger.info(f"Credit balance: {credits}")
                    return credits

            return None
        except Exception as e:
            logger.error(f"Error getting credit balance: {e}")
            return None

    def save_session(self, filepath: str = "session.json"):
        """Save session data to file"""
        session_data = {
            "cookies": self.cookies,
            "session_token": self.session_token,
            "timestamp": time.time()
        }
        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)
        logger.info(f"Session saved to {filepath}")

    def load_session(self, filepath: str = "session.json") -> bool:
        """Load session data from file"""
        try:
            with open(filepath, 'r') as f:
                session_data = json.load(f)

            self.cookies = session_data.get("cookies", {})
            self.session_token = session_data.get("session_token")

            # Check if session is expired (7 days)
            timestamp = session_data.get("timestamp", 0)
            age_days = (time.time() - timestamp) / (60 * 60 * 24)
            if age_days > 7:
                logger.warning(f"Session is {age_days:.1f} days old - may be expired")

            logger.info(f"Session loaded from {filepath}")
            return True
        except FileNotFoundError:
            logger.warning(f"Session file not found: {filepath}")
            return False
        except Exception as e:
            logger.error(f"Error loading session: {e}")
            return False

    def close(self):
        """Close the browser connection (but don't close the browser)"""
        if self.driver:
            # Don't call driver.quit() - just disconnect
            self.driver = None
            self.is_connected = False
            logger.info("Disconnected from Chrome (browser still running)")


def main():
    """Test the Session Manager"""
    print("=" * 60)
    print("VLTRN SUNO Session Manager - Test")
    print("=" * 60)

    manager = SessionManager()

    # Try to connect to existing Chrome
    print("\n[1] Attempting to connect to existing Chrome...")
    if not manager.connect_to_existing_chrome():
        print("    Could not connect. Please run Chrome with:")
        print(f"    /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={manager.debug_port}")
        return

    # Find SUNO tab
    print("\n[2] Looking for SUNO tab...")
    if manager.attach_to_suno_tab():
        print(f"    Current URL: {manager.driver.current_url}")

    # Extract cookies
    print("\n[3] Extracting cookies...")
    cookies = manager.extract_cookies()
    print(f"    Found {len(cookies)} cookies")
    if manager.session_token:
        print(f"    Session token found: {manager.session_token[:20]}...")

    # Check login status
    print("\n[4] Checking login status...")
    is_logged_in = manager.check_login_status()
    print(f"    Logged in: {is_logged_in}")

    # Get credits
    if is_logged_in:
        print("\n[5] Getting credit balance...")
        credits = manager.get_credit_balance()
        if credits:
            print(f"    Credits: {credits}")

    # Save session
    print("\n[6] Saving session...")
    session_path = Path(__file__).parent.parent / "session.json"
    manager.save_session(str(session_path))

    print("\n" + "=" * 60)
    print("Session Manager test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
