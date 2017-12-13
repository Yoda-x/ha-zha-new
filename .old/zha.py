"""
Binary sensors on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/binary_sensor.zha/
"""
import asyncio
import logging

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from homeassistant.components import zha
import bellows.zigbee.endpoint

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']

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
    discovery_info = zha.get_discovery_info(hass, discovery_info)
    _LOGGER.debug("discovery_info:%s", discovery_info)
    if discovery_info is None:
        return

    from bellows.zigbee.zcl.clusters.security import IasZone

    in_clusters = discovery_info['in_clusters']
    device_class = None
    endpoint=discovery_info['endpoint']
    cluster = endpoint.add_input_cluster(IasZone.cluster_id)
    in_clusters[IasZone.cluster_id] = cluster
    
    if discovery_info['new_join']:
        _LOGGER.debug("CLUSTER BIND")
        yield from cluster.bind()
        _LOGGER.debug("CLUSTER BIND DONE")
        ieee = cluster.endpoint.device.application.ieee
        _LOGGER.debug("CLUSTER WRITE")
        yield from cluster.write_attributes({'cie_addr': ieee})
        _LOGGER.debug("CLUSTER WRITE DONE")
        if 6 in endpoint.in_clusters:
            yield from endpoint.in_clusters[6].configure_reporting( 0, 1, 3600, '01')
        else:
            yield from endpoint.out_clusters[6].configure_reporting( 0, 1, 3600, '01')
        _LOGGER.debug("Config report")
 #       yield from e
    try:
        zone_type = yield from cluster['zone_type']
        device_class = CLASS_MAPPING.get(zone_type, None)
    except Exception:  # pylint: disable=broad-except
        # If we fail to read from the device, use a non-specific class
        pass
#    discovery_info = zha.get_discovery_info(hass, discovery_info)
    _LOGGER.debug("discovery_info:%s", discovery_info)
#    _LOGGER.debug("in.clusters:%s", endpoint.in_clusters)
    sensor = BinarySensor(device_class, **discovery_info)
    async_add_devices([sensor])


class BinarySensor(zha.Entity, BinarySensorDevice):
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
