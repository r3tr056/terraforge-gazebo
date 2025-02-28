import logging
import sys

def setup_logger(name, log_level=logging.INFO):
	"""Sets up a logger instance."""
	logger = logging.getLogger(name)
	logger.setLevel(log_level)

	stream_handler = logging.StreamHandler(sys.stdout)
	stream_handler.setLevel(log_level)

	formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	stream_handler.setFormatter(formatter)

	logger.addHandler(stream_handler)
	return logger

logger = setup_logger('gazebomg')