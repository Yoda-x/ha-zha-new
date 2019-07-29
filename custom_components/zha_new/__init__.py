"""
Support for ZigBee Home Automation devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
Revision: 0.81.100
"""

from importlib import import_module
import asyncio
import logging
_LOGGER = logging.getLogger(__name__)
_LOGGER.debug("start zha_new")
import voluptuous as vol
from homeassistant.helpers.event import async_track_point_in_time
import homeassistant.util.dt as dt_util
import datetime
import homeassistant.helpers.config_validation as cv
from homeassistant import const as ha_const
from homeassistant.helpers import discovery, entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util import slugify
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from .const import *
#from .helpers import create_MC_Entity

REQUIREMENTS = [
#    'https://github.com/Yoda-x/bellows/archive/master.zip#bellows==100.7.4.9',
    'https://github.com/Yoda-x/bellows/archive/master.zip#bellows==100.7.4.10',
    'https://github.com/Yoda-x/zigpy/archive/master.zip#zigpy==100.1.4.9',
#    'https://github.com/Yoda-x/zigpy/archive/master.zip#zigpy==100.1.4.7',
    ]


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
        zha.DeviceType.MAIN_POWER_OUTLET: 'switch',
        zha.DeviceType.ON_OFF_LIGHT: 'light',
        zha.DeviceType.DIMMABLE_LIGHT: 'light',
        zha.DeviceType.COLOR_DIMMABLE_LIGHT: 'light',
        zha.DeviceType.ON_OFF_LIGHT_SWITCH: 'binary_sensor',
        zha.DeviceType.DIMMER_SWITCH: 'binary_sensor',
        zha.DeviceType.COLOR_DIMMER_SWITCH: 'binary_sensor',
        zha.DeviceType.COLOR_SCENE_CONTROLLER: 'binary_sensor',
        zha.DeviceType.ON_OFF_SWITCH: 'binary_sensor',
        zha.DeviceType.LEVEL_CONTROL_SWITCH: 'binary_sensor',
        zha.DeviceType.REMOTE_CONTROL: 'binary_sensor',
        zha.DeviceType.OCCUPANCY_SENSOR: 'binary_sensor',
        zha.DeviceType.IAS_ZONE: 'binary_sensor',
        zha.DeviceType.LIGHT_SENSOR: 'binary_sensor',
        zha.DeviceType.ON_OFF_BALLAST: 'switch',
        zha.DeviceType.ON_OFF_PLUG_IN_UNIT:  'switch',
        zha.DeviceType.DIMMABLE_PLUG_IN_UNIT:  'switch',
        zha.DeviceType.COLOR_TEMPERATURE_LIGHT: 'light',
        zha.DeviceType.EXTENTED_COLOR_LIGHT: 'light',
        zha.DeviceType.LIGHT_LEVEL_SENSOR: 'binary_sensor',
        zha.DeviceType.NON_COLOR_CONTROLLER: 'binary_sensor',
        zha.DeviceType.NON_COLOR_SCENE_CONTROLLER: 'binary_sensor',
        zha.DeviceType.CONTROL_BRIDGE: 'binary_sensor',
        zha.DeviceType.ON_OFF_SENSOR: 'binary_sensor',

        }

    DEVICE_CLASS[zll.PROFILE_ID] = {
        zll.DeviceType.ON_OFF_LIGHT: 'light',
        zll.DeviceType.ON_OFF_PLUGIN_UNIT: 'switch',
        zll.DeviceType.DIMMABLE_LIGHT: 'light',
        zll.DeviceType.DIMMABLE_PLUGIN_UNIT: 'light',
        zll.DeviceType.COLOR_LIGHT: 'light',
        zll.DeviceType.EXTENDED_COLOR_LIGHT: 'light',
        zll.DeviceType.COLOR_TEMPERATURE_LIGHT: 'light',
        zll.DeviceType.COLOR_SCENE_CONTROLLER: 'binary_sensor',
        zll.DeviceType.SCENE_CONTROLLER: 'binary_sensor',
        zll.DeviceType.CONTROLLER: 'binary_sensor',
        zll.DeviceType.COLOR_CONTROLLER: 'binary_sensor',
        zll.DeviceType.ON_OFF_SENSOR: 'binary_sensor',
        }

    SINGLE_CLUSTER_DEVICE_CLASS.update({
        zcl.clusters.general.OnOff: 'switch',
        zcl.clusters.measurement.TemperatureMeasurement: 'sensor',
        zcl.clusters.measurement.RelativeHumidity: 'sensor',
        zcl.clusters.measurement.PressureMeasurement: 'sensor',
        zcl.clusters.measurement.IlluminanceMeasurement: 'sensor',
        zcl.clusters.measurement.OccupancySensing: 'binary_sensor',
        zcl.clusters.homeautomation.ElectricalMeasurement: 'sensor',
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

def _custom_endpoint_init(self, node_config, *argv):
    pass





async def async_setup(hass, config):


    global APPLICATION_CONTROLLER
    import bellows.ezsp
    from bellows.zigbee.application import ControllerApplication
    _LOGGER.debug("async_setup zha_new")
    ezsp_ = bellows.ezsp.EZSP()
    usb_path = config[DOMAIN].get(CONF_USB_PATH)
    baudrate = config[DOMAIN].get(CONF_BAUDRATE)
    await ezsp_.connect(usb_path, baudrate)

    database = config[DOMAIN].get(CONF_DATABASE)
    APPLICATION_CONTROLLER = ControllerApplication(ezsp_, database)
    listener = ApplicationListener(hass, config)
    APPLICATION_CONTROLLER.add_listener(listener)
    await APPLICATION_CONTROLLER.startup(auto_form=True)

    listener.component = component = EntityComponent(_LOGGER, DOMAIN, hass, datetime.timedelta(minutes=1))
    zha_controller = zha_state(hass, ezsp_, APPLICATION_CONTROLLER, 'controller', 'Init')
    listener.controller = zha_controller
    listener.registry = await hass.helpers.device_registry.async_get_registry()
    await component.async_add_entities([zha_controller])
    zha_controller.async_schedule_update_ha_state()
#    await asyncio.sleep(5)
    for device in APPLICATION_CONTROLLER.devices.values():
        hass.async_add_job(listener.async_device_initialized(device, False))
        await asyncio.sleep(0.1)

    async def permit(service):
        """Allow devices to join this network."""
        duration = service.data.get(ATTR_DURATION)
        _LOGGER.info("Permitting joins for %ss", duration)
        zha_controller._state = 'Permit'
        zha_controller.async_schedule_update_ha_state()
        await APPLICATION_CONTROLLER.permit(duration)

        async def _async_clear_state(entity):
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
        ieee_list = []
        ieee = service.data.get(ATTR_IEEE)
        nwk = service.data.get(ATTR_NWKID)
        if ieee == '' and nwk is None:
            _LOGGER.debug("service remove device str empty")
            return
        _LOGGER.debug("service remove device str: %s",  ieee if ieee else nwk)
        for device in APPLICATION_CONTROLLER.devices.values():
            if (ieee in str(device._ieee) and ieee != '') or nwk == device.nwk:
                ieee_list.append(device.ieee)
        for device in ieee_list:
            await APPLICATION_CONTROLLER.remove(device)

    hass.services.async_register(DOMAIN, SERVICE_REMOVE, remove,
                                 schema=SERVICE_SCHEMAS[SERVICE_REMOVE])

    async def command(service):
        listener.command(service.data)
#    hass.services.async_register(DOMAIN, SERVICE_COMMAND, command,
#                                 schema=SERVICE_SCHEMAS[SERVICE_COMMAND])

    async def mc_command(service):
        listener.mc_command(service.data)
    hass.services.async_register(DOMAIN, SERVICE_MC_COMMAND, mc_command,
                                 schema=SERVICE_SCHEMAS[SERVICE_MC_COMMAND])
                                 
    async def async_handle_light_step_up_service(service, *args, **kwargs):
        _LOGGER.debug("called service light_step_up %s %s", args, kwargs)
        return

    hass.services.async_register(
        DOMAIN, SERVICE_COLORTEMP_STEP_UP, async_handle_light_step_up_service,
        schema=SERVICE_SCHEMAS[SERVICE_COLORTEMP_STEP])
        
    zha_controller._state = "Run"
    zha_controller.async_schedule_update_ha_state()
    return True


class ApplicationListener:

    """All handlers for events that happen on the ZigBee application."""

    def __init__(self, hass, config):
        """Initialize the listener."""
        self._hass = hass
        self._config = config
        self.registry = None
        hass.data[DISCOVERY_KEY] = hass.data.get(DISCOVERY_KEY, {})
        hass.data[DISCOVERY_KEY][ENTITY_STORE] = hass.data[DISCOVERY_KEY].get(
            ENTITY_STORE,
            {})
        self.controller = None
        self._entity_list = dict()
        self.device_store = []
        self.mc_subscribers = {}
        self.custom_devices = {}
        self._groups = set()
        
    def device_updated(self,  device):
        pass 

    async def mc_command(data):
        
        
        
        return
        
    def subscribe_group(self, group_id):
        # keeps a list of susbcribers,
        # forwardrequest to zigpy if a group is new, otherwise do nothing
        _LOGGER.debug("received subscribe group: %s", group_id)
        if group_id in self._groups:
            return
        self._hass.async_add_job(
            APPLICATION_CONTROLLER.subscribe_group(group_id))
        #create dummy device
        
#        mdev = z.device.Device(self,  0, group_id)
#        mdev.add_endpoint(1)
#        mdev.endpoint[1].profile = z.profiles.zha.PROFILE_ID
#        for cluster_id in (0x0003, 0x0004, 0x0005, 0x0006, 0x0008, 0x0300):
#            mdev.endpoint[1].in_clusters[cluster_id] = cluster \
#                = z.zcl.Cluster.from_id(
#                    mdev.add_endpoint[1], 
#                    cluster_id
#                )
#            if hasattr(cluster, 'ep_attribute'):
#                mdev.endpoint[1]._cluster_attr[cluster.ep_attribute] = cluster
#        discovery_info = {
#            'device': mdev, 
#            'group_id': group_id}
#        entity = MEntity(discovery_info)
        self._groups.add(group_id)
        
        

    def unsubscribe_group(self, group_id):
        # keeps a list of susbcribers,
        # forwardrequest to zigpy if last subscriber is gone, otherwise do nothing
        self._hass.async_add_job(
            APPLICATION_CONTROLLER.unsubscribe_group(group_id))

    def device_removed(self,  device):
        """Remove related entities from HASS."""
        entity_store = get_entity_store(self._hass)
        _LOGGER.debug("remove %s", device._ieee)
        _LOGGER.debug("No of entities:%s",  len(entity_store))
        if device._ieee in entity_store:
            for dev_ent in entity_store[device._ieee]:
                _LOGGER.debug("remove entity %s", dev_ent.entity_id)
#                self._entity_list.pop(dev_ent.entity_id,  None)
                self._hass.async_add_job(dev_ent.async_remove())
            entity_store.pop(device._ieee)
                # cleanup Discovery_Key
        for dev_ent in list(self._hass.data[DISCOVERY_KEY]):
            if str(device._ieee) in dev_ent:
                self._hass.data[DISCOVERY_KEY].pop(dev_ent)

    def device_joined(self, device):
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
        _LOGGER.debug("Device initialized: %s:", device._ieee)
        self._hass.async_add_job(self.async_device_initialized(device, True))

    def device_left(self, device):
        self.controller._state = 'Left ' + str(device._ieee)
        self.controller.async_schedule_update_ha_state()

        async def _async_clear_state(entity):
            entity._state = 'Run'
            entity.async_schedule_update_ha_state()
        async_track_point_in_time(
            self.controller.hass, _async_clear_state(self.controller),
            dt_util.utcnow() + datetime.timedelta(seconds=5))

    async def async_device_initialized(self, device, join):
        """Handle device joined and basic information discovered (async)."""
        import zigpy.profiles
        populate_data()
        discovered_info = {}
        out_clusters = []
        primary_cluster = None
        # loop over endpoints

        if join:
            for endpoint_id, endpoint in device.endpoints.items():
                if endpoint_id == 0:  # ZDO
                    continue
                if 0 in endpoint.in_clusters:
                    discovered_info = await _discover_endpoint_info(endpoint)
                    device.model = device.model if device.model else discovered_info.get(CONF_MODEL, device.model)
                    device.manufacturer = discovered_info.get(CONF_MANUFACTURER, device.manufacturer)
        _LOGGER.debug("[0x%04x] device init for %s(%s)(%s) -> Endpoints: %s, %s ",
                      device.nwk,  type(device.model),  device.model,  device.ieee, list(device.endpoints.keys()),
                      "new join" if join else "already joined")
        for endpoint_id, endpoint in device.endpoints.items():
            _LOGGER.debug("[0x%04x:%s] endpoint init", device.nwk, endpoint_id, )
            if endpoint_id == 0:  # ZDO
                continue

            component = None
            profile_clusters = [set(), set()]
            device_key = '%s-%s' % (str(device.ieee), endpoint_id)
            node_config = self._config[DOMAIN][CONF_DEVICE_CONFIG].get(device_key, {})
            _LOGGER.debug("[0x%04x:%s] node config for %s: %s",
                          device.nwk,
                          endpoint_id,
                          device_key,
                          node_config)

            if CONF_TEMPLATE in node_config:
                device.model = node_config.get(CONF_TEMPLATE, "default")
                if device.model not in self.custom_devices:
                    self.custom_devices[device.model] = custom_module = get_custom_device_info(device.model)
                else:
                    custom_module = self.custom_devices[device.model]
                if '_custom_endpoint_init' in custom_module:
                    custom_module['_custom_endpoint_init'](endpoint, node_config,  device.model)

            discovered_info = {CONF_MODEL: device.model,
                               CONF_MANUFACTURER: device.manufacturer}
            if CONF_MANUFACTURER in node_config:
                discovered_info[CONF_MANUFACTURER] = device.manufacturer = node_config[CONF_MANUFACTURER]
            if CONF_MODEL in node_config:
                discovered_info[CONF_MODEL] = device.model = node_config[CONF_MODEL]
#               when a model name is available and not the template already applied,
#               use it to do custom init
            if (device.model and CONF_TEMPLATE not in node_config):
                if device.model not in self.custom_devices:
                    self.custom_devices[device.model] = custom_module = get_custom_device_info(device.model)
                else:
                    custom_module = self.custom_devices[device.model]
                _LOGGER.debug('[0x%04x:%s] pre call _custom_endpoint_init: %s',
                              device.nwk, endpoint_id,
                              custom_module)

                if custom_module.get('_custom_endpoint_init', None) is not None:
                    _LOGGER.debug('[0x%04x:%s] call _custom_endpoint_init: %s',
                                  device.nwk,
                                  endpoint_id,
                                  device.model)
                    custom_module['_custom_endpoint_init'](endpoint, node_config, device.model)
                else:
                    _LOGGER.debug('[0x%04x:%s] no call _custom_endpoint_init: %s',
                                  device.nwk,
                                  endpoint_id,
                                  device.model)

            _LOGGER.debug("[0x%04x:%s] node config for %s: %s",
                          device.nwk,
                          endpoint_id,
                          device_key,
                          node_config)

            if endpoint.profile_id in zigpy.profiles.PROFILES:
                profile = zigpy.profiles.PROFILES[endpoint.profile_id]
                if DEVICE_CLASS.get(endpoint.profile_id, {}).get(endpoint.device_type, None):
                    profile_clusters[0].update(profile.CLUSTERS[endpoint.device_type][0])
                    profile_clusters[1].update(profile.CLUSTERS[endpoint.device_type][1])
                    profile_info = DEVICE_CLASS[endpoint.profile_id]
                    component = profile_info[endpoint.device_type]
            # Override type (switch,light,sensor, binary_sensor,...) from config
            if ha_const.CONF_TYPE in node_config:
                component = node_config[ha_const.CONF_TYPE]
            if component in COMPONENT_CLUSTERS:
                profile_clusters = list(COMPONENT_CLUSTERS[component])

            # Add allowed In_Clusters from config
            if CONF_IN_CLUSTER in node_config:
                profile_clusters[0] = set(node_config.get(CONF_IN_CLUSTER))
            # Add allowed Out_Clusters from config
            if CONF_OUT_CLUSTER in node_config:
                profile_clusters[1] = set(node_config.get(CONF_OUT_CLUSTER))

            # if reporting is configured in yaml,
            # then create cluster if needed and setup reporting
            if join and CONF_CONFIG_REPORT in node_config:
                for report in node_config.get(CONF_CONFIG_REPORT):
                    report_cls, report_attr, report_min, report_max, report_change = report[0:5]
                    mfgCode = None if not report[5:] else report[5]
                    if report_cls in endpoint.in_clusters:
                        cluster = endpoint.in_clusters[report_cls]
                        await req_conf_report(
                            cluster,
                            report_attr,
                            report_min,
                            report_max,
                            report_change,
                            mfgCode=mfgCode)
            else:
                _LOGGER.debug("[0x%04x:%s] config reports skipped for %s, %s ",
                              device.nwk,
                              endpoint_id,
                              device._ieee,
                              "no reports configured" if join else "already joined")

            _LOGGER.debug("[0x%04x:%s] 2:profile %s, component: %s cluster:%s in_clusters: %s",
                          device.nwk,
                          endpoint_id,
                          endpoint.profile_id,
                          component,
                          profile_clusters, 
                          endpoint.in_clusters)
            
            in_clusters = set(endpoint.in_clusters.keys())
            out_clusters = set(endpoint.out_clusters.keys())
            sc = {cluster.cluster_id for cluster in SINGLE_CLUSTER_DEVICE_CLASS}
            c_intersect= in_clusters & sc
            _LOGGER.debug('[0x%04x:%s] Single Cluster: %s', 
                        device.nwk,  endpoint_id, c_intersect)
            primary_cluster = node_config.get('primary_cluster')
            if len(c_intersect)>1:
                if primary_cluster:
                    try:
                        c_intersect.remove(primary_cluster)
                    except Excecution:
                        pass
                else:
                        primary_cluster = sorted(list(c_intersect))[0]
                        c_intersect.remove(primary_cluster)
            else:
                c_intersect = set()
                
            
            if component:
            # allow all clusters to be used
                # only discovered clusters that are in the profile or configuration listed
#                in_clusters = [endpoint.in_clusters[c]
#                               for c in profile_clusters[0]
#                               if c in endpoint.in_clusters]
#                out_clusters = [endpoint.out_clusters[c]
#                                for c in profile_clusters[1]
#                                if c in endpoint.out_clusters]
                in_clusters -= c_intersect

                _LOGGER.debug("[0x%04x:%s]general entity:%s, component:%s clusters:%s<->%s",
                          device.nwk,
                          endpoint_id,
                          endpoint.profile_id,
                          component,
                          in_clusters,
                          out_clusters,
                          )                
                if in_clusters != [] or out_clusters != []:

                    # create  discovery info
                    discovery_info = {
                        'endpoint': endpoint,
                        'in_clusters': {c: endpoint.in_clusters[c] for c in in_clusters},
                        'out_clusters': {c: endpoint.out_clusters[c] for c in out_clusters},
                        'component': component,
                        'device': device,
                        'discovery_key': device_key,
                        'new_join': join,
                        'application': self,
                        'model': device.model,
                        'manufacturer': device.manufacturer,
                    }

                    self._hass.data[DISCOVERY_KEY][device_key] = discovery_info
                    """ goto to the specific code for switch,
                    light sensor or binary_sensor """
                    await discovery.async_load_platform(
                        self._hass,
                        component,
                        DOMAIN,
                        {'discovery_key': device_key},
                        self._config,
                    )
                    _LOGGER.debug("[0x%04x:%s] Create general entity:%s",
                                  device.nwk,
                                  endpoint_id,
                                  device._ieee)

            # initialize single clusters
            for cluster in c_intersect:
#                if ha_const.CONF_TYPE in node_config:
#                    component = node_config[ha_const.CONF_TYPE]
#                else:
                component = SINGLE_CLUSTER_DEVICE_CLASS[type(endpoint.in_clusters[cluster])]
                _LOGGER.debug("[0x%04x:%s] Create single-cluster entity: %s",
                              device.nwk,
                              endpoint_id,
                              cluster)
                cluster_key = '%s-%s' % (device_key, cluster)
                # cluster key -> single cluster
                discovery_info = {
                    'discovery_key': cluster_key,
                    'endpoint': endpoint,
                    'in_clusters': {cluster: endpoint.in_clusters[cluster]},
                    'out_clusters': {},
                    'new_join': join,
                    #                    'platform': PLATFORM,
                    'component': component,
                    'application': self
                }
                discovery_info.update(discovered_info)

                self._hass.data[DISCOVERY_KEY][cluster_key] = discovery_info
                
                await discovery.async_load_platform(
                            self._hass,
                            component,
                            DOMAIN,
                            {'discovery_key': cluster_key},
                            self._config,
                            )

        device._application.listener_event('device_updated', device)
        self.controller._state = 'Run'
        self.controller.async_schedule_update_ha_state()
        _LOGGER.debug("[0x%04x] Exit device init %s",
                      device.nwk,
                      device.ieee,
                      )

    async def command(self, service_data):
        command = service_data.get(ATTR_COMMAND)
        entity_id = service_data.get(ATTR_ENTITY_ID)
        entity = self._entity_list.get(entity_id, None)
        if not entity:
            _LOGGER.warn("entity %s unknown", entity_id)
            return
        if command == 'write_attribute':
            try:
                # expect cluster, attribute + value as minimal input
                cluster = service_data.get('cluster')
                attribute = service_data.get('attribute')
                value = service_data.get('value')
                mgfid = service_data.get('mfgid',)
            except KeyError:
                pass

                # Todo
                # find  entity for entity_id
                # get endpoint for entity
                #write attribute to endpoint



class Entity(RestoreEntity):

    """A base class for ZHA entities."""

    _domain = None  # Must be overridden by subclasses

    def __init__(self, endpoint, in_clusters, out_clusters, manufacturer,
                 model, **kwargs):
        """Init ZHA entity."""
        self._device_state_attributes = {}
        self.entity_connect = {}
        self.sub_listener = dict()
        self._device_class = None
        self._groups = None

        ieeetail = ''.join([
            '%02x' % (o, ) for o in endpoint.device.ieee[-4:]
        ])
        self.uid = str(endpoint.device._ieee) + "_" + str(endpoint.endpoint_id)
        if 'cluster_key' in kwargs:
            self.cluster_key = kwargs['cluster_key']
            self.uid += '_'
            self.uid += self.cluster_key
        if 'application' in kwargs:
            self._application = kwargs['application']
#            self._application._entity_list[self.entity_id] = self
#        self.platform = kwargs['platform']
        if model in self._application.custom_devices:
            self._custom_module = self._application.custom_devices[model]
        else:
            self._custom_module = {}
        if manufacturer is None:
            manufacturer = 'unknown'
        if model is None:
            model = 'unknown'

        self.entity_id = '%s.%s_%s_%s_%s' % (
            self._domain,
            slugify(manufacturer),
            slugify(model),
            ieeetail,
            endpoint.endpoint_id,
        )
        self.device = endpoint.device

        self._device_state_attributes['friendly_name'] = '%s %s' % (
            manufacturer,
            model,
        )
        self._device_state_attributes['model'] = model
        self._device_state_attributes['manufacturer'] = manufacturer
        self._model = model
        self._manufacturer = manufacturer

#        else:
#            self.entity_id = "%s.zha_%s_%s" % (
#                self._domain,
#                ieeetail,
#                endpoint.endpoint_id,
#            )
        if 'cluster_key' in kwargs:
            self.entity_id += '_'
            self.entity_id += kwargs['cluster_key']
            self._device_state_attributes['friendly_name'] += '_'
            self._device_state_attributes['friendly_name'] += kwargs['cluster_key']

        self._endpoint = endpoint
        self._in_clusters = in_clusters
        self._out_clusters = out_clusters
        self._state = None
        self._device_state_attributes['lqi'] = endpoint.device.lqi
        self._device_state_attributes['rssi'] = endpoint.device.rssi
        self._device_state_attributes['last seen'] = None
        self._device_state_attributes['nwk'] = endpoint.device.nwk
        self._device_state_attributes['path'] = 'unknown'
#        _LOGGER.debug("dir entity:%s",  dir(self))
        if self._custom_module.get('_parse_attribute', None):
            self._parse_attribute = self._custom_module['_parse_attribute']
        if self._custom_module.get('_custom_cluster_command', None):
            self._custom_cluster_command = self._custom_module['_custom_cluster_command']
        if self._custom_module.get('_custom_endpoint_init', None):
            self._custom_endpoint_init = self._custom_module['_custom_endpoint_init']

    @property
    def name(self):
        return self.entity_id

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return str(self._device_class)

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
        _LOGGER.debug("Cluster received: \n entity - \n command_id: %s \n args: %s",
                      self.entity_id, command_id, args)

    """dummy function; override from device handler"""
    def _custom_cluster_command(self, *args, **kwargs):
        return(args,  kwargs)

    """dummy function; override from device handler"""
    def _parse_attribute(self, *args, **kwargs):
        _LOGGER.debug(" dummy parse_attribute called with %s %s", args, kwargs)
        return(args,  kwargs)

    def _custom_endpoint_init(self, *args, **kwargs):
        """dummy function; override from device handler."""
        pass

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        self._device_state_attributes.update({
            'lqi': self._endpoint.device.lqi,
            'rssi': self._endpoint.device.rssi,
            'nwk': self._endpoint.device.nwk,
            'path': self._endpoint.device.path,
            'last seen': self._endpoint.device.last_seen,
            })
        return self._device_state_attributes

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        data = self._restore_data = await self.async_get_last_state()
        self._application._entity_list[self.entity_id] = self
        _LOGGER.debug("entity_list added: %s",  self._application._entity_list)
        try:
            _LOGGER.debug("Restore state for %s:",  self.entity_id)
            if data is not None and data.state:
                if (data.state == '-') or (data.state == ha_const.STATE_UNKNOWN):
                    self._state = None 
                elif hasattr(self,  'state_div'):
                    self._state = float(data.state) * self.state_div
                else:
                    self._state = 1 if data.state == ha_const.STATE_ON else 0
 
 #           self._device_state_attributes.update(data.attributes)
            self._device_state_attributes.pop('assumed_state',  None)
            self.device_state_attributes.pop('brightness', None)
            if not self._groups:
                self._groups = data.attributes.get("Group_id", list())
            for group in self._groups:
                self._endpoint._device._application.listener_event(
                                'subscribe_group',
                                group)
            self._device_state_attributes['Group_id'] = self._groups
        except Exception as e:
            _LOGGER.exception('Restore failed for %s: %s', self.entity_id, e)

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return False

    async def async_will_remove_from_hass(self) -> None:
        """ Run when entity will be removedd from hass."""
        await super().async_will_remove_from_hass()
        try:
            self._application._entity_list.pop(self.entity_id)
        except KeyError:
            pass

    @property
    def device_info(self):
        return{
            'connections': {(CONNECTION_ZIGBEE, self._endpoint.device._ieee)},
            'identifiers': {(DOMAIN, self._endpoint.device._ieee)},
            'model': self._model,
            'manufacturer': self._manufacturer,
        }

class MEntity(Entity):
    
    """ A dummy entity for multicasts. """
    def __init__(self, **dicovery_info):
        
        """Init ZHA entity."""
        in_clusters = entity_.out_clusters
        out_clusters = ()
        self._supported_features = 0b00111111
        self._available = True
        self._assumed = False
        self._device_class = None      
        self.uid = 'zha_group_sender'
        self.manufacturer = 'YODA'
        self.model = 'zha_group_sender'
        if 'application' in kwargs:
            self._application = kwargs['application']
        self._hidden= True

        self.entity_id = '%s.MC_%s' % (
            self._domain,
            slugify(group_id), 
        )
#        self.device = endpoint.device 

        self._device_state_attributes['friendly_name'] = '%s %s' % (
            self.manufacturer,
            self.model,
        )
        self._device_state_attributes['model'] = self.model
        self._device_state_attributes['manufacturer'] = self.manufacturer


        self._endpoint = endpoint
        self._in_clusters = in_clusters
        self._out_clusters = out_clusters
        self._state = True

async def _discover_endpoint_info(endpoint):
    import string
    """Find some basic information about an endpoint."""
    extra_info = {
        'manufacturer': None,
        'model': None,
        }

    async def read(attributes):
        """Read attributes and update extra_info convenience function."""
        result, _ = await endpoint.in_clusters[0].read_attributes(
            attributes,
            allow_cache=False,
        )
        extra_info.update(result)
        _LOGGER.debug("read attribute: %s", result)

#    try:
#        await read(['model','manufacturer'])
#    except:
#        _LOGGER.debug("read attribute failed: mode/manufacturer")
    try:
        await read(['model'])
    except Exception as e:
        _LOGGER.debug("single read attribute failed: model, %s", e)
    try:
        await read(['manufacturer'])
    except Exception as e:
        _LOGGER.debug("single read attribute failed: manufacturer, %s", e)
    for key, value in extra_info.items():
        _LOGGER.debug("%s: type(%s) %s", key, type(value), value)
        if isinstance(value, bytes):
            try:
                value = value.decode('ascii').strip()
                extra_info[key] = ''.join([x for x in value if x in string.printable])
                _LOGGER.debug("%s: type(%s) %s", key, type(extra_info[key]), extra_info[key])
            except UnicodeDecodeError as e:
                # Unsure what the best behaviour here is. Unset the key?
                _LOGGER.debug("unicode decode error, %s",  e)
    _LOGGER.debug("discover_endpoint_info:%s", extra_info)
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


async def attribute_read(endpoint, cluster, attributes):
    """Read attributes and update extra_info convenience fcunction."""
    result = await endpoint.in_clusters[cluster].read_attributes(
        attributes,
        allow_cache=True,
    )
    return result


async def get_battery(endpoint):
    if 1 not in endpoint.in_clusters:
        return 0xff
    battery = await attribute_read(endpoint, 0x0001, ['battery_voltage'])
    return battery[0]


async def discover_cluster_values(endpoint, cluster):
    attrids = [0, ]
    _LOGGER.debug("discover %s-%s for %s",
                  endpoint._device.ieee,
                  endpoint._endpoint_id,
                  cluster.cluster_id)
    try:
        v = await cluster.discover_attributes(0, 32)
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
        v = await cluster.read_attributes(attrids, allow_cache=True)
        _LOGGER.debug("attributes/values for cluster:%s", v[0])
    except:
        return({})
    return(v[0])

def get_custom_device_info(_model):
    custom_info = dict()

    try:
        dev_func = str(_model).lower().replace(".", "_").replace(" ", "_")
        device_module = import_module("custom_components.device." + dev_func)
        _LOGGER.debug("Import DH %s success", _model)
    except ImportError as e:
        _LOGGER.debug("Import DH %s failed: %s", _model, e.args)
        return {}
    custom_info['module'] = device_module
    custom_info['_custom_endpoint_init'] = getattr(
                                            device_module,
                                            '_custom_endpoint_init',
                                            None)
    custom_info['_custom_cluster_command'] = getattr(
                                            device_module,
                                            '_custom_cluster_command',
                                            None)
    custom_info['_parse_attribute'] = getattr(
                                            device_module,
                                            '_parse_attribute',
                                            None)
    custom_info['custom_parameters'] = getattr(
                                            device_module,
                                            'custom_parmeters',
                                            None)
    _LOGGER.debug('custom_info for %s: %s', _model, custom_info)
    return custom_info


def call_func(_model, function, *args):
    try:
        dev_func = _model.lower().replace(".", "_").replace(" ", "_")

        call_function = getattr(
            import_module("custom_components.device." + dev_func),
            function
            )
        return call_function(args)
    except ImportError as e:
        _LOGGER.debug("Import DH %s failed: %s", function, e.args)
    except Exception as e:
            _LOGGER.info("Excecution of DH %s failed: %s", dev_func, e.args)


async def req_conf_report(report_cls, report_attr, report_min, report_max, report_change, mfgCode=None):
        from zigpy.zcl.foundation import Status

        endpoint = report_cls._endpoint
        try:
            v = await report_cls.bind()
            if v[0] > 0:
                _LOGGER.debug("[0x%04x:%s:0x%04x]: bind failed: %s",
                              endpoint._device.nwk,
                              endpoint.endpoint_id,
                              report_cls.cluster_id,
                              Status(v[0]).name)
        except Exception as e:
            _LOGGER.debug("[0x%04x:%s:0x%04x]: : bind exceptional failed %s",
                          endpoint._device.nwk,
                          endpoint.endpoint_id,
                          report_cls.cluster_id,
                          e)
        try:
            v = await report_cls.configure_reporting(
                report_attr, int(report_min),
                int(report_max), report_change, manufacturer=mfgCode)
            _LOGGER.debug("[0x%04x:%s:0x%04x] set config report status: %s",
                          endpoint._device.nwk,
                          endpoint._endpoint_id,
                          report_cls.cluster_id,
                          v)
        except Exception as e:
            _LOGGER.error("[0x%04x:%s:0x%04x] set config report exeptional failed: %s",
                          endpoint._device.nwk,
                          endpoint.endpoint_id,
                          report_cls.cluster_id,
                          e)

class zha_state(entity.Entity):


    def __init__(self, hass, stack, application, name, state='Init'):
        self._device_state_attributes = {}
        self._device_state_attributes['friendly_name'] = 'Controller'
        self.hass = hass
        self._state = state
        self.entity_id = DOMAIN + '.' + name
        self.DOMAIN = DOMAIN
        self.stack = stack
        self.application = application

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return self._device_state_attributes

    @property
    def icon(self):
        if self._state == "Failed":
            return 'mdi:skull-crossbones'
        else:
            return 'mdi:emoticon-happy'

    async def async_update(self):
        result = await self.stack._command('neighborCount', [])
        self._device_state_attributes['neighborCount'] = result[0]
        entity_store = get_entity_store(self.hass)
        self._device_state_attributes['no_entities'] = len(entity_store)
        self._device_state_attributes['no_devices'] = len(self.application.devices)
#        result = await self.stack._command('getValue', 3)
#        _LOGGER.debug("buffer: %s", result[1])
        #        buffer = t.uint8_t(result[1])
#        self._device_state_attributes['FreeBuffers'] =  buffer
#        result = await self.stack._command('getSourceRouteTableFilledSize', [])
#        self._device_state_attributes['getSourceRouteTableFilledSize'] = result[0]
#        neighbors = await self.application.read_neighbor_table()
#        self._device_state_attributes['neighbors'] = neighbors
#        await self.application.update_topology()
        stats = self.application.stats()
        for key,  value in stats.items():
            self._device_state_attributes[key] = value
        status = self.application.status()
        self._device_state_attributes['status'] = status
        if (sum(status[0]) + sum(status[1]) > 0):
            self._state = "Failed"
        elif self._state == "Failed":
            self._state = "Run"
        self._device_state_attributes['Group_id'] = self.application._groups
