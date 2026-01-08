# Code Style and Conventions

## Language
- **Code Comments**: Turkish (original development language)
- **Docstrings**: Mix of German and English
- **Variable names**: English (snake_case)

## Python Style
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Type hints**: Used sparingly, mainly in Pydantic models
- **Docstrings**: Triple-quoted, brief descriptions
- **Imports**: Standard library first, then third-party, then local

## Pydantic Models (src/models.py)
- All data structures use Pydantic BaseModel
- Optional fields use `Optional[Type] = None`
- Default factories: `Field(default_factory=list)`

## PyQt5 Patterns
- Signals/Slots for async communication
- QThread workers for background processing
- Main window pattern with toolbar, dock panels

## Logging
- Use `logging` module
- Logger per module: `logger = logging.getLogger(__name__)`
- Levels: debug for verbose, info for summaries, warning for issues

## Error Handling
- Try/except around file operations and external calls
- User-facing errors via QMessageBox
- Debug info via print() or logger.debug()
