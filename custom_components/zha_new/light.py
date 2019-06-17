"""
Lights on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/light.zha/

"""
import logging
#import custom_components.zha_new.helpers as helpers
import asyncio as a
from .helpers import safe_read
from homeassistant.components import light
from homeassistant.const import (
    STATE_UNKNOWN,
    ATTR_SUPPORTED_FEATURES
    )
import custom_components.zha_new as zha_new
from importlib import import_module
import homeassistant.util.color as color_util
from zigpy.zcl.clusters.general import (
    LevelControl,
    OnOff,
    Groups,
    Scenes,
    Basic)
from zigpy.zcl.clusters.lighting import Color
from custom_components.zha_new.cluster_handler import (
    Cluster_Server)
import homeassistant.util.dt as dt_util
from .const import DOMAIN as PLATFORM
from .const import (
    SERVICE_SCHEMAS,
    SERVICE_COLORTEMP_STEP_UP,
    SERVICE_COLORTEMP_STEP_DOWN,
    SERVICE_COLORTEMP_STEP,
    ATTR_STEP,
    )
from homeassistant.components.light import DOMAIN
_LOGGER = logging.getLogger(__name__)

DEFAULT_DURATION = 0.5
CAPABILITIES_COLOR_HUE = 0x01
CAPABILITIES_COLOR_EXT_HUE = 0x02
CAPABILITIES_COLOR_LOOP = 0x04
CAPABILITIES_COLOR_XY = 0x08
CAPABILITIES_COLOR_TEMP = 0x10
UNSUPPORTED_ATTRIBUTE = 0x86


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """Set up the Zigbee Home Automation lights."""
    discovery_info = zha_new.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return

    application = discovery_info['application']
    endpoint = discovery_info['endpoint']
    in_clusters = discovery_info['in_clusters']
    join = discovery_info['new_join']
    component = hass.data[DOMAIN]
#    try:
#        discovery_info['color_capabilities'] \
#            = await endpoint.light_color['color_capabilities']
#    except AttributeError as e:
#        _LOGGER.debug("No color cluster: %s", e.args)
#    except KeyError as e:
#        _LOGGER.debug("Request for color_capabilities failed: %s", e.args)
#    except Exception as e:
#        _LOGGER.debug("Request for color_capabilities other error: %s", e.args)
#    entity = Light(**discovery_info)

    async def async_handle_step_up_ct_service(service):
        _LOGGER.debug('handle step up for %s: %s', service.data)

    component.async_register_entity_service(
        SERVICE_COLORTEMP_STEP_UP, SERVICE_SCHEMAS[SERVICE_COLORTEMP_STEP],
        'async_handle_step_up_ct_service'
        )
    component.async_register_entity_service(
        SERVICE_COLORTEMP_STEP_DOWN, SERVICE_SCHEMAS[SERVICE_COLORTEMP_STEP],
        'async_handle_step_down_ct_service'
        )
    if hasattr(discovery_info, 'multicast'):
        entity = MLight(**discovery_info)
    else:
        entity = Light(**discovery_info)
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
        _LOGGER.debug("entity has different name,change it: %s",  reg_dev_id)
        e_registry.async_update_entity(reg_dev_id.entity_id,
                                       new_entity_id=entity.entity_id)
    if reg_dev_id.entity_id in application._entity_list:
        _LOGGER.debug("entity exist,remove it: %s",  reg_dev_id)
        await application._entity_list.get(reg_dev_id.entity_id).async_remove()
    async_add_entities([entity])

    entity_store = zha_new.get_entity_store(hass)
    if endpoint.device._ieee not in entity_store:
        entity_store[endpoint.device._ieee] = []
    entity_store[endpoint.device._ieee].append(entity)
    if join:
        await auto_set_attribute_report(endpoint,  in_clusters)
    endpoint._device._application.listener_event('device_updated',
                                                 endpoint._device)


