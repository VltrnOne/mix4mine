#!/usr/bin/env python3
"""
VLTRN SUNO Quick Mixer
Fast interactive control of SUNO Studio mixing via AppleScript
"""
import subprocess
import time
import sys
import json


def chrome_js(js: str) -> str:
    """Execute JavaScript in Chrome"""
    escaped = js.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
    script = f'tell application "Google Chrome" to tell active tab of front window to execute javascript "{escaped}"'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip()


def chrome_url() -> str:
    """Get current URL"""
    result = subprocess.run([
        "osascript", "-e",
        'tell application "Google Chrome" to get URL of active tab of front window'
    ], capture_output=True, text=True)
    return result.stdout.strip()


def chrome_go(url: str):
    """Navigate to URL"""
    subprocess.run([
        "osascript", "-e",
        f'tell application "Google Chrome" to set URL of active tab of front window to "{url}"'
    ], capture_output=True)


def get_buttons() -> dict:
    """Get all buttons with their indices"""
    js = '''
    (function() {
        var btns = document.querySelectorAll("button");
        var result = {};
        for (var i = 0; i < btns.length; i++) {
            var text = btns[i].textContent.trim();
            if (text.length > 0 && text.length < 40) {
                result[text] = i;
            }
        }
        return JSON.stringify(result);
    })()
    '''
    result = chrome_js(js)
    try:
        import json
        return json.loads(result)
    except:
        return {}


def click_button(name_contains: str) -> bool:
    """Click a button by partial text match"""
    js = f'''
    (function() {{
        var btns = document.querySelectorAll("button");
        for (var btn of btns) {{
            if (btn.textContent.includes("{name_contains}")) {{
                btn.click();
                return "clicked";
            }}
        }}
        return "not found";
    }})()
    '''
    result = chrome_js(js)
    return "clicked" in str(result)


def click_button_index(index: int):
    """Click button by index"""
    chrome_js(f'document.querySelectorAll("button")[{index}].click()')


def get_page_text() -> str:
    """Get visible text on page"""
    return chrome_js('document.body.innerText.substring(0, 3000)')


def list_songs():
    """List songs in library"""
    js = '''
    (function() {
        var items = [];
        var all = document.querySelectorAll("*");
        for (var el of all) {
            var t = el.innerText;
            if (t && (t.includes("BPM") || t.includes("major") || t.includes("minor"))) {
                if (t.length < 100 && t.length > 5) {
                    var clean = t.replace(/\\n/g, " ").substring(0, 80);
                    if (!items.includes(clean)) items.push(clean);
                }
            }
        }
        return items.slice(0, 10).join("\\n");
    })()
    '''
    return chrome_js(js)


def get_tracks() -> list:
    """Get list of tracks in Studio project"""
    js = '''
    (function() {
        var text = document.body.innerText;
        var idx = text.indexOf("Untitled Project");
        if (idx < 0) idx = text.indexOf("Project");
        if (idx < 0) return "[]";

        var section = text.substring(idx, idx + 1000);
        var lines = section.split(String.fromCharCode(10));
        var tracks = [];
        var trackNum = 0;
        var skipWords = ["S", "Muted", "No Input", "Add Track", "Create", "Drop Here", "Clip", "Track", "Untitled Project"];

        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (line.length > 0 && line.length < 4 && !isNaN(parseInt(line))) {
                trackNum = parseInt(line);
            } else if (trackNum > 0 && line.length > 1 && line.length < 30 &&
                       skipWords.indexOf(line) === -1) {
                tracks.push({num: trackNum, name: line});
                trackNum = 0;
            }
        }
        return JSON.stringify(tracks);
    })()
    '''
    result = chrome_js(js)
    try:
        return json.loads(result)
    except:
        return []


def solo_track(track_num: int) -> bool:
    """Solo a specific track by number"""
    js = f'''
    (function() {{
        var btns = document.querySelectorAll("button");
        var found = false;
        var trackFound = false;

        for (var i = 0; i < btns.length; i++) {{
            var text = btns[i].textContent.trim();
            if (text === "{track_num}") {{
                trackFound = true;
            }}
            if (trackFound && text === "S") {{
                btns[i].click();
                return "soloed track {track_num}";
            }}
        }}
        return "track {track_num} not found";
    }})()
    '''
    result = chrome_js(js)
    return "soloed" in result


def mute_track(track_num: int) -> bool:
    """Mute a specific track by number (click M button)"""
    js = f'''
    (function() {{
        var btns = document.querySelectorAll("button");
        var trackFound = false;

        for (var i = 0; i < btns.length; i++) {{
            var text = btns[i].textContent.trim();
            if (text === "{track_num}") {{
                trackFound = true;
            }}
            if (trackFound && text === "M") {{
                btns[i].click();
                return "muted track {track_num}";
            }}
        }}
        return "mute not found for track {track_num}";
    }})()
    '''
    result = chrome_js(js)
    return "muted" in result


def select_track(track_num: int) -> bool:
    """Select a track by clicking on its number"""
    js = f'''
    (function() {{
        var btns = document.querySelectorAll("button");
        for (var i = 0; i < btns.length; i++) {{
            if (btns[i].textContent.trim() === "{track_num}") {{
                btns[i].click();
                return "selected track {track_num}";
            }}
        }}
        return "track {track_num} not found";
    }})()
    '''
    result = chrome_js(js)
    return "selected" in result


