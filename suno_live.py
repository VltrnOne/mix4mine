#!/usr/bin/env python3
"""
VLTRN SUNO Live Controller
Direct interaction with Chrome via AppleScript (no debugging port needed)
"""
import subprocess
import time
import json
import re
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

BASE_DIR = Path(__file__).parent


def run_applescript(script: str) -> str:
    """Run an AppleScript and return the result"""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()


def run_js_in_chrome(js_code: str) -> str:
    """Execute JavaScript in Chrome's active tab"""
    # Escape the JavaScript for AppleScript
    escaped_js = js_code.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    script = f'''
    tell application "Google Chrome"
        tell active tab of front window
            execute javascript "{escaped_js}"
        end tell
    end tell
    '''
    return run_applescript(script)


def get_chrome_url() -> str:
    """Get the current URL in Chrome"""
    script = '''
    tell application "Google Chrome"
        get URL of active tab of front window
    end tell
    '''
    return run_applescript(script)


def get_chrome_title() -> str:
    """Get the current page title in Chrome"""
    script = '''
    tell application "Google Chrome"
        get title of active tab of front window
    end tell
    '''
    return run_applescript(script)


def navigate_to(url: str):
    """Navigate Chrome to a URL"""
    script = f'''
    tell application "Google Chrome"
        set URL of active tab of front window to "{url}"
    end tell
    '''
    run_applescript(script)


def find_suno_tab() -> bool:
    """Find and switch to the SUNO tab"""
    script = '''
    tell application "Google Chrome"
        set windowList to every window
        repeat with w in windowList
            set tabList to every tab of w
            repeat with t in tabList
                if URL of t contains "suno.com" then
                    set active tab index of w to (index of t)
                    set index of w to 1
                    return "found"
                end if
            end repeat
        end repeat
        return "not found"
    end tell
    '''
    result = run_applescript(script)
    return "found" in result


def check_suno_login() -> Dict[str, Any]:
    """Check SUNO login status and credits"""
    js = '''
    (function() {
        var result = {logged_in: false, credits: null, user: null};

        // Check for user menu or avatar
        var userElements = document.querySelectorAll('[class*="avatar"], [class*="user"], [data-testid="user"]');
        if (userElements.length > 0) {
            result.logged_in = true;
        }

        // Try to find credits display
        var creditElements = document.querySelectorAll('[class*="credit"], [class*="Credit"]');
        for (var el of creditElements) {
            var text = el.textContent;
            var match = text.match(/(\d+)\s*credit/i);
            if (match) {
                result.credits = parseInt(match[1]);
                break;
            }
        }

        // Check URL
        if (window.location.href.includes('/studio') || window.location.href.includes('/create')) {
            result.logged_in = true;
        }

        return JSON.stringify(result);
    })()
    '''
    result = run_js_in_chrome(js)
    try:
        return json.loads(result)
    except:
        return {"logged_in": False, "credits": None, "error": result}


def get_song_list() -> List[Dict[str, str]]:
    """Get list of songs from the current SUNO page"""
    js = '''
    (function() {
        var songs = [];
        var songElements = document.querySelectorAll('[class*="song"], [data-testid*="song"], a[href*="/song/"]');

        for (var el of songElements) {
            var link = el.href || el.querySelector('a')?.href || '';
            var match = link.match(/\\/song\\/([a-f0-9-]+)/);
            if (match) {
                var title = el.textContent.trim().substring(0, 50);
                songs.push({id: match[1], title: title, url: link});
            }
        }

        // Remove duplicates
        var seen = {};
        songs = songs.filter(function(s) {
            if (seen[s.id]) return false;
            seen[s.id] = true;
            return true;
        });

        return JSON.stringify(songs.slice(0, 20));
    })()
    '''
    result = run_js_in_chrome(js)
    try:
        return json.loads(result)
    except:
        return []


