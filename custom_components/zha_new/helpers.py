import logging
import asyncio
#import zigpy.types as t
#import zigpy.zcl as z
_LOGGER = logging.getLogger(__name__)


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
            _LOGGER.debug("catched exception in cluster_discover_commands %s",  e)
            break
    _LOGGER.debug("discover_cluster_commands for %s: %s",  cluster.cluster_id, command_list)
    return command_list


async def cluster_discover_attributes(cluster, timeout=2):

    cls_start = 0
    cls_no = 20
    attribute_list = list()
    while True:
        try:
            done,  result = await asyncio.wait_for(cluster.discover_attributes(cls_start, cls_no),  timeout)
            _LOGGER.debug("discover_cluster_attributes for %s: %s",  cluster.cluster_id, result)
            attribute_list.extend(result).sort()
            if done:
                break
            else:
                cls_start = attribute_list[-1] + 1
        except TypeError:
            return
        except AttributeError:
            return
#        except Exception as e:
 #           _LOGGER.debug("catched exception in cluster_discover_attributes %s",  e)
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
