#!/usr/bin/env python3
"""
VLTRN SUNO Remix Controller
Automates song remixing in SUNO Studio via Selenium
"""
import os
import sys
import time
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

BASE_DIR = Path(__file__).parent


def connect_to_chrome(debug_port=9222):
    """Connect to Chrome with remote debugging"""
    try:
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
        driver = webdriver.Chrome(options=options)
        print(f"✅ Connected to Chrome on port {debug_port}")
        return driver
    except Exception as e:
        print(f"❌ Could not connect: {e}")
        print(f"\nPlease restart Chrome with debugging:")
        print(f'  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={debug_port}')
        return None


def find_suno_tab(driver):
    """Find and switch to SUNO tab"""
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if "suno.com" in driver.current_url:
            print(f"✅ Found SUNO: {driver.current_url}")
            return True
    return False


def get_songs_on_page(driver):
    """Get list of songs visible on the page"""
    songs = []
    try:
        # Find song elements
        song_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/song/']")
        seen = set()

        for elem in song_elements:
            href = elem.get_attribute("href") or ""
            if "/song/" in href:
                song_id = href.split("/song/")[-1].split("?")[0]
                if song_id not in seen and len(song_id) > 10:
                    seen.add(song_id)
                    title = elem.text.strip()[:50] or "Untitled"
                    songs.append({"id": song_id, "title": title, "url": href})
    except Exception as e:
        print(f"Error getting songs: {e}")

    return songs


def click_song_menu(driver, song_element):
    """Click the three-dot menu on a song"""
    try:
        # Hover over the song to reveal menu
        from selenium.webdriver.common.action_chains import ActionChains
        actions = ActionChains(driver)
        actions.move_to_element(song_element).perform()
        time.sleep(0.5)

        # Look for menu button (three dots)
        menu_buttons = driver.find_elements(By.CSS_SELECTOR,
            "[class*='menu'], [class*='more'], [aria-label*='menu'], button[class*='dots']")

        for btn in menu_buttons:
            if btn.is_displayed():
                btn.click()
                time.sleep(0.5)
                return True

        # Try finding by icon/svg
        svg_buttons = song_element.find_elements(By.CSS_SELECTOR, "button, [role='button']")
        for btn in svg_buttons:
            try:
                if btn.is_displayed() and btn.size['width'] < 50:  # Small icon button
                    btn.click()
                    time.sleep(0.5)
                    return True
            except:
                pass

    except Exception as e:
        print(f"Error clicking menu: {e}")
    return False


def find_remix_option(driver):
    """Find and click the Remix option in a menu"""
    try:
        # Look for remix in menus, buttons, or dropdowns
        remix_selectors = [
            "//*[contains(text(), 'Remix')]",
            "//*[contains(text(), 'remix')]",
            "//*[contains(text(), 'Cover')]",
            "//*[contains(text(), 'cover')]",
            "//*[contains(text(), 'Extend')]",
            "//*[contains(text(), 'extend')]",
            "button[class*='remix']",
            "[data-testid*='remix']"
        ]

        for selector in remix_selectors:
            try:
                if selector.startswith("//"):
                    elements = driver.find_elements(By.XPATH, selector)
                else:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)

                for elem in elements:
                    if elem.is_displayed():
                        text = elem.text.lower()
                        if 'remix' in text or 'cover' in text or 'extend' in text:
                            print(f"  Found: {elem.text}")
                            elem.click()
                            return True
            except:
                continue

    except Exception as e:
        print(f"Error finding remix: {e}")
    return False


def navigate_to_song(driver, song_id):
    """Navigate to a specific song page"""
    url = f"https://suno.com/song/{song_id}"
    driver.get(url)
    time.sleep(3)
    print(f"✅ Navigated to song: {song_id}")
    return True


def find_remix_button_on_song_page(driver):
    """Find remix/extend/cover buttons on a song page"""
    try:
        time.sleep(2)

        # Common button texts for remix features
        button_texts = ['Remix', 'Cover', 'Extend', 'Create Cover', 'Make Cover', 'Reuse Prompt']

        buttons = driver.find_elements(By.TAG_NAME, "button")

        for btn in buttons:
            try:
                text = btn.text.strip()
                for target in button_texts:
                    if target.lower() in text.lower():
                        print(f"  Found button: {text}")
                        return btn
            except:
                continue

        # Also check for links
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                text = link.text.strip()
                for target in button_texts:
                    if target.lower() in text.lower():
                        print(f"  Found link: {text}")
                        return link
            except:
                continue

        # Check for icon buttons with aria-labels
        icon_buttons = driver.find_elements(By.CSS_SELECTOR, "[aria-label]")
        for btn in icon_buttons:
            label = btn.get_attribute("aria-label") or ""
            for target in button_texts:
                if target.lower() in label.lower():
                    print(f"  Found icon: {label}")
                    return btn

    except Exception as e:
        print(f"Error finding remix button: {e}")

    return None


