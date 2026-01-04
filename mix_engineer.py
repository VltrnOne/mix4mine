#!/usr/bin/env python3
"""
VLTRN Mix Engineer
Natural language mixing and mastering interface
Combines SUNO AI generation with audio processing tools
"""
import subprocess
import json
import os
import time
import re
from pathlib import Path
from typing import Optional, Dict, List, Any

# Configuration
BASE_DIR = Path(__file__).parent
EXPORTS_DIR = BASE_DIR / "exports"
PROCESSED_DIR = BASE_DIR / "processed"
SESSIONS_DIR = BASE_DIR / "sessions"

for d in [EXPORTS_DIR, PROCESSED_DIR, SESSIONS_DIR]:
    d.mkdir(exist_ok=True)


class ChromeController:
    """Control Chrome/SUNO via AppleScript"""

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


class AudioProcessor:
    """Process audio with FFmpeg and SoX"""

    @staticmethod
    def check_tools() -> Dict[str, bool]:
        """Check which audio tools are available"""
        tools = {}
        for tool in ['ffmpeg', 'sox', 'ffprobe']:
            result = subprocess.run(['which', tool], capture_output=True)
            tools[tool] = result.returncode == 0
        return tools

    @staticmethod
    def apply_eq(input_file: str, output_file: str,
                 bass: int = 0, mid: int = 0, treble: int = 0) -> bool:
        """Apply 3-band EQ using FFmpeg"""
        # Bass: 100Hz, Mid: 1000Hz, Treble: 10000Hz
        filters = []
        if bass != 0:
            filters.append(f"equalizer=f=100:t=q:w=1:g={bass}")
        if mid != 0:
            filters.append(f"equalizer=f=1000:t=q:w=1:g={mid}")
        if treble != 0:
            filters.append(f"equalizer=f=10000:t=q:w=1:g={treble}")

        if not filters:
            return False

        filter_str = ",".join(filters)
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def apply_compression(input_file: str, output_file: str,
                         threshold: float = -20, ratio: float = 4,
                         attack: float = 5, release: float = 50) -> bool:
        """Apply dynamic range compression"""
        filter_str = f"acompressor=threshold={threshold}dB:ratio={ratio}:attack={attack}:release={release}"
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def apply_reverb(input_file: str, output_file: str,
                    room_size: float = 0.5, damping: float = 0.5,
                    wet: float = 0.3) -> bool:
        """Apply reverb effect"""
        # Using FFmpeg's aecho for reverb-like effect
        delay = int(room_size * 100)
        decay = 1 - damping
        filter_str = f"aecho=0.8:{decay}:{delay}:{decay * 0.5}"
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def apply_limiter(input_file: str, output_file: str,
                     limit: float = -1.0) -> bool:
        """Apply brick-wall limiter for mastering"""
        filter_str = f"alimiter=limit={limit}dB:level=false"
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def normalize(input_file: str, output_file: str,
                 target_lufs: float = -14.0) -> bool:
        """Loudness normalize for streaming"""
        filter_str = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def adjust_volume(input_file: str, output_file: str, db: float) -> bool:
        """Adjust volume in dB"""
        filter_str = f"volume={db}dB"
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def stereo_width(input_file: str, output_file: str, width: float = 1.5) -> bool:
        """Adjust stereo width (1.0 = normal, >1 = wider, <1 = narrower)"""
        filter_str = f"stereotools=mlev={width}"
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def high_pass(input_file: str, output_file: str, freq: int = 80) -> bool:
        """High-pass filter to remove rumble"""
        filter_str = f"highpass=f={freq}"
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def low_pass(input_file: str, output_file: str, freq: int = 18000) -> bool:
        """Low-pass filter"""
        filter_str = f"lowpass=f={freq}"
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    @staticmethod
    def analyze_audio(input_file: str) -> Dict[str, Any]:
        """Analyze audio file properties"""
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', input_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {}

    @staticmethod
    def chain_effects(input_file: str, output_file: str, filters: List[str]) -> bool:
        """Apply a chain of effects"""
        if not filters:
            return False
        filter_str = ",".join(filters)
        cmd = ['ffmpeg', '-y', '-i', input_file, '-af', filter_str, output_file]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0


