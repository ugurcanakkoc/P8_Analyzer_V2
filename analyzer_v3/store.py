"""Local versioned annotations. Any edit invalidates all baseline claim approvals."""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import sqlite3
import uuid

from .models import validate_box, validate_pin, validate_review

SCHEMA = '''CREATE TABLE IF NOT EXISTS pins(id TEXT PRIMARY KEY, body TEXT NOT NULL, version INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS boxes(id TEXT PRIMARY KEY, body TEXT NOT NULL, version INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, body TEXT NOT NULL, version INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS metadata(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, time TEXT NOT NULL, pin_id TEXT NOT NULL,
        old TEXT, new TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'pin');
    INSERT OR IGNORE INTO metadata VALUES(1,1);'''


class PinStore:
    def __init__(self, run):
        self.path = run/'annotations.sqlite3'
        self._ready=False

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path, timeout=10)
        try:
            if not self._ready:
                # Older pilot runs have no boxes table and no event kind: add them, keep the rows.
                db.executescript(SCHEMA)
                if 'kind' not in {row[1] for row in db.execute('PRAGMA table_info(events)')}:
                    db.execute("ALTER TABLE events ADD COLUMN kind TEXT NOT NULL DEFAULT 'pin'")
                self._ready=True
            with db:
                yield db
        finally:
            db.close()

    def initialize(self, pins, boxes=()):
        with self.connect() as db:
            db.executescript(SCHEMA)
            for p in pins:
                db.execute('INSERT OR IGNORE INTO pins VALUES(?,?,?)',(p['id'],json.dumps(p,ensure_ascii=False),p['version']))
            for b in boxes:
                db.execute('INSERT OR IGNORE INTO boxes VALUES(?,?,?)',(b['id'],json.dumps(b,ensure_ascii=False),1))

    def snapshot(self):
        with self.connect() as db:
            db.execute('BEGIN')
            revision=db.execute('SELECT revision FROM metadata WHERE id=1').fetchone()[0]
            rows=lambda table:[{**json.loads(body),'id':rid,'version':version}
                               for rid,body,version in db.execute(f'SELECT id,body,version FROM {table} ORDER BY rowid')]
            return revision,rows('pins'),rows('boxes'),rows('reviews')

    def _write(self, table, kind, record, payload, prefix):
        rid=payload.get('id')
        if rid is not None and (not isinstance(rid,str) or len(rid)>100):
            raise ValueError('Geçersiz kayıt kimliği.')
        expected=payload.get('expected_version')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=None
            if rid:
                row=db.execute(f'SELECT body,version FROM {table} WHERE id=?',(rid,)).fetchone()
                if row is None:
                    raise ValueError('Kayıt bulunamadı.')
                if type(expected) is not int or row[1]!=expected:
                    raise ValueError('Kayıt başka işlemde değişti. Sayfayı yenileyin.')
                old,version=row[0],row[1]+1
            else:
                rid,version=prefix+uuid.uuid4().hex,1
            record.update(id=rid,version=version)
            body=json.dumps(record,ensure_ascii=False)
            db.execute(f'INSERT INTO {table} VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body,'
                       'version=excluded.version',(rid,body,version))
            # Every edit bumps the shared revision: earlier confirmations are suspended, not silently kept.
            db.execute('UPDATE metadata SET revision=revision+1 WHERE id=1')
            db.execute('INSERT INTO events(time,pin_id,old,new,kind) VALUES(?,?,?,?,?)',
                       (datetime.now(timezone.utc).isoformat(),rid,old,body,kind))
        return record

    def change(self, payload, pages):
        return self._write('pins','pin',validate_pin(payload,pages),payload,'user_')

    def change_box(self, payload, pages):
        return self._write('boxes','box',validate_box(payload,pages),payload,'box_')

    def add_review(self, payload, pin_versions, revision, pages, page_signatures):
        """Freeze the reviewed pin versions AND the sheets the decision depends on."""
        record=validate_review(payload)
        record.update(pin_versions=pin_versions,annotation_revision=revision,
                      pages=sorted(pages),page_signatures=page_signatures,stale_events=[],
                      recorded_utc=datetime.now(timezone.utc).isoformat())
        return self._write('reviews','review',record,dict(payload,id=None),'review_')

    def mark_stale(self, pages, reason, revision):
        """Any mark or mask change on a sheet suspends every review that depends on that sheet.

        The decision text is kept; a dated staleness event is appended. Staleness never clears
        by itself: restoring the old geometry does not revive an approval.
        """
        stamp=datetime.now(timezone.utc).isoformat()
        touched=[]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for rid,body,version in db.execute('SELECT id,body,version FROM reviews ORDER BY rowid').fetchall():
                record=json.loads(body)
                if not (set(record.get('pages') or []) & set(pages)):
                    continue
                record.setdefault('stale_events',[]).append(
                    dict(time=stamp,pages=sorted(pages),reason=reason,annotation_revision=revision))
                db.execute('UPDATE reviews SET body=? WHERE id=?',(json.dumps(record,ensure_ascii=False),rid))
                db.execute('INSERT INTO events(time,pin_id,old,new,kind) VALUES(?,?,?,?,?)',
                           (stamp,rid,body,json.dumps(record,ensure_ascii=False),'review_stale'))
                touched.append(rid)
        return touched

    def events(self):
        with self.connect() as db:
            return [dict(id=i,time=t,record_id=r,kind=k,created=old is None,
                         body=json.loads(new)) for i,t,r,old,new,k in
                    db.execute('SELECT id,time,pin_id,old,new,kind FROM events ORDER BY id')]
