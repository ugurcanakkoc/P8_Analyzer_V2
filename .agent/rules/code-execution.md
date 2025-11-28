---
trigger: always_on
---

# Project Guidelines & Agent / Shell-Execution Policy

## 🎯 Project Overview  
This is a general guideline document for Python projects that may use AI agents, external libraries, or multiple source repositories.  
It defines coding style, project structure, agent behavior expectations, and security rules — especially regarding shell / external-command execution.  
Use this as a baseline for all your Python projects to ensure readability, maintainability, and safety.

---

## 📁 Directory & Structure Rules  

- All source code must reside under `src/<package_name>/`.  
- Organize code into modules by responsibility. Example sub-directories:  
  - `pdf_reader/` — PDF/image reading & parsing modules  
  - `connection_finder/` — connection / wiring / link detection modules  
  - `terminal_finder/` — terminal/terminal-block (klemens) detection modules  
  - `analysis/` — analysis / mapping / domain logic modules  
  - `utils/` — utility / shared helper functions  
- If the project grows, keep new modules under the same structure.  
- Test files must reside under a parallel `tests/` folder (or similar), matching module names for clarity.  

---

## 🧑‍💻 Coding Style & Conventions  

- Language: **Python 3.x**  
- Style: Follow **PEP 8** guidelines. Use snake_case for functions and variables; use CamelCase only for class names.  
- Documentation: Each function/class must include a docstring that describes its behavior, parameters, and return values.  
- Logging: Use the `logging` module for debug/info/error messages. *Do not* use bare `print()` in production code.  
- Avoid code duplication: Shared logic should live in `utils/` or common helper modules, not copied across modules.  
- Dependencies: All external dependencies must be declared (e.g. in `requirements.txt` or `pyproject.toml`), and virtual environments (venv, virtualenv, etc.) should be used.

---

## 🔄 Modularity & Extensibility  

- Each module should have a **single responsibility** — it should do one job well.  
- Adding new features or modules should not require rewriting existing code; extend via new modules or functions.  
- Modules should be loosely coupled — avoid deep interdependencies whenever possible.  
- For optional features (e.g. reading images, OCR, PDF parsing, symbol detection), design module interfaces so that you can plug/unplug functionality without disturbing the core logic.

---

## ✅ Testing & Quality Assurance  

- Use a testing framework (e.g. `pytest`) to write unit and integration tests for each module.  
- Tests must live in `tests/`, and mirror module structure.  
- Before merging code / releasing new version: run full test suite and ensure all tests pass.  
- Use code linters/formatters (e.g. `flake8`, `black`, `isort`) to enforce style and catch common mistakes.  

---

## 🤖 Agent (AI) Usage Guidelines  

- AI agents may be used for **writing code suggestions, refactoring, helper function generation, test scaffolding**, and similar tasks — but **must not** perform automatic commits, merges, deployments, or destructive actions.  
- Generated code by agents must respect all style, structure, documentation, and testing rules defined above.  
- Agent-generated code should always be manually reviewed by a human before integration.  
- When using external modules (from other repos, e.g. UVP, circuit-vision), ensure compatibility, licensing, and dependencies are checked by a human.

---

## 🔐 Shell / External-Command Execution Policy  

### ❗ Guidelines for executing shell commands or external processes  

- Avoid executing shell commands automatically via AI agents.  
- Prefer Python-native APIs over spawning external processes when possible (e.g. use `os`, `pathlib`, `shutil`, libraries for PDF/image processing etc., instead of shell tools). :contentReference[oaicite:0]{index=0}  
- If you must run external commands:  
  - Use Python’s built-in `subprocess` module. :contentReference[oaicite:1]{index=1}  
  - Pass command and its arguments as a list (not a string), and use `shell=False` (default). :contentReference[oaicite:2]{index=2}  
  - Do **not** use `os.system()`, `os.popen()` or `subprocess.Popen(..., shell=True)` unless absolutely necessary and carefully reviewed. :contentReference[oaicite:3]{index=3}  
  - Do **not** construct command strings using untrusted input; never trust raw input for shell arguments — sanitize or validate thoroughly. :contentReference[oaicite:4]{index=4}  
  - Avoid shell features like piping (`|`), redirection (`>`, `<`), wildcards, variable expansion — if required, consider using Python equivalents (redirect files via open/pipe, handle file operations in Python). :contentReference[oaicite:5]{index=5}  
- Commands that create, modify or delete files under `src/` (or project-code directories), or that manipulate version control (e.g. `git push --force`) should never run automatically — they must require manual human review / confirmation.  
- Avoid logging or printing sensitive data such as environment variables, secrets, credentials, database connection strings — especially when launching external commands.  

### 🚫 Disallowed or restricted commands for automatic execution by an agent  

- Any file deletion, forced deletion or write operations affecting project-code directories (e.g. `rm -rf`, `del`, `Remove-Item`, etc.).  
- Version-control destructive commands (e.g. `git push --force`, history rewriting).  
- Downloading and executing external scripts from untrusted sources (e.g. `curl | bash`, arbitrary pipe commands).  
- Any command not explicitly whitelisted by a human reviewer.  

### ✅ Procedure for External Actions that Require Human Review  

1. Propose the command in code comments, documentation, or an issue — explain purpose, input, and effect.  
2. A human developer reviews the proposed command, checks for safety, dependencies, environment variables, side effects.  
3. If approved, integrate call using secure `subprocess.run([...], shell=False, check=True, capture_output=True, etc.)` with sanitized arguments and proper error handling.  
4. Add or update tests mocking external behaviors, where appropriate.  

---

## 📄 Documentation & Contribution / Usage Guidelines  

- The project root must include a `README.md` describing: project purpose, how to set up environment, how to run, dependencies, module overview, example usage.  
- If project grows, maintain a `docs/` folder for extended documentation (architecture, module descriptions, data flow, usage examples).  
- Contributions / PRs must follow:  
  - Single logical change per PR (e.g. “add pdf_reader module”, “refactor connection_finder logic”, etc.)  
  - Tests added/updated for changed or new code.  
  - No lint or formatting errors.  
  - Documentation updated if needed (e.g. README, docstrings, docs).  

---

## 🛠️ Example Usage / Setup  

```bash
# Create / activate a virtual environment  
python -m venv .venv  
source .venv/bin/activate   # On Windows: .venv\\Scripts\\activate

# Install dependencies  
pip install -r requirements.txt  

# Run the project (example)  
python src/<package_name>/main.py --input path/to/input_file.pdf  
