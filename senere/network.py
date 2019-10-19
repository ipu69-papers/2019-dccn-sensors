from collections import deque

from senere.routing import build_static_routes, build_routes
from senere.topology import GATEWAY_NODE, Node, SENSOR_NODE


class Device:
    def __init__(self, node: Node):
        self.__node = node

    @property
    def address(self):
        return self.__node.address

    @property
    def node(self):
        return self.__node

    @property
    def turned_on(self):
        raise NotImplementedError

    @property
    def turned_off(self):
        return not self.turned_on


class Sensor(Device):
    def __init__(self, node: Node):
        super().__init__(node)
        self.__turned_on = True

    @property
    def turned_on(self):
        return self.__turned_on

    def turn_on(self):
        self.__turned_on = True

    def turn_off(self):
        self.__turned_on = False


class Gateway(Device):
    def __init__(self, node: Node):
        super().__init__(node)

    @property
    def turned_on(self):
        return True


def create_device(node: Node) -> Device:
    if node.type == GATEWAY_NODE:
        return Gateway(node)
    if node.type == SENSOR_NODE:
        return Sensor(node)
    raise ValueError(f'unrecognized node type "{node.type}"')


class RoutingManager:
    def __init__(self, owner):
        assert hasattr(owner, '_table')
        self.__owner = owner

    @property
    def table(self):
        return getattr(self.__owner, '_table')

    def add(self, route_record):
        self.table[route_record.source] = route_record

    def remove(self, address):
        try:
            del self.table[address]
            return 1
        except KeyError:
            return 0

    def all(self, order_by=None):
        records = list(self.table.values())
        if order_by is None:
            return records
        records.sort(key=lambda rec: getattr(rec, order_by))
        return records

    def get(self, address):
        return self.table[address]

    def filter(self, order_by=None, **kwargs):
        records = self.all()
        if 'address' in kwargs:
            target = kwargs['address']
            records = [r for r in records if
                       r.source == target or r.hext_hop == target]
        if 'source' in kwargs:
            records = [r for r in records if r.source == kwargs['source']]
        if 'next_hop' in kwargs:
            records = [r for r in records if r.next_hop == kwargs['next_hop']]
        if 'static' in kwargs:
            records = [r for r in records if r.static == kwargs['static']]
        if 'distance' in kwargs:
            records = [r for r in records if r.distance == kwargs['distance']]
        # Ordering:
        if order_by is not None:
            records.sort(key=lambda r: getattr(r, order_by))
        return records


class Network:
    STATIC = 'static'
    DYNAMIC = 'dynamic'

    def __init__(self, topology):
        self.__topology = topology
        self.devices = {
            node.address: create_device(node) for node in topology.nodes.all()
        }
        # Initiating routing table:
        self._table = {address: None for address in self.devices.keys()}
        self.__routing_manager = RoutingManager(self)

    @property
    def topology(self):
        return self.__topology

    def sensors(self):
        return [a for a, d in self.devices.items() if isinstance(d, Sensor)]

    def gateways(self):
        return [a for a, d in self.devices.items() if isinstance(d, Gateway)]

    def turned_off(self):
        return [a for a, d in self.devices.items() if d.turned_off]

    @property
    def routing_table(self):
        return self.__routing_manager

    def build_routing_table(self, mode=STATIC):
        """Connect nodes to gates via either shortest paths or static routes.
        """
        route_builder = {
            Network.STATIC: build_static_routes,
            Network.DYNAMIC: build_routes,
        }
        routes = route_builder[mode](self.__topology, exclude=self.turned_off())
        for route in routes:
            self.routing_table.add(route)

    def turn_off(self, address):
        """Turn node off and remove all its connections.
        """
        self.devices[address].turn_off()
        # Removing all routes going through this device:
        queue = deque([address])
        unconnected_nodes = []
        while queue:
            node = queue.popleft()
            unconnected_nodes.append(node)
            self.routing_table.remove(node)
            for route in self.routing_table.all():
                if route.next_hop in unconnected_nodes:
                    queue.append(route.source)

    def turn_on(self, target):
        """Turn one or multiple nodes on.
        """
        try:
            for address in target:
                self.devices[address].turn_on()
        except TypeError:
            self.devices[target].turn_on()

    def get_offline_nodes(self):
        """Get a list of all nodes either turned off or lost their connections.
        """
        return [addr for addr in self.sensors() if addr not in self._table]
