"""All constants related to the ZHA_NEW component."""
DOMAIN = 'zha_new'
CONF_BAUDRATE = 'baudrate'
CONF_DATABASE = 'database_path'
CONF_DEVICE_CONFIG = 'device_config'
CONF_USB_PATH = 'usb_path'
DATA_DEVICE_CONFIG = 'zha_device_config'
ENTITY_STORE = "entity_store"
DEVICE_CLASS = {}
SINGLE_CLUSTER_DEVICE_CLASS = {}
COMPONENT_CLUSTERS = {}
CONF_IN_CLUSTER = 'in_cluster'
CONF_OUT_CLUSTER = 'out_cluster'
CONF_CONFIG_REPORT = 'config_report'
CONF_MANUFACTURER = 'manufacturer'
CONF_MODEL = 'model'
CONF_TEMPLATE = 'template'
ATTR_DURATION = 'duration'
ATTR_IEEE = 'ieee'
ATTR_COMMAND = 'command'
ATTR_ENTITY_ID = 'entity_id'
ATTR_NWKID = "nwk"

SERVICE_PERMIT = 'permit'
SERVICE_REMOVE = 'remove'
SERVICE_COMMAND = 'command'

# ZigBee definitions
CENTICELSIUS = 'C-100'
# Key in hass.data dict containing discovery info
DISCOVERY_KEY = 'zha_discovery_info'

# Internal definitions
APPLICATION_CONTROLLER = None
