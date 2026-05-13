import os
import sys

# 1. Force all ML models and NLTK to load from the bundled 'offline_models' folder
# MUST happen BEFORE importing the app or logic modules
if getattr(sys, 'frozen', False):
    # If running as PyInstaller .exe bundle
    base_dir = sys._MEIPASS
else:
    # If running normally via python
    base_dir = os.path.dirname(os.path.abspath(__file__))

models_dir = os.path.join(base_dir, 'offline_models')
os.environ['HF_HOME'] = models_dir
os.environ['SENTENCE_TRANSFORMERS_HOME'] = models_dir

import nltk
nltk_data_dir = os.path.join(models_dir, 'nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.append(nltk_data_dir)

import threading
import webview
from app import app, socketio

def start_server():
    # Run the Flask-SocketIO server silently in background
    socketio.run(app, host='127.0.0.1', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    # 1. Start the Flask server
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 2. Create the standalone desktop window (looks like a native app)
    window = webview.create_window(
        title='Scholaris - Plagiarism Detection Engine',
        url='http://127.0.0.1:5000',
        width=1200,
        height=800,
        min_size=(800, 600)
    )

    # 3. Launch desktop interface
    webview.start()
