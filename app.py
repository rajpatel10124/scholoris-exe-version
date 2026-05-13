"""
app.py — Standalone Bulk Plagiarism Detection System
=====================================================
No users, no login, no courses, no assignments.
Upload files → Run plagiarism scan → View results with threshold filter.
Like iLovePDF but for plagiarism detection.
"""
import eventlet
eventlet.monkey_patch()

import json
import uuid
import datetime
import os
import time
import tempfile
import traceback
import threading
import zipfile
import shutil
import csv
import io
import re

from flask import (Flask, render_template, redirect, url_for, request,
                   flash, jsonify, abort, Response, current_app)
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from concurrent.futures import ThreadPoolExecutor, as_completed

from models import db, BulkCheckRun, BulkCheckResult
import logic


# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
# Database path: Move to home directory to avoid NTFS permission issues on external drives
if os.getenv('DATABASE_URL'):
    # In Cloud, use a persistent SQLite file on the EFS mount to avoid RDS complexity
    # We store it in static/uploads which is mounted to EFS
    db_path = os.path.join(app.root_path, 'static', 'uploads', 'scholaris.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
else:
    # Local development
    home_dir = os.path.expanduser("~")
    scholaris_dir = os.path.join(home_dir, ".scholaris_data")
    if not os.path.exists(scholaris_dir):
        os.makedirs(scholaris_dir)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(scholaris_dir, "scholaris.db")}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1 GB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Database
db.init_app(app)