class LightAttributeReports(Cluster_Server):
    current_x = None
    current_y = None

    def attribute_updated(self, attribute, value):
        _LOGGER.debug(
                "cluster:%s attribute=value received: %s=%s",
                self._cluster.cluster_id, attribute,
                value,
            )
        if self._entity._call_ongoing is True:
            return
        if self._cluster.cluster_id == OnOff.cluster_id:
            if attribute == 0:
                self._entity._state = True if value else False
#                self._entity.schedule_update_ha_state()
        if self._entity.is_on:
            if self._cluster.cluster_id == LevelControl.cluster_id:
                if attribute == 0:
                    self._entity._brightness = value
                    _LOGGER.debug(
                            "cluster:%s attribute=value processed %s=%s",
                            self._cluster.cluster_id,
                            attribute,
                            value,
                        )
        if self._cluster.cluster_id == Color.cluster_id:
                if attribute == 3:
                    self.current_x = value
                    self._entity._hs_color = (self.current_x, self.current_y)
                elif attribute == 4:
                    self.current_y == value
                    self._entity._hs_color = (self.current_x, self.current_y)
                elif attribute == 7:
                    self._entity._color_temp = value
        self._entity.schedule_update_ha_state()


class Light(zha_new.Entity, light.Light):

    """Representation of a ZHA or ZLL light."""

    _domain = DOMAIN

    def __init__(self, **kwargs):
        """Initialize the ZHA light."""
        super().__init__(**kwargs)

        in_clusters = kwargs['in_clusters']
        out_clusters = kwargs['out_clusters']
        endpoint = kwargs['endpoint']
        self._available = True
        self._assumed = False
#        self._groups = None
        self._grp_name = None
        self._supported_features = 0
        self._color_temp = None
        self._hs_color = None
        self._brightness = None
        self._current_x = None
        self._current_y = None
        self._color_temp_physical_min = None
        self._color_temp_physical_max = None
        self._call_ongoing = False
        self.CurrentHue = None
        self.CurrentSaturation = None
        self.EnhancedCurrentHue = None
        self._caps = 0

        if Groups.cluster_id in self._in_clusters:
            self._groups = list()
            self._device_state_attributes["Group_id"] = self._groups

        clusters = list(out_clusters.items()) + list(in_clusters.items())
        _LOGGER.debug("[0x%04x:%s] initialize cluster listeners: (%s/%s) ",
                      endpoint._device.nwk,
                      endpoint.endpoint_id,
                      list(in_clusters.keys()), list(out_clusters.keys()))
        for (_, cluster) in clusters:
            self.sub_listener[cluster.cluster_id] = LightAttributeReports(
                            self, cluster, cluster.cluster_id)

        endpoint._device.zdo.add_listener(self)

    async def async_handle_step_up_ct_service(self,  *args,  **kwargs):
        _LOGGER.debug('handle step up for Class Light %s: %s - %s', self.entity_id,  args,  kwargs)
        step = kwargs.get(ATTR_STEP, None)
        if not (step and hasattr(self._endpoint, 'light_color')):
            return False
        duration = kwargs.get(light.ATTR_TRANSITION, DEFAULT_DURATION)
        self._call_ongoing = True
        await self._endpoint.light_color.step_color_temp(
            0x01, step, int(duration/10), 0, 0)
        await a.sleep(duration)
        self._call_ongoing = False
        return True

    async def async_handle_step_down_ct_service(self,  *args,  **kwargs):
        _LOGGER.debug('handle step up for Class Light %s: %s - %s', self.entity_id,  args,  kwargs)
        step = kwargs.get(ATTR_STEP, None)
        if not (step and hasattr(self._endpoint, 'light_color')):
            return False
        duration = kwargs.get(light.ATTR_TRANSITION, DEFAULT_DURATION)
        self._call_ongoing = True
        await self._endpoint.light_color.step_color_temp(
            0x03, step, int(duration/10), 0, 0)
        await a.sleep(duration)
        self._call_ongoing = False
        return True

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        if self._state == STATE_UNKNOWN:
            return False
        return bool(self._state)

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return bool(self._assumed)

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug("turn_on with %s",  kwargs)
        self._call_ongoing = True
        """Turn the entity on."""
        duration = kwargs.get(light.ATTR_TRANSITION, DEFAULT_DURATION)
        duration = duration * 10  # tenths of s
        if light.ATTR_COLOR_TEMP in kwargs:
            temperature = kwargs[light.ATTR_COLOR_TEMP]
            await self._endpoint.light_color.move_to_color_temp(
                temperature, duration)
            self._color_temp = temperature

        if light.ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[light.ATTR_HS_COLOR]
            xy_color = color_util.color_hs_to_xy(*self._hs_color)
            await self._endpoint.light_color.move_to_color(
                int(xy_color[0] * 65535),
                int(xy_color[1] * 65535),
                duration,
            )

        if light.ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(
                light.ATTR_BRIGHTNESS, self._brightness)
            self._brightness = 2 if (brightness < 2) else brightness
            _LOGGER.debug("[0x%04x:%s] move_to_level_w_onoff: %s ",
                          self._endpoint._device.nwk,
                          self._endpoint.endpoint_id,
                          self._brightness)

            await self._endpoint.level.move_to_level_with_on_off(
                self._brightness,
                duration
            )
            self._state = True
        else:
            await self._endpoint.on_off.on()
            self._state = True
        await a.sleep(duration/10)
        self._call_ongoing = False

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._endpoint.on_off.off()
        self._state = False
