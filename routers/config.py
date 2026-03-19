# Global variables (with defaults)
from datetime import datetime


START_TIME = datetime.strptime("09:00", "%H:%M").time()
END_TIME = datetime.strptime("18:00", "%H:%M").time()
DEFAULT_ZONE = "EARLY"
DEFAULT_ZONE_SIZE = 50
MAIN_ZONE = "A"
PER_MINUTE_FEE = 0.1
OVERDUE_GRACE_PERIOD_MINUTES = 30
OVERDUE_PENALTY_PER_MINUTE = 0.5