"""
models.py — Pure Python Mock Database for Standalone Bulk Plagiarism Detection
=============================================================================
Zero SQLAlchemy, zero SQLite. Stores and retrieves records in pure JSON files.
Includes full dirty-tracking via in-memory identity map.
"""
import os
import sys
import json
from datetime import datetime

# Determine persistent data directory
def get_persistent_data_dir():
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        test_file = os.path.join(exe_dir, '.scholaris_write_test')
        try:
            with open(test_file, 'w') as f:
                f.write('check')
            os.remove(test_file)
            return exe_dir
        except Exception:
            return os.path.join(os.path.expanduser('~'), 'ScholarisData')
    else:
        return os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(get_persistent_data_dir(), 'scans_data')
os.makedirs(DATA_DIR, exist_ok=True)

class MockQuery:
    def __init__(self, model_class, items):
        self.model_class = model_class
        self.items = items

    def order_by(self, *args, **kwargs):
        # We sort by created_at desc by default
        self.items.sort(key=lambda x: getattr(x, 'created_at', datetime.min), reverse=True)
        return self

    def filter_by(self, **kwargs):
        filtered = []
        for item in self.items:
            match = True
            for k, v in kwargs.items():
                if getattr(item, k) != v:
                    match = False
                    break
            if match:
                filtered.append(item)
        return MockQuery(self.model_class, filtered)

    def all(self):
        return self.items

    def get(self, ident):
        for item in self.items:
            if getattr(item, 'id') == int(ident):
                return item
        return None

class BulkCheckRun:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', None)
        self.title = kwargs.get('title', 'Untitled Scan')
        self.total_files = kwargs.get('total_files', 0)
        self.processed_count = kwargs.get('processed_count', 0)
        self.status = kwargs.get('status', 'pending')
        self.threshold = kwargs.get('threshold', 40)
        self.accepted = kwargs.get('accepted', 0)
        self.rejected = kwargs.get('rejected', 0)
        self.manual_review = kwargs.get('manual_review', 0)
        self.elapsed_sec = kwargs.get('elapsed_sec', None)
        created_at = kwargs.get('created_at', None)
        if isinstance(created_at, str):
            try:
                self.created_at = datetime.fromisoformat(created_at)
            except ValueError:
                self.created_at = datetime.utcnow()
        else:
            self.created_at = created_at or datetime.utcnow()

    @property
    def results(self):
        # Dynamically load results to stay fresh
        return BulkCheckResult.query.filter_by(run_id=self.id).all()

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'total_files': self.total_files,
            'processed_count': self.processed_count,
            'status': self.status,
            'threshold': self.threshold,
            'accepted': self.accepted,
            'rejected': self.rejected,
            'manual_review': self.manual_review,
            'elapsed_sec': self.elapsed_sec,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class BulkCheckResult:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', None)
        self.run_id = kwargs.get('run_id', None)
        self.filename = kwargs.get('filename', '')
        self.verdict = kwargs.get('verdict', '')
        self.reason = kwargs.get('reason', '')
        self.peer_score = kwargs.get('peer_score', 0.0)
        self.external_score = kwargs.get('external_score', 0.0)
        self.ocr_confidence = kwargs.get('ocr_confidence', 0.0)
        self.is_digital = kwargs.get('is_digital', True)
        self.analysis_text = kwargs.get('analysis_text', '')
        self.peer_details = kwargs.get('peer_details', '')
        self.sentence_map = kwargs.get('sentence_map', '')

    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'filename': self.filename,
            'verdict': self.verdict,
            'reason': self.reason,
            'peer_score': self.peer_score,
            'external_score': self.external_score,
            'ocr_confidence': self.ocr_confidence,
            'is_digital': self.is_digital,
            'analysis_text': self.analysis_text,
            'peer_details': self.peer_details,
            'sentence_map': self.sentence_map
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

# Setup class-level queries
class ModelQueryDescriptor:
    def __get__(self, instance, owner):
        if owner == BulkCheckRun:
            return MockQuery(BulkCheckRun, _load_all_runs())
        elif owner == BulkCheckResult:
            return MockQuery(BulkCheckResult, _load_all_results())
        return None

BulkCheckRun.query = ModelQueryDescriptor()
BulkCheckResult.query = ModelQueryDescriptor()

# Global in-memory list of pending items that need to be committed
_pending_adds = []
_pending_deletes = []

# Global Identity Map
_loaded_runs = {}
_loaded_results = {}

