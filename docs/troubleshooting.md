# Troubleshooting & Quality Checklist

Back-link: referenced from `CLAUDE.md`.

## Pre-Commit Quality Checklist

- [ ] `./venv/Scripts/python.exe start_gui.py` — App starts without errors
- [ ] Load `data/ornek.pdf` — Default PDF loads
- [ ] Click "Analiz Et" — Analysis completes
- [ ] Check log panel — No unexpected errors
- [ ] `./venv/Scripts/python.exe -m pytest tests/ -v` — All tests pass

## Known Issues & Limitations

1. **No CI/CD** — Manual testing required
2. **Turkish UI** — Interface text in Turkish
3. **cairosvg dependency** — Required for SVG export, may need system libraries on some platforms