#        self.async_schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        _LOGGER.debug("polled state brightness: %s",  self._brightness)
        return self._brightness

    @property
    def xy_color(self):
        """Return the XY color value [float, float]."""
        return self._xy_color

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self._color_temp

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("%s async_update", self.entity_id)

        try:
            result, _ = await self._endpoint.on_off.read_attributes(
                    ['on_off'],
                    allow_cache=False,
                )
            _LOGGER.debug(" poll received for %s : %s", self.entity_id, result)
        except Exception as e:
            _LOGGER.debug('poll for %s failed: %s', self.entity_id,  e)
            result = None
        try:
            self._state = result['on_off']
            self._assumed = False
#            _LOGGER.debug("assumed state for %s is false", self.entity_id)
            self._device_state_attributes.update({
                'last seen': dt_util.now(),
            })
        except Exception:
            self._assumed = True
            return

        if self._groups is not None:
            try:
                result = await self._endpoint.groups.get_membership([])
                _LOGGER.debug("%s get membership : %s", self.entity_id,  result)
            except Exception as e:
                result = None
                _LOGGER.debug(
                        "%s get membership failed: %s",
                        self.entity_id,
                        e,
                    )
            if result:
                if result[0] >= 1:
                    self._groups = result[1]
                    if (self._device_state_attributes.get("Group_id")
                            != self._groups):
                        self._device_state_attributes["Group_id"] = self._groups
                        for groups in self._groups:
                            self._endpoint._device._application.listener_event(
                                'subscribe_group',
                                groups)
        if self.is_on:
            if self._supported_features & light.SUPPORT_BRIGHTNESS:
                result = await safe_read(self._endpoint.level,
                                         ['current_level'])
                if result:
                    self._brightness = result.get(
                            'current_level', self._brightness
                        )
                    _LOGGER.debug("poll brightness %s",  self._brightness)

            if self._supported_features & light.SUPPORT_COLOR_TEMP:
                result = await safe_read(self._endpoint.light_color,
                                         ['color_temperature'])
                if result:
                    self._color_temp = result.get('color_temperature',
                                                  self._color_temp)

            if self._supported_features & light.SUPPORT_COLOR:
                result = await safe_read(self._endpoint.light_color,
                                         ['current_x', 'current_y'])
                if result:
                    if 'current_x' in result and 'current_y' in result:
                        self._hs_color = (
                                result['current_x'], result['current_y']
                            )

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.
        False if entity pushes its state to HA.
        """
        return True

    def cluster_command(self, tsn, command_id, args):
        try:
            dev_func = self._model.replace(".", "_").replace(" ", "_")
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
        a.ensure_future(
                auto_set_attribute_report(self._endpoint,  self._in_clusters)
            )
        a.ensure_future(self.async_update())
        a.ensure_future(self._get_caps_features())
        self._assumed = False
        _LOGGER.debug(
                "0x%04x device announce for light received",
                self._endpoint._device.nwk,
            )

    @property
    def max_mireds(self):
        return (
            self._color_temp_physical_max
            if self._color_temp_physical_max
            else 500)

    @property
    def min_mireds(self):
        return (
            self._color_temp_physical_min
            if self._color_temp_physical_min
            else 153)

    async def get_range_mired(self):
        result = await safe_read(
                self._endpoint.light_color,
                ['color_temp_physical_min', 'color_temp_physical_max'],
            )
        if result:
            self._color_temp_physical_min = result.get(
                    'color_temp_physical_min', None
                )
            self._color_temp_physical_max = result.get(
                    'color_temp_physical_max', None
                )

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        try:
            self._supported_features = self._restore_data.attributes[ATTR_SUPPORTED_FEATURES]
        except Exception:
            await self._get_caps_features()

    async def _get_caps_features(self):
        self._caps = 0
        if hasattr(self._endpoint, 'light_color'):
            try:
                self._caps = await safe_read(
                    self._endpoint.light_color, ['color_capabilities']).get(
                        'color_capabilities')
            except AttributeError:
                self._caps = CAPABILITIES_COLOR_XY
                try:
                    result = await safe_read(
                        self._endpoint.light_color, ['color_temperature'])
                    if result.get('color_temperature') is not UNSUPPORTED_ATTRIBUTE:
                        self._caps = self._caps | CAPABILITIES_COLOR_TEMP
                except AttributeError:
                    pass

        if self._caps & CAPABILITIES_COLOR_TEMP:
            self._supported_features |= light.SUPPORT_COLOR_TEMP
            a.ensure_future(self.get_range_mired())  # TODO move to new join only
        if (self._caps & CAPABILITIES_COLOR_HUE) or (self._caps & CAPABILITIES_COLOR_EXT_HUE) or (self._caps & CAPABILITIES_COLOR_XY):
            self._supported_features |= light.SUPPORT_COLOR
            self._hs_color = (0, 0)
        if LevelControl.cluster_id in self._in_clusters:
            self._supported_features |= light.SUPPORT_BRIGHTNESS
            self._supported_features |= light.SUPPORT_TRANSITION
            try:
                self._brightness = self._restore_data.attributes[light.ATTR_BRIGHTNESS]
            except Exception:
                pass


async def auto_set_attribute_report(endpoint, in_clusters):
    _LOGGER.debug(
            "[0x%04x:%s] called to set reports",
            endpoint._device.nwk,
            endpoint.endpoint_id,
        )

    if 0x0006 in in_clusters:
        await zha_new.req_conf_report(
                endpoint.in_clusters[0x0006],  0,  1,  600, 1
            )
    if 0x0008 in in_clusters:
        await zha_new.req_conf_report(
                endpoint.in_clusters[0x0008],  0,  1,  600, 1
            )
    if 0x0300 in in_clusters:
        await zha_new.req_conf_report(
                endpoint.in_clusters[0x0300],  3,  1,  600, 1
            )
        await zha_new.req_conf_report(
                endpoint.in_clusters[0x0300],  4,  1,  600, 1
            )
        await zha_new.req_conf_report(
                endpoint.in_clusters[0x0300],  7,  1,  600, 1
            )
