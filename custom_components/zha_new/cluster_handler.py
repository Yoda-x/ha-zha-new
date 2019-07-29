
import logging
import homeassistant.util.dt as dt_util
import asyncio
import zigpy.types as t
import datetime
from homeassistant.helpers.event import async_track_point_in_time
from zigpy.zcl.clusters.homeautomation import ElectricalMeasurement
from zigpy.zcl.clusters.general import LevelControl, OnOff, Scenes
from zigpy.zcl.clusters.lightlink import LightLink
from zigpy.zcl.clusters.general import Basic, PowerConfiguration, Alarms
from zigpy.zcl.clusters.security import IasZone
from zigpy.zcl.clusters.measurement import OccupancySensing
from zigpy.zcl.clusters.measurement import TemperatureMeasurement
from .helpers import req_conf_report, safe_read
from .const import BatteryType
_LOGGER = logging.getLogger(__name__)


class Cluster_Server(object):
    def __init__(self, entity,  cluster,  identifier):
        self._cluster = cluster
        self._entity = entity
        self._identifier = identifier
        self._value = int(0)
        self.value = int(0)
        self._prev_tsn = int()
        cluster.add_listener(self)
        # overwrite function with device specific function
        if self._entity._custom_module.get('_parse_attribute', None):
            self._parse_attribute = self._entity._custom_module['_parse_attribute']

    def _parse_attribute(self, entity, attr,  value, *args,   **kwargs):
        _LOGGER.debug("called _parse attribute for &s-%s", self.entity,  self._identifier)
        return (attr,  value)

    def cluster_command(self, tsn, command_id, args):
        _LOGGER.debug('cluster command received:[0x%04x:%s] %s',
                      self._cluster.cluster_id,
                      command_id,
                      args
                      )

    def attribute_updated(self, attribute, value):
        _LOGGER.debug('Attribute report received on cluster [0x%04x:%s:]=%s',
                      self._cluster.cluster_id,
                      attribute,
                      value
                      )

        (attribute, value) = self._parse_attribute(
                        self._entity,
                        attribute,
                        value,
                        self._entity._model,
                        cluster_id=self._cluster.cluster_id)
        try:
            if attribute == self._entity.value_attribute:
                self._entity._state = value
        except Exception:
            pass
        self._entity.schedule_update_ha_state()

    async def join_prepare(self, **kwargs):
        return
        
    async def async_update(self):
        return


class Server_Basic(Cluster_Server):
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
                'last seen': dt_util.now(),
                'last command': command
        })
        self._entity.schedule_update_ha_state()


class Server_IasZone(Cluster_Server):

    def __init__(self, entity,  cluster,  identifier):
        self._ZoneStatus = t.bitmap16(0)
        super().__init__(entity,  cluster,  identifier)
        self.Status_Names = {
            0: 'ALARM1',
            1: 'ALARM2',
            2: 'TAMPER',
            3: 'BATTERY',
            4: 'SUPERVISION_REPORTS',
            5: 'RESTORE_REPORTS',
            6: 'TROUBLE',
            7: 'AC_MAINS',
            8: 'TEST',
            9: 'BATTERY_DEF',
        }

    def cluster_command(self, tsn, command_id, args):
        if tsn == self._prev_tsn:
            return
        self._prev_tsn = tsn
        if command_id == 0:
            attributes = {
                        'last seen': dt_util.now(),
                        }
            zone_change = self._ZoneStatus ^ args[0]
            self._ZoneStatus = args[0]
            for i in range(len(self.Status_Names)):
                attributes[self.Status_Names[i]] = (self._ZoneStatus >> i) & 1
                if (zone_change >> i) & 1:
                    event_data = {
                            'entity_id': self._entity.entity_id,
                            'channel': self._identifier,
                            'command':  self.Status_Names[i],
                            'data': (self._ZoneStatus >> i) & 1,
                           }
                    self._entity.hass.bus.fire('alarm', event_data)
                    _LOGGER.debug('alarm event [tsn:%s] %s', tsn, event_data)
            attributes['last detection'] = dt_util.now()
            self._entity._device_state_attributes.update(attributes)
            self._entity._state = args[0] & 3
            self._entity.schedule_update_ha_state()
        elif command_id == 1:
            _LOGGER.debug("Enroll requested")
            self._entity.hass.add_job(self._cluster.enroll_response(0, 0))


class Server_LevelControl(Cluster_Server):
    def __init__(self, entity,  cluster,  identifier):

        self.start_time = None
        self.step = int()
        self.on_off = None
        super().__init__(entity,  cluster,  identifier)

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
        if command in ('move_with_on_off', 'step_with_on_off'):
            self.on_off = True

        if command in ('step', 'step_with_on_off'):
            if args[0] == 0:
                event_data['up_down'] = 1
            elif args[0] == 1:
                event_data['up_down'] = -1
                if args[1] == 0:
                    self._value = 254
                    self._entity._state = 1
            event_data['step'] = args[1]
            self._value += event_data['up_down'] * event_data['step']
            if self._value <= 0:
                if self.on_off:
                    self._entity._state = 0
                self.value = 1
                self._value = 1
            elif self._value > 255:
                self._value = 254
                self.value = 254
            else:
                self.value = int(self._value)
                if self.on_off:
                    self._entity._state = 1
