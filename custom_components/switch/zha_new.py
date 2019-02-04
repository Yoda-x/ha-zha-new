"""Switches on Zigbee Home Automation networks."""
import asyncio
import logging
from asyncio import ensure_future
from homeassistant.components.switch import DOMAIN, SwitchDevice
import custom_components.zha_new as zha_new
from custom_components.zha_new.cluster_handler import (
    Cluster_Server,
    Server_OnOff,
    Server_Scenes,
    Server_Basic,
    Server_Groups,
    )
from importlib import import_module
from zigpy.zcl.foundation import Status
from zigpy.zcl.clusters.general import (
    OnOff,
    Groups,
    Scenes,
    Basic)

_LOGGER = logging.getLogger(__name__)

""" change to zha-new for use in home dir """
#DEPENDENCIES = ['zha_new']


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up Zigbee Home Automation switches."""
    discovery_info = zha_new.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return

    application = discovery_info['application']
    
    entity = Switch(**discovery_info)
    if application._entity_list.get(entity.entity_id):
        _LOGGER.debug("entity exist,remove it: %s",  entity.entity_id)
        await application._entity_list.get(entity.entity_id).remove()
    async_add_devices([entity])
    endpoint = discovery_info['endpoint']
    in_clusters = discovery_info['in_clusters']
    await auto_set_attribute_report(endpoint,  in_clusters)
    entity_store = zha_new.get_entity_store(hass)
    if endpoint.device._ieee not in entity_store:
        entity_store[endpoint.device._ieee] = []
    entity_store[endpoint.device._ieee].append(entity)


class Switch(zha_new.Entity, SwitchDevice):

    """ZHA switch."""

    _domain = DOMAIN

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        in_clusters = kwargs['in_clusters']
        out_clusters = kwargs['out_clusters']
        endpoint = kwargs['endpoint']
        self._groups = None
        if Groups.cluster_id in self._in_clusters:
            self._groups = []
            self._device_state_attributes["Group_id"] = self._groups
        clusters = list(out_clusters.items()) + list(in_clusters.items())
        _LOGGER.debug("[0x%04x:%s] initialize cluster listeners: -%s- ",
                      endpoint._device.nwk,
                      endpoint.endpoint_id,
                      clusters)
        for (key, cluster) in clusters:
            if OnOff.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_OnOff(
                                self, cluster, 'OnOff')
            elif Scenes.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_Scenes(
                                self, cluster, "Scenes")
            elif Basic.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_Basic(
                                self, cluster, "Basic")
            elif Groups.cluster_id == cluster.cluster_id:
                self.sub_listener[cluster.cluster_id] = Server_Groups(
                                self, cluster, "Basic")
            else:
                self.sub_listener[cluster.cluster_id] = Cluster_Server(
                                self, cluster, cluster.cluster_id)

        endpoint._device.zdo.add_listener(self)

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

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self._endpoint.on_off.on()
        self._state = 1

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._endpoint.on_off.off()
        self._state = 0

    async def async_update(self):
        """Retrieve latest state."""
        if OnOff.cluster_id in self._in_clusters:
            result = await zha_new.safe_read(
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

        if hasattr(self, '_groups'):
            try:
                result = await self._endpoint.groups.get_membership([])
            except:
                result = None
            _LOGGER.debug("%s get membership: %s", self.entity_id,  result)
            if result:
                if result[0] >= 1:
                    self._groups = result[1]
                    if self._device_state_attributes.get("Group_id") != self._groups:
                        self._device_state_attributes["Group_id"] = self._groups
                        for groups in self._groups:
                            self._endpoint._device._application.listener_event(
                                'subscribe_group',
                                groups)

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

    def device_announce(self, *args,  **kwargs):
        ensure_future(auto_set_attribute_report(self._endpoint,  self._in_clusters))
        ensure_future(self.async_update())
        self._assumed = False
        _LOGGER.debug("0x%04x device announce for switch received",  self._endpoint._device.nwk)

async def auto_set_attribute_report(endpoint, in_clusters):


    _LOGGER.debug("[0x%04x:%s] called to set reports",  endpoint._device.nwk,  endpoint.endpoint_id)

    if 0x0006 in in_clusters:
        await zha_new.req_conf_report(endpoint.in_clusters[0x0006],  0,  1,  600, 1)
