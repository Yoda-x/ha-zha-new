import logging
import asyncio
#import zigpy.types as t
import zigpy as z
_LOGGER = logging.getLogger(__name__)
from .const import (
    DISCOVERY_KEY,
    DOMAIN,
    )
from homeassistant.helpers import discovery
import sys
import traceback
async def cluster_discover_commands(cluster, timeout=2):

    cls_start = 0
    cls_no = 20
    command_list = list()
    while True:
        try:
            done, result = await asyncio.wait_for(cluster.discover_command_rec(cls_start, cls_no), timeout)
            _LOGGER.debug("discover_cluster_commands for %s: %s",  cluster.cluster_id, result)
            command_list.extend(result).sort()
            if done:
                break
            else:
                cls_start = command_list[-1] + 1
        except TypeError:
            return
        except AttributeError:
            return
        except Exception as e:
            _LOGGER.debug(
                "catched exception in cluster_discover_commands %s",
                e
                )
            break
    _LOGGER.debug("discover_cluster_commands for %s: %s",
            cluster.cluster_id, command_list)
    return command_list


async def cluster_discover_attributes(cluster, timeout=2):

    cls_start = 0
    cls_no = 20
    attribute_list = list()
    while True:
        try:
            done,  result = await asyncio.wait_for(cluster.discover_attributes(cls_start, cls_no),  timeout)
            _LOGGER.debug("discover_cluster_attributes for %s: %s",  cluster.cluster_id, result)
            attribute_list.extend(result)
            if done:
                break
            else:
                cls_start = attribute_list[-1] + 1
#        except TypeError:
#            return
#        except AttributeError:
#            return
        except Exception as e:
            _LOGGER.debug("catched exception in cluster_discover_attributes %s",  e)
            break
    _LOGGER.debug("discover_attributes for %s: %s",  cluster.cluster_id, attribute_list)
    return attribute_list


async def cluster_commisioning_groups(cluster, timeout=2):

    cls_start = 0
    cls_no = 0
    group_list = list()
    while True:
        total, cls_start,  result = await asyncio.wait_for(cluster.get_group_identifier_request(cls_start), timeout)
        _LOGGER.debug("discover_group_identifier for %s: %s",  cluster.cluster_id, result)
        group_list.extend(result)
        cls_start += cls_no
        if (cls_start + 1) >= total:
            break
        _LOGGER.debug("discover_commisioning_groups for %s: %s",  cluster.cluster_id, group_list)

    return [group.GroupId for group in group_list]


async def full_discovery(endpoint, timeout=5):
    commands = dict()
    attributes = dict()
    commands = dict()
    if 0x1000 in endpoint.in_clusters:
        #try:
        groups = await  cluster_commisioning_groups(endpoint.in_clusters[0x1000], timeout=timeout)
        #except Exception as e:
         #   _LOGGER.debug("catched exception in full_discovery  group_id %s",  e)

    for cluster_id,  cluster in endpoint.in_clusters.items():
        _LOGGER.debug("get information for cluster %s",  cluster_id)
        try:
            commands[cluster_id] = await cluster_discover_commands(cluster, timeout=timeout)
        except Exception as e:
            _LOGGER.debug("catched exception in full_discovery %s",  e)
        try:
            attributes[cluster_id] = await cluster_discover_attributes(cluster, timeout=timeout)
        except Exception as e:
            _LOGGER.debug("catched exception in full_discovery %s",  e)

async def create_MC_Entity(application, group_id):
    mdev = z.device(application, 0, group_id)
    mdev.add_endpoint(1)
    mdev.endpoint[1].profile = z.profiles.zha.PROFILE_ID
    for cluster_id in (0x0003, 0x0004, 0x0005, 0x0006, 0x0008, 0x0300):
        mdev.endpoint[1].in_clusters[cluster_id] = cluster \
            = z.zcl.Cluster.from_id(
                mdev.add_endpoint[1], 
                cluster_id
            )
        if hasattr(cluster, 'ep_attribute'):
            mdev.endpoint[1]._cluster_attr[cluster.ep_attribute] = cluster
    discovery_info = {
        'device': mdev,
        'group_id': group_id,
        'application': application,
        }
    device_key = "{}_MC_{}".format(DOMAIN, group_id)
    application._hass.data[DISCOVERY_KEY][device_key] = discovery_info
    await discovery.async_load_platform(
        application._hass,
        'light',
        DOMAIN,
        {'discovery_key': device_key},
        application._config,
    )
        
        
async def req_conf_report(report_cls, report_attr, report_min, report_max, report_change, mfgCode=None):
        from zigpy.zcl.foundation import Status

        endpoint = report_cls._endpoint
        try:
            v = await report_cls.bind()
            if v[0] > 0:
                _LOGGER.debug("[0x%04x:%s:0x%04x]: bind failed: %s",
                              endpoint._device.nwk,
                              endpoint.endpoint_id,
                              report_cls.cluster_id,
                              Status(v[0]).name)
        except Exception as e:
            _LOGGER.debug("[0x%04x:%s:0x%04x]: : bind exceptional failed %s",
                          endpoint._device.nwk,
                          endpoint.endpoint_id,
                          report_cls.cluster_id,
                          e)
        try:
            v = await report_cls.configure_reporting(
                report_attr, int(report_min),
                int(report_max), report_change, manufacturer=mfgCode)
            _LOGGER.debug("[0x%04x:%s:0x%04x] set config report status: %s",
                          endpoint._device.nwk,
                          endpoint._endpoint_id,
                          report_cls.cluster_id,
                          v)
        except Exception as e:
            _LOGGER.error("[0x%04x:%s:0x%04x] set config report exeptional failed: %s",
                          endpoint._device.nwk,
                          endpoint.endpoint_id,
                          report_cls.cluster_id,
                          e)
                          
async def safe_read(cluster, attributes):
    try:
        result, _ = await cluster.read_attributes(
            attributes,
            allow_cache=False,
        )
        return result
    except Exception as e:  # pylint: disable=broad-except
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exep_data = traceback.format_exception(exc_type, exc_value,
                                                       exc_traceback)
        for e in exep_data:
            _LOGGER.debug("> %s", e)
        _LOGGER.debug("safe_read failed: %s", e)
