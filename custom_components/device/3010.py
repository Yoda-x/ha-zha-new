"""" custom py file for device NYCE 3014."""
import logging
_LOGGER = logging.getLogger(__name__)


def _custom_endpoint_init(self, node_config, *argv):
    """set node_config based obn Lumi device_type."""
    config = {}
    selector = node_config.get('template', None)
    if not selector:
        selector = argv[0]
    _LOGGER.debug(" selector: %s", selector)
    config = {
            "config_report": [
                [0x0001, 0x0020, 60, 3600, 5], 
                [0x0001, 0x0021, 60, 3600, 5]
            ],
            "in_cluster": [0x0000, 0x0001, 0x0500, ],
            "out_cluster": [0x0500],
            "type": "binary_sensor",
    }
    self.add_input_cluster(0x0500)
    self.add_output_cluster(0x0500)
node_config.update(config)
