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
from homeassistant.helpers.event import async_track_point_in_time
from zigpy.zdo.types import Status

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


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    from zigpy.zcl.clusters.security import IasZone
    """Set up the Zigbee Home Automation binary sensors."""
    discovery_info = zha_new.get_discovery_info(hass, discovery_info)
    _LOGGER.debug("disocery info: %s", discovery_info)

    if discovery_info is None:
        return

    in_clusters = discovery_info['in_clusters']

    endpoint = discovery_info['endpoint']

    device_class = None
    """ create ias cluster if it not already exists"""

    if IasZone.cluster_id not in in_clusters:
        cluster = endpoint.add_input_cluster(IasZone.cluster_id)
        in_clusters[IasZone.cluster_id] = cluster
        endpoint.in_clusters[IasZone.cluster_id] = cluster
    else:
        cluster = in_clusters[IasZone.cluster_id]
        await cluster.bind()
    if discovery_info['new_join']:
        try:
            ieee = cluster.endpoint.device.application.ieee
            await cluster.write_attributes({'cie_addr': ieee})
            _LOGGER.debug("write cie done")
        except:
            _LOGGER.debug("bind/write cie failed")

        try:
            _LOGGER.debug("try zone read")
            zone_type = await cluster['zone_type']
            _LOGGER.debug("done zone read")
            device_class = CLASS_MAPPING.get(zone_type, None)
        except Exception:  # pylint: disable=broad-except
            pass

    entity = await _make_sensor(device_class, discovery_info)
    if hass.states.get(entity.entity_id):
        _LOGGER.debug("entity exist,remove it: %s",  entity.entity_id)
        hass.states.async_remove(entity.entity_id)
    async_add_devices([entity], update_before_add=False)

    _LOGGER.debug("set Entity object: %s-%s ", type(entity), entity.unique_id)
    entity_store = zha_new.get_entity_store(hass)
    if endpoint.device._ieee not in entity_store:
        entity_store[endpoint.device._ieee] = []
    entity_store[endpoint.device._ieee].append(entity)

    endpoint._device._application.listener_event('device_updated',
                                                 endpoint._device)
    _LOGGER.debug("Return binary_sensor init-cluster %s", endpoint.in_clusters)


async def _make_sensor(device_class, discovery_info):
    """Create ZHA sensors factory."""
    from zigpy.zcl.clusters.general import OnOff
    from zigpy.zcl.clusters.measurement import OccupancySensing

    in_clusters = discovery_info['in_clusters']
    out_clusters = discovery_info['out_clusters']
    endpoint = discovery_info['endpoint']

    if OnOff.cluster_id in in_clusters:
        sensor = OnOffSensor('opening',
                             **discovery_info,
                             cluster_key=OnOff.ep_attribute)
    elif OccupancySensing.cluster_id in in_clusters:
        sensor = OccupancySensor('motion',
                                 **discovery_info,
                                 cluster_key=OccupancySensing.ep_attribute)
        try:
            result = await zha_new.get_attributes(
                            endpoint,
                            OccupancySensing.cluster_id,
                            ['occupancy', 'occupancy_sensor_type'])
            sensor._device_state_attributes['occupancy_sensor_type'] = result[1]
            sensor._state = result[0]
        except:
            _LOGGER.debug("get attributes: failed")
    elif device_class == 'moisture':
        sensor = MoistureSensor('moisture', **discovery_info)
    elif endpoint.device_type in (0x0800, 0x0810, 0x0820, 0x0830):
        sensor = RemoteSensor(device_class, **discovery_info)
    else:
        sensor = BinarySensor(device_class, **discovery_info)

    if discovery_info['new_join']:
        for cluster in in_clusters.values():
            v = await cluster.bind()
            if v[0]:
                _LOGGER.error("[0x%04x:%s] bind input-cluster failed %s",
                              endpoint._device.nwk, endpoint.endpoint_id,
                              Status(v[0]).name
                              )
            _LOGGER.debug("[0x%04x:%s] bind input-cluster %s: %s",
                          endpoint._device.nwk,
                          endpoint.endpoint_id,
                          cluster.cluster_id,
                          v)
        for cluster in out_clusters.values():
            v = await cluster.bind()
            if v[0]:
                _LOGGER.error("[0x%04x:%s] bind output-cluster failed %s",
                              endpoint._device.nwk, endpoint.endpoint_id,
                              Status(v[0]).name
                              )
            _LOGGER.debug("[0x%04x:%s] bind output-cluster %s: %s",
                          endpoint._device.nwk,
                          endpoint.endpoint_id,
                          cluster.cluster_id,
                          v)

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
        from zigpy.zcl.clusters.security import IasZone
        self._ias_zone_cluster = self._in_clusters[IasZone.cluster_id]

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return bool(self._state)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    def cluster_command(self, tsn, command_id, args):
        """Handle commands received to this cluster."""
        if command_id == 0:
            self._state = args[0] & 3
            _LOGGER.debug("Updated alarm state: %s", self._state)
            self.schedule_update_ha_state()
        elif command_id == 1:
            _LOGGER.debug("Enroll requested")
            self.hass.add_job(self._ias_zone_cluster.enroll_response(0, 0))

    def attribute_updated(self, attribute, value):
        _LOGGER.debug('Binary sensor call _parse attribute: %s -- %s --%s',
                      self._custom_module,  attribute,  value)
        if self._custom_module.get('_parse_attribute', None) is not None:
            (attribute, value) = self._custom_module['_parse_attribute'](
                        self,
                        attribute,
                        value,
                        self._model)
