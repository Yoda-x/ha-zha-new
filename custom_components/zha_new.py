"""
Support for ZigBee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/

"""

import asyncio
import logging

import voluptuous as vol
from homeassistant.helpers.event import async_track_point_in_time
import homeassistant.util.dt as dt_util
import datetime
import homeassistant.helpers.config_validation as cv
from homeassistant import const as ha_const
from homeassistant.helpers import discovery, entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util import slugify
from importlib import import_module


REQUIREMENTS = ['bellows', 'zigpy']

DOMAIN = 'zha_new'

CONF_BAUDRATE = 'baudrate'
CONF_DATABASE = 'database_path'
CONF_DEVICE_CONFIG = 'device_config'
CONF_USB_PATH = 'usb_path'
DATA_DEVICE_CONFIG = 'zha_device_config'
ENTITY_STORE = "entity_store"


"""All constants related to the ZHA component."""

DEVICE_CLASS = {}
SINGLE_CLUSTER_DEVICE_CLASS = {}
COMPONENT_CLUSTERS = {}
CONF_IN_CLUSTER = 'in_cluster'
CONF_OUT_CLUSTER = 'out_cluster'
CONF_CONFIG_REPORT = 'config_report'
CONF_MANUFACTURER = 'manufacturer'
CONF_MODEL = 'model'
CONF_TEMPLATE = 'template'


def set_entity_store(hass, entity_store):
    all_discovery_info = hass.data.get(DISCOVERY_KEY, {})
    all_discovery_info[ENTITY_STORE] = entity_store


def get_entity_store(hass):
    all_discovery_info = hass.data.get(DISCOVERY_KEY, {})
    return all_discovery_info[ENTITY_STORE]


def populate_data():
    """Populate data using constants from bellows.

    These cannot be module level, as importing bellows must be done in a
    in a function.

    """

    from zigpy import zcl
    from zigpy.profiles import PROFILES, zha, zll

    DEVICE_CLASS[zha.PROFILE_ID] = {
        zha.DeviceType.ON_OFF_SWITCH: 'switch',
        zha.DeviceType.SMART_PLUG: 'switch',

        zha.DeviceType.ON_OFF_LIGHT: 'light',
        zha.DeviceType.DIMMABLE_LIGHT: 'light',
        zha.DeviceType.COLOR_DIMMABLE_LIGHT: 'light',
        zha.DeviceType.ON_OFF_LIGHT_SWITCH: 'light',
        zha.DeviceType.DIMMER_SWITCH: 'light',
        zha.DeviceType.COLOR_DIMMER_SWITCH: 'light',
    }

    DEVICE_CLASS[zll.PROFILE_ID] = {
        zll.DeviceType.ON_OFF_LIGHT: 'light',
        zll.DeviceType.ON_OFF_PLUGIN_UNIT: 'switch',
        zll.DeviceType.DIMMABLE_LIGHT: 'light',
        zll.DeviceType.DIMMABLE_PLUGIN_UNIT: 'light',
        zll.DeviceType.COLOR_LIGHT: 'light',
        zll.DeviceType.EXTENDED_COLOR_LIGHT: 'light',
        zll.DeviceType.COLOR_TEMPERATURE_LIGHT: 'light',
    }

    SINGLE_CLUSTER_DEVICE_CLASS.update({
        zcl.clusters.general.OnOff: 'switch',
        zcl.clusters.measurement.TemperatureMeasurement: 'sensor',
        zcl.clusters.measurement.RelativeHumidity: 'sensor',
        zcl.clusters.measurement.PressureMeasurement: 'sensor',
        zcl.clusters.measurement.IlluminanceMeasurement: 'sensor',
        zcl.clusters.measurement.OccupancySensing: 'binary_sensor',
    })

    # A map of hass components to all Zigbee clusters it could use
    for profile_id, classes in DEVICE_CLASS.items():
        profile = PROFILES[profile_id]
        for device_type, component in classes.items():
            if component not in COMPONENT_CLUSTERS:
                COMPONENT_CLUSTERS[component] = (set(), set())
            clusters = profile.CLUSTERS[device_type]
            COMPONENT_CLUSTERS[component][0].update(clusters[0])
            COMPONENT_CLUSTERS[component][1].update(clusters[1])
            """end populate_data """