class MixSession:
    """Manages a mixing session with history"""

    def __init__(self, name: str):
        self.name = name
        self.session_dir = SESSIONS_DIR / name
        self.session_dir.mkdir(exist_ok=True)
        self.history: List[Dict] = []
        self.current_file: Optional[str] = None
        self.version = 0
        self.load_session()

    def load_session(self):
        """Load session state if exists"""
        state_file = self.session_dir / "session.json"
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
                self.history = state.get('history', [])
                self.current_file = state.get('current_file')
                self.version = state.get('version', 0)

    def save_session(self):
        """Save session state"""
        state_file = self.session_dir / "session.json"
        with open(state_file, 'w') as f:
            json.dump({
                'history': self.history,
                'current_file': self.current_file,
                'version': self.version
            }, f, indent=2)

    def add_action(self, action: str, params: Dict, result: str):
        """Record an action in history"""
        self.history.append({
            'action': action,
            'params': params,
            'result': result,
            'version': self.version,
            'timestamp': time.time()
        })
        self.save_session()

    def set_source(self, file_path: str):
        """Set the source audio file"""
        self.current_file = file_path
        self.version = 0
        self.save_session()

    def get_versioned_path(self, suffix: str = "") -> str:
        """Get path for next version"""
        self.version += 1
        name = f"v{self.version:03d}{suffix}.wav"
        return str(self.session_dir / name)


