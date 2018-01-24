""" tradfri TRADFRI bulb E27 opal 1000lm template """
def _custom_endpoint_init(self, node_config, *argv):
  #  self.device_type= 0x0104
  #  self.profile_id=260
    config={
        "model": "tradfri_dimmer",
        "manufacturer": "Ikea",
        "config_report": [
            [ 0x0008, 0, 0, 3600, 1],
            ],
        "type": "light",
        }
    node_config.update(config)

def _custom_cluster_command(self, aps_frame, tsn, command_id, args):
    self._state = 1
    if command_id == 5:
        _up_down=1
    elif command_id == 1:
        _up_down=-1
    elif command_id == 7:
        return

    if args[1] == 70:
        self._brightness = self._brightness + (16 * _up_down)
    elif   args[1] == 195:
        self._brightness = self._brightness + (32 * _up_down)
    if self._brightness > 255:
        self._brightness = 255
    elif self._brightness <= 0:
            self._brightness = 0
            self._state = 0
    self.schedule_update_ha_state()
