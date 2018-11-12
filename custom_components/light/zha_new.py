"""
Lights on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/light.zha/

"""
import logging
from asyncio import ensure_future
from homeassistant.components import light
from homeassistant.const import STATE_UNKNOWN
import custom_components.zha_new as zha_new
from importlib import import_module
import homeassistant.util.color as color_util
from zigpy.zcl.foundation import Status
_LOGGER = logging.getLogger(__name__)

DEFAULT_DURATION = 0.5
CAPABILITIES_COLOR_XY = 0x08
CAPABILITIES_COLOR_TEMP = 0x10
UNSUPPORTED_ATTRIBUTE = 0x86


async def async_setup_platform(hass, config,
                               async_add_devices, discovery_info=None):
    """Set up the Zigbee Home Automation lights."""
    discovery_info = zha_new.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return

    endpoint = discovery_info['endpoint']
    in_clusters = discovery_info['in_clusters']
    try:
        discovery_info['color_capabilities'] \
            = await endpoint.light_color['color_capabilities']
    except AttributeError as e:
        _LOGGER.debug("No color cluster: %s", e.args)
    except KeyError as e:
        _LOGGER.debug("Request for color_capabilities failed: %s", e.args)
    except Exception as e:
        _LOGGER.debug("Request for color_capabilities other error: %s", e.args)
    entity = Light(**discovery_info)

    if hass.states.get(entity.entity_id):
        _LOGGER.debug("entity exist,remove it: %s",
                      dir(hass.states.get(entity.entity_id)))
        hass.states.async_remove(entity.entity_id)
    async_add_devices([entity])

    entity_store = zha_new.get_entity_store(hass)
    if endpoint.device._ieee not in entity_store:
        entity_store[endpoint.device._ieee] = []
    entity_store[endpoint.device._ieee].append(entity)
    await auto_set_attribute_report(endpoint,  in_clusters)
    endpoint._device._application.listener_event('device_updated',
                                                 endpoint._device)

class Light(zha_new.Entity, light.Light):

    """Representation of a ZHA or ZLL light."""

    _domain = light.DOMAIN

    def __init__(self, **kwargs):
        """Initialize the ZHA light."""
        super().__init__(**kwargs)

        self._available = True
        self._assumed = False
        self._groups = None
        self._grp_name = None
        self._supported_features = 0
        self._color_temp = None
        self._hs_color = None
        self._brightness = None

        import zigpy.zcl.clusters as zcl_clusters
        if zcl_clusters.general.LevelControl.cluster_id in self._in_clusters:
            self._supported_features |= light.SUPPORT_BRIGHTNESS
            self._supported_features |= light.SUPPORT_TRANSITION
            self._brightness = 0
        if zcl_clusters.lighting.Color.cluster_id in self._in_clusters:
            color_capabilities = kwargs.get('color_capabilities', 0x10)
            if color_capabilities & CAPABILITIES_COLOR_TEMP:
                self._supported_features |= light.SUPPORT_COLOR_TEMP

            if color_capabilities & CAPABILITIES_COLOR_XY:
                self._supported_features |= light.SUPPORT_COLOR
                self._hs_color = (0, 0)

        if zcl_clusters.general.Groups.cluster_id in self._in_clusters:
            self._groups = []
            self._device_state_attributes["Group_id"] = self._groups

        in_clusters = kwargs['in_clusters']
        out_clusters = kwargs['out_clusters']
        clusters = list(out_clusters.items()) +  list(in_clusters.items())
        for (key, cluster) in clusters:
            cluster.add_listener(self)
        endpoint = kwargs['endpoint']
        endpoint._device.zdo.add_listener(self)

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        if self._state == STATE_UNKNOWN:
            return False
        return bool(self._state)

