"""Switches on Zigbee Home Automation networks."""
import asyncio
import logging

from homeassistant.components.switch import DOMAIN, SwitchDevice
from custom_components import zha_new
from importlib import import_module

_LOGGER = logging.getLogger(__name__)

""" change to zha-new for use in home dir """
DEPENDENCIES = ['zha_new']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Zigbee Home Automation switches."""
    discovery_info = zha_new.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return
#    endpoint=discovery_info['endpoint']
    entity = Switch(**discovery_info)
    if hass.states.get(entity.entity_id):
        _LOGGER.debug("entity exist,remove it: %s",  entity.entity_id)
        hass.states.async_remove(entity.entity_id)
    add_devices([entity])
    endpoint = discovery_info['endpoint']

    entity_store = zha_new.get_entity_store(hass)
    if endpoint.device._ieee not in entity_store:
        entity_store[endpoint.device._ieee] = []
    entity_store[endpoint.device._ieee].append(entity)


class Switch(zha_new.Entity, SwitchDevice):

    """ZHA switch."""

    from zigpy.zcl.clusters.general import OnOff
    _domain = DOMAIN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        endpoint = kwargs['endpoint']
        for cluster in endpoint.out_clusters.values():
            cluster.add_listener(self)

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._state is None:
            return False
        return bool(self._state)

    def attribute_updated(self, attribute, value):
        _LOGGER.debug("attribute update: %s = %s ", attribute, value)
        try:
            dev_func = self._model.lower().replace(".", "_").replace(" ", "_")
            _parse_attribute = getattr(import_module(
                "custom_components.device." + dev_func), "_parse_attribute")
            (attribute, value) = _parse_attribute(
                self, attribute, value, dev_func)
        except ImportError as e:
            _LOGGER.debug("Import DH %s failed: %s", dev_func, e.args)
        except Exception as e:
            _LOGGER.info("Excecution of DH %s failed: %s", dev_func, e.args)
        if attribute == 0:
            self._state = bool(value)
        _LOGGER.debug("attribute update: %s = %s ", attribute, value)
        self.schedule_update_ha_state()

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        yield from self._endpoint.on_off.on()
        self._state = 1

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        yield from self._endpoint.on_off.off()
        self._state = 0

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        if 6 in self._in_clusters:
            result = yield from zha_new.safe_read(
                self._endpoint.on_off, ['on_off'])
        else:
            return
        try:
            self._state = result['on_off']
            self._available = True
        except Exception:
            self._available = False

        if not self._state:
            return

    def cluster_command(self, tsn, command_id, args):
        _LOGGER.debug("cluster command update: %s = %s ", command_id, args)
        try:
            dev_func = self._model.lower().replace(".", "_").replace(" ", "_")
            _custom_cluster_command = getattr(
                import_module("custom_components.device." + dev_func),
                "_custom_cluster_command"
                )
            _custom_cluster_command(self, tsn, command_id, args)
        except ImportError as e:
            _LOGGER.debug("Import DH %s failed: %s", dev_func, e.args)
        except Exception as e:
            _LOGGER.info("Excecution of DH %s failed: %s", dev_func, e.args)
