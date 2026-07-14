import sys
import os

# Add the project root to sys.path if not there
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from app.core.logging import configure_structlog, get_logger
    configure_structlog()
    logger = get_logger("test")
    logger.info("Test message")
except Exception as e:
    import traceback
    traceback.print_exc()
