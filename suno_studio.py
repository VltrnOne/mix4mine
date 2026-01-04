#!/usr/bin/env python3
"""
VLTRN SUNO Studio Mixer Controller
Automates mixing and track manipulation in SUNO Studio via AppleScript
"""
import subprocess
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any


def run_applescript(script: str) -> str:
    """Run an AppleScript and return the result"""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()


def run_js(js_code: str) -> str:
    """Execute JavaScript in Chrome's active tab"""
    escaped_js = js_code.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    script = f'''
    tell application "Google Chrome"
        tell active tab of front window
            execute javascript "{escaped_js}"
        end tell
    end tell
    '''
    return run_applescript(script)


def get_url() -> str:
    """Get current Chrome URL"""
    script = '''
    tell application "Google Chrome"
        get URL of active tab of front window
    end tell
    '''
    return run_applescript(script)


def navigate(url: str):
    """Navigate Chrome to URL"""
    script = f'''
    tell application "Google Chrome"
        set URL of active tab of front window to "{url}"
    end tell
    '''
    run_applescript(script)


def click_element(selector: str) -> bool:
    """Click an element by CSS selector"""
    js = f'''
    (function() {{
        var el = document.querySelector("{selector}");
        if (el) {{
            el.click();
            return "clicked";
        }}
        return "not found";
    }})()
    '''
    result = run_js(js)
    return "clicked" in result


def click_button_by_text(text: str) -> bool:
    """Click a button containing specific text"""
    js = f'''
    (function() {{
        var buttons = document.querySelectorAll("button");
        for (var btn of buttons) {{
            if (btn.textContent.includes("{text}")) {{
                btn.click();
                return "clicked: " + btn.textContent.trim();
            }}
        }}
        return "not found";
    }})()
    '''
    result = run_js(js)
    return "clicked" in result


def get_studio_state() -> Dict[str, Any]:
    """Get current Studio state"""
    js = '''
    (function() {
        var state = {
            bpm: null,
            tracks: 0,
            position: null,
            hasProject: false
        };

        // Find BPM
        var bpmEl = document.querySelector("[class*='bpm'], [data-testid*='bpm']");
        if (bpmEl) {
            var match = bpmEl.textContent.match(/(\\d+)\\s*BPM/i);
            if (match) state.bpm = parseInt(match[1]);
        }

        // Count tracks
        var tracks = document.querySelectorAll("[class*='track'], [data-testid*='track']");
        state.tracks = tracks.length;

        // Check for project
        if (document.body.innerText.includes("Untitled Project") ||
            document.body.innerText.includes("Export")) {
            state.hasProject = true;
        }

        return JSON.stringify(state);
    })()
    '''
    result = run_js(js)
    try:
        return json.loads(result)
    except:
        return {"error": result}


def set_bpm(bpm: int) -> bool:
    """Set the project BPM"""
    js = f'''
    (function() {{
        // Try to find and click BPM element
        var bpmElements = document.querySelectorAll("[class*='bpm'], button");
        for (var el of bpmElements) {{
            if (el.textContent.includes("BPM")) {{
                el.click();
                return "clicked bpm";
            }}
        }}
        return "bpm not found";
    }})()
    '''
    result = run_js(js)

    if "clicked" in result:
        time.sleep(0.5)
        # Try to input the new BPM
        js_input = f'''
        (function() {{
            var inputs = document.querySelectorAll("input[type='number'], input");
            for (var inp of inputs) {{
                if (inp.offsetParent !== null) {{
                    inp.value = "{bpm}";
                    inp.dispatchEvent(new Event("input", {{ bubbles: true }}));
                    inp.dispatchEvent(new Event("change", {{ bubbles: true }}));
                    return "set to {bpm}";
                }}
            }}
            return "no input found";
        }})()
        '''
        result = run_js(js_input)
        return "set to" in result
    return False


def open_library() -> bool:
    """Open the song library in Studio"""
    return click_button_by_text("Open Library") or click_button_by_text("Library")


def add_track() -> bool:
    """Add a new track to the project"""
    return click_button_by_text("Add Track")


def create_song() -> bool:
    """Click Create Song button"""
    return click_button_by_text("Create Song") or click_button_by_text("Create")


