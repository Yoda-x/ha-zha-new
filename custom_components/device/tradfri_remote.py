""" tradfri TRADFRI remote template """
from zigpy.zcl.clusters.general import OnOff
def _custom_endpoint_init(self, node_config, *argv):
  #  self.device_type= 0x0104
  #  self.profile_id=260
    config={
        "model": "tradfri_remote",
        "manufacturer": "Ikea",
        "type": "switch",
        }
    node_config.update(config)

def _custom_cluster_command(self, tsn, command_id, args):
    value=self._brightness
    self._state = 1
    if command_id == 5:
        _up_down=1
    elif command_id == 1:
        _up_down=-1
    elif command_id == 7:
        return

    if args[1] == 70:
        value = value + (16 * _up_down)
    elif   args[1] == 195:
        value = value + (32 * _up_down)
    if value > 255:
        self._brightness= 255
    elif value <= 0:
        self._state = 0
        self._brightness= 0
    else:
        self._brightness = value
    self.schedule_update_ha_state()
