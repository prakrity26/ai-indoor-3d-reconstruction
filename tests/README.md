# tests

Each phase adds tests for the behavior it introduces.

Phase 1: `test_preprocessing.py` covers validation failures and uniform frame extraction using synthetic OpenCV videos. No large real indoor videos are committed.

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
