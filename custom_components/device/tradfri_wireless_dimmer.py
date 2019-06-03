""" tradfri dimmer template."""
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
                [0x0001, 0x0020, 60, 600, 5], 
                [0x0001, 0x0021, 60, 600, 5]
            ],
            "in_cluster": [0x0000, 0x0001, ],
            "type": "binary_sensor",
    }
    node_config.update(config)


def _custom_cluster_command(self, tsn, command_id, args):
    pass