# Jinja filters
@app.template_filter('fromjson')
def fromjson_filter(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# MODEL WARMUP
# ─────────────────────────────────────────────────────────────────────────────
@app.before_request
def warmup_once():
    """Trigger model warmup on the first request if not already done."""
    if not hasattr(app, '_models_warmed'):
        app._models_warmed = True
        print("[SCHOLARIS] Starting background model warmup...")
        threading.Thread(target=logic.warmup_models, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# DEPENDENCY CHECK
# ─────────────────────────────────────────────────────────────────────────────
def check_dependencies():
    issues = []
    for pkg, pip_name in [
        ('faiss',                'faiss-cpu'),
        ('sentence_transformers','sentence-transformers'),
        ('cv2',                  'opencv-python'),
        ('pytesseract',          'pytesseract'),
        ('PyPDF2',               'PyPDF2'),
        ('pdf2image',            'pdf2image'),
        ('docx',                 'python-docx'),
        ('nltk',                 'nltk'),
        ('rapidfuzz',            'rapidfuzz'),
    ]:
        try:
            __import__(pkg)
        except (ImportError, OSError, Exception):
            issues.append(f"  pip install {pip_name}")
    if issues:
        print("\n[SCHOLARIS] WARNING — some plagiarism dependencies missing:")
        for i in issues:
            print(i)
        print()
    else:
        print("[SCHOLARIS] OK - All plagiarism dependencies found.")
    return len(issues) == 0


# =============================================================================
# LANDING PAGE
# =============================================================================
@app.route('/')
def index():
    """Landing page — hero + upload CTA."""
    return render_template('index.html')


@app.route('/health')
def health():
    """Health check for Load Balancer."""
    return jsonify(status="ok"), 200


# =============================================================================
# HISTORY — list all past scan runs
# =============================================================================
@app.route('/history')
def history():
    runs = BulkCheckRun.query.order_by(BulkCheckRun.created_at.desc()).all()
    return render_template('history.html', runs=runs)


# =============================================================================
# NEW SCAN — upload form
# =============================================================================
@app.route('/scan/new', methods=['GET', 'POST'])
def new_scan():
    if request.method == 'GET':
        return render_template('new_scan.html')

    # POST — process upload and start background scan
    title = request.form.get('title', '').strip() or 'Untitled Scan'
    threshold = max(0, min(100, int(request.form.get('threshold', 40))))

    upload_zip = request.files.get('zipfile')
    upload_files = request.files.getlist('files')

    has_zip = upload_zip and upload_zip.filename
    has_files = upload_files and upload_files[0].filename

    if not has_zip and not has_files:
        flash('Please upload a ZIP file or select individual files.', 'danger')
        return redirect(url_for('new_scan'))

    temp_dir = tempfile.mkdtemp(prefix='bulk_scan_')
    try:
        if has_zip:
            upload_zip.save(os.path.join(temp_dir, secure_filename(upload_zip.filename)))
        for fs in upload_files:
            if fs and fs.filename:
                fs.save(os.path.join(temp_dir, secure_filename(fs.filename)))

        bulk_run = BulkCheckRun(
            title=title,
            threshold=threshold,
            total_files=0,
            processed_count=0,
            status='pending',
        )
        db.session.add(bulk_run)
        db.session.commit()

        # Start background scan
        threading.Thread(
            target=run_bulk_check_task,
            args=(current_app._get_current_object(), bulk_run.id, temp_dir, threshold),
            daemon=True,
        ).start()

        return redirect(url_for('scan_status', run_id=bulk_run.id))

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        flash(f'Upload error: {e}', 'danger')
        return redirect(url_for('new_scan'))


# =============================================================================
# SCAN STATUS — real-time progress
# =============================================================================
@app.route('/scan/<int:run_id>/status')
def scan_status(run_id):
    run = db.get_or_404(BulkCheckRun, run_id)
    db.session.refresh(run)
    if run.status == 'completed':
        return redirect(url_for('scan_results', run_id=run.id))
    return render_template('bulk_status.html', run=run)


# =============================================================================
# SCAN RESULTS — view results with threshold filter
# =============================================================================
@app.route('/scan/<int:run_id>/results')
def scan_results(run_id):
    run = db.get_or_404(BulkCheckRun, run_id)
    return render_template('results.html', run=run)


# =============================================================================
# HEATMAP — only for digital (computerized) files
# =============================================================================
@app.route('/scan/<int:run_id>/result/<int:result_id>/heatmap')
def result_heatmap(run_id, result_id):
    result = db.get_or_404(BulkCheckResult, result_id)
    if result.run_id != run_id:
        abort(404)

    # Gate: only show heatmap for digital (computerized) files
    if not result.is_digital:
        flash('Heatmap is only available for computerized (digital text) files, not OCR-extracted documents.', 'warning')
        return redirect(url_for('scan_results', run_id=run_id))

    heatmap_data = json.loads(result.sentence_map or '[]')
    return render_template('heatmap_view.html',
                           title=f"Heatmap: {result.filename}",
                           result=result,
                           run=result.run,
                           heatmap=heatmap_data)


# =============================================================================
# DOWNLOAD CSV
# =============================================================================
@app.route('/scan/<int:run_id>/csv')
def download_csv(run_id):
    run = db.get_or_404(BulkCheckRun, run_id)
    db_results = BulkCheckResult.query.filter_by(run_id=run_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Filename', 'Verdict', 'Reason', 'Peer Score (%)',
                     'External Score (%)', 'OCR Confidence (%)', 'Is Digital', 'Analysis Text'])

    for r in db_results:
        writer.writerow([
            r.filename, r.verdict, r.reason,
            r.peer_score, r.external_score, r.ocr_confidence,
            'Yes' if r.is_digital else 'No',
            (r.analysis_text or '').replace('\n', ' | '),
        ])

    output.seek(0)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=scan_{run.id}_{ts}.csv'},
    )


# =============================================================================
# DOWNLOAD EXCEL
# =============================================================================
@app.route('/scan/<int:run_id>/excel')
def download_excel(run_id):
    run = db.get_or_404(BulkCheckRun, run_id)
    db_results = BulkCheckResult.query.filter_by(run_id=run_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Filename', 'Verdict', 'Reason', 'Peer Score (%)',
                     'External Score (%)', 'OCR Confidence (%)', 'Is Digital', 'Analysis Text'])

    for r in db_results:
        writer.writerow([
            r.filename, r.verdict, r.reason,
            r.peer_score, r.external_score, r.ocr_confidence,
            'Yes' if r.is_digital else 'No',
            (r.analysis_text or '').replace('\n', ' | '),
        ])

    output.seek(0)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return Response(
        output.getvalue(),
        mimetype='application/vnd.ms-excel',
        headers={'Content-Disposition': f'attachment; filename=scan_{run.id}_{ts}.xlsx'},
    )