class PromptParser:
    """Parse natural language mixing prompts"""

    # Keywords for different operations
    EQ_KEYWORDS = ['eq', 'equalizer', 'bass', 'treble', 'mid', 'mids', 'highs', 'lows',
                   'frequency', 'frequencies', 'bright', 'dark', 'warm', 'muddy', 'crisp']

    COMPRESSION_KEYWORDS = ['compress', 'compression', 'compressor', 'dynamics',
                            'punch', 'punchy', 'squash', 'glue', 'thick']

    REVERB_KEYWORDS = ['reverb', 'room', 'hall', 'space', 'ambient', 'wet', 'dry',
                       'atmosphere', 'depth']

    VOLUME_KEYWORDS = ['volume', 'level', 'loud', 'quiet', 'gain', 'boost', 'cut',
                       'turn up', 'turn down', 'louder', 'softer']

    MASTER_KEYWORDS = ['master', 'mastering', 'finalize', 'polish', 'streaming',
                       'spotify', 'release', 'final']

    STYLE_KEYWORDS = ['style', 'genre', 'vibe', 'feel', 'mood', 'sound like',
                      'similar to', 'remake', 'reimagine', 'version']

    WIDTH_KEYWORDS = ['stereo', 'width', 'wide', 'narrow', 'mono', 'spread']

    @classmethod
    def parse(cls, prompt: str) -> Dict[str, Any]:
        """Parse a mixing prompt and extract operations"""
        prompt_lower = prompt.lower()

        result = {
            'original': prompt,
            'operations': [],
            'requires_suno': False,
            'requires_audio_processing': False
        }

        # Check for EQ operations
        if any(kw in prompt_lower for kw in cls.EQ_KEYWORDS):
            eq_params = cls._parse_eq(prompt_lower)
            if eq_params:
                result['operations'].append({'type': 'eq', 'params': eq_params})
                result['requires_audio_processing'] = True

        # Check for compression
        if any(kw in prompt_lower for kw in cls.COMPRESSION_KEYWORDS):
            comp_params = cls._parse_compression(prompt_lower)
            result['operations'].append({'type': 'compression', 'params': comp_params})
            result['requires_audio_processing'] = True

        # Check for reverb
        if any(kw in prompt_lower for kw in cls.REVERB_KEYWORDS):
            reverb_params = cls._parse_reverb(prompt_lower)
            result['operations'].append({'type': 'reverb', 'params': reverb_params})
            result['requires_audio_processing'] = True

        # Check for volume
        if any(kw in prompt_lower for kw in cls.VOLUME_KEYWORDS):
            vol_params = cls._parse_volume(prompt_lower)
            result['operations'].append({'type': 'volume', 'params': vol_params})
            result['requires_audio_processing'] = True

        # Check for stereo width
        if any(kw in prompt_lower for kw in cls.WIDTH_KEYWORDS):
            width_params = cls._parse_width(prompt_lower)
            result['operations'].append({'type': 'stereo_width', 'params': width_params})
            result['requires_audio_processing'] = True

        # Check for mastering
        if any(kw in prompt_lower for kw in cls.MASTER_KEYWORDS):
            result['operations'].append({'type': 'master', 'params': {}})
            result['requires_audio_processing'] = True

        # Check for style/SUNO operations
        if any(kw in prompt_lower for kw in cls.STYLE_KEYWORDS):
            result['requires_suno'] = True
            result['style_prompt'] = prompt

        return result

    @classmethod
    def _parse_eq(cls, prompt: str) -> Dict:
        """Extract EQ parameters from prompt"""
        params = {'bass': 0, 'mid': 0, 'treble': 0}

        # Bass adjustments
        if 'more bass' in prompt or 'boost bass' in prompt or 'add bass' in prompt:
            params['bass'] = 4
        elif 'less bass' in prompt or 'cut bass' in prompt or 'reduce bass' in prompt:
            params['bass'] = -4
        elif 'warm' in prompt:
            params['bass'] = 2
            params['treble'] = -1

        # Treble/highs adjustments
        if 'more treble' in prompt or 'brighter' in prompt or 'crisp' in prompt or 'bright' in prompt:
            params['treble'] = 3
        elif 'less treble' in prompt or 'dark' in prompt or 'darker' in prompt:
            params['treble'] = -3

        # Mids adjustments
        if 'more mids' in prompt or 'boost mids' in prompt:
            params['mid'] = 3
        elif 'less mids' in prompt or 'scoop' in prompt or 'scooped' in prompt:
            params['mid'] = -4
        elif 'muddy' in prompt or 'clear' in prompt:
            params['mid'] = -2
            params['treble'] = 2

        return params

    @classmethod
    def _parse_compression(cls, prompt: str) -> Dict:
        """Extract compression parameters from prompt"""
        params = {'threshold': -20, 'ratio': 4, 'attack': 5, 'release': 50}

        if 'heavy' in prompt or 'squash' in prompt:
            params['ratio'] = 8
            params['threshold'] = -25
        elif 'light' in prompt or 'gentle' in prompt:
            params['ratio'] = 2
            params['threshold'] = -15
        elif 'punch' in prompt or 'punchy' in prompt:
            params['attack'] = 20
            params['ratio'] = 4
        elif 'glue' in prompt:
            params['ratio'] = 2
            params['threshold'] = -10

        return params

    @classmethod
    def _parse_reverb(cls, prompt: str) -> Dict:
        """Extract reverb parameters from prompt"""
        params = {'room_size': 0.5, 'damping': 0.5, 'wet': 0.3}

        if 'hall' in prompt or 'large' in prompt or 'big' in prompt:
            params['room_size'] = 0.9
            params['wet'] = 0.4
        elif 'room' in prompt or 'small' in prompt:
            params['room_size'] = 0.3
            params['wet'] = 0.2
        elif 'plate' in prompt:
            params['room_size'] = 0.6
            params['damping'] = 0.3

        if 'wet' in prompt or 'lots of' in prompt or 'more reverb' in prompt:
            params['wet'] = 0.5
        elif 'dry' in prompt or 'subtle' in prompt or 'less reverb' in prompt:
            params['wet'] = 0.15

        return params

    @classmethod
    def _parse_volume(cls, prompt: str) -> Dict:
        """Extract volume parameters from prompt"""
        params = {'db': 0}

        if 'louder' in prompt or 'turn up' in prompt or 'boost' in prompt:
            params['db'] = 3
        elif 'quieter' in prompt or 'turn down' in prompt or 'reduce' in prompt:
            params['db'] = -3
        elif 'much louder' in prompt:
            params['db'] = 6
        elif 'much quieter' in prompt:
            params['db'] = -6

        # Look for specific dB values
        db_match = re.search(r'([+-]?\d+)\s*db', prompt)
        if db_match:
            params['db'] = int(db_match.group(1))

        return params

    @classmethod
    def _parse_width(cls, prompt: str) -> Dict:
        """Extract stereo width parameters from prompt"""
        params = {'width': 1.0}

        if 'wider' in prompt or 'spread' in prompt or 'wide' in prompt:
            params['width'] = 1.5
        elif 'narrow' in prompt or 'mono' in prompt or 'centered' in prompt:
            params['width'] = 0.5
        elif 'very wide' in prompt:
            params['width'] = 2.0

        return params


