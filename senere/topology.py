from collections import namedtuple

import numpy as np

from senere.options import defaults

SENSOR_NODE = 'sensor'
GATEWAY_NODE = 'gateway'


Node = namedtuple('Node', ('address', 'type', 'x', 'y', 'radio_range'))


def position_of(node):
    return np.asarray([node.x, node.y])


def distance_between(node_a, node_b):
    r = position_of(node_a) - position_of(node_b)
    return np.sqrt(r.dot(r))


class Topology:
    def __init__(self):
        self._nodes = {}
        self.__nodes_manager = NodesManager(self)
        self._connections = {}
        self.__connections_manager = ConnectionsManager(self, can_connect=(
            lambda src, dst: (distance_between(src, dst) <=
                              min(src.radio_range, dst.radio_range))))

    @property
    def nodes(self):
        return self.__nodes_manager

    @property
    def connections(self):
        return self.__connections_manager

    def __str__(self):
        nodes = '\n'.join(
            f'- {n.address}: {n.type} at {n.x:.2f},{n.y:.2f}, '
            f'radio_range={n.radio_range:.2f}'
            for n in self.nodes.all(order_by='address'))
        connections = '\n'.join(
            f'- {c[0]} ==> {c[1]}' for c in self.connections.all(
                order_by='from_addr'))
        return f'NODES:\n{nodes}\nCONNECTIONS:\n{connections}'


# noinspection PyProtectedMember
class NodesManager:
    def __init__(self, owner):
        """Create node manager. The only thing required from owner is to
        have `_nodes` dictionary."""
        self.__owner = owner

    @property
    def owner(self):
        return self.__owner

    def add(self, address, node_type, x, y, **kwargs):
        radio_range = kwargs.get('radio_range', defaults['radio_range'])
        node = Node(address, node_type, x, y, radio_range)
        self.__owner._nodes[address] = node

    def remove(self, address):
        try:
            del self.owner._nodes[address]
        except KeyError:
            return 0
        connections = self.__owner.connections
        for from_addr, _ in connections.filter(address=address):
            connections.remove(from_addr)
        return 1

    def has(self, address):
        return address in self.__owner._nodes

    def count(self):
        return len(self.__owner._nodes)

    def all(self, order_by=None):
        nodes = list(self.__owner._nodes.values())
        if order_by is not None:
            nodes.sort(key=(lambda node: getattr(node, order_by)))
        return nodes

    def get(self, address):
        return self.__owner._nodes[address]

    def filter(self, order_by=None, **kwargs):
        """Get a list of nodes filtered by types or addresses.
        If several filters were passed, they will be conjuncted.

        Possible filters:

        - `type`, `type__in`, `type__not_in`: filter by node types
        - `address`, `address__in`, `address__not_in`: filter by node address

        Examples:

            1) To get a list of gateways with addresses from [1, 5, 3]:
            >>> filter(type__not_in=[SENSOR_NODE], address__in=[1, 5, 3])

            2) To get a gateway with address 5:
            >>> filter(type=GATEWAY_NODE, address=5)

        :return a list of nodes matching filters
        """
        nodes = self.all(order_by=None)
        #
        # 1) Inspecting nodes types:
        #
        if 'type' in kwargs:
            nodes = [n for n in nodes if n.type == kwargs['type']]
        if 'type__in' in kwargs:
            nodes = [n for n in nodes if n.type in kwargs['type__in']]
        if 'type__not_in' in kwargs:
            nodes = [n for n in nodes if n.type not in kwargs['type__not_in']]
        #
        # 2) Inspecting node addresses:
        #
        if 'address' in kwargs:
            address = kwargs['address']
            nodes = [n for n in nodes if n.address == address]
        if 'address__in' in kwargs:
            address_set = kwargs['address__in']
            nodes = [n for n in nodes if n.address in address_set]
        if 'address__not_in' in kwargs:
            address_set = kwargs['address_not_in']
            nodes = [n for n in nodes if n.address not in address_set]

        if order_by is not None:
            nodes.sort(key=(lambda node: getattr(node, order_by)))
        return nodes


# noinspection PyProtectedMember
class ConnectionsManager:
    ORDER_KEYS = {
        'from_addr': lambda c: c[0],
        'to_addr': lambda c: c[1],
    }

    def __init__(self, owner, can_connect=None):
        self.__owner = owner
        self.can_connect = can_connect if can_connect else (lambda a, b: True)

    @property
    def owner(self):
        return self.__owner

    def add(self, from_addr, to_addr):
        from_node = self.__owner.nodes.get(from_addr)
        to_node = self.__owner.nodes.get(to_addr)
        if self.can_connect(from_node, to_node):
            self.__owner._connections[from_addr] = to_addr
        else:
            raise ValueError(f'nodes {from_addr} and {to_addr} '
                             f'can not be connected')

    def remove(self, from_addr):
        try:
            del self.owner._connections[from_addr]
            return 1
        except KeyError:
            return 0

    def count(self):
        return len(self.owner._connections)

    def get_next_hop(self, from_addr):
        return self.owner._connections[from_addr]

    def all(self, order_by=None):
        connections = [
            (key, value) for key, value in self.owner._connections.items()]
        if order_by is not None:
            connections.sort(key=ConnectionsManager.ORDER_KEYS[order_by])
        return connections

    def filter(self, order_by=None, **kwargs):
        connections = self.all()
        if 'address' in kwargs:
            address = kwargs['address']
            connections = [
                c for c in connections if c[0] == address or c[1] == address]
        if order_by is not None:
            connections.sort(key=ConnectionsManager.ORDER_KEYS[order_by])
        return connections


#
# Topology generators:
#
def build_tree_topology(depth, num_trees=1):
    pass