#    @property
#    def available(self) -> bool:
#       return bool(self._available)

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return bool(self._assumed) 

    async def async_turn_on(self, **kwargs):
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

        if self._brightness is not None:
            brightness = kwargs.get(
                light.ATTR_BRIGHTNESS, self._brightness or 255)
            self._brightness = brightness
            # Move to level with on/off:

            await self._endpoint.level.move_to_level_with_on_off(
                brightness,
                duration
            )
            self._state = 1
            self.async_schedule_update_ha_state()
            self.async_update()
            return

        await self._endpoint.on_off.on()
        self._state = 1
        self.async_update_ha_state(force_refresh=True)
        self.async_update()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self._endpoint.on_off.off()
        self._state = 0
        self.async_schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
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
        import zigpy.zcl.clusters as zcl_clusters
        _LOGGER.debug("%s async_update", self.entity_id)

        if zcl_clusters.general.OnOff.cluster_id in self._in_clusters:
            result = await zha_new.safe_read(self._endpoint.on_off, ['on_off'])
        else:
            return
        try:
            self._state = result['on_off']
            self._assumed = False
        except Exception:
            self._assumed = True
            return

        if hasattr(self,'_groups'):
            try:
                result = await self._endpoint.groups.get_membership([])
            except:
                result = None
            _LOGGER.debug("%s get membership: %s", self.entity_id,  result)
            if result:
                if result[0] >= 1:
                    self._groups = result[1]
                    if self._device_state_attributes["Group_id"] != self._groups:
                        self._device_state_attributes["Group_id"] = self._groups
                        for groups in self._groups:
                            self._endpoint._device._application.listener_event(
                                'subscribe_group',
                                groups)
            if not self._state:
                return

        if self._supported_features & light.SUPPORT_BRIGHTNESS:
            result = await zha_new.safe_read(self._endpoint.level,
                                             ['current_level'])
            if result:
                self._brightness = result.get('current_level', self._brightness)

        if self._supported_features & light.SUPPORT_COLOR_TEMP:
            result = await zha_new.safe_read(self._endpoint.light_color,
                                             ['color_temperature'])
            if result:
                self._color_temp = result.get('color_temperature',
                                              self._color_temp)

        if self._supported_features & light.SUPPORT_COLOR:
            result = await zha_new.safe_read(self._endpoint.light_color,
                                             ['current_x', 'current_y'])
            if result:
                if 'current_x' in result and 'current_y' in result:
                    self._hs_color = (result['current_x'], result['current_y'])

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
        ensure_future(auto_set_attribute_report(self._endpoint,  self._in_clusters))
        ensure_future(self.async_update())

async def auto_set_attribute_report(endpoint, in_clusters):
    async def req_conf_report(report_cls, report_attr, report_min, report_max, report_change, mfgCode=None):
        try:
            v = await report_cls.bind()
            if v[0] > 0:
                _LOGGER.debug("[0x%04x:%s:0x%04x]: bind failed: %s",
                              endpoint._device.nwk,
                              endpoint.endpoint_id,
                              report_cls.cluster_id,
                              Status(v[0]).name)
        except Exception as e:
            _LOGGER.debug("[0x%04x:%s:0x%04x]: : bind exceptional failed %s",
                          endpoint._device.nwk,
                          endpoint.endpoint_id,
                          report_cls.cluster_id,
                          e)
        try:
            v = await report_cls.configure_reporting(
                report_attr, int(report_min),
                int(report_max), report_change, manufacturer=mfgCode)
            _LOGGER.debug("[0x%04x:%s:0x%04x] set config report status: %s",
                          endpoint._device.nwk,
                          endpoint._endpoint_id,
                          report_cls.cluster_id,
                          v)
        except Exception as e:
            _LOGGER.error("[0x%04x:%s:0x%04x] set config report exeptional failed: %s",
                          endpoint._device.nwk,
                          endpoint.endpoint_id,
                          report_cls.cluster_id,
                          e)
    if 0x0006 in in_clusters:
        await req_conf_report(endpoint.in_clusters[0x0006],  0,  1,  60, 1)
    if 0x0008 in in_clusters:
        await req_conf_report(endpoint.in_clusters[0x0008],  0,  1,  60, 1)
    if 0x0300 in in_clusters:
        await req_conf_report(endpoint.in_clusters[0x0300],  3,  0,  60, 1)
        await req_conf_report(endpoint.in_clusters[0x0006],  4,  0,  60, 1)
        await req_conf_report(endpoint.in_clusters[0x0006],  7,  0,  60, 1)
        