class MixEngineer:
    """Main mixing engineer interface"""

    def __init__(self):
        self.chrome = ChromeController()
        self.audio = AudioProcessor()
        self.parser = PromptParser()
        self.session: Optional[MixSession] = None
        self.tools = self.audio.check_tools()

    def start_session(self, name: str):
        """Start or resume a mixing session"""
        self.session = MixSession(name)
        print(f"\n{'='*60}")
        print(f"VLTRN Mix Engineer - Session: {name}")
        print(f"{'='*60}")

        if self.session.current_file:
            print(f"Resuming with: {self.session.current_file}")
            print(f"Version: {self.session.version}")

        # Check tools
        print("\nAudio Tools Status:")
        for tool, available in self.tools.items():
            status = "✓" if available else "✗"
            print(f"  {status} {tool}")

        if not self.tools.get('ffmpeg'):
            print("\n⚠️  FFmpeg not found - audio processing limited")
            print("   Install with: brew install ffmpeg")

    def set_source(self, file_path: str) -> bool:
        """Set the source audio file for mixing"""
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return False

        self.session.set_source(file_path)

        # Analyze the audio
        info = self.audio.analyze_audio(file_path)
        if info:
            stream = info.get('streams', [{}])[0]
            fmt = info.get('format', {})
            print(f"\nSource Audio:")
            print(f"  Duration: {float(fmt.get('duration', 0)):.1f}s")
            print(f"  Sample Rate: {stream.get('sample_rate', 'N/A')} Hz")
            print(f"  Channels: {stream.get('channels', 'N/A')}")
            print(f"  Bitrate: {int(fmt.get('bit_rate', 0))/1000:.0f} kbps")

        return True

    def process_prompt(self, prompt: str) -> str:
        """Process a natural language mixing prompt"""
        if not self.session:
            return "No session active. Use start_session() first."

        if not self.session.current_file:
            return "No source file set. Use set_source() first."

        # Parse the prompt
        parsed = self.parser.parse(prompt)

        if not parsed['operations'] and not parsed['requires_suno']:
            return self._suggest_operations(prompt)

        results = []
        current_file = self.session.current_file

        # Process each operation
        for op in parsed['operations']:
            op_type = op['type']
            params = op['params']

            output_file = self.session.get_versioned_path(f"_{op_type}")

            success = False
            if op_type == 'eq':
                success = self.audio.apply_eq(current_file, output_file, **params)
                results.append(f"EQ: bass={params['bass']:+d}dB, mid={params['mid']:+d}dB, treble={params['treble']:+d}dB")

            elif op_type == 'compression':
                success = self.audio.apply_compression(current_file, output_file, **params)
                results.append(f"Compression: {params['ratio']}:1 @ {params['threshold']}dB")

            elif op_type == 'reverb':
                success = self.audio.apply_reverb(current_file, output_file, **params)
                results.append(f"Reverb: room={params['room_size']:.1f}, wet={params['wet']:.1f}")

            elif op_type == 'volume':
                success = self.audio.adjust_volume(current_file, output_file, params['db'])
                results.append(f"Volume: {params['db']:+d}dB")

            elif op_type == 'stereo_width':
                success = self.audio.stereo_width(current_file, output_file, params['width'])
                results.append(f"Stereo Width: {params['width']:.1f}x")

            elif op_type == 'master':
                # Apply mastering chain
                temp_file = self.session.get_versioned_path("_master_temp")

                # Chain: High-pass → Compression → EQ → Limiter → Normalize
                filters = [
                    "highpass=f=30",
                    "acompressor=threshold=-18dB:ratio=3:attack=10:release=100",
                    "equalizer=f=100:t=q:w=1:g=1,equalizer=f=10000:t=q:w=1:g=1.5",
                    "alimiter=limit=-1dB:level=false",
                    "loudnorm=I=-14:TP=-1.5:LRA=11"
                ]
                success = self.audio.chain_effects(current_file, output_file, filters)
                results.append("Mastering chain applied (HP, Comp, EQ, Limiter, Loudness)")

            if success:
                current_file = output_file
                self.session.current_file = output_file
                self.session.add_action(op_type, params, "success")
            else:
                results.append(f"  ⚠️ {op_type} failed")

        # Handle SUNO style requests
        if parsed['requires_suno']:
            results.append("\n🎵 Style change requested - this requires SUNO AI regeneration")
            results.append(f"   Prompt: {parsed.get('style_prompt', prompt)}")
            results.append("   Use 'regenerate' command in SUNO Studio")

        self.session.save_session()

        return "\n".join([
            f"\n✓ Applied {len(parsed['operations'])} operation(s):",
            *[f"  • {r}" for r in results],
            f"\nCurrent version: v{self.session.version:03d}",
            f"Output: {self.session.current_file}"
        ])

    def _suggest_operations(self, prompt: str) -> str:
        """Suggest operations based on unclear prompt"""
        return """
I'm not sure what mixing operation you want. Here are some examples:

EQ / Tone:
  "make it brighter"
  "add more bass"
  "cut the mids, it's muddy"
  "make it warmer"

Compression / Dynamics:
  "add some punch"
  "make it glue together"
  "heavy compression"

Reverb / Space:
  "add hall reverb"
  "make it sound bigger"
  "add subtle room ambience"

Volume / Levels:
  "make it louder"
  "turn it down 3dB"

Stereo / Width:
  "make it wider"
  "narrow the stereo image"

Mastering:
  "master for streaming"
  "finalize the mix"

What would you like to do?
"""

    def show_history(self):
        """Show session history"""
        if not self.session:
            return "No session active"

        print(f"\n{'='*60}")
        print(f"Session History: {self.session.name}")
        print(f"{'='*60}")

        for i, action in enumerate(self.session.history):
            print(f"\n[{action['version']:03d}] {action['action']}")
            print(f"      Params: {action['params']}")

    def undo(self) -> str:
        """Revert to previous version"""
        if not self.session or self.session.version < 2:
            return "Nothing to undo"

        prev_version = self.session.version - 1
        prev_file = None

        # Find previous version file
        for f in self.session.session_dir.glob(f"v{prev_version:03d}*.wav"):
            prev_file = str(f)
            break

        if prev_file and os.path.exists(prev_file):
            self.session.current_file = prev_file
            self.session.version = prev_version
            self.session.save_session()
            return f"Reverted to version {prev_version}"

        return "Could not find previous version"

    def export(self, filename: str) -> str:
        """Export current version to final file"""
        if not self.session or not self.session.current_file:
            return "No file to export"

        output = PROCESSED_DIR / filename
        subprocess.run([
            'ffmpeg', '-y', '-i', self.session.current_file,
            '-c:a', 'libmp3lame', '-b:a', '320k', str(output)
        ], capture_output=True)

        return f"Exported to: {output}"