def fill_create_form(lyrics: str, style: str, title: str = "", instrumental: bool = False) -> bool:
    """Fill the SUNO create form"""
    # Navigate to create page if needed
    current_url = get_chrome_url()
    if "/create" not in current_url:
        navigate_to("https://suno.com/create")
        time.sleep(3)

    # Try to click Custom mode
    js_custom = '''
    (function() {
        var customBtn = document.querySelector('[class*="custom"], button:contains("Custom")');
        if (!customBtn) {
            var buttons = document.querySelectorAll('button');
            for (var btn of buttons) {
                if (btn.textContent.includes('Custom')) {
                    btn.click();
                    return 'clicked custom';
                }
            }
        } else {
            customBtn.click();
            return 'clicked custom';
        }
        return 'no custom button';
    })()
    '''
    run_js_in_chrome(js_custom)
    time.sleep(1)

    # Fill lyrics
    escaped_lyrics = lyrics.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
    js_lyrics = f'''
    (function() {{
        var textareas = document.querySelectorAll('textarea');
        for (var ta of textareas) {{
            var placeholder = ta.placeholder || '';
            if (placeholder.toLowerCase().includes('lyric') || placeholder.toLowerCase().includes('write')) {{
                ta.value = '{escaped_lyrics}';
                ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return 'filled lyrics';
            }}
        }}
        if (textareas.length > 0) {{
            textareas[0].value = '{escaped_lyrics}';
            textareas[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
            return 'filled first textarea';
        }}
        return 'no textarea found';
    }})()
    '''
    result = run_js_in_chrome(js_lyrics)
    print(f"  Lyrics: {result}")

    # Fill style
    escaped_style = style.replace("'", "\\'")
    js_style = f'''
    (function() {{
        var inputs = document.querySelectorAll('input');
        for (var inp of inputs) {{
            var placeholder = inp.placeholder || '';
            if (placeholder.toLowerCase().includes('style') || placeholder.toLowerCase().includes('genre')) {{
                inp.value = '{escaped_style}';
                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return 'filled style';
            }}
        }}
        return 'no style input found';
    }})()
    '''
    result = run_js_in_chrome(js_style)
    print(f"  Style: {result}")

    # Fill title if provided
    if title:
        escaped_title = title.replace("'", "\\'")
        js_title = f'''
        (function() {{
            var inputs = document.querySelectorAll('input');
            for (var inp of inputs) {{
                var placeholder = inp.placeholder || '';
                if (placeholder.toLowerCase().includes('title') || placeholder.toLowerCase().includes('name')) {{
                    inp.value = '{escaped_title}';
                    inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return 'filled title';
                }}
            }}
            return 'no title input found';
        }})()
        '''
        result = run_js_in_chrome(js_title)
        print(f"  Title: {result}")

    return True


def click_create_button() -> bool:
    """Click the Create/Generate button"""
    js = '''
    (function() {
        var buttons = document.querySelectorAll('button');
        for (var btn of buttons) {
            var text = btn.textContent.toLowerCase();
            if (text.includes('create') || text.includes('generate') || text.includes('make')) {
                if (!btn.disabled) {
                    btn.click();
                    return 'clicked: ' + btn.textContent;
                }
            }
        }
        return 'no create button found';
    })()
    '''
    result = run_js_in_chrome(js)
    print(f"  Button: {result}")
    return "clicked" in result


def wait_for_generation(timeout: int = 180) -> Optional[str]:
    """Wait for song generation to complete"""
    print("  Waiting for generation...", end="", flush=True)
    start = time.time()

    while time.time() - start < timeout:
        # Check if URL changed to a song page
        url = get_chrome_url()
        if "/song/" in url:
            song_id = url.split("/song/")[-1].split("?")[0]
            print(f" Done!")
            return song_id

        # Check for new song in the page
        js = '''
        (function() {
            var links = document.querySelectorAll('a[href*="/song/"]');
            if (links.length > 0) {
                var href = links[0].href;
                var match = href.match(/\\/song\\/([a-f0-9-]+)/);
                if (match) return match[1];
            }
            return '';
        })()
        '''
        song_id = run_js_in_chrome(js)
        if song_id:
            print(f" Done!")
            return song_id

        print(".", end="", flush=True)
        time.sleep(5)

    print(" Timeout!")
    return None