#        else:
#            _LOGGER.debug('no call _parse attribute: %s', self._custom_module)

        if attribute == self.value_attribute:
            self._state = value

        self.schedule_update_ha_state()
        _LOGGER.debug("zha.binary_sensor update: %s = %s ", attribute, value)


class OccupancySensor(BinarySensor):

    """ ZHA Occupancy Sensor."""

    value_attribute = 0
    re_arm_sec = 20
    invalidate_after = None
    _state = 0

    def __init__(self, device_class, **kwargs):
        endpoint = kwargs['endpoint']
        super().__init__(device_class, **kwargs)
        for cluster in endpoint.out_clusters.values():
            cluster.add_listener(self)

    def attribute_updated(self, attribute, value):
        """ handle trigger events from motion sensor.
        clear state after re_arm_sec seconds."""
        _LOGGER.debug("Attribute updated: %s %s", attribute, value)
        if self._custom_module.get('_parse_attribute', None) is not None:
            (attribute, value) = self._custom_module[
                        '_parse_attribute'](self, attribute, value, self._model)

        @asyncio.coroutine
        def _async_clear_state(entity):
            _LOGGER.debug("async_clear_state")
            if (entity.invalidate_after is None
                    or entity.invalidate_after < dt_util.utcnow()):
                entity._state = bool(0)
                entity.schedule_update_ha_state()

        if attribute == self.value_attribute:
            self._state = value
            self.invalidate_after = dt_util.utcnow() + datetime.timedelta(
                seconds=self.re_arm_sec)
            self._device_state_attributes['last detection:'] \
                = self.invalidate_after
            async_track_point_in_time(
                self.hass, _async_clear_state(self),
                self.invalidate_after)
        self.schedule_update_ha_state()


class OnOffSensor(BinarySensor):

    """ ZHA On Off Sensor."""

    value_attribute = 0

    def __init__(self, device_class, **kwargs):
        super().__init__(device_class, **kwargs)
        endpoint = kwargs['endpoint']

        for cluster in endpoint.out_clusters.values():
            cluster.add_listener(self)


class MoistureSensor(BinarySensor):

    """ ZHA On Off Sensor."""

    value_attribute = 0

    def __init__(self, device_class, **kwargs):
        endpoint = kwargs['endpoint']
        super().__init__(device_class, **kwargs)
        for cluster in endpoint.out_clusters.values():
            cluster.add_listener(self)


class Cluster_Server(object):
    def __init__(self, entity,  cluster,  identifier):
        self._cluster = cluster
        self._entity = entity
        self._identifier = identifier
        cluster.add_listener(self)
        self._value = int(0)
        self.value = int()
        self._prev_tsn = int()

    def cluster_command(self, tsn, command_id, args):
        _LOGGER.debug('cluster command receicved:[%s]:%s',
                      command_id,
                      args
                      )


class Basic(Cluster_Server):
    def cluster_command(self, tsn, command_id, args):
        from zigpy.zcl.clusters.general import Basic
        if tsn == self._prev_tsn:
            return
        self._prev_tsn = tsn
        command = Basic.server_commands.get(command_id, ('unknown', ))
        event_data = {
                    'entity_id': self._entity.entity_id,
                    'channel': self._identifier,
                    'command': command
                   }
        self._entity.hass.bus.fire('click', event_data)
        _LOGGER.debug('click event [tsn:%s] %s', tsn, event_data)
        self._entity._device_state_attributes.update({
                'Last seen': dt_util.now(),
                'Last command': command
        })
        self._entity.schedule_update_ha_state()


