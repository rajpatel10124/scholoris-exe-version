import os
import urllib.request

# Define directories
css_dir = "static/css"
fonts_dir = "static/css/fonts"
js_dir = "static/js"

os.makedirs(css_dir, exist_ok=True)
os.makedirs(fonts_dir, exist_ok=True)
os.makedirs(js_dir, exist_ok=True)

assets = {
    # Bootstrap CSS
    "static/css/bootstrap.min.css": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
    # Bootstrap JS
    "static/js/bootstrap.bundle.min.js": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js",
    # Bootstrap Icons CSS
    "static/css/bootstrap-icons.css": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css",
    # Bootstrap Icons Font WOFF2
    "static/css/fonts/bootstrap-icons.woff2": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/fonts/bootstrap-icons.woff2",
    # Bootstrap Icons Font WOFF
    "static/css/fonts/bootstrap-icons.woff": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/fonts/bootstrap-icons.woff",
    # Socket.IO JS Client
    "static/js/socket.io.js": "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.4/socket.io.js",
}

print("[Offline Assets] Starting download of required assets...")
for path, url in assets.items():
    try:
        print(f"Downloading: {url} -> {path}")
        # Add User-Agent header to avoid blockages
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            with open(path, "wb") as f:
                f.write(response.read())
        print(f"  Saved successfully!")
    except Exception as e:
        print(f"  Error downloading {path}: {e}")

print("[Offline Assets] Downloads complete!")