""" Schema for configurable options in configuration.yaml """
DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema({
    vol.Optional(ha_const.CONF_TYPE): cv.string,
    vol.Optional(CONF_IN_CLUSTER): cv.ensure_list,
    vol.Optional(CONF_OUT_CLUSTER): cv.ensure_list,
    vol.Optional(CONF_CONFIG_REPORT): cv.ensure_list,
    vol.Optional(CONF_MODEL): cv.string,
    vol.Optional(CONF_MANUFACTURER): cv.string,
    vol.Optional(CONF_TEMPLATE): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        CONF_USB_PATH: cv.string,
        vol.Optional(CONF_BAUDRATE, default=57600): cv.positive_int,
        CONF_DATABASE: cv.string,
        vol.Optional(CONF_DEVICE_CONFIG, default={}):
            vol.Schema({cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}),
    })
}, extra=vol.ALLOW_EXTRA)

ATTR_DURATION = 'duration'
ATTR_IEEE = 'ieee'

SERVICE_PERMIT = 'permit'
SERVICE_REMOVE = 'remove'

SERVICE_SCHEMAS = {
    SERVICE_PERMIT: vol.Schema({
        vol.Optional(ATTR_DURATION, default=60):
            vol.All(vol.Coerce(int), vol.Range(0, 255)),
    }),
    SERVICE_REMOVE: vol.Schema({
        vol.Optional(ATTR_IEEE, default=''): cv.string
    }),
}


# ZigBee definitions
CENTICELSIUS = 'C-100'
# Key in hass.data dict containing discovery info
DISCOVERY_KEY = 'zha_discovery_info'

# Internal definitions
APPLICATION_CONTROLLER = None
_LOGGER = logging.getLogger(__name__)

# to be overwritten by DH
def _custom_endpoint_init(self, node_config, *argv):
    pass


class zha_state(entity.Entity):
    def __init__(self, hass, stack,  name,   state='Init'):
        self._device_state_attributes = {}
        self._device_state_attributes['friendly_name'] = 'Controller'
        self.hass = hass
        self._state = state
        self.entity_id = DOMAIN + '.' + name
        self.platform = DOMAIN
        self.stack = stack

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._device_state_attributes

    @asyncio.coroutine
    def async_update(self):
        result = yield from self.stack._command('neighborCount', [])
        self._device_state_attributes['neighborCount'] = result[0]
        entity_store = get_entity_store(self.hass)
        self._device_state_attributes['no_devices'] = len(entity_store)
        result = yield from self.stack._command('getValue', 3 )
        _LOGGER.debug("buffer: %s",  result)
#        buffer = t.uint8_t(result[1])
#        self._device_state_attributes['FreeBuffers'] =  buffer
#        result = yield from self.stack._command('getSourceRouteTableFilledSize',  [])
#        self._device_state_attributes['getSourceRouteTableFilledSize'] =  result[0]