#        elif command == 'move_to_level_with_on_off':
#            self.value = self._value
        elif command in ('move_with_on_off', 'move'):
            if args[0] == 0:
                event_data['up_down'] = 1
            elif args[0] == 1:
                event_data['up_down'] = -1
            self.step = args[1] * event_data['up_down']
            event_data['step'] = args[1]
            if self.start_time is None:
                self.start_time = dt_util.utcnow().timestamp()

        elif command == 'stop':
            if self.start_time is not None:
                delta_time = dt_util.utcnow().timestamp() - self.start_time
                _LOGGER.debug('Delta: %s move: %s',  delta_time, delta_time * self.step)
                self._value += int(delta_time * self.step)
                self.start_time = None
                if self._value <= 1:
                    if self.on_off:
                        self._entity._state = 0
                    self.value = 1
                    self._value = 1
                elif self._value >= 254:

                    self._value = 254
                    self.value = 254
                else:
                    self.value = int(self._value)
                    if self.on_off:
                        self._entity._state = 1

        self._entity.hass.bus.fire('click', event_data)
        _LOGGER.debug('click event [tsn:%s] %s', tsn, event_data)
        self._entity._device_state_attributes.update({
                'last seen': dt_util.now(),
                self._identifier: self.value,
                'last command': command
        })
        self._entity.schedule_update_ha_state()


class Server_OnOff(Cluster_Server):
    def cluster_command(self, tsn, command_id, args):

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
            self._entity._state = 1
        elif command == 'off':
            self._entity._state = 0
        elif command == 'toggle':
            self._entity._state = self._entity._state ^ 1
        self._entity.hass.bus.fire('click', event_data)
        _LOGGER.debug('click event [tsn:%s] %s', tsn, event_data)
        self._entity._device_state_attributes.update({
                'last seen': dt_util.now(),
                self._identifier: self._value,
                'last command': command
        })
        self._entity.schedule_update_ha_state()

    def attribute_updated(self, attribute, value):
        _LOGGER.debug('Attribute report received on cluster [0x%04x:%s:]=%s',
                      self._cluster.cluster_id,
                      attribute,
                      value
                      )

        (attribute, value) = self._parse_attribute(
                        self._entity,
                        attribute,
                        value,
                        self._entity._model,
                        cluster_id=self._cluster.cluster_id)
        try:
            if attribute == self._entity.value_attribute:
                self._entity._state = value
        except Exception:
            _LOGGER.debug("no default cluster defined")
        finally:
            if attribute == 0:
                self._entity._state = bool(value)
        self._entity.schedule_update_ha_state()


class Server_Groups(Cluster_Server):
    def attribute_updated(self, attribute, value):
        _LOGGER.debug('Group report received: %s %s', attribute, value)


class Server_LightLink(Cluster_Server):
    def __init__(self, entity,  cluster,  identifier):
        self._groups = list()
        super().__init__(entity,  cluster,  identifier)


#    def attribute_updated(self, attribute, value):
#        _LOGGER.debug('LightLink report received: %s %s',  attribute,  value)

    async def join_prepare(self, timeout=15):
        from .helpers import cluster_commisioning_groups
        _LOGGER.debug('LightLink prepare')
        try:
            self._entity._groups = self._groups = await cluster_commisioning_groups(self._cluster)
            _LOGGER.debug("discovered group from lightlink: %s", self._groups)
        except Exception as e:
            _LOGGER.debug(
                "catched exception in commissioning group_id %s",  e)


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
        _LOGGER.debug('click event [tsn:%s] %s', tsn, event_data)
        self._entity._device_state_attributes.update({
                'last seen': dt_util.now(),
                self._identifier: args,
                'last command': command
        })

        self._entity.schedule_update_ha_state()


class Server_OccupancySensing(Cluster_Server):

    value_attribute = 0
    re_arm_sec = 20
    invalidate_after = None
    _state = 0

    def attribute_updated(self, attribute, value):
        """ handle trigger events from motion sensor.
        clear state after re_arm_sec seconds."""
        _LOGGER.debug("Attribute received: %s %s", attribute, value)
        (attribute, value) = self._entity._parse_attribute(self._entity, attribute, value, self._entity._model, cluster_id=self._cluster.cluster_id)

        @asyncio.coroutine
        def _async_clear_state(entity):
            _LOGGER.debug("async_clear_state")
            if (entity.invalidate_after is None
                    or entity.invalidate_after < dt_util.utcnow()):
                entity._entity._state = bool(0)
                entity._entity.schedule_update_ha_state()

        if attribute == self.value_attribute:
            self._entity._state = value
            self.invalidate_after = dt_util.utcnow() + datetime.timedelta(
                seconds=self.re_arm_sec)
            self._entity._device_state_attributes['last detection'] \
                = dt_util.utcnow()
            async_track_point_in_time(
                self._entity.hass, _async_clear_state(self),
                self.invalidate_after)
            self._entity.hass.bus.fire('alarm', {
                    'entity_id': self._entity.entity_id,
                    'channel': self._identifier,
                    'command': "motion",
                   })

        self._entity.schedule_update_ha_state()