def interactive_mode():
    """Run the interactive mixing interface"""
    engineer = MixEngineer()

    print("""
╔══════════════════════════════════════════════════════════════╗
║              VLTRN MIX ENGINEER v1.0                        ║
║         Natural Language Audio Mixing & Mastering           ║
╠══════════════════════════════════════════════════════════════╣
║  Commands:                                                   ║
║    session <name>  - Start/resume a session                 ║
║    source <file>   - Set source audio file                  ║
║    [prompt]        - Natural language mixing command        ║
║    history         - Show session history                   ║
║    undo            - Revert to previous version             ║
║    export <name>   - Export final mix                       ║
║    help            - Show examples                          ║
║    quit            - Exit                                   ║
╚══════════════════════════════════════════════════════════════╝
    """)

    while True:
        try:
            cmd = input("\nmix> ").strip()

            if not cmd:
                continue

            if cmd.lower() in ('quit', 'exit', 'q'):
                break

            elif cmd.lower() == 'help':
                print(engineer._suggest_operations(""))

            elif cmd.lower().startswith('session '):
                name = cmd[8:].strip()
                engineer.start_session(name)

            elif cmd.lower().startswith('source '):
                path = cmd[7:].strip()
                engineer.set_source(path)

            elif cmd.lower() == 'history':
                engineer.show_history()

            elif cmd.lower() == 'undo':
                print(engineer.undo())

            elif cmd.lower().startswith('export '):
                name = cmd[7:].strip()
                if not name.endswith('.mp3'):
                    name += '.mp3'
                print(engineer.export(name))

            else:
                # Treat as mixing prompt
                if not engineer.session:
                    print("Start a session first: session <name>")
                elif not engineer.session.current_file:
                    print("Set a source file first: source <file>")
                else:
                    result = engineer.process_prompt(cmd)
                    print(result)

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")

    print("\nGoodbye!")


if __name__ == "__main__":
    interactive_mode()
