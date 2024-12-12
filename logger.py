# logger.py
import logging
from logging.handlers import RotatingFileHandler
import os


def setup_logger(app):
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # Set up file handler
    file_handler = RotatingFileHandler(
        'logs/pirkey_avot.log',
        maxBytes=1024 * 1024,  # 1MB
        backupCount=10
    )

    # Set up formatter
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(formatter)

    # Set up app logger
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Pirkey Avot startup')

    return app

# Usage in app.py:
# from logger import setup_logger
# app = setup_logger(app)