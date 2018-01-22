"""" custom py file for device """
import logging
import homeassistant.util.dt as dt_util
_LOGGER = logging.getLogger(__name__)

def _custom_endpoint_init(self, node_config,*argv):
    """set node_config"""
    config={}
    if self._endpoint_id == 10:
        """ smartenergy metering"""
        config={
            "in_cluster": [0x0702,],
            "config_report": [
            [ 0x0702, 0, 5, 180, 1 ],
            ],
            "type": "sensor", 
            }
        node_config.update(config)
    if self._endpoint_id == 1:
        config={
            "in_cluster": [0,],
            "config_report": [
            [ 0x0006, 0, 1, 180, 1 ],
            [ 0x0702, 0, 5, 180, 1 ],
            ],
            "type": "switch", 
            }
        node_config.update(config)


def _parse_attribute(entity, attrib, value, *argv):
    return(attrib, value)
##    import bellows.types as t
##    from bellows.zigbee.zcl import foundation as f
##    
##    if type(value) is str:
##        result = bytearray()
##        result.extend(map(ord,value))
##        value = result
##
##    """ parse custom attributes """
##    attributes={}
##    if attrib == 0xff02:
##        attribute_name=("state", "battery_voltage_mV","val3","val4","val5","val6")
##        result=[]
##        value= value[1:]
##        while value:
##            svalue, value = f.TypeValue.deserialize(value)
##            result.append(svalue.value)
##            _LOGGER.debug("parse 0xff02: %s", svalue.value)
##        attributes = dict(zip(attribute_name,result))
##        if "state" in attributes:
##            attrib = 0
##            value=attributes["state"].value
##        if "battery_voltage_mV" in attributes:
##            attributes["battery_level"] = int(_battery_percent(attributes["battery_voltage_mV"]) )
##
##    elif attrib == 0xff01:
##        _LOGGER.debug("Parse dict 0xff01: set friendly attribute names" )
##        attribute_name={
##            4 : "X-attrib-4",
##            1 : "battery_voltage_mV", 
##            100 : "temperature" , 
##            101 : "humidity",
##            5 : "X-attrib-5",
##            6 : "X-attrib-6", 
##            10 : "X-attrib-10"
##        }
##        result={}
##        _LOGGER.debug("Parse dict 0xff01: parsing" )
##        while value:
##            skey = int(value[0])
##            svalue, value = f.TypeValue.deserialize(value[1:])
##            result[skey]  = svalue.value
##        for item, value in result.items():
##            key = attribute_name[item] if item in attribute_name else "0xff02-" 
##            attributes[key] = value
##        if "battery_voltage_mV" in attributes:
##            attributes["battery_level"] = int(_battery_percent(attributes["battery_voltage_mV"]))
##    elif attrib == 43041:
##        attribute_name=("X-attrib-val1",
##                        "X-attrib-val2",
##                        "X-attrib-val3")
##        result=[]
##        svalue, value = t.uint40_t.deserialize(value)
##        result.append(svalue)
##        svalue, value = f.TypeValue.deserialize(value) 
##        result.append(svalue.value)
##        svalue, value = f.TypeValue.deserialize(value) 
##        result.append(svalue.value)
##        attributes = dict(zip(attribute_name,result))
##    else:
##        result=value    
##    _LOGGER.debug("Parse Result: %s", result)
##    
##    attributes["Last seen"] = dt_util.now()
##    entity._device_state_attributes.update(attributes)
##    return(attrib, result)
