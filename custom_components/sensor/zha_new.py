"""
Sensors on Zigbee Home Automation networks.
For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/sensor.zha/
"""
import asyncio
import logging
import time

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import TEMP_CELSIUS
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.helpers import discovery, entity
from custom_components import zha_new
from importlib import import_module

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha_new']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up Zigbee Home Automation sensors."""
    _LOGGER.debug("Enter sensor.zha: %s",discovery_info)
    discovery_info = zha_new.get_discovery_info(hass, discovery_info)
    endpoint=discovery_info['endpoint']
    _LOGGER.debug("Enter sensor.zha: %s",discovery_info)
    if discovery_info is None:
        return

    sensor = yield from make_sensor(discovery_info)
    _LOGGER.debug("Create sensor.zha: %s",sensor.entity_id)
    async_add_devices([sensor])
    endpoint._device._application.listener_event('device_updated', endpoint._device)


@asyncio.coroutine
def make_sensor(discovery_info):
    """Create ZHA sensors factory."""
    from bellows.zigbee.zcl.clusters.measurement import TemperatureMeasurement
    from bellows.zigbee.zcl.clusters.measurement import RelativeHumidity
    from bellows.zigbee.zcl.clusters.measurement import OccupancySensing
    

    in_clusters = discovery_info['in_clusters']
    endpoint = discovery_info['endpoint']
    
    if TemperatureMeasurement.cluster_id in in_clusters:
        sensor = TemperatureSensor(**discovery_info,cluster_key = TemperatureMeasurement.ep_attribute)
    elif RelativeHumidity.cluster_id in in_clusters:
        sensor = HumiditySensor(**discovery_info, cluster_key = RelativeHumidity.ep_attribute )
    elif OccupancySensing.cluster_id in in_clusters:
        sensor = OccupancySensor(**discovery_info, cluster_key = OccupancySensing.ep_attribute )
        try: 
            result = yield from zha_new.get_attributes(endpoint, OccupancySensing.cluster_id, ['occupancy',
                                                                                               'occupancy_sensor_type'])
            sensor._device_state_attributes['occupancy_sensor_type'] = result[1]
            sensor._state= result[0]
       
        except:
            _LOGGER.debug("get attributes: failed")
    else:
        sensor = Sensor(**discovery_info)

#    attr = sensor.value_attribute
#    if discovery_info['new_join']:
#        cluster = list(in_clusters.values())[0]
#        yield from cluster.bind()
#        yield from cluster.configure_reporting(
#            attr, 300, 600, sensor.min_reportable_change,
#        )
    _LOGGER.debug("Return make_sensor")
    
    
    
    return sensor

"""dummy function; override from device handler"""
def _parse_attribute(entity, attrib, value):
    return(attrib, value)

class Sensor(zha_new.Entity):
    """Base ZHA sensor."""

    _domain = DOMAIN
    value_attribute = 0
    min_reportable_change = 1

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        if isinstance(self._state, float):
            return str(round(self._state, 2))
        return self._state

    def attribute_updated(self, attribute, value):
        try:
            dev_func= self._model.replace(".","_")
            _parse_attribute = getattr(import_module("custom_components.device." + dev_func), "_parse_attribute")
        except ImportError:
            _LOGGER.debug("load module %s failed ", dev_func)

        (attribute, value) = _parse_attribute(self, attribute, value)
        """Handle attribute update from device."""
        _LOGGER.debug("Attribute updated: %s=%s",attribute, value)
        if attribute == self.value_attribute:
            self._state = value        
        self.schedule_update_ha_state()


class TemperatureSensor(Sensor):
    """ZHA temperature sensor."""
    from bellows.zigbee.zcl.clusters.measurement import TemperatureMeasurement
    
    min_reportable_change = 50  # 0.5'C

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self.hass.config.units.temperature_unit

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state == 'unknown':
            return '-'
        celsius = round(float(self._state) / 100, 1)
        return convert_temperature(
            celsius, TEMP_CELSIUS, self.unit_of_measurement)

class HumiditySensor(Sensor):
    """ZHA  humidity sensor."""

    min_reportable_change = 50  # 0.5 %

    @property
    def unit_of_measurement(self):
        """Return the unit of measuremnt of this entity."""
        return "%"

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state == 'unknown':
            return '-'
        percent = round(float(self._state) / 100, 1)
        return percent


