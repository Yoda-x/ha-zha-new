"""
Binary sensors on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation

at https://home-assistant.io/components/binary_sensor.zha/

"""
import asyncio
import logging
import datetime
import homeassistant.util.dt as dt_util
from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
import custom_components.zha_new as zha_new
import custom_components.zha_new.helpers as helpers
from homeassistant.helpers.event import async_track_point_in_time
from zigpy.zdo.types import Status
from zigpy.zcl.clusters.general import LevelControl, OnOff, Scenes
from zigpy.zcl.clusters.lightlink import LightLink
from zigpy.zcl.clusters.general import Basic, PowerConfiguration
from zigpy.zcl.clusters.security import IasZone
from zigpy.zcl.clusters.measurement import OccupancySensing
from zigpy.zcl.clusters.measurement import TemperatureMeasurement
from .const import DOMAIN as PLATFORM
_LOGGER = logging.getLogger(__name__)
from custom_components.zha_new.cluster_handler import (
    Cluster_Server,
    Server_OnOff,
    Server_Scenes,
    Server_Basic,
    Server_LevelControl, 
    Server_IasZone, 
    Server_OccupancySensing, 
    Server_TemperatureMeasurement,
    Server_PowerConfiguration, 
    Server_LightLink, 
    )
# ZigBee Cluster Library Zone Type to Home Assistant device class
CLASS_MAPPING = {
    0x000d: 'motion',
    0x0015: 'opening',
    0x0028: 'smoke',
    0x002a: 'moisture',
    0x002b: 'gas',
    0x002d: 'vibration',
}


def setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    _LOGGER.debug("disocery info setup_platform: %s", discovery_info)

    return True


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the Zigbee Home Automation binary sensors."""
    discovery_info = zha_new.get_discovery_info(hass, discovery_info)

    if discovery_info is None:
        return

    in_clusters = discovery_info['in_clusters']
    endpoint = discovery_info['endpoint']
    application = discovery_info['application']
    device_class = None
#    groups = None

    if discovery_info['new_join']:
#        if 0x1000 in endpoint.in_clusters:
#            try:
#                groups = await  helpers.cluster_commisioning_groups(
#                    endpoint.in_clusters[0x1000])
#            except Exception as e:
#                _LOGGER.debug(
#                    "catched exception in commissioning group_id %s",  e)

        """ create ias cluster if it not already exists"""
        if IasZone.cluster_id not in in_clusters:
            cluster = endpoint.add_input_cluster(IasZone.cluster_id)
            in_clusters[IasZone.cluster_id] = cluster
            endpoint.in_clusters[IasZone.cluster_id] = cluster
        else:
            cluster = in_clusters[IasZone.cluster_id]
            await cluster.bind()

        try:
            ieee = cluster.endpoint.device.application.ieee
            result = await cluster.write_attributes({'cie_addr': ieee})
            _LOGGER.debug("write cie:%s", result)
        except Exception:
            _LOGGER.debug("bind/write cie failed")
        else:
            if not result:
                try:
                    await cluster.enroll_response(0, 0)
                except Exception:
                    _LOGGER.debug("send enroll_command failed")

                try:
                    _LOGGER.debug("try zone read")
                    zone_type = await cluster['zone_type']
                    _LOGGER.debug("done zone read")
                    device_class = CLASS_MAPPING.get(zone_type, None)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.debug("zone read failed")

#    discovery_info['groups'] = groups
    entity = await _make_sensor(device_class, discovery_info)

    # initialize/discover clusters 
    if discovery_info['new_join']:
        for CH in entity.sub_listener.values(): 
          await CH.join_prepare()

    e_registry = await hass.helpers.entity_registry.async_get_registry()
    reg_dev_id = e_registry.async_get_or_create(
            DOMAIN, PLATFORM, entity.uid,
            suggested_object_id=entity.entity_id,
            device_id=str(entity.device._ieee)
        )
    if entity.entity_id != reg_dev_id.entity_id and 'unknown' in reg_dev_id.entity_id:
        _LOGGER.debug("entity different name,change it: %s",  reg_dev_id)
        e_registry.async_update_entity(reg_dev_id.entity_id,
                                       new_entity_id=entity.entity_id)
    if reg_dev_id.entity_id in application._entity_list:
        _LOGGER.debug("entity exist,remove it: %s",  reg_dev_id)
        await application._entity_list.get(reg_dev_id.entity_id).async_remove()
    async_add_devices([entity])

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

    in_clusters = discovery_info['in_clusters']
    out_clusters = discovery_info['out_clusters']
    endpoint = discovery_info['endpoint']
    if endpoint.device_type in (
                0x0800,
                0x0810,
                0x0820,
                0x0830,
                0x0000,
                0x0001,
                0x0006,
                ):
        sensor = RemoteSensor('remote', **discovery_info)
    elif device_class == 'moisture':
        sensor = MoistureSensor('moisture', **discovery_info)
    elif device_class == 'motion':
        sensor = OccupancySensor('motion', **discovery_info)
    elif (OnOff.cluster_id in in_clusters
          or OnOff.cluster_id in out_clusters):
        sensor = OnOffSensor('opening',
                             **discovery_info,
                             cluster_key=OnOff.ep_attribute)
    elif (OccupancySensing.cluster_id in in_clusters
          or OccupancySensing.cluster_id in out_clusters):
        sensor = OccupancySensor('motion',
                                 **discovery_info,
                                 cluster_key=OccupancySensing.ep_attribute)
    else:
        sensor = BinarySensor(device_class, **discovery_info)

    if discovery_info['new_join']:
        for cluster in in_clusters.values():
            try:
                v = await cluster.bind()
            except Exception:
                v = [Status.TIMEOUT]
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

    _LOGGER.debug("[0x%04x:%s] exit make binary-sensor ",
                  endpoint._device.nwk,
                  endpoint.endpoint_id)
    return sensor

#########################################################
# Binary Sensor Classes ########################################


class BinarySensor(zha_new.Entity, BinarySensorDevice):

    """THe ZHA Binary Sensor."""

    _domain = DOMAIN
    value_attribute = 0

    def __init__(self, device_class, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(**kwargs)
        self._device_class = device_class
#        self._ias_zone_cluster = self._in_clusters[IasZone.cluster_id]
        endpoint = kwargs['endpoint']
        self._groups = kwargs.get('groups', None)
        in_clusters = kwargs['in_clusters']
        out_clusters = kwargs['out_clusters']
        clusters = list(out_clusters.items()) + list(in_clusters.items())
        _LOGGER.debug("[0x%04x:%s] initialize cluster listeners: -%s- ",
                      endpoint._device.nwk,
                      endpoint.endpoint_id,
                      clusters)

        for (_, cluster) in clusters:
            if LevelControl.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_LevelControl(
                                self, cluster, 'Level')
            elif OnOff.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_OnOff(
                                self, cluster, 'OnOff')
            elif Scenes.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_Scenes(
                                self, cluster, "Scenes")
            elif IasZone.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_IasZone(
                                self, cluster, "IasZone")
            elif Basic.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_Basic(
                                self, cluster, "Basic")
            elif OccupancySensing.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_OccupancySensing(
                                self, cluster, "OccupancySensing")
            elif TemperatureMeasurement.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_TemperatureMeasurement(
                                self, cluster, "TemperatureMeasurement")
            elif PowerConfiguration.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_PowerConfiguration(
                                self, cluster, "PowerConfiguration")
            elif LightLink.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_LightLink(
                                self, cluster, "LightLink")
                                
                                
            else:
                self.sub_listener[cluster.cluster_id] = Cluster_Server(
                                self, cluster, cluster.cluster_id)
        endpoint._device.zdo.add_listener(self)
#        asyncio.ensure_future(helpers.full_discovery(self._endpoint, timeout=10))

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return bool(self._state)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

#    def cluster_command(self, tsn, command_id, args):
#        """Handle commands received to this cluster."""
#        if command_id == 0:
#            self._state = args[0] & 3
#            _LOGGER.debug("Updated alarm state: %s", self._state)
#            self.schedule_update_ha_state()
#        elif command_id == 1:
#            _LOGGER.debug("Enroll requested")
#            self.hass.add_job(self._ias_zone_cluster.enroll_response(0, 0))

    def attribute_updated(self, attribute, value):
        _LOGGER.debug("Attribute received on entity: %s %s", attribute, value)
        (attribute, value) = self._parse_attribute(
                        self,
                        attribute,
                        value,
                        self._model,
                        cluster_id=None)
        if attribute == self.value_attribute:
            self._state = value
        self.schedule_update_ha_state()

    async def device_announce(self, *args,  **kwargs):
        _LOGGER.debug(
                "0x%04x device announce for BINARY_SENSOR received",
                self._endpoint._device.nwk
                )
#        asyncio.ensure_future(helpers.full_discovery(self._endpoint, timeout=14))
        if 0x1000 in self._endpoint.in_clusters:
            try:
                groups = await  helpers.cluster_commisioning_groups(
                    self._endpoint.in_clusters[0x1000],
                    timeout=10
                )
            except Exception as e:
                _LOGGER.debug("catched exception in commissioning group_id %s",  e)
            for group in groups:
                self._endpoint._device._application.listener_event(
                            'subscribe_group',
                            group)


class OccupancySensor(BinarySensor):

    """ ZHA Occupancy Sensor."""

    value_attribute = 0
    re_arm_sec = 20
    invalidate_after = None
    _state = 0

    def attribute_updated(self, attribute, value):
        """ handle trigger events from motion sensor.
        clear state after re_arm_sec seconds."""
        _LOGGER.debug("Attribute received: %s %s", attribute, value)
        (attribute, value) = self._parse_attribute(
                self,
                attribute,
                value,
                self._model,
                cluster_id=None,
            )

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
            self._device_state_attributes['last detection'] \
                = self.invalidate_after
            async_track_point_in_time(
                self.hass, _async_clear_state(self),
                self.invalidate_after)
        self.schedule_update_ha_state()


class OnOffSensor(BinarySensor):

    """ ZHA On Off Sensor."""

    value_attribute = 0
    cluster_default = 0x0006


class MoistureSensor(BinarySensor):

    """ ZHA Moisture Sensor."""

    value_attribute = 0


class RemoteSensor(BinarySensor):

    """Remote controllers."""

    def __init__(self, device_class, **kwargs):
        super().__init__(device_class, **kwargs)
        self._brightness = 0
        self._supported_features = 0

    def cluster_command(self, tsn, command_id, args):
        update_attrib = {}
        update_attrib['last seen'] = dt_util.now()
        self._entity._device_state_attributes.update({
                'last seen': dt_util.now(),
                self._identifier: self.value,
                'channels': list(c.identifier for c in self.sub_listener_out.items())
        })
        self._entity.schedule_update_ha_state()
        self.schedule_update_ha_state()
