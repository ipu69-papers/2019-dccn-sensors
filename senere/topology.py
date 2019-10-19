import networkx as nx

import numpy as np

from senere.options import defaults
from senere.utilities import GridArea

SENSOR_NODE = 'sensor'
GATEWAY_NODE = 'gateway'


# noinspection PyShadowingBuiltins
class Node:
    def __init__(self, address, type=SENSOR_NODE, x=0, y=0,
                 radio_range=None):
        self.address = address
        self.type = type
        self.x = x
        self.y = y
        self.radio_range = radio_range or defaults['radio_range']

    def __str__(self):
        return f'{self.type}({self.address} @ {self.x:.2f},{self.y:.2f} ' \
               f'R={self.radio_range:.2f})'

    def __repr__(self):
        return str(self)

    def __iter__(self):
        for val in (self.address, self.type, self.x, self.y, self.radio_range):
            yield val

    def __eq__(self, other):
        return tuple(self) == tuple(other)

    def __ne__(self, other):
        return not self.__eq__(other)


def position_of(node):
    return np.asarray([node.x, node.y])


def distance_between(node_a, node_b):
    r = position_of(node_a) - position_of(node_b)
    return np.sqrt(r.dot(r))


class Topology:
    def __init__(self, nodes=None, connections=None):
        nodes = nodes or []
        connections = connections or []
        self._nodes = {n.address: n for n in nodes}
        self._connections = {c[0]: c[1] for c in connections}
        self.__nodes_manager = NodesManager(self)
        self.__connections_manager = ConnectionsManager(self, can_connect=(
            lambda src, dst: (distance_between(src, dst) <=
                              min(src.radio_range, dst.radio_range))))

    @property
    def nodes(self):
        return self.__nodes_manager

    @property
    def connections(self):
        return self.__connections_manager

    def get_connections_graph(self):
        graph = nx.DiGraph()
        nodes = self.nodes.values(['address', 'type', 'x', 'y', 'radio_range'])
        graph.add_nodes_from((n['address'], n) for n in nodes)
        graph.add_edges_from(self.connections.all())
        return graph

    def get_neighbours_graph(self):
        graph = nx.Graph()
        nodes = self.nodes.values(['address', 'type', 'x', 'y', 'radio_range'])
        graph.add_nodes_from((n['address'], n) for n in nodes)
        nodes_list = graph.nodes()
        for address_a, adj_list in self.neighbours().items():
            for address_b in adj_list:
                node_a, node_b = nodes_list[address_a], nodes_list[address_b]
                graph.add_edge(node_a, node_b)
        return graph

    def draw(self, **kwargs):
        """Draw a topology graph using NetworkX and Matplotlib.

        Draw the graph with Matplotlib and NetworkX with nodes with fixed
        positions, and optional edges for connections and/or for
        neighbours.

        All styling attributes are optional. If not provided, defaults
        from :func:`senere.options.defaults` are used.

        Other Parameters
        ----------------
        sensor_color : color string, optional
            Color of the nodes with ``type='sensor'``

        gateway_color : color string, optional
            Color of the nodes with ``type='gateway'``

        draw_conn_edges : bool, optional (default=True)
            Flag indicating whether to draw edges between connected nodes

        draw_neigh_edges : bool, optional (default=False)
            Flag indicating whether to draw edges between neighbour nodes

        conn_line_width : integer, optional
            Line width of the edges representing connections

        conn_line_style : string, optional
            Line style of the edges representing connections
            (solid|dashed|dotted,dashdot)

        neigh_line_width : integer, optional
            Line width of the edges representing neighbourhood relation

        neigh_line_style : string, optional
            Line style of the edges representing neighbourhood relation
            (solid|dashed|dotted,dashdot)
        """
        conn_graph = self.get_connections_graph()
        node_list = conn_graph.nodes(data=True)

        # Assigning positions:
        positions = {node: (attr['x'], attr['y']) for node, attr in node_list}

        # Assigning colors:
        colors_dict = {
            SENSOR_NODE: kwargs.get('sensor_color', defaults['sensor_color']),
            GATEWAY_NODE: kwargs.get('gateway_color', defaults['gateway_color'])
        }
        colors = [colors_dict[attrs['type']] for _, attrs in node_list]

        # Build a new graph:
        graph = nx.MultiGraph()
        graph.add_nodes_from(node_list)

        if kwargs.get('draw_conn_edges', True):
            style = kwargs.get('conn_line_style', defaults['conn_line_style'])
            width = kwargs.get('conn_line_width', defaults['conn_line_width'])
            graph.add_edges_from(conn_graph.edges(), style=style, width=width)

        if kwargs.get('draw_neigh_edges', False):
            style = kwargs.get('neigh_line_style', defaults['neigh_line_style'])
            width = kwargs.get('neigh_line_width', defaults['neigh_line_width'])
            neighbour_edges = []
            neighbours = self.neighbours()
            for node, adj in neighbours.items():
                neighbour_edges.extend((node, neighbour) for neighbour in adj)
            graph.add_edges_from(neighbour_edges, style=style, width=width)

        edges_attrs = [e[-1] for e in graph.edges(data=True)]
        style = [e['style'] for e in edges_attrs]
        width = [e['width'] for e in edges_attrs]

        kds = {}
        if 'ax' in kwargs:
            kds['ax'] = kwargs['ax']
        nx.draw_networkx(graph, positions, node_color=colors, style=style,
                         width=width, **kds)

    def neighbours(self):
        nodes = self.nodes.all()
        neighbours = {node.address: [] for node in nodes}
        for i, node_a in enumerate(nodes):
            for node_b in nodes[i+1:]:
                if distance_between(node_a, node_b) <= min(
                        node_a.radio_range, node_b.radio_range):
                    neighbours[node_a.address].append(node_b.address)
                    neighbours[node_b.address].append(node_a.address)
        return neighbours

    def shift_addresses(self, offset: int):
        # Update nodes:
        for node in self.nodes.all():
            node.address += offset

        # Update nodes table:
        new_nodes = {
            addr + offset: node for addr, node in self._nodes.items()}
        self._nodes = new_nodes

        # Update connections:
        new_connections = {
            from_addr + offset: to_addr + offset
            for from_addr, to_addr in self._connections.items()}
        self._connections = new_connections

    def shift_pos(self, dx, dy):
        for node in self.nodes.all():
            node.x += dx
            node.y += dy

    @staticmethod
    def join(*topologies):
        nodes, connections = [], []
        for t in topologies:
            nodes.extend(t.nodes.all())
            connections.extend(t.connections.all())
        return Topology(nodes=nodes, connections=connections)

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

    def add(self, address, node_type, x, y, radio_range=None):
        radio_range = radio_range or defaults['radio_range']
        node = Node(address, node_type, x, y, radio_range)
        self.__owner._nodes[address] = node

    def add_from(self, sequence):
        for record in sequence:
            if hasattr(record, 'keys'):
                self.add(**record)
            else:
                self.add(*record)

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

    def values(self, keys, order_by=None, flat=False):
        nodes = self.all(order_by)
        if flat and len(keys) == 1:
            return [getattr(node, keys[0]) for node in nodes]
        return [{key: getattr(node, key) for key in keys} for node in nodes]

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

    def add_from(self, sequence):
        for record in sequence:
            if hasattr(record, 'keys'):
                self.add(**record)
            else:
                self.add(*record)

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

    def has_next_hop(self, from_addr):
        return from_addr in self.owner._connections

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
# noinspection PyPep8Naming
def build_tree_topology(depth, arity=1, dx=10, dy=10, roe=0.1):
    D, A = depth, arity

    # Compute distances between nodes at d-th level:
    delta_x = np.zeros(D + 1)
    delta_x[D] = dx
    for d in range(D - 1, -1, -1):
        delta_x[d] = delta_x[d + 1] * A

    # Compute X-width of children in a subtree at d-th level:
    width = (A - 1) * delta_x

    # Compute number of nodes at d-th level:
    num_nodes = np.zeros(D + 1, dtype=int)
    num_nodes[0] = 1
    for d in range(1, D + 1):
        num_nodes[d] = num_nodes[d - 1] * A

    # Compute nodes coordinates:
    pos_x = list(np.zeros(num_nodes[d]) for d in range(D + 1))
    pos_y = np.zeros(D + 1)
    for d in range(D, -1, -1):
        offset = 0 if d == D else pos_x[d + 1][0] + 0.5 * width[d + 1]
        x_intervals = [offset] + [delta_x[d]] * (num_nodes[d] - 1)
        pos_x[d] = np.cumsum(x_intervals)
        pos_y[d] = 0 if d == D else pos_y[d + 1] + dy

    # Compute radio ranges for each level:
    R = (1 + roe) * np.sqrt((width/2) ** 2 + dy ** 2)
    # Since root doesn't have parent, its radio range is the same as for
    # its children, if depth is greater then zero:
    R[0] = R[1] if D > 0 else defaults['radio_range']
    # Only leafs at last level, so their distances should be determined by
    # connection to parent only:
    R[D] = R[D - 1]

    # Compute addresses of the leftmost node at each level:
    first_address = np.cumsum([1] + list(num_nodes))[:-1]

    # Now we can build a topology. We start from the gateway at the root:
    topology = Topology()
    topology.nodes.add(1, GATEWAY_NODE, pos_x[0][0], pos_y[0], R[0])
    address = 2
    for d in range(1, D + 1):
        parent = first_address[d - 1]
        y = pos_y[d]
        r = max(R[d - 1], R[d])
        for i in range(num_nodes[d]):
            if i > 0 and i % A == 0:
                parent += 1
            topology.nodes.add(address, SENSOR_NODE, pos_x[d][i], y, r)
            topology.connections.add(address, parent)
            address += 1
    return topology