class Server_TemperatureMeasurement(Cluster_Server):
    def attribute_updated(self, attribute, value):

        update_attrib = {}
        if attribute == 0:
            update_attrib['Temperature'] = round(float(value) / 100, 1)
        update_attrib['last seen'] = dt_util.now()
        self._entity._device_state_attributes.update(update_attrib)

        self._entity.schedule_update_ha_state()


class Server_PowerConfiguration(Cluster_Server):
    def attribute_updated(self, attribute, value):
        update_attrib = {}
        _LOGGER.debug('Power report received: %s %s',  attribute,  value)
        if attribute == 0x20:
            update_attrib['Battery_Voltage'] = round(float(value) / 10, 1)
        elif attribute == 0x21:
            update_attrib['battery_level'] = value / 2
        elif attribute == 0x31:
            update_attrib['battery_type'] = BatteryType.get(value)
        update_attrib['last seen'] = dt_util.now()
        self._entity._device_state_attributes.update(update_attrib)
#        self._entity.schedule_update_ha_state()

    async def join_prepare(self, timeout=15):
        from .helpers import cluster_discover_attributes
        _LOGGER.debug('Power prepare')
        attribute_list = await cluster_discover_attributes(self._cluster, timeout)
        for attribute in attribute_list:
            if attribute.attrid == 0x20:
                await req_conf_report(
                  self._cluster,  0x20,  60,  7200, 10
                )
            elif attribute.attrid == 0x21:
                await req_conf_report(
                  self._cluster,  0x21,  60,  7200, 10
                )
            elif attribute.attrid == 0x31:
                result = await safe_read(self._cluster,  ['battery_size'])
                if not result:
                    return
                batterySize = result.get('battery_size')
                self._entity._device_state_attributes['battery_type'] = BatteryType.get(batterySize)
#                self._entity.schedule_update_ha_state()



class Server_ElectricalMeasurement(Cluster_Server):
    
#    def attribute_updated(self, attribute, value):
#        pass

    async def join_prepare(self, timeout=15):
        _LOGGER.debug("measurement_type: %s",  'start')
        m_type = await safe_read(self._cluster,  ['measurement_type'])
        if not m_type:
            _LOGGER.debug("measurement_type: %s",  'failed')
            return
        _LOGGER.debug("measurement_type: %x",  m_type)
        self._entity._device_state_attributes['measurement_type'] = m_type.get('measurement_type')
#                self._entity.schedule_update_ha_state()

    async def async_update(self):
        from .helpers import cluster_discover_attributes
        attribute_list = await cluster_discover_attributes(self._cluster, 2, start = 0x0000)
        attributes = [a.attrid for a in attribute_list]
        result = await safe_read(self._cluster,  ['measurement_type'])
        if not result:
            _LOGGER.debug("measurement_type: %s",  'failed')
            return
        m_type=result.get('measurement_type')
        if m_type & 8:
            phaseA = await safe_read(self._cluster, attributes)
#            self._entity._device_state_attributes['active_power'] = active_power
            _LOGGER.debug("Phase A: %s",  phaseA)


class Server_Alarms(Cluster_Server):
#    def attribute_updated(self, attribute, value):
#        _LOGGER.info('Alarms report received: %s %s',  attribute,  value)

#
#        update_attrib = {}
#        if attribute == 0:
#            update_attrib['Temperature'] = round(float(value) / 100, 1)
#        update_attrib['last seen'] = dt_util.now()
#        self._entity._device_state_attributes.update(update_attrib)
#
#        self._entity.schedule_update_ha_state()
    pass

def init_clusters(entity, clusters):
    for (_, cluster) in clusters:
        if LevelControl.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_LevelControl(
                            entity, cluster, 'Level')
        elif OnOff.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_OnOff(
                            entity, cluster, 'OnOff')
        elif Scenes.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_Scenes(
                            entity, cluster, "Scenes")
        elif IasZone.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_IasZone(
                            entity, cluster, "IasZone")
        elif Basic.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_Basic(
                            entity, cluster, "Basic")
        elif OccupancySensing.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_OccupancySensing(
                            entity, cluster, "OccupancySensing")
        elif TemperatureMeasurement.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_TemperatureMeasurement(
                            entity, cluster, "TemperatureMeasurement")
        elif PowerConfiguration.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_PowerConfiguration(
                            entity, cluster, "PowerConfiguration")
        elif LightLink.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_LightLink(
                            entity, cluster, "LightLink")
        elif ElectricalMeasurement.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_ElectricalMeasurement(
                            entity, cluster, "ElectricalMeasurement")
        elif Alarms.cluster_id == cluster.cluster_id:
            entity.sub_listener[cluster.cluster_id] = Server_Alarms(
                            entity, cluster, "Alarms")
        else:
            entity.sub_listener[cluster.cluster_id] = Cluster_Server(
                            entity, cluster, cluster.cluster_id)