@asyncio.coroutine
def async_setup(hass, config):

    global APPLICATION_CONTROLLER
    import bellows.ezsp
    from bellows.zigbee.application import ControllerApplication

    ezsp_ = bellows.ezsp.EZSP()
    usb_path = config[DOMAIN].get(CONF_USB_PATH)
    baudrate = config[DOMAIN].get(CONF_BAUDRATE)
    yield from ezsp_.connect(usb_path, baudrate)

    database = config[DOMAIN].get(CONF_DATABASE)
    APPLICATION_CONTROLLER = ControllerApplication(ezsp_, database)
    listener = ApplicationListener(hass, config)
    APPLICATION_CONTROLLER.add_listener(listener)
    yield from APPLICATION_CONTROLLER.startup(auto_form=True)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    zha_controller = zha_state(hass,   ezsp_, 'controller',  'Init')
    listener.controller = zha_controller
    yield from component.async_add_entities([zha_controller])
    zha_controller.async_schedule_update_ha_state()

    for device in APPLICATION_CONTROLLER.devices.values():
        hass.async_add_job(listener.async_device_initialized(device, False))
        yield from asyncio.sleep(0.1)

    @asyncio.coroutine
    def permit(service):
        """Allow devices to join this network."""
        duration = service.data.get(ATTR_DURATION)
        _LOGGER.info("Permitting joins for %ss", duration)
        zha_controller._state = 'Permit'
        zha_controller.async_schedule_update_ha_state()
        yield from APPLICATION_CONTROLLER.permit(duration)

        @asyncio.coroutine
        def _async_clear_state(entity):
            if entity._state == 'Permit':
                entity._state = 'Run'
            entity.async_schedule_update_ha_state()

        async_track_point_in_time(
            zha_controller.hass, _async_clear_state(zha_controller),
            dt_util.utcnow() + datetime.timedelta(seconds=duration))

    hass.services.async_register(DOMAIN, SERVICE_PERMIT, permit,
                                 schema=SERVICE_SCHEMAS[SERVICE_PERMIT])

    
    async def remove(service):
        """remove device from the network"""
        ieee_list=[]
        ieee = service.data.get(ATTR_IEEE)
        if ieee == '':
            _LOGGER.debug("service remove device str empty")
            return
        _LOGGER.debug("service remove device str: %s",  ieee)
        for device in APPLICATION_CONTROLLER.devices.values():
            if ieee in str(device._ieee):
                ieee_list.append(device.ieee)
        for device in ieee_list:        
            await APPLICATION_CONTROLLER.remove(device)

    hass.services.async_register(DOMAIN, SERVICE_REMOVE, remove,
                                 schema=SERVICE_SCHEMAS[SERVICE_REMOVE])

    zha_controller._state = "Run"
    zha_controller.async_schedule_update_ha_state()
    return True


class ApplicationListener:

    """All handlers for events that happen on the ZigBee application."""

    def __init__(self, hass, config):
        """Initialize the listener."""
        self._hass = hass
        self._config = config
        hass.data[DISCOVERY_KEY] = hass.data.get(DISCOVERY_KEY, {})
        hass.data[DISCOVERY_KEY][ENTITY_STORE] = hass.data[DISCOVERY_KEY].get(ENTITY_STORE, {})

        self.controller = None
        self._entity_list = []
        self.device_store = []
        self.mc_subscribers = {}


    def device_updated(self,  device):
        pass
    
    
    def subscribe_group(self, group_id):
        # keeps a list of susbcribers, forwardrequest to zigpy if a group is new, otherwise do nothing
        _LOGGER.debug("received subscribe group: %s", group_id)
        self._hass.async_add_job(APPLICATION_CONTROLLER.subscribe_group(group_id))


    def unsubscribe_group(self, group_id):
        # keeps a list of susbcribers, forwardrequest to zigpy if last subscriber is gone, otherwise do nothing
        pass
    
    
    def device_removed(self,  device):
        """Remove related entities from HASS."""
        entity_store = get_entity_store(self._hass)
        _LOGGER.debug("remove %s", device._ieee)
        _LOGGER.debug("No of entities:%s",  len(entity_store))
        if device._ieee in entity_store:
            for dev_ent in entity_store[device._ieee]:
                _LOGGER.debug("remove entity %s", dev_ent.entity_id)
                _LOGGER.debug("platform used: %s ", dir(dev_ent.platform))
                self._hass.async_add_job( dev_ent.async_remove())
            entity_store.pop(device._ieee)

    def device_joined(self, device):
        """Handle device joined.

        At this point, no information about the device is known other than its
        address

        """
        # Wait for device_initialized, instead
        self.controller._state = 'Joined ' + str(device._ieee)
        self.controller.async_schedule_update_ha_state()
        _LOGGER.debug("Device joined: %s:", device._ieee)

    def device_announce(self, device):
        """if a device rej/oines the network, eg switched on again."""
        _LOGGER.debug("Device announced: %s:", device._ieee)
        """find the device entities and get updates"""

    def device_initialized(self, device):
        """Handle device joined and basic information discovered."""
        self.controller._state = 'Device init ' + str(device._ieee)
        self.controller.async_schedule_update_ha_state()
        self._hass.async_add_job(self.async_device_initialized(device, True))

    def device_left(self, device):