def generate_song(title: str, lyrics: str, style: str) -> Optional[str]:
    """Generate a song with the given parameters"""
    print(f"\n{'='*50}")
    print(f"Generating: {title}")
    print(f"{'='*50}")

    # Fill the form
    if not fill_create_form(lyrics, style, title):
        print("Failed to fill form")
        return None

    time.sleep(1)

    # Click create
    if not click_create_button():
        print("Failed to click create button")
        return None

    # Wait for generation
    song_id = wait_for_generation()

    if song_id:
        print(f"\nSong created: https://suno.com/song/{song_id}")
        return song_id
    else:
        print("\nGeneration failed or timed out")
        return None


def main():
    print("=" * 60)
    print("VLTRN SUNO Live Controller")
    print("=" * 60)

    # Check for SUNO tab
    print("\n[1] Finding SUNO tab...")
    if find_suno_tab():
        print("    Found SUNO tab")
    else:
        print("    SUNO not open - navigating...")
        navigate_to("https://suno.com/create")
        time.sleep(3)

    # Check current URL
    url = get_chrome_url()
    print(f"    URL: {url}")

    # Check login status
    print("\n[2] Checking login status...")
    status = check_suno_login()
    print(f"    Logged in: {status.get('logged_in', False)}")
    if status.get('credits'):
        print(f"    Credits: {status['credits']}")

    # Get song list if on library page
    print("\n[3] Getting recent songs...")
    songs = get_song_list()
    if songs:
        print(f"    Found {len(songs)} songs:")
        for s in songs[:5]:
            print(f"      - {s['id'][:8]}... : {s['title'][:30]}")
    else:
        print("    No songs found on this page")

    # Interactive mode
    print("\n" + "=" * 60)
    print("Commands: generate, status, songs, quit")
    print("=" * 60)

    while True:
        try:
            cmd = input("\n> ").strip().lower()

            if cmd == "quit" or cmd == "exit":
                break

            elif cmd == "status":
                status = check_suno_login()
                print(f"Logged in: {status.get('logged_in')}")
                print(f"Credits: {status.get('credits', 'Unknown')}")
                print(f"URL: {get_chrome_url()}")

            elif cmd == "songs":
                songs = get_song_list()
                for s in songs:
                    print(f"  {s['id'][:8]} : {s['title'][:40]}")

            elif cmd == "generate":
                title = input("  Title: ").strip() or f"VLTRN_{int(time.time())}"
                theme = input("  Theme: ").strip() or "love and hope"
                genre = input("  Genre [pop]: ").strip() or "pop"

                # Generate simple lyrics
                lyrics = f"""[Verse 1]
Walking through the {theme}
Every moment feels so bright
The world is changing around us
And everything feels right

[Chorus]
This is our time to shine
{theme.title()} is on my mind
Together we will find
A love that's truly divine

[Verse 2]
The journey takes us forward
With every step we take
{theme.title()} guides our way
For both our hearts sake

[Chorus]
This is our time to shine
{theme.title()} is on my mind
Together we will find
A love that's truly divine
"""
                style = f"[{genre}, upbeat, catchy, modern production]"

                song_id = generate_song(title, lyrics, style)
                if song_id:
                    # Save to log
                    log_file = BASE_DIR / "generated_songs.json"
                    try:
                        with open(log_file, 'r') as f:
                            log = json.load(f)
                    except:
                        log = []

                    log.append({
                        "id": song_id,
                        "title": title,
                        "theme": theme,
                        "genre": genre,
                        "timestamp": time.time()
                    })

                    with open(log_file, 'w') as f:
                        json.dump(log, f, indent=2)

            else:
                print("Commands: generate, status, songs, quit")

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
