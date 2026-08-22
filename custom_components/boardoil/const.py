"""Constants for boardoil."""

from logging import Logger, getLogger

from awesomeversion import AwesomeVersion

LOGGER: Logger = getLogger(__package__)

DOMAIN = "boardoil"
MIN_HA_VERSION = "2026.7.0"
MIN_REQUIRED_BOARDOIL_VERSION = AwesomeVersion("1.5.0")
DEFAULT_SCAN_INTERVAL = 60  # seconds

ATTR_BOARD = "board"
ATTR_CARD_ID = "card_id"
ATTR_COLUMN = "column"
ATTR_COLUMN_NAME = "column_name"
ATTR_CARD_TYPE = "card_type"
ATTR_CARD_TYPE_NAME = "card_type_name"
ATTR_TITLE = "title"
ATTR_DESCRIPTION = "description"
ATTR_TAG_NAMES = "tag_names"
ATTR_SLICK_NAME = "slick_name"
ATTR_EXTERNAL_URL = "external_url"
ATTR_ASSIGNED_USER = "assigned_user"
ATTR_COMMENT = "comment"

EVENT_TYPE_CARD_CREATED = "card_created"
EVENT_TYPE_CARD_REMOVED = "card_removed"
EVENT_TYPE_CARD_UPDATED = "card_updated"
EVENT_TYPE_CARD_MOVED = "card_moved"