def build_forest_topology(num_trees, depth, arity=1, dx=10, dy=10, roe=0.1,
                          dt=10):
    trees = [build_tree_topology(depth, arity, dx, dy, roe)
             for _ in range(num_trees)]

    for i, tree in enumerate(trees):
        if i == 0:
            continue
        prev_tree = trees[i - 1]
        address_offset = max(prev_tree.nodes.values(['address'], flat=True))
        x = max(prev_tree.nodes.values(['x'], flat=True))
        tree.shift_addresses(address_offset)
        tree.shift_pos(x + dt, 0)

    forest = Topology.join(*trees)
    return forest


def build_random_topology(num_gateways, num_sensors, radio_range=10.0,
                          min_distance=2.0, min_gw_distance=20.0,
                          max_gw_distance=40.0, start_pos=(100, 100)):
    # 1) Find positions for gateways:
    area = GridArea(min_gw_distance, max_gw_distance, [start_pos])
    area.add_random_points(num_gateways-1)
    gateways_positions = area.all_points

    # 2) Find positions for sensors:
    area = GridArea(min_distance, radio_range, gateways_positions)
    area.add_random_points(num_sensors)
    sensors_positions = area.added_points

    # 3) Create a topology and add nodes:
    t = Topology()
    t.nodes.add_from([
        {'address': i + 1, 'node_type': GATEWAY_NODE,
         'x': pos[0], 'y': pos[1], 'radio_range': radio_range
         } for i, pos in enumerate(gateways_positions)])
    t.nodes.add_from([
        {'address': i + num_gateways + 1, 'node_type': SENSOR_NODE,
         'x': pos[0], 'y': pos[1], 'radio_range': radio_range
         } for i, pos in enumerate(sensors_positions)])

    # 4) Build shortest paths from gateways:
    from .routing import build_routes
    routes = build_routes(t)
    for route in routes:
        if route.source != route.gateway:
            t.connections.add(route.source, route.next_hop)

    return t