def fill_remix_form(driver, new_style=None, keep_lyrics=True):
    """Fill in the remix form with new style"""
    try:
        time.sleep(2)

        # Look for style input
        if new_style:
            style_inputs = driver.find_elements(By.CSS_SELECTOR,
                "input[placeholder*='style'], input[placeholder*='Style'], input[placeholder*='genre']")

            if not style_inputs:
                # Try textareas
                style_inputs = driver.find_elements(By.CSS_SELECTOR,
                    "textarea[placeholder*='style'], input[type='text']")

            for inp in style_inputs:
                try:
                    if inp.is_displayed():
                        inp.clear()
                        inp.send_keys(new_style)
                        print(f"  Filled style: {new_style}")
                        return True
                except:
                    continue

    except Exception as e:
        print(f"Error filling form: {e}")

    return False


def click_create_remix(driver):
    """Click the create/generate button for remix"""
    try:
        button_texts = ['Create', 'Generate', 'Remix', 'Make', 'Submit']

        buttons = driver.find_elements(By.TAG_NAME, "button")

        for btn in buttons:
            try:
                text = btn.text.strip()
                if any(t.lower() in text.lower() for t in button_texts):
                    if btn.is_enabled() and btn.is_displayed():
                        btn.click()
                        print(f"  Clicked: {text}")
                        return True
            except:
                continue

    except Exception as e:
        print(f"Error clicking create: {e}")

    return False


def remix_song(driver, song_id, new_style):
    """Full remix workflow"""
    print(f"\n{'='*50}")
    print(f"Remixing song: {song_id}")
    print(f"New style: {new_style}")
    print(f"{'='*50}")

    # Navigate to song
    navigate_to_song(driver, song_id)

    # Find remix button
    print("\n[1] Looking for remix option...")
    remix_btn = find_remix_button_on_song_page(driver)

    if remix_btn:
        remix_btn.click()
        time.sleep(2)
        print("  Clicked remix button")
    else:
        print("  No remix button found - checking for menu...")
        # Try menu approach
        # Look for three dots or more options
        menu_btns = driver.find_elements(By.CSS_SELECTOR,
            "[aria-label*='more'], [aria-label*='menu'], [class*='menu']")
        for btn in menu_btns:
            try:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    if find_remix_option(driver):
                        break
            except:
                continue

    # Fill remix form
    print("\n[2] Filling remix form...")
    fill_remix_form(driver, new_style)

    # Click create
    print("\n[3] Creating remix...")
    time.sleep(1)
    click_create_remix(driver)

    # Wait for generation
    print("\n[4] Waiting for generation...")
    start = time.time()
    while time.time() - start < 180:
        current_url = driver.current_url
        if "/song/" in current_url and song_id not in current_url:
            new_id = current_url.split("/song/")[-1].split("?")[0]
            print(f"\n✅ Remix created: {new_id}")
            print(f"   URL: https://suno.com/song/{new_id}")
            return new_id
        print(".", end="", flush=True)
        time.sleep(5)

    print("\n⚠️ Timeout - check SUNO manually")
    return None


def interactive_mode(driver):
    """Interactive remix mode"""
    print("\n" + "="*60)
    print("VLTRN SUNO Remix Controller")
    print("="*60)

    while True:
        print("\nCommands:")
        print("  list     - Show songs on current page")
        print("  remix    - Remix a song")
        print("  goto     - Navigate to a song")
        print("  refresh  - Refresh page")
        print("  quit     - Exit")

        try:
            cmd = input("\n> ").strip().lower()

            if cmd == "quit" or cmd == "exit":
                break

            elif cmd == "list":
                songs = get_songs_on_page(driver)
                if songs:
                    print(f"\nFound {len(songs)} songs:")
                    for i, s in enumerate(songs[:10]):
                        print(f"  {i+1}. {s['id'][:8]}... : {s['title']}")
                else:
                    print("No songs found on this page")

            elif cmd == "refresh":
                driver.refresh()
                time.sleep(2)
                print("Page refreshed")

            elif cmd == "goto":
                song_id = input("  Song ID: ").strip()
                if song_id:
                    navigate_to_song(driver, song_id)

            elif cmd == "remix":
                songs = get_songs_on_page(driver)
                if songs:
                    print("\nAvailable songs:")
                    for i, s in enumerate(songs[:10]):
                        print(f"  {i+1}. {s['id'][:8]}... : {s['title']}")

                    choice = input("\nEnter song number or ID: ").strip()

                    try:
                        idx = int(choice) - 1
                        song_id = songs[idx]['id']
                    except:
                        song_id = choice

                    print(f"\nRemixing: {song_id}")
                    new_style = input("New style tags (e.g., [jazz, smooth, saxophone]): ").strip()

                    if new_style:
                        remix_song(driver, song_id, new_style)
                    else:
                        print("Style required for remix")
                else:
                    song_id = input("Enter song ID to remix: ").strip()
                    if song_id:
                        new_style = input("New style tags: ").strip()
                        if new_style:
                            remix_song(driver, song_id, new_style)

            else:
                print("Unknown command")

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    print("="*60)
    print("VLTRN SUNO Remix Controller")
    print("="*60)

    # Connect to Chrome
    print("\n[1] Connecting to Chrome...")
    driver = connect_to_chrome()

    if not driver:
        print("\nTo start Chrome with debugging, run:")
        print('/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222')
        sys.exit(1)

    # Find SUNO tab
    print("\n[2] Finding SUNO tab...")
    if not find_suno_tab(driver):
        print("  Navigating to SUNO...")
        driver.get("https://suno.com/studio")
        time.sleep(3)

    print(f"  Current: {driver.current_url}")

    # Interactive mode
    interactive_mode(driver)

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
