from collections import namedtuple, deque

import networkx as nx
import numpy as np

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


RouteRecord = namedtuple('RouteRecord', ['source', 'next_hop', 'gateway',
                                         'distance', 'static'])


def build_static_routes(topology):
    nodes = topology.nodes.values(['address', 'type'])
    gateways = [n['address'] for n in nodes if n['type'] == GATEWAY_NODE]

    # Build a precursors dictionary:
    #   node -> [nodes using this node as next hop]
    precursors = {n['address']: [] for n in nodes}
    for conn in topology.connections.all():
        from_addr, to_addr = conn
        precursors[to_addr].append(from_addr)

    # We will also need to store which node is connected to which gateway:
    gateway_dict = {
        n['address']: n['address'] if n['type'] == GATEWAY_NODE else None
        for n in nodes
    }

    # Now we build routes. We start from gateways by adding routes like
    #   source=gw, next_hop=gw, gateway=gw, distance=0, static=True
    # After inspecting a gateway, we add all its precursors to visiting queue
    # and build routes for them, and so on. A bit like simplified Dijkstra.
    routes = []
    visiting = deque((gw_addr, gw_addr, 0) for gw_addr in gateways)
    while visiting:
        curr_node, next_hop, dist = visiting[0]
        gw = gateway_dict[next_hop]
        routes.append(RouteRecord(curr_node, next_hop, gw, dist, static=True))
        # Since current node is visited, we remove it from visiting queue
        # and add all its precursors. Since each node has at most one
        # connection, we do not need to worry about multiple paths, so
        # do not check whether this node is already in visiting queue:
        del visiting[0]
        visiting.extend((p, curr_node, dist + 1) for p in precursors[curr_node])
        gateway_dict[curr_node] = gw
    return routes


# noinspection PyPep8Naming
def build_routes(topology, exclude=None):
    NOT_VISITED = 'not visited'
    QUEUED = 'queued'
    VISITED = 'visited'

    exclude = exclude or []
    nodes = topology.nodes.values(['address', 'type'])

    # Filter excluded nodes and gateways:
    nodes = [n for n in nodes if n['address'] not in exclude]
    gateways = [n['address'] for n in nodes if n['type'] == GATEWAY_NODE]

    # We need neighbourhood information, built based on radio range.
    # However, we also need to exclude stations passed via `exclude`
    # argument:
    neighbourhood = topology.neighbours()
    for node_a in exclude:
        for node_b in neighbourhood[node_a]:
            neighbourhood[node_b].remove(node_a)
        del neighbourhood[node_a]

    # Define main structures for Dijkstra routing algorithm:
    mark = {
        node['address']: NOT_VISITED if node['type'] == SENSOR_NODE else QUEUED
        for node in nodes
    }
    distance = {node['address']: np.inf for node in nodes}
    gw_map = {node['address']: None for node in nodes}
    queue = deque()
    routes = []

    # First, create static routes for gateways, mark them as visited,
    # add their neighbours to the queue:
    for gw in gateways:
        routes.append(RouteRecord(gw, gw, gw, 0, True))
        for v in neighbourhood[gw]:
            if mark[v] == NOT_VISITED:
                queue.append(v)
                mark[v] = QUEUED
        gw_map[gw] = gw
        distance[gw] = 0
        mark[gw] = VISITED

    # Then, inspect all nodes in the queue until it becomes empty, like
    # in Dijkstra algorithm:
    while queue:
        node = queue.popleft()
        next_hop = None
        for v in neighbourhood[node]:
            v_mark = mark[v]
            if v_mark == NOT_VISITED:
                queue.append(v)
                mark[v] = QUEUED
            elif next_hop is None or distance[v] < distance[next_hop]:
                next_hop = v
        if next_hop is not None:
            d = distance[next_hop] + 1
            gw = gw_map[next_hop]
            gw_map[node] = gw
            distance[node] = d
            routes.append(RouteRecord(node, next_hop, gw, d, False))
        mark[node] = VISITED
    return routes


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
    def __init__(self, topology):
        self.__topology = topology
        self.devices = {
            node.address: create_device(node) for node in topology.nodes.all()
        }
        self.next_hop = {}
        self.distance = {}
        # Building a network graph:
        self.graph = nx.DiGraph()
        self.graph.add_nodes_from(self.devices.keys())

    @property
    def topology(self):
        return self.__topology

    def sensors(self):
        return [a for a, d in self.devices.items() if isinstance(d, Sensor)]

    def gateways(self):
        return [a for a, d in self.devices.items() if isinstance(d, Gateway)]

    def connect(self):
        """Connect nodes to gates via either shortest paths or static routes.
        """
        connections = self.topology.connections.all()
        if connections:
            for conn in connections:
                if (self.devices[conn[0]].turned_on and
                        self.devices[conn[1]].turned_on):
                    self.next_hop[conn[0]] = conn[1]
                    self.graph.add_edge(conn[0], conn[1])
            self._update_distances()

    def turn_off(self, address):
        """Turn node off and remove all its connections.
        """
        precursors = [fa for fa, na in self.next_hop.items() if na == address]
        for fa in precursors:
            self.graph.remove_edge(fa, address)
            self.next_hop[fa] = None
        if self.next_hop[address] is not None:
            self.graph.remove_edge(address, self.next_hop[address])
        self.next_hop[address] = None
        self.devices[address].turn_off()
        self._update_distances()

    def turn_on(self, target):
        """Turn one or multiple nodes on.
        """
        try:
            for address in target:
                self.devices[address].turn_on()
        except TypeError:
            self.devices[target].turn_on()
        self.connect()

    def get_offline_nodes(self):
        """Get a list of all nodes either turned off or lost their connections.
        """
        return [addr for addr, d in self.distance.items() if d == np.inf]

    def _update_distances(self):
        gateways = self.gateways()
        devices = list(self.devices.keys())
        self.distance = {d: np.inf for d in devices}
        for gw in gateways:
            spl = dict(nx.single_target_shortest_path_length(self.graph, gw))
            for d in devices:
                if d in spl and self.distance[d] > spl[d]:
                    self.distance[d] = spl[d]