def _load_all_runs():
    runs = []
    run_file = os.path.join(DATA_DIR, 'runs.json')
    if os.path.exists(run_file):
        try:
            with open(run_file, 'r') as f:
                data = json.load(f)
                for r in data:
                    rid = r['id']
                    if rid in _loaded_runs:
                        obj = _loaded_runs[rid]
                    else:
                        obj = BulkCheckRun.from_dict(r)
                        _loaded_runs[rid] = obj
                    runs.append(obj)
        except Exception as e:
            print(f"[MockDB] Error loading runs: {e}")

    # Merge with pending additions
    for x in _pending_adds:
        if isinstance(x, BulkCheckRun):
            if x.id not in _loaded_runs:
                _loaded_runs[x.id] = x
            if not any(r.id == x.id for r in runs):
                runs.append(x)

    # Filter out pending deletions
    runs = [r for r in runs if not any(d.id == r.id and isinstance(d, BulkCheckRun) for d in _pending_deletes)]
    return runs

def _load_all_results():
    results = []
    res_file = os.path.join(DATA_DIR, 'results.json')
    if os.path.exists(res_file):
        try:
            with open(res_file, 'r') as f:
                data = json.load(f)
                for r in data:
                    rid = r['id']
                    if rid in _loaded_results:
                        obj = _loaded_results[rid]
                    else:
                        obj = BulkCheckResult.from_dict(r)
                        _loaded_results[rid] = obj
                    results.append(obj)
        except Exception as e:
            print(f"[MockDB] Error loading results: {e}")

    # Merge with pending additions
    for x in _pending_adds:
        if isinstance(x, BulkCheckResult):
            if x.id not in _loaded_results:
                _loaded_results[x.id] = x
            if not any(r.id == x.id for r in results):
                results.append(x)

    # Filter out pending deletions
    results = [r for r in results if not any(d.id == r.id and isinstance(d, BulkCheckResult) for d in _pending_deletes)]
    return results

def _save_runs(runs):
    run_file = os.path.join(DATA_DIR, 'runs.json')
    try:
        with open(run_file, 'w') as f:
            json.dump([r.to_dict() for r in runs], f)
    except Exception as e:
        print(f"[MockDB] Error saving runs: {e}")

def _save_results(results):
    res_file = os.path.join(DATA_DIR, 'results.json')
    try:
        with open(res_file, 'w') as f:
            json.dump([r.to_dict() for r in results], f)
    except Exception as e:
        print(f"[MockDB] Error saving results: {e}")

class MockSession:
    def add(self, obj):
        global _pending_adds
        # Assign an auto-incrementing ID if none exists
        if obj.id is None:
            if isinstance(obj, BulkCheckRun):
                runs = _load_all_runs()
                obj.id = max([r.id for r in runs] + [0]) + 1
            elif isinstance(obj, BulkCheckResult):
                results = _load_all_results()
                obj.id = max([r.id for r in results] + [0]) + 1
        if obj not in _pending_adds:
            _pending_adds.append(obj)
        if obj in _pending_deletes:
            _pending_deletes.remove(obj)

    def delete(self, obj):
        global _pending_deletes, _pending_adds
        if obj not in _pending_deletes:
            _pending_deletes.append(obj)
        if obj in _pending_adds:
            _pending_adds.remove(obj)

    def commit(self):
        global _pending_adds, _pending_deletes
        
        # Apply additions to loaded maps
        for x in _pending_adds:
            if isinstance(x, BulkCheckRun):
                _loaded_runs[x.id] = x
            elif isinstance(x, BulkCheckResult):
                _loaded_results[x.id] = x
                
        # Apply deletions
        for x in _pending_deletes:
            if isinstance(x, BulkCheckRun):
                if x.id in _loaded_runs:
                    del _loaded_runs[x.id]
                # Cascade delete results
                to_del = [rid for rid, r in _loaded_results.items() if r.run_id == x.id]
                for rid in to_del:
                    del _loaded_results[rid]
            elif isinstance(x, BulkCheckResult):
                if x.id in _loaded_results:
                    del _loaded_results[x.id]
                    
        # Load all from disk first to merge everything
        all_runs = _load_all_runs()
        all_results = _load_all_results()
        
        # Now, save the exact contents of the identity maps back to disk
        _save_runs(all_runs)
        _save_results(all_results)
        
        _pending_adds.clear()
        _pending_deletes.clear()

    def rollback(self):
        global _pending_adds, _pending_deletes
        _pending_adds.clear()
        _pending_deletes.clear()

    def refresh(self, obj):
        pass

class MockDB:
    def __init__(self):
        self.session = MockSession()

    def init_app(self, app):
        pass

    def create_all(self):
        pass

    def get_or_404(self, model_class, ident):
        obj = model_class.query.get(ident)
        if not obj:
            from flask import abort
            abort(404)
        return obj

db = MockDB()