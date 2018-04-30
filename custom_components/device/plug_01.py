"""" custom py file for device """
import logging
_LOGGER = logging.getLogger(__name__)

def _custom_endpoint_init(self, node_config,*argv):
    """set node_config"""

    self.profile_id = 260
    if self.device_type == 0x0010:
        self.device_type = 0x0051
    config={
        "config_report": [
            [ 6, 0, 0, 60, 1 ],
            ]
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
