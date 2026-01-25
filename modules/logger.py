import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03dZ [%(threadName)s] %(levelname)s:%(filename)s:%(lineno)d: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger("app")