#        self._hass.async_add_job(APPLICATION_CONTROLLER.remove(device._ieee))
#        """Handle device leaving the network. need to  remove entities"""
        _LOGGER.debug("Device left: remove the device from bellows")
        self.controller._state ='Left ' + str(device._ieee)
        self.controller.async_schedule_update_ha_state()

        @asyncio.coroutine
        def _async_clear_state(entity):
            entity._state = 'Run'
            entity.async_schedule_update_ha_state()
        async_track_point_in_time(
            self.controller.hass, _async_clear_state(self.controller),
            dt_util.utcnow() + datetime.timedelta(seconds=5))

    @asyncio.coroutine
    def async_device_initialized(self, device, join):
        """Handle device joined and basic information discovered (async)."""
        import zigpy.profiles
        populate_data()
        discovered_info = {}

        """ loop over endpoints"""
        for endpoint_id, endpoint in device.endpoints.items():
            _LOGGER.debug("ZHA_NEW: Endpoint loop : %s", endpoint_id)
            if endpoint_id == 0:  # ZDO
                continue

            component = None
            profile_clusters = [set(), set()]

            """device_key=ieee-EP ->endpoint"""
            device_key = '%s-%s' % (str(device.ieee), endpoint_id)
            node_config = self._config[DOMAIN][CONF_DEVICE_CONFIG].get(device_key, {})
            _LOGGER.debug("node config for %s: %s", device_key, node_config)
            if CONF_TEMPLATE in node_config:
                try:
                    dev_func = node_config.get(CONF_TEMPLATE, "default").replace(".", "_").replace(" ", "_")
                    _custom_endpoint_init = getattr(import_module("custom_components.device." + dev_func), "_custom_endpoint_init")
                    _custom_endpoint_init(endpoint, node_config, dev_func)
                    _LOGGER.debug("Load template %s success ", dev_func)
                except ImportError as e:
                    _LOGGER.debug("Import of template %s failed: %s", dev_func, e.args)
                except Exception as e:
                    _LOGGER.info("Excecution of template %s failed: %s", dev_func, e.args)

            if CONF_MANUFACTURER in node_config:
                discovered_info[CONF_MANUFACTURER] = node_config[CONF_MANUFACTURER]
            if CONF_MODEL in node_config:
                discovered_info[CONF_MODEL] = node_config[CONF_MODEL]
            elif 0 in endpoint.in_clusters:
                """ just get device_info if cluster 0 exists"""
             #   if join:
              #      v = yield from discover_cluster_values(endpoint, endpoint.in_clusters[0])
                discovered_info = yield from _discover_endpoint_info(endpoint)
