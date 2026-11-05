"""
结构化日志与追踪配置
"""

import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

logger = logging.getLogger("agentic_commerce")
