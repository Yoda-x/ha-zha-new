""" tradfri TRADFRI bulb E27 opal 1000lm template """
def _custom_endpoint_init(self, node_config,*argv):
    self.profile_id=260
    self.device_type= 0x0101
    config={
        "config_report": [
            [ 6, 0, 0, 60, 1 ],
            [ 8, 0, 0, 60, 1 ],
            ]
    }
