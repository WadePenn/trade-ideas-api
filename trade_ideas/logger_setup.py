"""logger_setup.py — Structured logging for trade_ideas."""
from __future__ import annotations
import logging, logging.handlers, os, sys
from typing import Optional

_DARK  = "\033["; _RESET = "\033[0m"
_COLS  = {logging.DEBUG:"\033[36m", logging.INFO:"\033[32m",
          logging.WARNING:"\033[33m", logging.ERROR:"\033[31m", logging.CRITICAL:"\033[35m"}

class _CF(logging.Formatter):
    def format(self, r):
        r.levelname = f"{_COLS.get(r.levelno,'')}{r.levelname:<8}{_RESET}"
        return super().format(r)

def get_logger(app_logger=None, log_file=None, level=logging.INFO,
               max_bytes=5*1024*1024, backup_count=3, enable_console=True):
    lg = logging.getLogger("trade_ideas")
    if lg.handlers:
        return lg
    lg.setLevel(level)
    if enable_console:
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(level)
        h.setFormatter(_CF("%(asctime)s  %(levelname)s  %(name)s — %(message)s", datefmt="%H:%M:%S"))
        lg.addHandler(h)
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=max_bytes,
                                                   backupCount=backup_count, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  [%(filename)s:%(lineno)d] — %(message)s",
            datefmt="%H:%M:%S"))
        lg.addHandler(fh)
    if app_logger is not None:
        lg.parent = app_logger; lg.propagate = True
    else:
        lg.propagate = False
    return lg

def set_level(level):
    for name in ["trade_ideas","trade_ideas.panel","trade_ideas.engine",
                 "trade_ideas.ibkr","trade_ideas.api","trade_ideas.events"]:
        logging.getLogger(name).setLevel(level)
