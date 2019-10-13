from senere.network import build_static_routes, RouteRecord, build_routes
from senere.topology import Topology, GATEWAY_NODE, SENSOR_NODE


#
# TEST STATIC ROUTING
#
def test_only_gateway_static_routes_exist_for_topology_without_connections():
    """Check if topology has no static connections, no static routes created.
    """
    topology = Topology()
    topology.nodes.add_from([
        dict(address=1, node_type=GATEWAY_NODE, x=0.0, y=0.0, radio_range=5),
        dict(address=5, node_type=GATEWAY_NODE, x=4.0, y=0.0, radio_range=5),
        dict(address=2, node_type=SENSOR_NODE, x=2.0, y=2.0, radio_range=5),
        dict(address=3, node_type=SENSOR_NODE, x=0.0, y=4.9, radio_range=5)
    ])
    routes = build_static_routes(topology)
    assert len(routes) == 2
    assert RouteRecord(1, 1, 1, 0, True) in routes
    assert RouteRecord(5, 5, 5, 0, True) in routes


def test_static_routes_correctly_built_for_forest_with_unconnected_nodes():
    """Test that static routes are built correctly for a forest topology.

    In this test we consider the following topology:

    ```
    (#1: 0,0)           (#3: 5,0)                     (#2: 100,0)
       ^  ^                    ^
       |  |                    |
       |  +--(#4: 2.5,2.5)   (#5: 5,2.5)
       |
    (#6: 0,5) <-- (#7: 5,5)                 (#8: 50,5)
    ```

    We expect the routes `1=>1`, `2=>2`, `3=>3`, `6=>1`, `7=>6`, `4=>1`
    and `5=>2`.
    """
    topology = Topology()
    topology.nodes.add_from([
        dict(address=1, node_type=GATEWAY_NODE, x=0, y=0, radio_range=10),
        dict(address=2, node_type=GATEWAY_NODE, x=100, y=0, radio_range=10),
        dict(address=3, node_type=GATEWAY_NODE, x=5, y=0, radio_range=10),
        dict(address=4, node_type=SENSOR_NODE, x=2.5, y=2.5, radio_range=10),
        dict(address=5, node_type=SENSOR_NODE, x=5, y=2.5, radio_range=10),
        dict(address=6, node_type=SENSOR_NODE, x=0, y=5, radio_range=10),
        dict(address=7, node_type=SENSOR_NODE, x=5, y=5, radio_range=10),
        dict(address=8, node_type=SENSOR_NODE, x=50, y=5, radio_range=10),
    ])
    topology.connections.add_from([(4, 1), (5, 3), (6, 1), (7, 6)])
    routes = build_static_routes(topology)
    assert len(routes) == 7
    assert RouteRecord(1, 1, 1, 0, True) in routes
    assert RouteRecord(2, 2, 2, 0, True) in routes
    assert RouteRecord(3, 3, 3, 0, True) in routes
    assert RouteRecord(4, 1, 1, 1, True) in routes
    assert RouteRecord(5, 3, 3, 1, True) in routes
    assert RouteRecord(6, 1, 1, 1, True) in routes
    assert RouteRecord(7, 6, 1, 2, True) in routes


def test_static_routing_ignores_cycles():
    """Test that if cycles preset in topology, they are ignored in routing.

    In this test we consider the following topology:

    ```
    (S2: 0,0) -----> (G1: 5,0) <---- (S5: 10,0)

            (S3: 2.5,5) <--> (S4: 7.5,5)
    ```

    We expect that only routes `1=>1`, `2=>1` and `5=>1` are created.
    """
    topology = Topology()
    topology.nodes.add_from([
        dict(address=1, node_type=GATEWAY_NODE, x=5, y=0, radio_range=10),
        dict(address=2, node_type=SENSOR_NODE, x=0, y=0, radio_range=10),
        dict(address=3, node_type=SENSOR_NODE, x=2.5, y=5, radio_range=10),
        dict(address=4, node_type=SENSOR_NODE, x=7.5, y=5, radio_range=10),
        dict(address=5, node_type=SENSOR_NODE, x=10, y=0, radio_range=10),
    ])
    topology.connections.add_from([(2, 1), (5, 1), (3, 4), (4, 3)])
    routes = build_static_routes(topology)
    assert len(routes) == 3
    assert RouteRecord(1, 1, 1, 0, True) in routes
    assert RouteRecord(2, 1, 1, 1, True) in routes
    assert RouteRecord(5, 1, 1, 1, True) in routes


#
# TEST DYNAMIC ROUTING
#
def test_build_routes_for_connected_graph():
    topology = Topology()
    topology.nodes.add(1, GATEWAY_NODE, x=0, y=0, radio_range=6)
    topology.nodes.add(2, GATEWAY_NODE, x=5, y=0, radio_range=6)
    topology.nodes.add(3, SENSOR_NODE, x=0, y=5, radio_range=6)
    topology.nodes.add(4, SENSOR_NODE, x=0, y=10, radio_range=6)
    topology.nodes.add(5, SENSOR_NODE, x=10.9, y=0, radio_range=6)
    routes = build_routes(topology)
    assert len(routes) == 5
    assert RouteRecord(1, 1, 1, 0, True) in routes
    assert RouteRecord(2, 2, 2, 0, True) in routes
    assert RouteRecord(3, 1, 1, 1, False) in routes
    assert RouteRecord(4, 3, 1, 2, False) in routes
    assert RouteRecord(5, 2, 2, 1, False) in routes


def test_build_routes_with_excluded_nodes():
    """Check that if we disable a node, routes won't use it.

    Topology:
    ```
                            [1]<--------+
                                        |
     (7)........(2)<-X    X->(6)       (4)<-+
                                            |
                (3) -----------------> (5)--+
    ```

    Sensor #3 can reach sensors 2, 6, and 5.
    After we turn off sensors #2 and #6, sensor #3 should be re-routed via #5.
    Sensor #7 is unreachable since it can be connected via sensor #2 only.
    """
    topology = Topology()
    topology.nodes.add(1, GATEWAY_NODE, x=15, y=0, radio_range=11)
    topology.nodes.add(2, SENSOR_NODE, x=10, y=5, radio_range=11)
    topology.nodes.add(3, SENSOR_NODE, x=10, y=10, radio_range=11)
    topology.nodes.add(4, SENSOR_NODE, x=20, y=5, radio_range=11)
    topology.nodes.add(5, SENSOR_NODE, x=20, y=10, radio_range=11)
    topology.nodes.add(6, SENSOR_NODE, x=15, y=5, radio_range=11)
    topology.nodes.add(7, SENSOR_NODE, x=0, y=5, radio_range=11)

    routes = build_routes(topology)
    assert len(routes) == 7
    assert (RouteRecord(3, 2, 1, 2, False) in routes or
            RouteRecord(3, 6, 1, 2, False) in routes)
    assert RouteRecord(7, 2, 1, 2, False) in routes

    routes = build_routes(topology, exclude=[2, 6])
    assert len(routes) == 4
    assert RouteRecord(1, 1, 1, 0, True) in routes
    assert RouteRecord(4, 1, 1, 1, False) in routes
    assert RouteRecord(5, 4, 1, 2, False) in routes
    assert RouteRecord(3, 5, 1, 3, False) in routes
