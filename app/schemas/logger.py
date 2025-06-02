import logging
import sys

logging.getLogger().handlers.clear()
# Create a logger
logger = logging.getLogger("console_logger")
logger.setLevel(logging.INFO)  # Set the lowest log level to capture all messages
#logger.handlers.clear()
logger.propagate = False
# Create a console handler (prints logs to console)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)  # Set handler level to show all logs

# Define log message format
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(formatter)  # Apply the custom formatting to the handler

# Add console handler to logger (avoid adding multiple handlers)
if not logger.hasHandlers():
    logger.addHandler(console_handler)