#                if discovered_info[CONF_MODEL] is None  \
#                    and discovered_info[CONF_MANUFACTURER] is None  \
#                        and endpoint.profile_id == 49246:
#                    endpoint.profile_id = 260
#                    discovered_info = yield from _discover_endpoint_info(endpoint)
#                    endpoint.profile_id = 49246

            """ when a model name is available and not the template already applied, use it to do custom init"""
            if (discovered_info[CONF_MODEL] is not None) and (CONF_TEMPLATE not in node_config):
                try:
                    dev_func = discovered_info.get(CONF_MODEL, "default").replace(".", "_").replace(" ", "_")
                    _custom_endpoint_init = getattr(import_module("custom_components.device." + dev_func), "_custom_endpoint_init")
                    _custom_endpoint_init(endpoint, node_config, dev_func)
                    _LOGGER.debug("Load DH %s success ", dev_func)
                except ImportError as e:
                    _LOGGER.debug("Import DH %s failed: %s", dev_func, e.args)
                except Exception as e:
                    _LOGGER.info("Excecution of DH %s failed: %s", dev_func, e.args)

            _LOGGER.debug("node config for %s: %s", device_key, node_config)

            #_LOGGER.debug("profile %s ", endpoint.profile_id)
            if endpoint.profile_id in zigpy.profiles.PROFILES:
                profile = zigpy.profiles.PROFILES[endpoint.profile_id]
                if DEVICE_CLASS.get(endpoint.profile_id, {}).get(endpoint.device_type, None):
                    profile_clusters[0].update(profile.CLUSTERS[endpoint.device_type][0])
                    profile_clusters[1].update(profile.CLUSTERS[endpoint.device_type][1])
                    profile_info = DEVICE_CLASS[endpoint.profile_id]
                    component = profile_info[endpoint.device_type]

            """ Override type (switch,light,sensor, binary_sensor,...) from config """
            if ha_const.CONF_TYPE in node_config:
                component = node_config[ha_const.CONF_TYPE]
            if component in COMPONENT_CLUSTERS:
                profile_clusters = COMPONENT_CLUSTERS[component]

            """ Add additional allowed In_Clusters from config """
            if CONF_IN_CLUSTER in node_config:
                profile_clusters[0].update(node_config.get(CONF_IN_CLUSTER))
            """ Add aditional allowed Out_Clusters from config """
            if CONF_OUT_CLUSTER in node_config:
                profile_clusters[1].update(node_config.get(CONF_OUT_CLUSTER))

            """ if reporting is configured in yaml, then create cluster if needed and setup reporting """
            if CONF_CONFIG_REPORT in node_config and join:
                for report in node_config.get(CONF_CONFIG_REPORT):
                    report_cls, report_attr, report_min, report_max, report_change = report
                    if report_cls not in endpoint.in_clusters:
                        cluster = endpoint.add_input_cluster(report_cls)
                    else:
                        cluster = endpoint.in_clusters[report_cls]
                    try:
                        yield from endpoint.in_clusters[report_cls].bind()
                        yield from endpoint.in_clusters[report_cls].configure_reporting(report_attr, int(report_min), int(report_max), report_change)
                    except:
                        _LOGGER.info("Error: set config report failed: %s", report)
#            try:
#                battery_voltage = yield from get_battery(endpoint)
#            except:
#                pass

            _LOGGER.debug("2:profile %s, component: %s cluster:%s", endpoint.profile_id, component, profile_clusters)
            if component:
                """only discovered clusters that are in the profile or configuration listed"""
                in_clusters = [endpoint.in_clusters[c]
                               for c in profile_clusters[0]
                               if c in endpoint.in_clusters]
                out_clusters = [endpoint.out_clusters[c]
                                for c in profile_clusters[1]
                                if c in endpoint.out_clusters]
                """create  discovery info """
                discovery_info = {
                    'component': component,
                    'device': device,
                    'domain': DOMAIN,
                    'discovery_key': device_key,
                    'endpoint': endpoint,
                    'entity': None, 
                    'new_join': join,
                    'in_clusters': {c.cluster_id: c for c in in_clusters},
                    'out_clusters': {c.cluster_id: c for c in out_clusters},
                }
                """ add 'manufacturer', 'model'  to discovery_info"""

                discovery_info.update(discovered_info)
                self._hass.data[DISCOVERY_KEY][device_key] = discovery_info
                """ goto to the specific code for switch, light sensor or binary_sensor """
                yield from discovery.async_load_platform(
                    self._hass,
                    component,
                    DOMAIN,
                    {'discovery_key': device_key},
                    self._config,
                )
                _LOGGER.debug("Return from component general entity:%s", device._ieee)

            """if a discovered cluster is not in the allowed clusters and part of 
            SINGLE_CLUSTERS_DEVCICE_CLASS, the clusters that were not in discovery above
            then create just this cluster in discovery endpoints
            initialize single clusters """
            for cluster_id, cluster in endpoint.in_clusters.items():
                cluster_type = type(cluster)
                if cluster_id in profile_clusters[0]:
                    continue
                if cluster_type not in SINGLE_CLUSTER_DEVICE_CLASS:
                    continue
                if ha_const.CONF_TYPE in node_config:
                    component = node_config[ha_const.CONF_TYPE]
                else:
                    component = SINGLE_CLUSTER_DEVICE_CLASS[cluster_type]
                #if join:
                    #v = yield from discover_cluster_values(endpoint, cluster)
                    #_LOGGER.debug("discovered atributes/values for %s-%s-%s: %s",
                    #              endpoint._device._ieee ,
                     #             endpoint._endpoint_id ,
                      #            cluster.cluster_id,
                       #           v )
                """cluster key -> single cluster """
                cluster_key = '%s-%s' % (device_key, cluster_id)
                discovery_info = {
                    'discovery_key': cluster_key,
                    'endpoint': endpoint,
                    'in_clusters': {cluster.cluster_id: cluster},
                    'out_clusters': {},
                    'new_join': join,
                    'domain': DOMAIN,
                    'component': component,
                    'entity': None,
                }
                discovery_info.update(discovered_info)

                self._hass.data[DISCOVERY_KEY][cluster_key] = discovery_info

                yield from discovery.async_load_platform(
                    self._hass,
                    component,
                    DOMAIN,
                    {'discovery_key': cluster_key},
                    self._config,
                )
                _LOGGER.debug("Return from single-cluster entity:%s", discovery_info)

        _LOGGER.debug("Return from zha device init: %s", endpoint.in_clusters)
        device._application.listener_event('device_updated', device)
        self.controller._state = 'Run'
        self.controller._device_state_attributes['no_of_entities'] = len(self._entity_list)
        self.controller.async_schedule_update_ha_state()

