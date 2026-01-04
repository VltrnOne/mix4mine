#!/usr/bin/env python3
"""
VLTRN SUNO Web Interface
Flask-based dashboard for music production automation
"""
import os
import json
import time
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# Import our automation modules
from mix_engineer import MixEngineer, AudioProcessor, PromptParser
from quick_mixer import chrome_js, chrome_url, get_tracks, solo_track, mute_track, play, stop

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'vltrn-suno-2024'
app.config['UPLOAD_FOLDER'] = Path(__file__).parent / 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

socketio = SocketIO(app, cors_allowed_origins="*")

# Create required directories
for d in ['uploads', 'exports', 'processed', 'sessions', 'stems']:
    (Path(__file__).parent / d).mkdir(exist_ok=True)

# Global state
engineer = MixEngineer()
current_session = None


# ============== API Routes ==============

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get current system status"""
    try:
        url = chrome_url()
        tracks = get_tracks() if 'suno.com' in url else []

        session_info = None
        if engineer.session:
            session_info = {
                'name': engineer.session.name,
                'version': engineer.session.version,
                'current_file': engineer.session.current_file,
                'history_count': len(engineer.session.history)
            }

        return jsonify({
            'status': 'connected',
            'chrome_url': url,
            'in_studio': 'studio' in url,
            'tracks': tracks,
            'session': session_info,
            'tools': AudioProcessor.check_tools()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/api/session', methods=['POST'])
def create_session():
    """Create or resume a mixing session"""
    data = request.json
    name = data.get('name', f'session_{int(time.time())}')

    engineer.start_session(name)

    return jsonify({
        'success': True,
        'session': {
            'name': engineer.session.name,
            'version': engineer.session.version,
            'current_file': engineer.session.current_file
        }
    })


@app.route('/api/source', methods=['POST'])
def set_source():
    """Set source audio file"""
    data = request.json
    file_path = data.get('path')

    if not file_path or not os.path.exists(file_path):
        return jsonify({'success': False, 'error': 'File not found'})

    if not engineer.session:
        engineer.start_session(f'session_{int(time.time())}')

    success = engineer.set_source(file_path)

    # Analyze audio
    info = AudioProcessor.analyze_audio(file_path)

    return jsonify({
        'success': success,
        'audio_info': info
    })


@app.route('/api/mix', methods=['POST'])
def process_mix():
    """Process a mixing prompt"""
    data = request.json
    prompt = data.get('prompt', '')

    if not engineer.session:
        return jsonify({'success': False, 'error': 'No session active'})

    if not engineer.session.current_file:
        return jsonify({'success': False, 'error': 'No source file set'})

    # Parse and process
    result = engineer.process_prompt(prompt)

    # Emit update via WebSocket
    socketio.emit('mix_update', {
        'version': engineer.session.version,
        'result': result,
        'current_file': engineer.session.current_file
    })

    return jsonify({
        'success': True,
        'result': result,
        'version': engineer.session.version
    })


@app.route('/api/undo', methods=['POST'])
def undo_action():
    """Undo last action"""
    result = engineer.undo()
    return jsonify({
        'success': 'Reverted' in result,
        'message': result,
        'version': engineer.session.version if engineer.session else 0
    })


@app.route('/api/export', methods=['POST'])
def export_mix():
    """Export final mix"""
    data = request.json
    filename = data.get('filename', f'mix_{int(time.time())}.mp3')

    if not filename.endswith('.mp3'):
        filename += '.mp3'

    result = engineer.export(filename)

    return jsonify({
        'success': 'Exported' in result,
        'message': result,
        'filename': filename
    })


@app.route('/api/history')
def get_history():
    """Get session history"""
    if not engineer.session:
        return jsonify({'history': []})

    return jsonify({
        'history': engineer.session.history,
        'version': engineer.session.version
    })


# ============== Studio Control Routes ==============

@app.route('/api/studio/tracks')
def studio_tracks():
    """Get SUNO Studio tracks"""
    tracks = get_tracks()
    return jsonify({'tracks': tracks})


@app.route('/api/studio/solo/<int:track_num>', methods=['POST'])
def studio_solo(track_num):
    """Solo a track"""
    success = solo_track(track_num)
    return jsonify({'success': success, 'track': track_num, 'action': 'solo'})


@app.route('/api/studio/mute/<int:track_num>', methods=['POST'])
def studio_mute(track_num):
    """Mute a track"""
    success = mute_track(track_num)
    return jsonify({'success': success, 'track': track_num, 'action': 'mute'})


@app.route('/api/studio/play', methods=['POST'])
def studio_play():
    """Start playback"""
    success = play()
    return jsonify({'success': success, 'action': 'play'})


@app.route('/api/studio/stop', methods=['POST'])
def studio_stop():
    """Stop playback"""
    success = stop()
    return jsonify({'success': success, 'action': 'stop'})


@app.route('/api/studio/navigate', methods=['POST'])
def studio_navigate():
    """Navigate to SUNO Studio"""
    subprocess.run([
        "osascript", "-e",
        'tell application "Google Chrome" to set URL of active tab of front window to "https://suno.com/studio"'
    ], capture_output=True)
    time.sleep(2)
    return jsonify({'success': True})


# ============== File Upload Routes ==============

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload audio file"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})

    filename = secure_filename(file.filename)
    filepath = app.config['UPLOAD_FOLDER'] / filename
    file.save(str(filepath))

    # Analyze the uploaded file
    info = AudioProcessor.analyze_audio(str(filepath))

    return jsonify({
        'success': True,
        'path': str(filepath),
        'filename': filename,
        'info': info
    })


@app.route('/api/files')
def list_files():
    """List available audio files"""
    files = []

    for folder in ['uploads', 'exports', 'processed', 'stems']:
        folder_path = Path(__file__).parent / folder
        if folder_path.exists():
            for f in folder_path.glob('*'):
                if f.suffix.lower() in ['.wav', '.mp3', '.flac', '.m4a', '.aiff']:
                    files.append({
                        'name': f.name,
                        'path': str(f),
                        'folder': folder,
                        'size': f.stat().st_size
                    })

    return jsonify({'files': files})


# ============== EQ Presets ==============

@app.route('/api/presets')
def get_presets():
    """Get mixing presets"""
    presets = {
        'vocal_presence': {
            'name': 'Vocal Presence',
            'prompt': 'boost mids slightly, add clarity, light compression'
        },
        'warm_vintage': {
            'name': 'Warm Vintage',
            'prompt': 'make it warmer, add subtle saturation, roll off highs'
        },
        'modern_pop': {
            'name': 'Modern Pop',
            'prompt': 'bright and punchy, tight bass, wide stereo'
        },
        'lo_fi': {
            'name': 'Lo-Fi',
            'prompt': 'cut highs, add warmth, subtle room reverb'
        },
        'radio_ready': {
            'name': 'Radio Ready',
            'prompt': 'master for streaming, loud and clear'
        },
        'cinematic': {
            'name': 'Cinematic',
            'prompt': 'big hall reverb, wide stereo, dramatic compression'
        }
    }
    return jsonify({'presets': presets})


# ============== WebSocket Events ==============

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('connected', {'status': 'ok'})


@socketio.on('refresh_status')
def handle_refresh():
    """Refresh and emit status"""
    try:
        url = chrome_url()
        tracks = get_tracks() if 'suno.com' in url else []

        emit('status_update', {
            'chrome_url': url,
            'tracks': tracks,
            'session': {
                'name': engineer.session.name if engineer.session else None,
                'version': engineer.session.version if engineer.session else 0
            }
        })
    except Exception as e:
        emit('error', {'message': str(e)})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("VLTRN SUNO Web Interface")
    print("="*60)
    print("\nStarting server at http://localhost:5050")
    print("Press Ctrl+C to stop\n")

    socketio.run(app, host='0.0.0.0', port=5050, debug=True, allow_unsafe_werkzeug=True)
