"""
Sensors on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/sensor.zha/

"""
import asyncio
import logging

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import TEMP_CELSIUS
from homeassistant.util.temperature import convert as convert_temperature
from custom_components import zha_new
from importlib import import_module

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha_new']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    from zigpy.zcl.clusters.security import IasZone
    """Set up Zigbee Home Automation sensors."""
    discovery_info = zha_new.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return
    endpoint = discovery_info['endpoint']
    in_clusters = discovery_info['in_clusters']

    """ create ias cluster if it not already exists"""
    if IasZone.cluster_id not in in_clusters:
        cluster = endpoint.add_input_cluster(IasZone.cluster_id)
        in_clusters[IasZone.cluster_id] = cluster
        endpoint.in_clusters[IasZone.cluster_id] = cluster
    else:
        cluster = in_clusters[IasZone.cluster_id]

    if discovery_info['new_join']:
        try:
            yield from cluster.bind()
            ieee = cluster.endpoint.device.application.ieee
            yield from cluster.write_attributes({'cie_addr': ieee})
            _LOGGER.debug("write cie done")
        except:
            _LOGGER.debug("bind/write cie failed")

    entity = yield from make_sensor(discovery_info)
    _LOGGER.debug("Create sensor.zha: %s", entity.entity_id)
    if hass.states.get(entity.entity_id):
        _LOGGER.debug("entity exist,remove it: %s",  entity.entity_id)
        hass.states.async_remove(entity.entity_id)

    async_add_devices([entity], update_before_add=False)
    endpoint._device._application.listener_event(
                    'device_updated', endpoint._device)
    entity_store = zha_new.get_entity_store(hass)
    if endpoint.device._ieee not in entity_store:
        entity_store[endpoint.device._ieee] = []
    entity_store[endpoint.device._ieee].append(entity)


@asyncio.coroutine
def make_sensor(discovery_info):
    """Create ZHA sensors factory."""
    from zigpy.zcl.clusters.measurement import TemperatureMeasurement
    from zigpy.zcl.clusters.measurement import RelativeHumidity
    from zigpy.zcl.clusters.measurement import PressureMeasurement
    from zigpy.zcl.clusters.measurement import IlluminanceMeasurement
    from zigpy.zcl.clusters.smartenergy import Metering

    in_clusters = discovery_info['in_clusters']
    endpoint = discovery_info['endpoint']

    if TemperatureMeasurement.cluster_id in in_clusters:
        sensor = TemperatureSensor(**discovery_info,
                                   cluster_key=TemperatureMeasurement.ep_attribute)
    elif RelativeHumidity.cluster_id in in_clusters:
        sensor = HumiditySensor(**discovery_info,
                                cluster_key=RelativeHumidity.ep_attribute)
    elif PressureMeasurement.cluster_id in in_clusters:
        sensor = PressureSensor(**discovery_info,
                                cluster_key=PressureMeasurement.ep_attribute)
    elif Metering.cluster_id in in_clusters:
        sensor = MeteringSensor(**discovery_info,
                                cluster_key=Metering.ep_attribute)
    elif IlluminanceMeasurement.cluster_id in in_clusters:
        sensor = IlluminanceSensor(**discovery_info,
                                   cluster_key=IlluminanceMeasurement.ep_attribute)
    else:
        sensor = Sensor(**discovery_info)

    _LOGGER.debug("Return make_sensor - %s", endpoint._device._ieee)
    return sensor


class Sensor(zha_new.Entity):

    """Base ZHA sensor."""

    _domain = DOMAIN
    value_attribute = 0
    min_reportable_change = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        out_clusters = kwargs['out_clusters']
        for cluster in out_clusters.values():
            cluster.add_listener(self)

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        if isinstance(self._state, float):
            return str(round(self._state, 2))
        return self._state

    def attribute_updated(self, attribute, value):
        if self._custom_module.get('_parse_attribute', None) is not None:
            (attribute, value) = self._custom_module[
                '_parse_attribute'](self, attribute, value, self._model)
        if attribute == self.value_attribute:
            self._state = value
        self.schedule_update_ha_state()


class TemperatureSensor(Sensor):

    """ZHA temperature sensor."""

    min_reportable_change = 20

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self.hass.config.units.temperature_unit

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state is None:
            return '-'
        celsius = round(float(self._state) / 100, 1)
        return convert_temperature(
            celsius, TEMP_CELSIUS, self.unit_of_measurement)


class HumiditySensor(Sensor):

    """ZHA  humidity sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measuremnt of this entity."""
        return "%"

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state is None:
            return '-'
        percent = round(float(self._state) / 100, 1)
        return percent


class PressureSensor(Sensor):

    """ZHA  pressure sensor."""

    min_reportable_change = 50

    @property
    def unit_of_measurement(self):
        """Return the unit of measuremnt of this entity."""
        return "hPa"

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state is None:
            return '-'

        return self._state


class IlluminanceSensor(Sensor):

    """ZHA  pressure sensor."""

    min_reportable_change = 5

    @property
    def unit_of_measurement(self):
        """Return the unit of measuremnt of this entity."""
        return "lx"

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state is None:
            return None
        return self._state


class MeteringSensor(Sensor):
    value_attribute = 0
    """ZHA  smart engery metering."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.meter_cls = self._endpoint.in_clusters[0x0702]

    @property
    def unit_of_measurement(self):
        """Return the unit of measuremnt of this entity."""
        return "kWh"

    @property
    def state(self):
        """Return the state of the entity."""
        if self._state is None:
            return "-"
        kwh = round(float(self._state) / 100, 2)
        return kwh

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.
        False if entity pushes its state to HA.
        """
        return False

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
#        ptr=0
#        #_LOGGER.debug("%s async_update", self.entity_id)
#      #  while len_v==1:
#        v = yield from self.meter_cls.discover_attributes(0, 32)
        attribs = [0, ]
#        for item in v[0]:
#            self.meter_attributes[item.attrid]=item.datatype
#            ptr=item.attrid + 1 if item.attrid > ptr else ptr
#        attribs.extend(list(self.meter_attributes.keys()))
#     #   _LOGGER.debug("query %s:", attribs)
#        #v = yield from self.meter_cls.read_attributes_raw(attribs)
        v = yield from self.meter_cls.read_attributes(attribs)
#     #   _LOGGER.debug("attributes for cluster:%s" , v[0])
        for attrid, value in v[0].items():
            if attrid == 0:
                self._state = value
#            attrid_record=Metering.attributes.get(attrid,None )
#            if attrid_record:
#                self._device_state_attributes[attrid_record[0]] = value
#            else:
#                self._device_state_attributes["metering_"+str(attrid)] = value
#        #self._state = v[0].value

    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        _LOGGER.debug("sensor cluster_command %s", command_id)