def play() -> bool:
    """Start playback"""
    js = '''
    (function() {
        var btns = document.querySelectorAll("button[aria-label*='Play'], [aria-label*='play']");
        for (var btn of btns) {
            if (btn.offsetParent !== null) {
                btn.click();
                return "playing";
            }
        }
        return "play not found";
    })()
    '''
    return "playing" in chrome_js(js)


def stop() -> bool:
    """Stop playback"""
    js = '''
    (function() {
        var btns = document.querySelectorAll("button[aria-label*='Stop'], button[aria-label*='Pause']");
        for (var btn of btns) {
            if (btn.offsetParent !== null) {
                btn.click();
                return "stopped";
            }
        }
        return "stop not found";
    })()
    '''
    return "stopped" in chrome_js(js)


def print_help():
    print("""
VLTRN SUNO Quick Mixer Commands:
================================
Navigation:
  url           - Show current URL
  studio        - Go to SUNO Studio
  library       - Go to My Library

Studio Mixing:
  tracks        - List all tracks in project
  solo <n>      - Solo track n
  mute <n>      - Mute track n (if available)
  select <n>    - Select track n
  play          - Start playback
  stop          - Stop playback

Page Interaction:
  text          - Show page text
  buttons       - List all buttons
  songs         - List visible songs
  click <text>  - Click button containing text
  btn <n>       - Click button by index

Utility:
  refresh       - Refresh page
  wait <n>      - Wait n seconds
  help          - Show this help
  quit          - Exit
""")


def main():
    print("=" * 50)
    print("VLTRN SUNO Quick Mixer")
    print("=" * 50)

    url = chrome_url()
    print(f"Connected to: {url}")

    if "suno.com" not in url:
        print("Not on SUNO - navigating to Studio...")
        chrome_go("https://suno.com/studio")
        time.sleep(3)

    print_help()

    while True:
        try:
            cmd = input("\nmixer> ").strip()

            if not cmd:
                continue

            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if action in ("quit", "exit", "q"):
                break

            elif action == "help":
                print_help()

            elif action == "url":
                print(chrome_url())

            elif action == "studio":
                chrome_go("https://suno.com/studio")
                time.sleep(2)
                print("Navigated to Studio")

            elif action == "library":
                chrome_go("https://suno.com/me")
                time.sleep(2)
                print("Navigated to Library")

            elif action == "text":
                print(get_page_text())

            elif action == "buttons":
                buttons = get_buttons()
                print(f"\nFound {len(buttons)} buttons:")
                for name, idx in sorted(buttons.items(), key=lambda x: x[1]):
                    if len(name) < 30:
                        print(f"  [{idx:3d}] {name}")

            elif action == "songs":
                songs = list_songs()
                if songs:
                    print("\nVisible songs/clips:")
                    print(songs)
                else:
                    print("No songs found - try 'library' or clicking 'Open Library'")

            elif action == "tracks":
                tracks = get_tracks()
                if tracks:
                    print(f"\nFound {len(tracks)} tracks:")
                    for t in tracks:
                        print(f"  Track {t['num']}: {t['name']}")
                else:
                    print("No tracks found - make sure you're in Studio")

            elif action == "solo":
                if args:
                    try:
                        track_num = int(args)
                        if solo_track(track_num):
                            print(f"Soloed track {track_num}")
                        else:
                            print(f"Could not solo track {track_num}")
                    except ValueError:
                        print("Invalid track number")
                else:
                    print("Usage: solo <track_number>")

            elif action == "mute":
                if args:
                    try:
                        track_num = int(args)
                        if mute_track(track_num):
                            print(f"Muted track {track_num}")
                        else:
                            print(f"Could not mute track {track_num}")
                    except ValueError:
                        print("Invalid track number")
                else:
                    print("Usage: mute <track_number>")

            elif action == "select":
                if args:
                    try:
                        track_num = int(args)
                        if select_track(track_num):
                            print(f"Selected track {track_num}")
                        else:
                            print(f"Could not select track {track_num}")
                    except ValueError:
                        print("Invalid track number")
                else:
                    print("Usage: select <track_number>")

            elif action == "play":
                if play():
                    print("Playing")
                else:
                    print("Could not start playback")

            elif action == "stop":
                if stop():
                    print("Stopped")
                else:
                    print("Could not stop playback")

            elif action == "click":
                if args:
                    if click_button(args):
                        print(f"Clicked button containing '{args}'")
                    else:
                        print(f"No button found containing '{args}'")
                else:
                    print("Usage: click <button text>")

            elif action == "btn":
                if args:
                    try:
                        idx = int(args)
                        click_button_index(idx)
                        print(f"Clicked button [{idx}]")
                    except ValueError:
                        print("Invalid button index")
                else:
                    print("Usage: btn <index>")

            elif action == "refresh":
                chrome_js("location.reload()")
                time.sleep(2)
                print("Page refreshed")

            elif action == "wait":
                try:
                    secs = int(args) if args else 2
                    print(f"Waiting {secs}s...")
                    time.sleep(secs)
                except:
                    print("Invalid wait time")

            else:
                print(f"Unknown command: {action}")
                print("Type 'help' for commands")

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
