from senere.topology import Topology, GATEWAY_NODE, SENSOR_NODE, Node


def test_shifting_address():
    t = Topology()
    t.nodes.add(1, GATEWAY_NODE, 0, 0, 10)
    t.nodes.add(20, GATEWAY_NODE, 20, 0, 10)
    t.nodes.add(2, SENSOR_NODE, 5, 0, 10)
    t.nodes.add(3, SENSOR_NODE, 0, 5, 10)
    t.nodes.add(4, SENSOR_NODE, 12, 0, 10)
    t.nodes.add(21, SENSOR_NODE, 29, 0, 10)
    t.nodes.add(30, SENSOR_NODE, 100, 100, 10)
    t.connections.add_from([(2, 1), (3, 1), (4, 2), (21, 20)])

    t.shift_addresses(100)

    assert t.nodes.get(101) == Node(101, GATEWAY_NODE, 0, 0, 10)
    assert t.nodes.get(120) == Node(120, GATEWAY_NODE, 20, 0, 10)
    assert t.nodes.get(102) == Node(102, SENSOR_NODE, 5, 0, 10)
    assert t.nodes.get(103) == Node(103, SENSOR_NODE, 0, 5, 10)
    assert t.nodes.get(104) == Node(104, SENSOR_NODE, 12, 0, 10)
    assert t.nodes.get(121) == Node(121, SENSOR_NODE, 29, 0, 10)
    assert t.nodes.get(130) == Node(130, SENSOR_NODE, 100, 100, 10)

    assert t.connections.all(order_by='from_addr') == [
        (102, 101), (103, 101), (104, 102), (121, 120)
    ]


def test_shifting_position():
    t = Topology()
    t.nodes.add(1, GATEWAY_NODE, 0, 0, 10)
    t.nodes.add(2, SENSOR_NODE, 8, 0, 10)
    t.nodes.add(3, SENSOR_NODE, 0, 8, 10)
    t.nodes.add(4, SENSOR_NODE, 100, 100, 10)
    t.connections.add_from([(2, 1), (3, 1)])

    t.shift_pos(dx=23, dy=37)

    assert t.nodes.get(1) == Node(1, GATEWAY_NODE, 23, 37, 10)
    assert t.nodes.get(2) == Node(2, SENSOR_NODE, 31, 37, 10)
    assert t.nodes.get(3) == Node(3, SENSOR_NODE, 23, 45, 10)
    assert t.nodes.get(4) == Node(4, SENSOR_NODE, 123, 137, 10)
    assert t.connections.all(order_by='from_addr') == [(2, 1), (3, 1)]