# =============================================================================
# DELETE SCAN RUN
# =============================================================================
@app.route('/scan/<int:run_id>/delete', methods=['POST'])
def delete_scan(run_id):
    run = db.get_or_404(BulkCheckRun, run_id)
    db.session.delete(run)
    db.session.commit()
    flash('Scan deleted.', 'success')
    return redirect(url_for('history'))


# =============================================================================
# BACKGROUND SCAN TASK
# =============================================================================
def run_bulk_check_task(app, run_id, temp_dir, threshold):
    """Background task to run bulk plagiarism check."""
    with app.app_context():
        t0 = time.time()
        try:
            bulk_run = BulkCheckRun.query.get(run_id)
            if not bulk_run:
                return
            bulk_run.status = 'processing'
            db.session.commit()

            # Helper to emit progress
            def push_progress(pct, msg):
                socketio.emit('bulk_progress', {
                    'run_id': run_id,
                    'percentage': pct,
                    'message': msg,
                    'processed': bulk_run.processed_count,
                    'total': bulk_run.total_files,
                }, room=f"bulk_{run_id}")

            push_progress(5, "Initializing analysis engine...")

            # Allowed file types — default for standalone tool
            allowed_types = ['pdf', 'docx', 'doc', 'txt', 'jpg', 'jpeg', 'png', 'tiff', 'tif', 'bmp', 'webp']

            # --- Phase 0: Extract ZIPs ---
            for root, _, fs in os.walk(temp_dir):
                for f in fs:
                    if f.lower().endswith('.zip'):
                        zp = os.path.join(root, f)
                        try:
                            with zipfile.ZipFile(zp, 'r') as z:
                                for member in z.namelist():
                                    if member.endswith('/'):
                                        continue
                                    dest = os.path.normpath(os.path.join(temp_dir, member))
                                    if not dest.startswith(temp_dir):
                                        continue
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    with z.open(member) as src, open(dest, 'wb') as dst:
                                        dst.write(src.read())
                            os.remove(zp)
                        except Exception as e:
                            print(f"[Bulk-BG] ZIP Error: {e}", flush=True)

            push_progress(10, "Scanning files...")

            # Collect files
            filtered_paths = []
            for root, _, files in os.walk(temp_dir):
                for f in files:
                    p = os.path.join(root, f)
                    ext = f.rsplit('.', 1)[-1].lower() if '.' in f else ''
                    if ext in allowed_types:
                        filtered_paths.append(p)

            bulk_run.total_files = len(filtered_paths)
            db.session.commit()
            print(f"[Bulk-BG] Task #{run_id} starting for {len(filtered_paths)} files...", flush=True)
            push_progress(15, f"Found {len(filtered_paths)} files. Starting text extraction...")

            if not filtered_paths:
                bulk_run.status = 'completed'
                db.session.commit()
                push_progress(100, "No files to process.")
                return

            # --- Phase 1: Text extraction ---
            extracted = {}
            def _extract_one(p):
                return p, logic.extract_text_bulk(p)

            _workers = min(2, len(filtered_paths))
            with ThreadPoolExecutor(max_workers=_workers) as pool:
                futures = {pool.submit(_extract_one, p): p for p in filtered_paths}
                for fut in as_completed(futures):
                    p_current = futures[fut]
                    try:
                        path, result = fut.result()
                        extracted[path] = result
                        bulk_run.processed_count += 1
                        db.session.commit()
                    except Exception as e:
                        print(f"[Bulk-BG] Extraction error: {e}", flush=True)
                        extracted[p_current] = ("", None, None, 0.0)
                        bulk_run.processed_count += 1
                        db.session.commit()

            push_progress(40, "Text extraction complete. Building comparison index...")

            # --- Phase 2: Build submission list ---
            local_submissions = []
            for p in filtered_paths:
                txt, _, fhash, conf = extracted.get(p, ("", None, None, 0.0))
                
                ext = p.lower().rsplit('.', 1)[-1] if '.' in p else ''
                is_img = ext in ['jpg', 'jpeg', 'png', 'tiff', 'tif', 'bmp', 'webp']
                is_txt_doc = ext in ['txt', 'docx', 'doc']
                
                if is_img:
                    is_digital = False
                elif is_txt_doc:
                    is_digital = True
                else:
                    # It's a PDF. Digital PDFs return conf=100.0 explicitly.
                    is_digital = (conf or 0) > 99.0

                local_submissions.append({
                    'text': txt,
                    'author_username': os.path.basename(p),
                    'submission_id': None,
                    'filename': os.path.basename(p),
                    'original_filename': os.path.basename(p),
                    '_unique_id': f'local_{p}',
                    '_path': p,
                    '_file_hash': fhash,
                    '_ocr_confidence': conf,
                    '_is_digital': is_digital,
                })

            all_submissions = local_submissions

            # --- Phase 3: Pre-calculate embeddings ---
            print(f"\n[Bulk-BG] PRE-CALCULATING METADATA FOR {len(all_submissions)} DOCUMENTS...", flush=True)
            precomputed_embeddings = {}
            bulk_hashes = set()
            bulk_authors = {}

            # Semantic Embeddings
            if hasattr(logic, '_HAS_ST') and logic._HAS_ST:
                try:
                    st_model = logic._get_st_model()
                    unique_texts = []
                    seen = set()
                    for s in all_submissions:
                        text = s.get('text')
                        if not text:
                            continue
                        cl = logic.clean_text(text)
                        if cl and cl not in seen:
                            seen.add(cl)
                            unique_texts.append(cl)
                    if unique_texts:
                        print(f"  ↳ Generating semantic embeddings for {len(unique_texts)} docs...", flush=True)
                        import numpy as np
                        embeddings = st_model.encode(unique_texts, batch_size=16, convert_to_numpy=True).astype("float32")
                        if hasattr(logic, '_HAS_FAISS') and logic._HAS_FAISS:
                            import faiss as _faiss
                            _faiss.normalize_L2(embeddings)
                        else:
                            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                            embeddings = embeddings / np.maximum(norms, 1e-10)
                        precomputed_embeddings = {t: emb for t, emb in zip(unique_texts, embeddings)}
                except Exception as e:
                    print(f"  ↳ [ERROR] Embedding: {e}", flush=True)

            # Structural Fingerprints (Winnowing)
            print(f"  ↳ Generating structural fingerprints...", flush=True)
            for s in all_submissions:
                txt = s.get('text')
                if not txt:
                    continue
                fp = logic.get_winnowing_fingerprint(txt)
                auth = s.get('author_username', 'Document')
                for h in fp:
                    bulk_hashes.add(h)
                    if h not in bulk_authors:
                        bulk_authors[h] = auth

            precomputed_embeddings['_bulk_hashes'] = bulk_hashes
            precomputed_embeddings['_bulk_authors'] = bulk_authors

            # ── Corpus-level TF-IDF ───────────────────────────────────────────
            # Fit ONE vectorizer on ALL documents so that terms appearing in
            # most submissions (e.g. "router rip", "objective", "experiment",
            # "routing table") get near-zero IDF weight. Only genuinely unique
            # copied phrases will carry meaningful TF-IDF scores.
            # min_df=2: a term must appear in ≥2 docs to be counted at all;
            # terms appearing in every doc automatically get very low IDF.
            print(f"  ↳ Building corpus TF-IDF to suppress common lab terms...", flush=True)
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                corpus_texts = [
                    logic.clean_text(s.get('text', ''))
                    for s in all_submissions
                    if s.get('text')
                ]
                if len(corpus_texts) >= 3:
                    corpus_tfidf = TfidfVectorizer(
                        ngram_range=(1, 2),
                        max_features=20000,
                        sublinear_tf=True,
                        min_df=2,   # must appear in ≥2 docs to be weighted
                    )
                    corpus_tfidf.fit(corpus_texts)
                    logic.set_corpus_tfidf(corpus_tfidf)
                    print(f"  ↳ Corpus TF-IDF ready ({len(corpus_texts)} docs, vocab size suppressed for common terms).", flush=True)
            except Exception as _e:
                print(f"  ↳ Corpus TF-IDF skipped: {_e}", flush=True)

            push_progress(70, "Running AI semantic analysis...")

            # Pre-load AI model
            try:
                logic._get_ai_detect_model()
            except Exception:
                pass

            # --- Phase 4: Plagiarism Checks ---
            results = []
            total_local = len(local_submissions)

            print(f"\n[Bulk-BG] ANALYZING {total_local} FILES...", flush=True)
            for i, lsub in enumerate(local_submissions):
                try:
                    _path = lsub['_path']
                    _txt = lsub['text']
                    _hash = lsub['_file_hash']
                    _conf = lsub['_ocr_confidence']
                    _uid = lsub['_unique_id']
                    _is_digital = lsub['_is_digital']
                    f_name = os.path.basename(_path)
                    print(f"  [{i+1}/{total_local}] Analyzing: {f_name}...", flush=True)

                    _others = [s for s in all_submissions if s['_unique_id'] != _uid]
                    _rep = logic.bulk_run_plagiarism_check_preextracted(
                        text=_txt, file_hash=_hash,
                        ocr_confidence=_conf or 100.0,
                        other_submissions=_others,
                        threshold=threshold,
                        precomputed_embeddings=precomputed_embeddings,
                        filename=f_name,
                    )

                    # Exact hash check
                    if _hash:
                        for s in _others:
                            oh = s.get('_file_hash') or s.get('content_hash')
                            if oh and oh == _hash:
                                _rep['verdict'] = 'rejected'
                                _rep['reason'] = f"Exact duplicate of {s['author_username']}"
                                _rep['peer_score'] = 1.0
                                _rep['is_exact_duplicate'] = True
                                break

                    # Skip heatmap for OCR files
                    heatmap_data = _rep.get('heatmap', []) if _is_digital else []

                    results.append({
                        'id': str(uuid.uuid4())[:8],
                        'filename': os.path.relpath(_path, temp_dir),
                        'verdict': _rep.get('verdict', 'unknown'),
                        'reason': _rep.get('reason', ''),
                        'peer_score': round(_rep.get('peer_score', 0.0) * 100, 1),
                        'external_score': _rep.get('external_score', 0.0),
                        'ocr_confidence': _rep.get('ocr_confidence', 0.0),
                        'is_digital': _is_digital,
                        'analysis_text': _rep.get('analysis_text', ''),
                        'peer_details': _rep.get('peer_details', {}),
                        'heatmap': heatmap_data,
                    })
                except Exception as e:
                    results.append({
                        'filename': os.path.basename(lsub.get('_path', '')),
                        'verdict': 'error', 'reason': str(e),
                        'peer_score': 0.0, 'external_score': 0.0,
                        'ocr_confidence': 0.0, 'is_digital': False,
                        'analysis_text': '', 'peer_details': {},
                        'heatmap': [],
                    })

            # --- Phase 5: Save results ---
            elapsed = round(time.time() - t0, 1)
            for row in results:
                db.session.add(BulkCheckResult(
                    run_id=run_id,
                    filename=row['filename'],
                    verdict=row['verdict'],
                    reason=str(row['reason'])[:255],
                    peer_score=row['peer_score'],
                    external_score=row['external_score'],
                    ocr_confidence=row['ocr_confidence'],
                    is_digital=row['is_digital'],
                    analysis_text=row.get('analysis_text', ''),
                    peer_details=json.dumps(row['peer_details']),
                    sentence_map=json.dumps(row['heatmap']),
                ))

            bulk_run.status = 'completed'
            bulk_run.elapsed_sec = elapsed
            bulk_run.accepted = sum(1 for r in results if r['verdict'] == 'accepted')
            bulk_run.rejected = sum(1 for r in results if r['verdict'] == 'rejected')
            bulk_run.manual_review = sum(1 for r in results if r['verdict'] in ('manual_review', 'error'))
            db.session.commit()
            push_progress(100, "Analysis complete!")
            print(f"[Bulk-BG] Task #{run_id} finished in {elapsed}s", flush=True)

        except Exception as e:
            db.session.rollback()
            try:
                br = BulkCheckRun.query.get(run_id)
                if br:
                    br.status = 'error'
                    db.session.commit()
            except Exception:
                pass
            print(f"[Bulk-BG] Task #{run_id} failed: {e}", flush=True)
            traceback.print_exc()
        finally:
            try:
                logic._offload_ai_model()
            except Exception:
                pass
            try:
                logic.set_corpus_tfidf(None)  # reset for next scan
            except Exception:
                pass
            shutil.rmtree(temp_dir, ignore_errors=True)


