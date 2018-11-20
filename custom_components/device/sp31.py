"""" custom py file for device SP31 from net2grid."""
import logging
_LOGGER = logging.getLogger(__name__)


def _custom_endpoint_init(self, node_config, *argv):
    """set node_config."""
    config = {}
    if self._endpoint_id == 10:  # smartenergy metering
        config = {
            "in_cluster": [0x0702, ],
            "config_report": [
                [0x0702, 0, 5, 180, 1],
            ],
            "type": "sensor",
            }
        node_config.update(config)
    if self._endpoint_id == 1:
        config = {
            "in_cluster": [0x0000, 0x0006],
            "out_cluster": [],
            "config_report": [
                [0x0006, 0, 1, 180, 1],
            ],
            "type": "switch",
            }
        node_config.update(config)


def _parse_attribute(entity, attrib, value, *argv):
    """parse non standard attributes."""
    return(attrib, value)
