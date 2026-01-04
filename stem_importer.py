#!/usr/bin/env python3
"""
VLTRN SUNO Stem Importer
Automates importing audio stems into SUNO Studio tracks
"""
import subprocess
import time
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple

BASE_DIR = Path(__file__).parent
STEMS_DIR = BASE_DIR / "stems"
STEMS_DIR.mkdir(exist_ok=True)


class ChromeController:
    """Control Chrome via AppleScript"""

    @staticmethod
    def run_js(js: str) -> str:
        escaped = js.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
        script = f'tell application "Google Chrome" to tell active tab of front window to execute javascript "{escaped}"'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return result.stdout.strip()

    @staticmethod
    def get_url() -> str:
        result = subprocess.run([
            "osascript", "-e",
            'tell application "Google Chrome" to get URL of active tab of front window'
        ], capture_output=True, text=True)
        return result.stdout.strip()

    @staticmethod
    def navigate(url: str):
        subprocess.run([
            "osascript", "-e",
            f'tell application "Google Chrome" to set URL of active tab of front window to "{url}"'
        ], capture_output=True)

    @staticmethod
    def keystroke(key: str, modifiers: str = ""):
        """Send keystroke to Chrome"""
        if modifiers:
            script = f'''
            tell application "System Events"
                tell process "Google Chrome"
                    keystroke "{key}" using {modifiers}
                end tell
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                tell process "Google Chrome"
                    keystroke "{key}"
                end tell
            end tell
            '''
        subprocess.run(["osascript", "-e", script], capture_output=True)

    @staticmethod
    def click_coordinates(x: int, y: int):
        """Click at specific screen coordinates"""
        script = f'''
        tell application "System Events"
            click at {{{x}, {y}}}
        end tell
        '''
        subprocess.run(["osascript", "-e", script], capture_output=True)