# =============================================================================
# ENTRY POINT
# =============================================================================
# Background Initialization: Ensures we pass health checks immediately while loading models/DB
def init_db_and_models(app_obj):
    with app_obj.app_context():
        max_retries = 20
        retry_delay = 5
        for i in range(max_retries):
            try:
                if "postgresql" in app_obj.config['SQLALCHEMY_DATABASE_URI']:
                    try:
                        from sqlalchemy import text
                        db.session.execute(text("GRANT ALL ON SCHEMA public TO scholaris_admin"))
                        db.session.commit()
                    except Exception:
                        pass
                db.create_all()
                # Raw SQL Fallback
                if "postgresql" in app_obj.config['SQLALCHEMY_DATABASE_URI']:
                    from sqlalchemy import text
                    db.session.execute(text("""
                        CREATE TABLE IF NOT EXISTS bulk_check_run (id SERIAL PRIMARY KEY, title VARCHAR(255), total_files INTEGER, processed_count INTEGER, status VARCHAR(50), threshold INTEGER, accepted INTEGER, rejected INTEGER, manual_review INTEGER, elapsed_sec FLOAT, created_at TIMESTAMP WITHOUT TIME ZONE);
                        CREATE TABLE IF NOT EXISTS bulk_check_result (id SERIAL PRIMARY KEY, run_id INTEGER REFERENCES bulk_check_run(id) ON DELETE CASCADE, filename VARCHAR(255), verdict VARCHAR(50), reason VARCHAR(255), peer_score FLOAT, external_score FLOAT, ocr_confidence FLOAT, is_digital BOOLEAN, analysis_text TEXT, peer_details TEXT, sentence_map TEXT, created_at TIMESTAMP WITHOUT TIME ZONE);
                    """))
                    db.session.commit()
                print("[SCHOLARIS] Database schema verified/created.")
                break
            except Exception as e:
                print(f"[SCHOLARIS] DB connection retry {i+1}/{max_retries}: {e}")
                time.sleep(retry_delay)
        
        # Also warmup models in this background thread
        try:
            logic.warmup_models()
        except Exception as e:
            print(f"[SCHOLARIS] Background warmup failed: {e}")