class Entity(entity.Entity):

    """A base class for ZHA entities."""

    _domain = None  # Must be overridden by subclasses

    def __init__(self, endpoint, in_clusters, out_clusters, manufacturer,
                 model, **kwargs):
        """Init ZHA entity."""
        self._device_state_attributes = {}
        self.entity_connect = {}
        ieeetail = ''.join([
            '%02x' % (o, ) for o in endpoint.device.ieee[-4:]
        ])
        self.uid = str(endpoint.device._ieee) + "_" + str(endpoint.endpoint_id)
        if 'cluster_key' in kwargs:
            self.cluster_key = kwargs['cluster_key']
            self.uid += '_'
            self.uid += self.cluster_key

        if manufacturer and model is not None:
            self.entity_id = '%s.%s_%s_%s_%s' % (
                self._domain,
                slugify(manufacturer),
                slugify(model),
                ieeetail,
                endpoint.endpoint_id,
            )
            self._device_state_attributes['friendly_name'] = '%s %s' % (
                manufacturer,
                model,
            )
            self._device_state_attributes['model'] = model
            self._device_state_attributes['manufacturer'] = manufacturer
            self._model = model

        else:
            self.entity_id = "%s.zha_%s_%s" % (
                self._domain,
                ieeetail,
                endpoint.endpoint_id,
            )
        if 'cluster_key' in kwargs:
            self.entity_id += '_'
            self.entity_id += kwargs['cluster_key']
            self._device_state_attributes['friendly_name'] += '_'
            self._device_state_attributes['friendly_name'] += kwargs['cluster_key']

        for cluster in in_clusters.values():
            cluster.add_listener(self)
            cluster.bind()
        for cluster in out_clusters.values():
            cluster.add_listener(self)
            cluster.bind()
        self._endpoint = endpoint
        self._in_clusters = in_clusters
        self._out_clusters = out_clusters
        self._state = None
        self._device_state_attributes['lqi'] = endpoint.device.lqi
        self._device_state_attributes['rssi'] = endpoint.device.rssi

    @property
    def unique_id(self):
        return self.uid

    def attribute_updated(self, attribute, value):
        self._state = value
        self.schedule_update_ha_state()

    def zdo_command(self,  tsn, command_id, args):
        """Handle a ZDO command received on this cluster."""
        _LOGGER.debug("ZDO received: \n entity - \n command_id: %s \n args: %s",
                      self.entity_id, command_id, args)

    def cluster_command(self,  tsn, command_id, args):
        """ handle incomming cluster commands."""
        pass

    """dummy function; override from device handler"""
    def _custom_cluster_command(self,  tsn, command_id, args):
        pass

    """dummy function; override from device handler"""
    def _parse_attribute(self, entity, attrib, value, *argv):
        return(attrib, value)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        self._device_state_attributes['lqi'] = self._endpoint.device.lqi
        self._device_state_attributes['rssi'] = self._endpoint.device.rssi
        return self._device_state_attributes


