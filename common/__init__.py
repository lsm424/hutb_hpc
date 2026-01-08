import loguru
import configparser

loguru.logger.add("./hutb_hpc.log", colorize=True, level="INFO", encoding="utf-8", retention="5 days", rotation="1 day", enqueue=True)
logger = loguru.logger

cfg = configparser.ConfigParser()
cfg.read('config.ini', encoding="utf-8")