# Start background initialization immediately
threading.Thread(target=init_db_and_models, args=(app,), daemon=True).start()

if __name__ == '__main__':
    with app.app_context():
        # --- AUTO CLEANUP FOR REFACTOR ---
        old_db = os.path.join(app.root_path, 'scholaris.db')
        old_db_instance = os.path.join(app.root_path, 'instance', 'scholaris.db')
        for db_file in [old_db, old_db_instance]:
            if os.path.exists(db_file):
                try:
                    os.remove(db_file)
                    print(f"[Cleanup] Deleted old database schema -> {db_file}")
                except Exception as e:
                    pass

        # Delete unused templates
        templates_dir = os.path.join(app.root_path, 'templates')
        kept = {'base.html', 'index.html', 'new_scan.html', 'history.html', 'results.html', 'bulk_status.html', 'heatmap_view.html'}
        if os.path.exists(templates_dir):
            for filename in os.listdir(templates_dir):
                if filename.endswith(".html") and filename not in kept:
                    try:
                        os.remove(os.path.join(templates_dir, filename))
                        print(f"[Cleanup] Deleted unused template -> {filename}")
                    except Exception as e:
                        pass

        check_dependencies()
        try:
            logic.warmup_models()
        except Exception as e:
            print(f"[WARN] Model warmup failed (will load on first use): {e}")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)