"""Persistent, project-independent symbol library. Shapes only — never wiring or approvals.

An entry stores what a symbol LOOKS like and WHERE its ends and labels sit relative to the
symbol: shape objects, pin offsets, label search offsets, the evidence it was captured from,
the customer/style profile and the transforms it may be matched under.

The source sheet's device and pin TEXTS are kept as capture evidence (source_device_label,
source_pin_label) so a later match can be compared against them and differences reported. They
are never copied into another document as an identity: every candidate's device and pin names
are re-read from the new page, and the candidate rows carry empty device fields.

An entry never stores connections, wire colours, cross sections or any approval of a connection.
Entries stay DRAFT until a named person approves them.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import re
import sqlite3
import uuid

STATUSES = {"DRAFT", "APPROVED", "RETIRED"}
TRANSFORMS = {"TRANSLATION"}
NEVER_STORED = ["CONNECTIONS", "WIRE_COLOR", "CROSS_SECTION", "APPROVAL_OF_CONNECTIONS"]
# Kept as capture evidence only; never written into another document as an identity.
EVIDENCE_ONLY = ["SOURCE_DEVICE_LABEL", "SOURCE_PIN_LABEL"]
NEVER_COPIED = ["DEVICE_NAME", "PIN_NAME", "CONNECTIONS", "WIRE_COLOR", "CROSS_SECTION",
                "APPROVAL_OF_CONNECTIONS"]
SCHEMA = '''CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, body TEXT NOT NULL, version INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, time TEXT NOT NULL, entry_id TEXT NOT NULL,
        old TEXT, new TEXT NOT NULL, action TEXT NOT NULL);'''


def propose_family(descriptor, source_device=None):
    """A first name for the family, from the drawn shape and the source tag letter. Editable."""
    kinds = [row[0] for row in descriptor["core"]]
    shape = ("eğrili" if "curve" in kinds else "çizgili")
    letter = ""
    if source_device:
        match = re.search(r"-(?:\d+)?([A-Z]+)", source_device.upper())
        letter = match.group(1) if match else ""
    return " ".join(x for x in [letter, shape, "%d uçlu sembol" % len(descriptor["pins"])] if x)


def entry_from_descriptor(descriptor, evidence, profile, family=None, source_device=None, note=""):
    """Build a DRAFT entry. Pin/device texts are kept only as SOURCE evidence for comparison."""
    return dict(
        family=family or propose_family(descriptor, source_device),
        family_source="USER" if family else "PROPOSED_FROM_SHAPE_AND_SOURCE_TAG",
        status="DRAFT", approved_by=None, approved_utc=None,
        shape=dict(core=descriptor["core"], size=descriptor["size"], anchor=descriptor["anchor"]),
        pins=[dict(offset=p["offset"], kind=p["kind"], label_offset=p["pin_label_offset"],
                   label_tolerance=2.0, source_pin_label=p["source_pin_label"],
                   external_lines_in_source=p["external_lines"]) for p in descriptor["pins"]],
        label_regions=dict(device=dict(offset=descriptor["device_label_offset"], tolerance=2.0),
                           pins=[p["pin_label_offset"] for p in descriptor["pins"]]),
        source_device_label=descriptor["source_device_label"],
        evidence=dict(evidence, captured_utc=datetime.now(timezone.utc).isoformat()),
        profile=profile, transforms=["TRANSLATION"], never_stored=NEVER_STORED,
        evidence_only=EVIDENCE_ONLY, never_copied=NEVER_COPIED, note=note,
        unverified_curves=descriptor.get("unverified_curves", []),
        limitation="Yalnız öteleme ile eşleştirilir. Ölçek, dönme ve aynalama desteklenmez; "
                   "eşleşmemesi yokluk kanıtı değildir. Kaynak belgenin cihaz ve pin yazıları "
                   "yalnız KANIT olarak saklanır (karşılaştırma ve fark uyarısı için); yeni "
                   "belgeye kimlik olarak aktarılmaz. Bağlantı, renk, kesit ve onay hiç saklanmaz.")


def validate_update(data):
    changes = {}
    if "family" in data:
        family = data["family"]
        if not isinstance(family, str) or not family.strip() or len(family) > 200:
            raise ValueError("Aile adı geçersiz.")
        changes.update(family=family.strip(), family_source="USER")
    if "status" in data:
        if data["status"] not in STATUSES:
            raise ValueError("Kütüphane durumu bilinmiyor.")
        if data["status"] == "APPROVED":
            approver = data.get("approved_by", "")
            if not isinstance(approver, str) or not approver.strip():
                raise ValueError("Onay için onaylayan adı zorunlu.")
            changes.update(approved_by=approver.strip(),
                           approved_utc=datetime.now(timezone.utc).isoformat())
        changes["status"] = data["status"]
    if "note" in data:
        if not isinstance(data["note"], str) or len(data["note"]) > 600:
            raise ValueError("Not geçersiz.")
        changes["note"] = data["note"]
    if not changes:
        raise ValueError("Değiştirilecek alan yok.")
    return changes


class SymbolLibrary:
    """One local SQLite file shared by every run; rows are versioned and never deleted."""

    def __init__(self, path):
        self.path = path
        self._ready = False

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        try:
            if not self._ready:
                db.executescript(SCHEMA)
                self._ready = True
            with db:
                yield db
        finally:
            db.close()

    def entries(self):
        with self.connect() as db:
            return [{**json.loads(body), "id": rid, "version": version}
                    for rid, body, version in db.execute(
                        "SELECT id,body,version FROM entries ORDER BY rowid")]

    def get(self, entry_id):
        entry = next((e for e in self.entries() if e["id"] == entry_id), None)
        if entry is None:
            raise ValueError("Kütüphane kaydı bulunamadı: " + str(entry_id))
        return entry

    def add(self, entry):
        entry_id = "sym_" + uuid.uuid4().hex
        record = dict(entry, id=entry_id, version=1)
        with self.connect() as db:
            db.execute("INSERT INTO entries VALUES(?,?,?)",
                       (entry_id, json.dumps(record, ensure_ascii=False), 1))
            db.execute("INSERT INTO events(time,entry_id,old,new,action) VALUES(?,?,?,?,?)",
                       (datetime.now(timezone.utc).isoformat(), entry_id, None,
                        json.dumps(record, ensure_ascii=False), "add"))
        return record

    def update(self, entry_id, expected_version, changes):
        """Edit name, status or note. Shape and evidence stay as captured; history is kept."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body,version FROM entries WHERE id=?", (entry_id,)).fetchone()
            if row is None:
                raise ValueError("Kütüphane kaydı bulunamadı.")
            if type(expected_version) is not int or row[1] != expected_version:
                raise ValueError("Kayıt başka işlemde değişti. Listeyi yenileyin.")
            record = dict(json.loads(row[0]), **changes)
            record.update(id=entry_id, version=row[1]+1)
            db.execute("UPDATE entries SET body=?,version=? WHERE id=?",
                       (json.dumps(record, ensure_ascii=False), record["version"], entry_id))
            db.execute("INSERT INTO events(time,entry_id,old,new,action) VALUES(?,?,?,?,?)",
                       (datetime.now(timezone.utc).isoformat(), entry_id, row[0],
                        json.dumps(record, ensure_ascii=False), "update"))
        return record

    def history(self, entry_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT id,time,entry_id,old,new,action FROM events ORDER BY id")
            return [dict(id=i, time=t, entry_id=e, action=a, previous=json.loads(o) if o else None,
                         current=json.loads(n))
                    for i, t, e, o, n, a in rows if entry_id is None or e == entry_id]


def descriptor_of(entry):
    """Turn a stored entry back into a match recipe. Source texts stay comparison-only."""
    shape = entry["shape"]
    return dict(core=[tuple(row) if not isinstance(row, tuple) else row for row in shape["core"]],
                size=tuple(shape["size"]), anchor=dict(shape["anchor"]),
                pins=[dict(offset=tuple(p["offset"]), kind=p["kind"],
                           pin_label_offset=p["label_offset"] and tuple(p["label_offset"]),
                           source_pin_label=p.get("source_pin_label"),
                           external_lines=p.get("external_lines_in_source", 0),
                           source_pin="", source_device="", pin_id=None)
                      for p in entry["pins"]],
                device_label_offset=entry["label_regions"]["device"]["offset"],
                source_device_label=entry.get("source_device_label"),
                device_issue=None, unverified_curves=entry.get("unverified_curves", []))
