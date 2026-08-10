import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import io
import sys

formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s - %(filename)s:%(lineno)d - %(message)s"
)

logger = logging.getLogger("main")
logger.setLevel(logging.INFO)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

stdout_stream = sys.stdout
stderr_stream = sys.stderr
if isinstance(stdout_stream, io.TextIOBase) and stdout_stream.encoding and stdout_stream.encoding.lower() != "utf-8":
    stdout_stream = io.TextIOWrapper(stdout_stream.buffer, encoding="utf-8", errors="replace", line_buffering=True)
if isinstance(stderr_stream, io.TextIOBase) and stderr_stream.encoding and stderr_stream.encoding.lower() != "utf-8":
    stderr_stream = io.TextIOWrapper(stderr_stream.buffer, encoding="utf-8", errors="replace", line_buffering=True)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False


play_logger = logging.getLogger("play")
play_log_file = "logs/play.log"
Path(play_log_file).parent.mkdir(parents=True, exist_ok=True)
play_logger.setLevel(logging.INFO)
file_handler = TimedRotatingFileHandler(
    play_log_file,
    encoding="utf-8",
    when="midnight",  # 按天分割（午夜时分）
    interval=1,  # 每1天轮换一次
    backupCount=7,
)
file_handler.setFormatter(formatter)
play_logger.addHandler(file_handler)

play_console_handler = logging.StreamHandler(stdout_stream)
play_console_handler.setLevel(logging.INFO)
play_console_handler.setFormatter(formatter)

main_console_handler = logging.StreamHandler(stderr_stream)
main_console_handler.setLevel(logging.INFO)
main_console_handler.setFormatter(formatter)

logger.handlers.clear()
logger.addHandler(main_console_handler)

play_logger.addHandler(play_console_handler)
play_logger.propagate = False