@asyncio.coroutine
def _discover_endpoint_info(endpoint):
    """Find some basic information about an endpoint."""
    extra_info = {
        'manufacturer': None,
        'model': None,
    }
    if 0 not in endpoint.in_clusters:
        return extra_info

    @asyncio.coroutine
    def read(attributes):
        """Read attributes and update extra_info convenience function."""
        result, _ = yield from endpoint.in_clusters[0].read_attributes(
            attributes,
            allow_cache=True,
        )
        extra_info.update(result)

    try:
        yield from read(['model'])
    except:
        _LOGGER.debug("single read attribute failed: model")
    try:
        yield from read(['manufacturer'])
    except:
        _LOGGER.debug("single read attribute failed: manufacturer, ")
    for key, value in extra_info.items():
        if isinstance(value, bytes):
            try:
                extra_info[key] = value.decode('ascii').strip()
            except UnicodeDecodeError:
                # Unsure what the best behaviour here is. Unset the key?
                pass

    return extra_info


def get_discovery_info(hass, discovery_info):
    """Get the full discovery info for a device.

    Some of the info that needs to be passed to platforms is not JSON
    serializable, so it cannot be put in the discovery_info dictionary. This
    component places that info we need to pass to the platform in hass.data,
    and this function is a helper for platforms to retrieve the complete
    discovery info.

    """
    if discovery_info is None:
        return
    discovery_key = discovery_info.get('discovery_key', None)
    all_discovery_info = hass.data.get(DISCOVERY_KEY, {})
    discovery_info = all_discovery_info.get(discovery_key, None)
    return discovery_info


@asyncio.coroutine
def attribute_read(endpoint, cluster, attributes):
    """Read attributes and update extra_info convenience fcunction."""
    result = yield from endpoint.in_clusters[cluster].read_attributes(
        attributes,
        allow_cache=True,
    )
    return result


@asyncio.coroutine
def get_battery(endpoint):
    if 1 not in endpoint.in_clusters:
        return 0xff
    battery = yield from attribute_read(endpoint, 0x0001, ['battery_voltage'])
    return battery[0]


@asyncio.coroutine
def discover_cluster_values(endpoint, cluster):
    attrids = [0, ]
    _LOGGER.debug("discover %s-%s for %s",
                  endpoint._device.ieee,
                  endpoint._endpoint_id,
                  cluster.cluster_id)
    try:
        v = yield from cluster.discover_attributes(0, 32)
    except:
        pass
    _LOGGER.debug("discover %s for %s: %s", endpoint._endpoint_id, cluster.cluster_id, v[0])
    if isinstance(v[0], int):
        attrids = [0, 1, 2, 3, 4, 5, 6, 7, 8, 16, 17, 18]
    else:
        for item in v[0]:
            attrids.append(item.attrid)
    _LOGGER.debug("discover_cluster_attributes: query %s:", attrids)
    try:
        v = yield from cluster.read_attributes(attrids, allow_cache=True)
        _LOGGER.debug("attributes/values for cluster:%s", v[0])
    except:
        return({})
    return(v[0])


async def safe_read(cluster, attributes):
    """Swallow all exceptions from network read.
    If we throw during initialization, setup fails. Rather have an
    entity that exists, but is in a maybe wrong state, than no entity.
    """
    try:
        result, _ = await cluster.read_attributes(
            attributes,
            allow_cache=False,
        )
        return result
    except Exception:  # pylint: disable=broad-except
        return {}
