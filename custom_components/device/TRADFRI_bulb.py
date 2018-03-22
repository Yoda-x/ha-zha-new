""" tradfri TRADFRI bulb E27 opal 1000lm template """
def _custom_endpoint_init(self, node_config,*argv):
    if self.endpoint_id == 1:
        self.profile_id=260
        if self.device_type == 0x0220:
            self.device_type = 0x0102
        else:
            self.device_type = 0x0101
        config={
            "config_report": [
                [ 6, 0, 0, 60, 1 ],
                [ 8, 0, 0, 60, 1 ],
                ]
        }
        node_config.update(config)
