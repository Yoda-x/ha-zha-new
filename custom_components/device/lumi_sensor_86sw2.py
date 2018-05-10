"""" custom py file for device."""
import logging

_LOGGER = logging.getLogger(__name__)


def _custom_endpoint_init(self, node_config, *argv):
    config = {
         "in_cluster": [0x0000, ],
         "out_cluster": [0x0006], 
        "type": "binary_sensor",
        }
    node_config.update(config)
    self.add_output_cluster(6)
    
