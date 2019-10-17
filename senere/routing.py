from collections import namedtuple, deque

import numpy as np

from senere.topology import GATEWAY_NODE, SENSOR_NODE

RouteRecord = namedtuple('RouteRecord', ['source', 'next_hop', 'gateway',
                                         'distance', 'static'])


def build_static_routes(topology, exclude=None):
    exclude = exclude or []
    nodes = topology.nodes.values(['address', 'type'])

    # Filter excluded nodes:
    nodes = [n for n in nodes if n['address'] not in exclude]
    gateways = [n['address'] for n in nodes if n['type'] == GATEWAY_NODE]

    # Build a precursors dictionary:
    #   node -> [nodes using this node as next hop]
    precursors = {n['address']: [] for n in nodes}
    for conn in topology.connections.all():
        from_addr, to_addr = conn
        if from_addr not in exclude and to_addr not in exclude:
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