class Server_LevelControl(Cluster_Server):
    def cluster_command(self, tsn, command_id, args):
        from zigpy.zcl.clusters.general import LevelControl
        if tsn == self._prev_tsn:
            return
        self._prev_tsn = tsn
        command = LevelControl.server_commands.get(command_id, ('unknown', ))[0]
        event_data = {
                    'entity_id': self._entity.entity_id,
                    'channel': self._identifier,
                    'command': command
                   }
        if args[0] == 0:
            event_data['up_down'] = 1
        else:
            event_data['up_down'] = -1
        event_data['step'] = args[1]
        if command in ('move_with_on_off', 'move', 'step', 'step_with_on_off'):
            self._value += event_data['up_down'] * event_data['step']
            if self._value <= 0:
                self.value = 0
                self._value = -10
            elif self._value > 1000:

                self._value = 1000
                self.value = 100
            else:
                self.value = int(self._value/10)
#        elif command == 'move_to_level_with_on_off':
#            self.value = self._value
        elif command == 'stop':
            return

        self._entity.hass.bus.fire('click', event_data)
#        _LOGGER.debug('click event [tsn:%s] %s', tsn, event_data)
        self._entity._device_state_attributes.update({
                'Last seen': dt_util.now(),
                self._identifier: self.value,
                'Last command': command
        })
        self._entity.schedule_update_ha_state()


class Server_OnOff(Cluster_Server):
    def cluster_command(self, tsn, command_id, args):
        from zigpy.zcl.clusters.general import OnOff
        if tsn == self._prev_tsn:
            return
        self._prev_tsn = tsn
        command = OnOff.server_commands.get(command_id, ('unknown', ))[0]
        event_data = {
                    'entity_id': self._entity.entity_id,
                    'channel': self._identifier,
                    'command': command
                   }
        if command == 'on':
            self._value = 1
        elif command == 'off':
            self._value = 0
        elif command == 'toggle':
            self._value = int(abs(self._value - 1))
        self._entity._state = self._value
        self._entity.hass.bus.fire('click', event_data)
#        _LOGGER.debug('click event [tsn:%s] %s', tsn, event_data)
        self._entity._device_state_attributes.update({
                'Last seen': dt_util.now(),
                self._identifier: self._value,
                'Last command': command
        })
        self._entity.schedule_update_ha_state()


class Server_Scenes(Cluster_Server):
    def cluster_command(self, tsn, command_id, args):
        from zigpy.zcl.clusters.general import Scenes
        if tsn == self._prev_tsn:
            return
        self._prev_tsn = tsn
        command = Scenes.server_commands.get(command_id, ('unknown', ))[0]
        event_data = {
                    'entity_id': self._entity.entity_id,
                    'channel': self._identifier,
                    'command': command,
                    self._identifier: args
                   }
        self._entity.hass.bus.fire('click', event_data)
#        _LOGGER.debug('Scenes cluster called %s', event_data)
        self._entity._device_state_attributes.update({
                'Last seen': dt_util.now(),
                self._identifier: args,
                'Last command': command
        })
        self._entity.schedule_update_ha_state()


class RemoteSensor(BinarySensor):

    """Remote controllers."""

    def __init__(self, device_class, **kwargs):
        from zigpy.zcl.clusters.general import LevelControl, OnOff, Scenes
        super().__init__(device_class, **kwargs)
        self._brightness = 0
        self._supported_features = 0
        endpoint = kwargs['endpoint']
        self.sub_listener_out = {}
        for cluster in endpoint.out_clusters.values():
            if LevelControl.cluster_id == cluster.cluster_id:
                self.sub_listener_out[cluster.cluster_id] = Server_LevelControl(
                                self, cluster, 'Level')
            elif OnOff.cluster_id == cluster.cluster_id:
                self.sub_listener_out[cluster.cluster_id] = Server_OnOff(
                                self, cluster, 'OnOff')
            elif Scenes.cluster_id == cluster.cluster_id:
                self.sub_listener_out[cluster.cluster_id] = Server_Scenes(
                                self, cluster, "Scenes")
            else:
                cluster.add_listener(self)

    def cluster_command(self, tsn, command_id, args):
        update_attrib = {}
        update_attrib['Last seen'] = dt_util.now()
        self._entity._device_state_attributes.update({
                'Last seen': dt_util.now(),
                self._identifier: self.value,
                'channels': list(c.identifier for c in self.sub_listener_out.items())
        })
        self._entity.schedule_update_ha_state()
        self.schedule_update_ha_state()
