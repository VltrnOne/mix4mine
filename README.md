# VLTRN SUNO Automation Suite

Complete automation framework for SUNO AI music production, mixing, and mastering.

## Tools

### 1. Mix Engineer (`mix_engineer.py`)
Natural language mixing and mastering interface.

```bash
python mix_engineer.py
```

**Commands:**
```
session <name>  - Start/resume a mixing session
source <file>   - Load audio file to mix
[prompt]        - Natural language mixing command
history         - Show changes history
undo            - Revert to previous version
export <name>   - Export final mix
```

**Example Prompts:**
- "make it brighter"
- "add more bass"
- "heavy compression"
- "add hall reverb"
- "master for streaming"
- "make it wider"

### 2. Quick Mixer (`quick_mixer.py`)
Fast interactive control of SUNO Studio.

```bash
python quick_mixer.py
```

**Commands:**
```
tracks        - List all tracks in project
solo <n>      - Solo track n
mute <n>      - Mute track n
select <n>    - Select track n
play          - Start playback
stop          - Stop playback
```

### 3. Stem Importer (`stem_importer.py`)
Import audio stems into SUNO Studio.

```bash
python stem_importer.py
```

**Commands:**
```
scan <folder>  - Scan folder for audio files
prepare        - Convert stems for SUNO
workflow       - Show import workflow
tracks         - List Studio tracks
add            - Add new track
```

### 4. SUNO Live (`suno_live.py`)
Direct Chrome control via AppleScript.

### 5. SUNO Remix (`suno_remix.py`)
Automate song remixing.

### 6. SUNO Studio (`suno_studio.py`)
Full studio control interface.

## Workflow

### Export & Mix Workflow:
1. Export stems from SUNO Studio
2. Load into Mix Engineer: `source /path/to/audio.wav`
3. Apply mixing with natural language prompts
4. Export final: `export final_mix.mp3`

### Stem Import Workflow:
1. Place stems in `stems/` folder
2. Run `python stem_importer.py`
3. Scan: `scan ./stems`
4. Prepare: `prepare`
5. Follow workflow instructions

## Requirements

- Python 3.8+
- FFmpeg: `brew install ffmpeg`
- Chrome browser with SUNO logged in
- macOS (for AppleScript automation)

## Directories

- `exports/` - Source audio files
- `processed/` - Processed output files
- `sessions/` - Mix session history
- `stems/` - Audio stems for import
- `downloads/` - Downloaded SUNO songs

## Quick Start

```bash
# Start mixing session
python mix_engineer.py

# In the mixer:
mix> session ask_of_me
mix> source /path/to/exported_track.wav
mix> make it brighter and add punch
mix> add some hall reverb
mix> master for streaming
mix> export Ask_Of_Me_Remastered.mp3
```