class StemAnalyzer:
    """Analyze audio stems for import preparation"""

    @staticmethod
    def analyze_file(file_path: str) -> Dict:
        """Get audio file properties"""
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            stream = data.get('streams', [{}])[0]
            fmt = data.get('format', {})
            return {
                'path': file_path,
                'filename': os.path.basename(file_path),
                'duration': float(fmt.get('duration', 0)),
                'sample_rate': int(stream.get('sample_rate', 0)),
                'channels': stream.get('channels', 0),
                'bitrate': int(fmt.get('bit_rate', 0)) // 1000,
                'format': fmt.get('format_name', 'unknown')
            }
        return {'path': file_path, 'error': 'Could not analyze'}

    @staticmethod
    def convert_to_suno_format(input_file: str, output_file: str) -> bool:
        """Convert audio to SUNO-compatible format (WAV 48kHz stereo)"""
        cmd = [
            'ffmpeg', '-y', '-i', input_file,
            '-ar', '48000',     # 48kHz sample rate
            '-ac', '2',         # Stereo
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def detect_stem_type(filename: str) -> str:
        """Guess stem type from filename"""
        name = filename.lower()

        stem_patterns = {
            'vocals': ['vocal', 'vox', 'voice', 'sing', 'lead_vocal'],
            'backing_vocals': ['backing', 'bv', 'harmony', 'choir', 'back_vocal'],
            'drums': ['drum', 'beat', 'kick', 'snare', 'hihat', 'percussion'],
            'bass': ['bass', 'sub', 'low'],
            'guitar': ['guitar', 'gtr', 'acoustic', 'electric_guitar'],
            'keyboard': ['keys', 'keyboard', 'piano', 'synth', 'organ', 'rhodes'],
            'strings': ['string', 'violin', 'cello', 'orchestra', 'orchestral'],
            'brass': ['brass', 'trumpet', 'horn', 'trombone', 'sax'],
            'fx': ['fx', 'effect', 'sfx', 'ambient', 'atmosphere'],
            'other': []
        }

        for stem_type, patterns in stem_patterns.items():
            for pattern in patterns:
                if pattern in name:
                    return stem_type

        return 'other'


class SunoStudioImporter:
    """Import stems into SUNO Studio"""

    def __init__(self):
        self.chrome = ChromeController()
        self.analyzer = StemAnalyzer()

    def ensure_studio(self) -> bool:
        """Make sure we're in SUNO Studio"""
        url = self.chrome.get_url()
        if 'suno.com/studio' not in url:
            print("Navigating to SUNO Studio...")
            self.chrome.navigate("https://suno.com/studio")
            time.sleep(3)
            return True
        return True

    def get_current_tracks(self) -> List[Dict]:
        """Get list of tracks in current project"""
        js = '''
        (function() {
            var text = document.body.innerText;
            var idx = text.indexOf("Project");
            if (idx < 0) return "[]";

            var section = text.substring(idx, idx + 1500);
            var lines = section.split(String.fromCharCode(10));
            var tracks = [];
            var trackNum = 0;
            var skipWords = ["S", "M", "Muted", "No Input", "Add Track", "Create", "Drop Here", "Clip", "Track", "Untitled Project", "Project"];

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
        result = self.chrome.run_js(js)
        try:
            return json.loads(result)
        except:
            return []

    def add_track(self) -> bool:
        """Add a new track to the project"""
        js = '''
        (function() {
            var btns = document.querySelectorAll("button");
            for (var btn of btns) {
                if (btn.textContent.includes("Add Track")) {
                    btn.click();
                    return "added";
                }
            }
            return "not found";
        })()
        '''
        result = self.chrome.run_js(js)
        return "added" in result

    def select_track(self, track_num: int) -> bool:
        """Select a track by number"""
        js = f'''
        (function() {{
            var btns = document.querySelectorAll("button");
            for (var btn of btns) {{
                if (btn.textContent.trim() === "{track_num}") {{
                    btn.click();
                    return "selected";
                }}
            }}
            return "not found";
        }})()
        '''
        result = self.chrome.run_js(js)
        return "selected" in result

    def open_library(self) -> bool:
        """Open the song/audio library"""
        js = '''
        (function() {
            var btns = document.querySelectorAll("button");
            for (var btn of btns) {
                var text = btn.textContent.toLowerCase();
                if (text.includes("library") || text.includes("open library")) {
                    btn.click();
                    return "opened";
                }
            }
            return "not found";
        })()
        '''
        result = self.chrome.run_js(js)
        return "opened" in result

    def click_import(self) -> bool:
        """Click import/upload button"""
        js = '''
        (function() {
            var btns = document.querySelectorAll("button, [role='button']");
            for (var btn of btns) {
                var text = btn.textContent.toLowerCase();
                var label = (btn.getAttribute("aria-label") || "").toLowerCase();
                if (text.includes("import") || text.includes("upload") ||
                    label.includes("import") || label.includes("upload")) {
                    btn.click();
                    return "clicked";
                }
            }

            // Try file input
            var inputs = document.querySelectorAll("input[type='file']");
            for (var inp of inputs) {
                if (inp.offsetParent !== null) {
                    inp.click();
                    return "file input clicked";
                }
            }

            return "not found";
        })()
        '''
        result = self.chrome.run_js(js)
        return "clicked" in result

    def drag_and_drop_hint(self) -> str:
        """Get hint about drag-and-drop area"""
        js = '''
        (function() {
            var dropZones = document.querySelectorAll("[class*='drop'], [class*='Drop'], [data-testid*='drop']");
            if (dropZones.length > 0) {
                return "Drop zones found: " + dropZones.length;
            }

            var text = document.body.innerText;
            if (text.includes("Drop Here") || text.includes("drag")) {
                return "Drag and drop supported";
            }

            return "Manual import may be required";
        })()
        '''
        return self.chrome.run_js(js)

    def prepare_stems(self, stem_files: List[str]) -> List[Dict]:
        """Prepare stems for import - analyze and convert if needed"""
        prepared = []

        for file_path in stem_files:
            if not os.path.exists(file_path):
                print(f"  Skipping (not found): {file_path}")
                continue

            info = self.analyzer.analyze_file(file_path)
            if 'error' in info:
                print(f"  Skipping (error): {file_path}")
                continue

            info['stem_type'] = self.analyzer.detect_stem_type(info['filename'])

            # Check if conversion needed
            needs_conversion = (
                info['sample_rate'] != 48000 or
                info['channels'] != 2 or
                not file_path.lower().endswith('.wav')
            )

            if needs_conversion:
                output_name = Path(file_path).stem + "_suno.wav"
                output_path = str(STEMS_DIR / output_name)

                print(f"  Converting: {info['filename']} -> {output_name}")
                if self.analyzer.convert_to_suno_format(file_path, output_path):
                    info['converted_path'] = output_path
                    info['needs_conversion'] = True
            else:
                info['needs_conversion'] = False

            prepared.append(info)

        return prepared

    def show_import_workflow(self, stems: List[Dict]):
        """Show step-by-step import workflow"""
        print("\n" + "="*60)
        print("STEM IMPORT WORKFLOW")
        print("="*60)

        print(f"\nPrepared {len(stems)} stems for import:\n")

        for i, stem in enumerate(stems, 1):
            path = stem.get('converted_path', stem['path'])
            print(f"  {i}. {stem['filename']}")
            print(f"     Type: {stem['stem_type']}")
            print(f"     Duration: {stem['duration']:.1f}s")
            if stem.get('needs_conversion'):
                print(f"     Converted to: {stem['converted_path']}")

        print("\n" + "-"*60)
        print("IMPORT STEPS:")
        print("-"*60)
        print("""
1. In SUNO Studio, select the target track (or add new track)
2. Click "Open Library" or the import button
3. Drag your audio file to the track, or use the file picker:
""")

        for i, stem in enumerate(stems, 1):
            path = stem.get('converted_path', stem['path'])
            print(f"   Track {i}: {path}")

        print("""
4. Adjust clip position on timeline as needed
5. Set track volume and effects

KEYBOARD SHORTCUTS (in SUNO Studio):
  Space       - Play/Stop
  Cmd+Z       - Undo
  Cmd+S       - Save project
  +/-         - Zoom in/out
""")


def scan_stem_folder(folder: str) -> List[str]:
    """Scan folder for audio files"""
    audio_extensions = {'.wav', '.mp3', '.aiff', '.flac', '.m4a', '.ogg'}
    stems = []

    folder_path = Path(folder)
    if not folder_path.exists():
        return []

    for f in folder_path.iterdir():
        if f.suffix.lower() in audio_extensions:
            stems.append(str(f))

    return sorted(stems)


def interactive_mode():
    """Interactive stem import mode"""
    importer = SunoStudioImporter()

    print("""
╔══════════════════════════════════════════════════════════════╗
║              VLTRN SUNO STEM IMPORTER v1.0                   ║
║           Import audio stems into SUNO Studio                ║
╠══════════════════════════════════════════════════════════════╣
║  Commands:                                                   ║
║    scan <folder>   - Scan folder for audio files            ║
║    prepare         - Prepare scanned stems for import       ║
║    workflow        - Show import workflow                    ║
║    tracks          - List current Studio tracks             ║
║    add             - Add new track                          ║
║    select <n>      - Select track number                    ║
║    library         - Open song library                      ║
║    studio          - Navigate to Studio                     ║
║    help            - Show this help                         ║
║    quit            - Exit                                   ║
╚══════════════════════════════════════════════════════════════╝
    """)

    scanned_stems = []
    prepared_stems = []

    while True:
        try:
            cmd = input("\nstems> ").strip()

            if not cmd:
                continue

            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if action in ('quit', 'exit', 'q'):
                break

            elif action == 'help':
                print(__doc__)

            elif action == 'studio':
                importer.ensure_studio()
                print("Navigated to SUNO Studio")

            elif action == 'tracks':
                tracks = importer.get_current_tracks()
                if tracks:
                    print(f"\nFound {len(tracks)} tracks:")
                    for t in tracks:
                        print(f"  Track {t['num']}: {t['name']}")
                else:
                    print("No tracks found - navigate to Studio first")

            elif action == 'add':
                if importer.add_track():
                    print("Track added")
                else:
                    print("Could not add track")

            elif action == 'select':
                if args:
                    try:
                        track_num = int(args)
                        if importer.select_track(track_num):
                            print(f"Selected track {track_num}")
                        else:
                            print(f"Could not select track {track_num}")
                    except ValueError:
                        print("Invalid track number")
                else:
                    print("Usage: select <track_number>")

            elif action == 'library':
                if importer.open_library():
                    print("Library opened")
                else:
                    print("Could not open library")

            elif action == 'scan':
                if args:
                    folder = os.path.expanduser(args)
                    scanned_stems = scan_stem_folder(folder)
                    if scanned_stems:
                        print(f"\nFound {len(scanned_stems)} audio files:")
                        for f in scanned_stems:
                            print(f"  {os.path.basename(f)}")
                    else:
                        print("No audio files found in that folder")
                else:
                    # Default to stems folder
                    scanned_stems = scan_stem_folder(str(STEMS_DIR))
                    if scanned_stems:
                        print(f"\nFound {len(scanned_stems)} audio files in stems folder:")
                        for f in scanned_stems:
                            print(f"  {os.path.basename(f)}")
                    else:
                        print(f"No stems in {STEMS_DIR}")
                        print("Usage: scan <folder_path>")

            elif action == 'prepare':
                if scanned_stems:
                    print("\nPreparing stems...")
                    prepared_stems = importer.prepare_stems(scanned_stems)
                    print(f"\nPrepared {len(prepared_stems)} stems for import")
                else:
                    print("No stems scanned. Use 'scan <folder>' first")

            elif action == 'workflow':
                if prepared_stems:
                    importer.show_import_workflow(prepared_stems)
                elif scanned_stems:
                    print("Run 'prepare' first to analyze stems")
                else:
                    print("Scan a folder first with 'scan <folder>'")

            elif action == 'drop':
                hint = importer.drag_and_drop_hint()
                print(hint)

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
    interactive_mode()
