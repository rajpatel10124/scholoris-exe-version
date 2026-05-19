import os
import sys

# 1. Force all ML models and NLTK to load from 'offline_models' folder
# MUST happen BEFORE importing the app or logic modules
if getattr(sys, 'frozen', False):
    # Packaged executable directory
    exe_dir = os.path.dirname(sys.executable)
    models_dir = os.path.join(exe_dir, 'offline_models')
    if not os.path.exists(models_dir):
        models_dir = os.path.join(sys._MEIPASS, 'offline_models')
else:
    # Development directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, 'offline_models')

os.environ['HF_HOME'] = models_dir
os.environ['SENTENCE_TRANSFORMERS_HOME'] = models_dir

# ─────────────────────────────────────────────────────────────────────────────
# EXPLICIT IMPORTS FOR PYINSTALLER (Guarantees bundling of all ML & web dependencies)
# ─────────────────────────────────────────────────────────────────────────────
import nltk
import sentence_transformers
import sklearn
import sklearn.feature_extraction
import sklearn.metrics.pairwise
import sklearn.utils._typedefs
import rapidfuzz
import flask_socketio
import engineio.async_drivers.threading
import faiss
import pdfplumber
import vector_service
import webview
import PIL
import numpy
import xxhash
import deep_translator
import docx
import pypdf
import pytesseract

# Set NLTK data directory
nltk_data_dir = os.path.join(models_dir, 'nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.append(nltk_data_dir)

import threading
import webview
os.environ['SCHOLARIS_DESKTOP'] = '1'
from app import app, socketio

import time
import socket
import urllib.request
import traceback

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p

if __name__ == '__main__':
    port = get_free_port()
    server_url = f'http://127.0.0.1:{port}'

    def start_server():
        try:
            socketio.run(app, host='127.0.0.1', port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
        except Exception as e:
            with open("scholaris_crash_log.txt", "w") as f:
                f.write(traceback.format_exc())

    # 1. Start the Flask server
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 2. Wait up to 5 seconds for the server to be ready
    for _ in range(50):
        try:
            urllib.request.urlopen(server_url)
            break
        except Exception:
            time.sleep(0.1)

    # 3. Create the standalone desktop window (looks like a native app)
    window = webview.create_window(
        title='Scholaris - Plagiarism Detection Engine',
        url=server_url,
        width=1200,
        height=800,
        min_size=(800, 600)
    )

    # 4. Bind window close event to force exit process and release DB locks
    def on_closed():
        os._exit(0)
    window.events.closed += on_closed

    # 5. Launch desktop interface
    webview.start()