def get_library_songs() -> List[Dict[str, str]]:
    """Get songs available in the library"""
    js = '''
    (function() {
        var songs = [];
        var links = document.querySelectorAll("a[href*='/song/']");
        var seen = {};

        for (var link of links) {
            var href = link.href;
            var match = href.match(/\\/song\\/([a-f0-9-]+)/);
            if (match && !seen[match[1]]) {
                seen[match[1]] = true;
                songs.push({
                    id: match[1],
                    title: link.textContent.trim().substring(0, 50),
                    url: href
                });
            }
        }

        return JSON.stringify(songs.slice(0, 20));
    })()
    '''
    result = run_js(js)
    try:
        return json.loads(result)
    except:
        return []


def import_song_to_track(song_id: str) -> bool:
    """Import a song from library to a track"""
    # First open library
    if not open_library():
        print("Could not open library")
        return False

    time.sleep(1)

    # Find and click the song
    js = f'''
    (function() {{
        var links = document.querySelectorAll("a[href*='/song/{song_id}'], [data-id='{song_id}']");
        for (var link of links) {{
            link.click();
            return "clicked song";
        }}

        // Try finding by partial ID
        var allLinks = document.querySelectorAll("a[href*='/song/']");
        for (var link of allLinks) {{
            if (link.href.includes("{song_id.split('-')[0]}")) {{
                link.click();
                return "clicked song (partial match)";
            }}
        }}

        return "song not found";
    }})()
    '''
    result = run_js(js)
    return "clicked" in result


def get_tracks_info() -> List[Dict[str, Any]]:
    """Get information about tracks in the project"""
    js = '''
    (function() {
        var tracks = [];
        var trackElements = document.querySelectorAll("[class*='track'], [role='row']");

        for (var i = 0; i < trackElements.length; i++) {
            var track = trackElements[i];
            var text = track.textContent.trim().substring(0, 100);
            if (text.length > 0) {
                tracks.push({
                    index: i,
                    content: text
                });
            }
        }

        return JSON.stringify(tracks.slice(0, 10));
    })()
    '''
    result = run_js(js)
    try:
        return json.loads(result)
    except:
        return []


def solo_track(track_index: int) -> bool:
    """Solo a specific track"""
    js = f'''
    (function() {{
        var soloButtons = document.querySelectorAll("[aria-label*='solo'], [class*='solo'], button");
        var count = 0;
        for (var btn of soloButtons) {{
            if (btn.textContent.toLowerCase().includes("s") ||
                btn.getAttribute("aria-label")?.toLowerCase().includes("solo")) {{
                if (count === {track_index}) {{
                    btn.click();
                    return "soloed track " + {track_index};
                }}
                count++;
            }}
        }}
        return "solo button not found";
    }})()
    '''
    result = run_js(js)
    return "soloed" in result


def mute_track(track_index: int) -> bool:
    """Mute a specific track"""
    js = f'''
    (function() {{
        var muteButtons = document.querySelectorAll("[aria-label*='mute'], [class*='mute'], button");
        var count = 0;
        for (var btn of muteButtons) {{
            if (btn.textContent.toLowerCase().includes("m") ||
                btn.getAttribute("aria-label")?.toLowerCase().includes("mute")) {{
                if (count === {track_index}) {{
                    btn.click();
                    return "muted track " + {track_index};
                }}
                count++;
            }}
        }}
        return "mute button not found";
    }})()
    '''
    result = run_js(js)
    return "muted" in result


def export_project() -> bool:
    """Export the current project"""
    return click_button_by_text("Export")


def play_project() -> bool:
    """Start playback"""
    js = '''
    (function() {
        var playBtn = document.querySelector("[aria-label*='Play'], [class*='play']");
        if (playBtn) {
            playBtn.click();
            return "playing";
        }
        return "play not found";
    })()
    '''
    result = run_js(js)
    return "playing" in result


def stop_project() -> bool:
    """Stop playback"""
    js = '''
    (function() {
        var stopBtn = document.querySelector("[aria-label*='Stop'], [aria-label*='Pause']");
        if (stopBtn) {
            stopBtn.click();
            return "stopped";
        }
        return "stop not found";
    })()
    '''
    result = run_js(js)
    return "stopped" in result


