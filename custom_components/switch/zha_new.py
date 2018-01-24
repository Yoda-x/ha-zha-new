"""
Switches on Zigbee Home Automation networks.

"""
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

    add_devices([Switch(**discovery_info)])


class Switch(zha_new.Entity, SwitchDevice):
    """ZHA switch."""

    _domain = DOMAIN

    @property
    def is_on(self) -> bool:
        """Return if the switch is on based on the statemachine."""
        if self._state == None:
            return False
        return bool(self._state)
    
    def cluster_command(self, aps_frame, tsn, command_id, args):
        """Handle commands received to this cluster."""
        pass
    
    def attribute_updated(self, attribute, value):
        _LOGGER.debug("attribute update: %s = %s ", attribute, value)
        try:
            dev_func= self._model.replace(".","_").replace(" ","_")
            _parse_attribute = getattr(import_module("custom_components.device." + dev_func), "_parse_attribute")
            #(attribute, value) = _parse_attribute(self,attribute, value, dev_func)
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
        v = yield from self._endpoint.on_off.read_attributes(
            ['on_off',],
            allow_cache=False,
            )
        self._state = v[0]['on_off']
        _LOGGER.debug("on_off %s",  self._state)
