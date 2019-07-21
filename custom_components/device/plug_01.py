"""" custom py file for device."""
import logging
_LOGGER = logging.getLogger(__name__)


def _custom_endpoint_init(self, node_config, *argv):
    """set node_config."""

    self.profile_id = 260
    if self.device_type == 0x0010:
        self.device_type = 0x0051
    config = {
        "config_report": [
            [6, 0, 0, 60, 1],
            ],
        "in_cluster": [0x0000, 0x0006],
        "out_cluster": [],
    }
    node_config.update(config)