def interactive_studio():
    """Interactive studio control mode"""
    print("\n" + "="*60)
    print("VLTRN SUNO Studio Controller")
    print("="*60)

    # Check we're in Studio
    url = get_url()
    if "studio" not in url:
        print("Navigating to Studio...")
        navigate("https://suno.com/studio")
        time.sleep(3)

    # Get initial state
    state = get_studio_state()
    print(f"\nStudio State:")
    print(f"  BPM: {state.get('bpm', 'Unknown')}")
    print(f"  Tracks: {state.get('tracks', 0)}")
    print(f"  Project loaded: {state.get('hasProject', False)}")

    print("\nCommands:")
    print("  state       - Show current state")
    print("  bpm <n>     - Set BPM")
    print("  library     - Open library")
    print("  songs       - List library songs")
    print("  add         - Add track")
    print("  tracks      - Show track info")
    print("  import <id> - Import song to track")
    print("  solo <n>    - Solo track n")
    print("  mute <n>    - Mute track n")
    print("  play        - Start playback")
    print("  stop        - Stop playback")
    print("  export      - Export project")
    print("  quit        - Exit")

    while True:
        try:
            cmd = input("\n> ").strip().lower()
            parts = cmd.split(maxsplit=1)
            action = parts[0] if parts else ""
            args = parts[1] if len(parts) > 1 else ""

            if action == "quit" or action == "exit":
                break

            elif action == "state":
                state = get_studio_state()
                print(json.dumps(state, indent=2))

            elif action == "bpm":
                if args:
                    try:
                        bpm = int(args)
                        if set_bpm(bpm):
                            print(f"BPM set to {bpm}")
                        else:
                            print("Could not set BPM")
                    except ValueError:
                        print("Invalid BPM value")
                else:
                    print("Usage: bpm <value>")

            elif action == "library":
                if open_library():
                    print("Library opened")
                else:
                    print("Could not open library")

            elif action == "songs":
                songs = get_library_songs()
                if songs:
                    print(f"\nFound {len(songs)} songs:")
                    for i, s in enumerate(songs):
                        print(f"  {i+1}. {s['id'][:8]}... : {s['title']}")
                else:
                    print("No songs found - try 'library' first")

            elif action == "add":
                if add_track():
                    print("Track added")
                else:
                    print("Could not add track")

            elif action == "tracks":
                tracks = get_tracks_info()
                if tracks:
                    print(f"\nFound {len(tracks)} tracks:")
                    for t in tracks:
                        print(f"  Track {t['index']}: {t['content'][:50]}")
                else:
                    print("No tracks found")

            elif action == "import":
                if args:
                    if import_song_to_track(args):
                        print("Song imported")
                    else:
                        print("Could not import song")
                else:
                    print("Usage: import <song_id>")

            elif action == "solo":
                if args:
                    try:
                        track_num = int(args)
                        if solo_track(track_num):
                            print(f"Track {track_num} soloed")
                        else:
                            print("Could not solo track")
                    except ValueError:
                        print("Invalid track number")
                else:
                    print("Usage: solo <track_number>")

            elif action == "mute":
                if args:
                    try:
                        track_num = int(args)
                        if mute_track(track_num):
                            print(f"Track {track_num} muted")
                        else:
                            print("Could not mute track")
                    except ValueError:
                        print("Invalid track number")
                else:
                    print("Usage: mute <track_number>")

            elif action == "play":
                if play_project():
                    print("Playing")
                else:
                    print("Could not start playback")

            elif action == "stop":
                if stop_project():
                    print("Stopped")
                else:
                    print("Could not stop playback")

            elif action == "export":
                if export_project():
                    print("Export dialog opened")
                else:
                    print("Could not open export")

            elif action == "create":
                if create_song():
                    print("Create Song clicked")
                else:
                    print("Could not click Create Song")

            else:
                print("Unknown command. Type 'quit' to exit.")

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")

    print("\nGoodbye!")


def main():
    """Main entry point"""
    print("="*60)
    print("VLTRN SUNO Studio Mixer")
    print("="*60)

    # Check Chrome connection
    try:
        url = get_url()
        print(f"Connected to Chrome: {url}")
    except Exception as e:
        print(f"Error: Could not connect to Chrome: {e}")
        print("\nMake sure Chrome is running and AppleScript is enabled:")
        print("View > Developer > Allow JavaScript from Apple Events")
        return

    # Navigate to Studio if needed
    if "studio" not in url:
        print("\nNavigating to SUNO Studio...")
        navigate("https://suno.com/studio")
        time.sleep(3)

    # Start interactive mode
    interactive_studio()


if __name__ == "__main__":
    main()
