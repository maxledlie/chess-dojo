import json
import datetime
from pathlib import Path
import structlog


_POSITIONS_FILE = Path(__file__).parent.parent / "positions.json"


logger = structlog.get_logger()


def get_todays_position() -> dict | None:
    with open(_POSITIONS_FILE) as f:
        data = json.load(f)
    today = datetime.date.today().isoformat()
    result = data.get("positions", {}).get(today)
    logger.debug("Today's game: ", result)
    return result
