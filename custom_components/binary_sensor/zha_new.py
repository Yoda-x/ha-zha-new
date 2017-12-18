"""
Binary sensors on Zigbee Home Automation networks.
For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/binary_sensor.zha/
"""
import asyncio
import logging

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from custom_components import zha_new



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
        
    if discovery_info['new_join']:
        yield from cluster.bind()
        ieee = cluster.endpoint.device.application.ieee
        yield from cluster.write_attributes({'cie_addr': ieee})
        _LOGGER.debug("write cie done")

    try:
        _LOGGER.debug("try zone read")
        zone_type = yield from cluster['zone_type']
        _LOGGER.debug("done zone read")
        device_class = CLASS_MAPPING.get(zone_type, None)
    except Exception:  # pylint: disable=broad-except
        device_class="unknown"

    sensor = BinarySensor(device_class, **discovery_info)
    async_add_devices([sensor])
    endpoint._device._application.listener_event('device_updated', endpoint._device)
    _LOGGER.debug("Return from binary_sensor- ias cluster %s", endpoint.in_clusters)

class BinarySensor(zha_new.Entity, BinarySensorDevice):
    """THe ZHA Binary Sensor."""

    _domain = DOMAIN

    def __init__(self, device_class, **kwargs):
        """Initialize the ZHA binary sensor."""
        super().__init__(**kwargs)
        self._device_class = device_class
        from bellows.zigbee.zcl.clusters.security import IasZone
        self._ias_zone_cluster = self._in_clusters[IasZone.cluster_id]

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self._state == 'unknown':
            return False
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
        if attribute == 0:
            self._state = value
        else:
            self._device_state_attributes[attribute] = value
        
        self.schedule_update_ha_state()
        _LOGGER.debug("zha.binary_sensor update: %s = %s ", attribute, value)
