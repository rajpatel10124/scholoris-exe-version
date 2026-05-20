import os
import sys
import traceback

# 1. Trapped Imports Wrapper for Visual Diagnostics on Target PCs
try:
    # Force all ML models and NLTK to load from 'offline_models' folder
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

    # EXPLICIT DEPENDENCY LOADING
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
    os.environ['SCHOLARIS_DESKTOP'] = '1'
    from app import app, socketio

except Exception as e:
    # Capture error immediately
    err_msg = traceback.format_exc()
    # Write detailed log file to the executable directory
    try:
        log_path = "scholaris_startup_error.txt"
        if getattr(sys, 'frozen', False):
            log_path = os.path.join(os.path.dirname(sys.executable), "scholaris_startup_error.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(err_msg)
    except Exception:
        pass

    # Display a clear, user-friendly popup window so the user/HOD isn't left in the dark
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        
        # Determine actionable advice based on the error content
        advice = "Common fixes:\n1. Install Microsoft Visual C++ Redistributable (required for FAISS/NumPy).\n2. Install Microsoft WebView2 Runtime (required for the desktop window interface)."
        if "webview" in err_msg.lower():
            advice = "Fix: Please download and install the Microsoft WebView2 Runtime from: https://developer.microsoft.com/en-us/microsoft-edge/webview2/"
        elif "faiss" in err_msg.lower() or "numpy" in err_msg.lower() or "dll load failed" in err_msg.lower():
            advice = "Fix: Please download and install the Microsoft Visual C++ Redistributable (x64) from: https://aka.ms/vs/17/release/vc_redist.x64.exe"
            
        messagebox.showerror(
            "Scholaris - Startup Error",
            f"An error occurred while launching Scholaris on this PC:\n\n{e}\n\n{advice}\n\n"
            f"A detailed crash report has been saved to:\n'{log_path}'"
        )
    except Exception:
        pass
    sys.exit(1)

import time
import socket
import urllib.request

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
