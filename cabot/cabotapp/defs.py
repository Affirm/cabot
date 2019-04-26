# Constant definitions

CHECK_TYPES = (
    ('>', 'Greater than'),
    ('>=', 'Greater than or equal'),
    ('<', 'Less than'),
    ('<=', 'Less than or equal'),
    ('==', 'Equal to'),
)

PASSING_STATUS = 'PASSING'
ACKED_STATUS = 'ACKED'
WARNING_STATUS = 'WARNING'
ERROR_STATUS = 'ERROR'
CRITICAL_STATUS = 'CRITICAL'

RAW_DATA_LIMIT = 500000

DEFAULT_CHECK_FREQUENCY = 5
DEFAULT_CHECK_RETRIES = 0

DEFAULT_HTTP_TIMEOUT = 30
MAX_HTTP_TIMEOUT = 32
DEFAULT_HTTP_STATUS_CODE = 200

DEFAULT_TCP_TIMEOUT = 8
MAX_TCP_TIMEOUT = 16

TIMESTAMP_FORMAT = "%b %d, %Y, %H:%M %Z"  # Eg: "Dec 10, 2018, 21:34 UTC"

# options to present in the dropdown on the for creating an ack
EXPIRE_AFTER_HOURS_OPTIONS = [1, 2, 4, 8, 24]

# number of closed acks to show at the bottom of the acknowledgements page
NUM_VISIBLE_CLOSED_ACKS = 12
