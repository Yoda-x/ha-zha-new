"""
Binary sensors on Zigbee Home Automation networks.
For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/binary_sensor.zha/
"""
import asyncio
import logging
import datetime
from importlib import import_module
import homeassistant.util.dt as dt_util
from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from custom_components import zha_new
from homeassistant.helpers.event import track_point_in_time
from homeassistant.helpers.event import async_track_point_in_time


_LOGGER = logging.getLogger(__name__)
""" changed to zha-new to use in home dir """
DEPENDENCIES = ['zha_new']

# ZigBee Cluster Library Zone Type to Home Assistant device class
CLASS_MAPPING = {
    0x000d: 'motion',
    0x0015: 'opening',
    0x0028: 'smoke',
    0x002a: 'moisture',
    0x002b: 'gas',
    0x002d: 'vibration',
}


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Zigbee Home Automation binary sensors."""
    discovery_info = zha_new.get_discovery_info(hass, discovery_info)
    _LOGGER.debug("disocery info: %s", discovery_info)
    
    if discovery_info is None:
        return

    from bellows.zigbee.zcl.clusters.security import IasZone
    import bellows.zigbee.endpoint

    in_clusters = discovery_info['in_clusters']
    endpoint=discovery_info['endpoint']
    
    device_class = None
    """ create ias cluster if it not already exists"""
    
    if IasZone.cluster_id not in in_clusters:
        cluster = endpoint.add_input_cluster(IasZone.cluster_id)
        in_clusters[IasZone.cluster_id] = cluster
        endpoint.in_clusters[IasZone.cluster_id] = cluster
    else:
        cluster = in_clusters[IasZone.cluster_id]
    #yield from cluster.bind()    
    if discovery_info['new_join']:
        try:
            ieee = cluster.endpoint.device.application.ieee
            yield from cluster.write_attributes({'cie_addr': ieee})
            _LOGGER.debug("write cie done")
        except:
            _LOGGER.debug("bind/write cie failed")

        try:
            _LOGGER.debug("try zone read")
            zone_type = yield from cluster['zone_type']
            _LOGGER.debug("done zone read")
            device_class = CLASS_MAPPING.get(zone_type, None)
        except Exception:  # pylint: disable=broad-except
            #device_class='none'
            pass

    sensor = yield from _make_sensor(device_class, discovery_info)
    if hass.states.get(sensor.entity_id):
        _LOGGER.debug("entity exist,remove it: %s",  sensor.entity_id)
        hass.states.async_remove(sensor.entity_id)
    async_add_devices([sensor], update_before_add=False)
    endpoint._device._application.listener_event('device_updated', endpoint._device)
    _LOGGER.debug("Return from binary_sensor init-cluster %s", endpoint.in_clusters)

def _make_sensor(device_class, discovery_info):
    """Create ZHA sensors factory."""
    from bellows.zigbee.zcl.clusters.general import OnOff
    from bellows.zigbee.zcl.clusters.measurement import OccupancySensing
    

    in_clusters = discovery_info['in_clusters']
    endpoint = discovery_info['endpoint']
    
    if OnOff.cluster_id in in_clusters:
        sensor = OnOffSensor('opening', **discovery_info,   cluster_key = OnOff.ep_attribute)
    elif OccupancySensing.cluster_id in in_clusters:
        sensor = OccupancySensor('motion',**discovery_info, cluster_key = OccupancySensing.ep_attribute )
        try: 
            result = yield from zha_new.get_attributes(endpoint, OccupancySensing.cluster_id, ['occupancy', 'occupancy_sensor_type'])
            sensor._device_state_attributes['occupancy_sensor_type'] = result[1]
            sensor._state= result[0]
        except:
            _LOGGER.debug("get attributes: failed")
    elif device_class == 'moisture':
        sensor = MoistureSensor('moisture', **discovery_info)
        
    else:
        sensor = BinarySensor(device_class, **discovery_info)
    _LOGGER.debug("Return make_sensor")
    return sensor

def _parse_attribute(attrib, value):
    return(attrib, value)

class BinarySensor(zha_new.Entity, BinarySensorDevice):
    """THe ZHA Binary Sensor."""

    _domain = DOMAIN
    value_attribute = 0

    def __init__(self, device_class, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(**kwargs)
        self._device_class = device_class
        from bellows.zigbee.zcl.clusters.security import IasZone
        self._ias_zone_cluster = self._in_clusters[IasZone.cluster_id]
            
    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        #_LOGGER.debug("self_state: %s->%s", type(self._state), self._state)
        return bool(self._state)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    def cluster_command(self, aps_frame, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id == 0:
            self._state = args[0] & 3
            _LOGGER.debug("Updated alarm state: %s", self._state)
            self.schedule_update_ha_state()
        elif command_id == 1:
            _LOGGER.debug("Enroll requested")
            self.hass.add_job(self._ias_zone_cluster.enroll_response(0, 0))

    def attribute_updated(self, attribute, value):
        try:
            dev_func= self._model.replace(".","_").replace(" ","_")
            _parse_attribute = getattr(import_module("custom_components.device." + dev_func), "_parse_attribute")
            (attribute, value) = _parse_attribute(self,attribute, value, dev_func)
        except ImportError as e:
            _LOGGER.debug("Import DH %s failed: %s", dev_func, e.args)
        except Exception as e:
            _LOGGER.info("Excecution of DH %s failed: %s", dev_func, e.args)
   
        if attribute == 0:
            self._state = value
                
        self.schedule_update_ha_state()
        _LOGGER.debug("zha.binary_sensor update: %s = %s ", attribute, value)
    
class OccupancySensor(BinarySensor):
    """ ZHA Occupancy Sensor """
    value_attribute = 0
    re_arm_sec = 20
    invalidate_after = None
    _state = 0
    
    def attribute_updated(self, attribute, value):
        
        try:
            dev_func= self._model.replace(".","_")
            _parse_attribute = getattr(import_module("custom_components.device." + dev_func), "_parse_attribute")
            (attribute, value) = _parse_attribute(self, attribute, value, dev_func)
        except ImportError as e:
            _LOGGER.debug("Import DH %s failed: %s", dev_func, e.args)
        except Exception as e:
            _LOGGER.info("Excecution of DH %s failed: %s", dev_func, e.args)
                              
        """Handle attribute update from device."""
        
        
        """ handle trigger events from motion sensor, clear state after re_arm_sec seconds """
        _LOGGER.debug("Attribute updated: %s %s", attribute, value)
        if attribute == self.value_attribute:
            self._state = value
            
            """ clear state to False"""
            @asyncio.coroutine
            def _async_clear_state(entity):
                _LOGGER.debug("async_clear_state")
                if (entity.invalidate_after == None) or ( entity.invalidate_after < dt_util.utcnow()):
                    entity._state = bool(0)
        #            entity.invalidate_after=None
                    entity.schedule_update_ha_state()
                
        self.invalidate_after = dt_util.utcnow() + datetime.timedelta(
            seconds=self.re_arm_sec)
        self._device_state_attributes['last detection:'] = self.invalidate_after
        async_track_point_in_time(
            self.hass, _async_clear_state(self),
            self.invalidate_after)
        self.schedule_update_ha_state()
        
class OnOffSensor(BinarySensor):
    """ ZHA On Off Sensor """
    value_attribute = 0

class MoistureSensor(BinarySensor):
    """ ZHA On Off Sensor """
    value_attribute = 0
