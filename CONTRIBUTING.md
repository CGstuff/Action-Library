# Contributing to Action Library

Thank you for your interest in contributing to Action Library! This document provides guidelines and instructions for contributing.

## Prerequisites

- Python 3.9 or higher
- Git
- A code editor (VS Code recommended)

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/action-library.git
   cd action-library
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python run.py
   ```

## Project Structure

```
action-library/
├── animation_library/      # Main application package
│   ├── config.py          # Configuration and constants
│   ├── main.py            # Entry point
│   ├── core/              # Business logic
│   ├── models/            # Data models (Qt Model/View)
│   ├── services/          # Database, Blender integration
│   ├── themes/            # Theme system
│   ├── views/             # Qt view components
│   ├── widgets/           # UI widgets and dialogs
│   └── utils/             # Utilities and helpers
├── blender_plugin/        # Blender addon
├── assets/                # Icons and images
└── requirements.txt       # Python dependencies
```

For detailed architecture information, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Code Style

### General Guidelines

- Use **type hints** for all function parameters and return values
- Write **docstrings** for all public classes and methods
- Follow **PEP 8** style guidelines
- Keep functions focused and under 50 lines when possible

### Example

```python
def load_animation(self, uuid: str) -> Optional[Animation]:
    """
    Load an animation by its UUID.

    Args:
        uuid: The unique identifier of the animation

    Returns:
        Animation object if found, None otherwise
    """
    return self._db_service.get_animation(uuid)
```

### Naming Conventions

- Classes: `PascalCase` (e.g., `AnimationCardDelegate`)
- Functions/methods: `snake_case` (e.g., `load_thumbnail`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CARD_SIZE`)
- Private members: prefix with `_` (e.g., `self._db_service`)

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Commit Messages

Write clear, concise commit messages:

```
Add thumbnail caching for improved performance

- Implement LRU cache for loaded thumbnails
- Add cache invalidation on theme change
- Update tests for new caching behavior
```

## Pull Request Process

1. **Create a branch** from `master` for your changes
2. **Make your changes** following the code style guidelines
3. **Test your changes** thoroughly
4. **Update documentation** if needed
5. **Submit a pull request** with a clear description

### PR Description Template

```markdown
## Summary
Brief description of changes

## Changes
- List of specific changes made

## Testing
How you tested these changes

## Screenshots (if applicable)
Before/after screenshots for UI changes
```

## Reporting Issues

When reporting bugs, please include:

- Python version (`python --version`)
- Operating system
- Steps to reproduce the issue
- Expected vs actual behavior
- Any error messages or logs

## Questions?

Feel free to open an issue for questions or discussions about potential contributions.
