"""All constants related to the ZHA_NEW component."""
import homeassistant.helpers.config_validation as cv
import voluptuous as vol


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
ATTR_STEP = 'step'

SERVICE_PERMIT = 'permit'
SERVICE_REMOVE = 'remove'
SERVICE_COMMAND = 'command'
SERVICE_COLORTEMP_STEP_UP = 'step_up_CT'
SERVICE_COLORTEMP_STEP_DOWN = 'step_down_CT'
SERVICE_COLORTEMP_STEP = 'step'


# ZigBee definitions
CENTICELSIUS = 'C-100'
# Key in hass.data dict containing discovery info
DISCOVERY_KEY = 'zha_discovery_info'

# Internal definitions
APPLICATION_CONTROLLER = None

SERVICE_SCHEMAS = {
    SERVICE_PERMIT: vol.Schema({
        vol.Optional(ATTR_DURATION, default=60):
            vol.All(vol.Coerce(int), vol.Range(0, 255)),
    }),
    SERVICE_REMOVE: vol.Schema({
        vol.Optional(ATTR_IEEE, default=''): cv.string,
        vol.Optional(ATTR_NWKID): cv.positive_int,
        #            vol.All(vol.Coerce(int), vol.Range(1, 65532)),
    }),
    SERVICE_COMMAND: vol.Schema({
        ATTR_ENTITY_ID: cv.string,
        ATTR_COMMAND: cv.string,
        vol.Optional('cluster'): cv.positive_int,
        vol.Optional('attribute'): cv.positive_int,
        vol.Optional('value'): cv.positive_int,
    }),
    SERVICE_COLORTEMP_STEP: vol.Schema({
        ATTR_ENTITY_ID: cv.comp_entity_ids,
        ATTR_STEP: vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
    })
    }
