"""Disposable UI-test copy; leaves the user's original annotation database untouched."""
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from analyzer_v3.service import Pilot
from analyzer_v3.server import make_server

with tempfile.TemporaryDirectory(prefix='uvp-ui-qa-') as temporary:
    run=Path(temporary)/'run'
    source=ROOT/'output/pilots/E122/20260909_v3_p03'
    run.mkdir()
    for name in ['manifest.json','geometry.json','raw_page.json','seeds.json','inventory.json','page.png','annotations.sqlite3']:
        shutil.copy2(source/name,run/name)
    server=make_server(Pilot(run),8766)
    print('Disposable UI test: http://127.0.0.1:8766',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
