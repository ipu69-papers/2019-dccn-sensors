from itertools import product

import numpy as np
import pytest
from numpy.ma import sqrt

from senere.options import defaults
from senere.topology import Topology, GATEWAY_NODE, SENSOR_NODE, Node, \
    build_tree_topology, build_forest_topology


def test_shifting_address():
    t = Topology()
    t.nodes.add(1, GATEWAY_NODE, 0, 0, 10)
    t.nodes.add(2, SENSOR_NODE, 5, 0, 10)
    t.nodes.add(3, SENSOR_NODE, 12, 0, 10)
    t.nodes.add(4, SENSOR_NODE, 100, 100, 10)
    t.connections.add_from([(2, 1), (3, 2)])

    t.shift_addresses(100)

    assert t.nodes.get(101) == Node(101, GATEWAY_NODE, 0, 0, 10)
    assert t.nodes.get(102) == Node(102, SENSOR_NODE, 5, 0, 10)
    assert t.nodes.get(103) == Node(103, SENSOR_NODE, 12, 0, 10)
    assert t.nodes.get(104) == Node(104, SENSOR_NODE, 100, 100, 10)

    assert t.connections.all(order_by='from_addr') == [(102, 101), (103, 102)]


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


def test_join():
    t1 = Topology()
    t1.nodes.add(1, GATEWAY_NODE, 0, 0, 10)
    t1.nodes.add(2, SENSOR_NODE, 4, 0, 10)
    t1.connections.add(2, 1)

    t2 = Topology()
    t2.nodes.add(10, GATEWAY_NODE, 8, 8, 10)
    t2.nodes.add(11, SENSOR_NODE, 6, 2, 10)
    t2.connections.add(11, 10)

    t = Topology.join(t1, t2)
    assert t1.nodes.count() == 2
    assert t2.nodes.count() == 2
    assert t.nodes.values(['address'], order_by='address', flat=True) == [
        1, 2, 10, 11]
    assert t.connections.all(order_by='from_addr') == [(2, 1), (11, 10)]


#############################################################################
# TOPOLOGY PRODUCING METHODS TESTS
#############################################################################
def test_tree_topology_with_zero_depth_contains_gateway_only():
    """Check build_tree_topology() returns a topology with a single node
    and without connections when depth is 0"""
    t = build_tree_topology(depth=0, arity=1, dy=4)
    nodes = t.nodes.all()
    assert len(nodes) == 1
    assert nodes[0].type == GATEWAY_NODE
    assert nodes[0].address == 1
    assert (nodes[0].x, nodes[0].y) == (0, 0)
    assert nodes[0].radio_range == defaults['radio_range']
    assert t.connections.count() == 0


def test_binary_tree_topology():
    """Build a binary tree with depth 3 and check nodes and connections in it.
    """
    t = build_tree_topology(depth=3, arity=2, dx=1, dy=1, roe=0.2)
    nodes = t.nodes.all(order_by='address')
    connections = t.connections.all(order_by='from_addr')

    # Radio ranges at levels 0, 1 and 2 are determined by radio range,
    # required by nodes at level 1:
    # - root connects only children at level 1
    # - children at level 2 need less range for their children, so
    #   distance is determined by connection to parent:
    range_1 = 1.2 * sqrt(5)
    # However, leaves at level 3 have radio ranges, determined by connections
    # to their parents at level 2:
    range_2 = 1.2 * sqrt(2)

    # Check nodes number and the root:
    assert t.nodes.count() == 15
    assert t.nodes.get(1) == Node(1, GATEWAY_NODE, 3.5, 3, range_1)

    # Check nodes at level 1:
    for i in [0, 1]:
        addr, x, y = i + 2, 1.5 + 4 * i, 2
        assert t.nodes.get(addr) == Node(addr, SENSOR_NODE, x, y, range_1)

    # Check nodes at level 2:
    for i in range(4):
        addr, x, y = i + 4, 0.5 + 2 * i, 1
        assert t.nodes.get(addr) == Node(addr, SENSOR_NODE, x, y, range_1)

    # Check nodes at level 3:
    for i in range(4):
        addr, x, y = i + 8, i, 0
        assert t.nodes.get(addr) == Node(addr, SENSOR_NODE, x, y, range_2)

    # Check connections:
    assert t.connections.all(order_by='from_addr') == [
        (2, 1), (3, 1), (4, 2), (5, 2), (6, 3), (7, 3),
        (8, 4), (9, 4), (10, 5), (11, 5), (12, 6), (13, 6), (14, 7), (15, 7)]


def test_forest_topology():
    """Test building a forest topology.
    """
    t = build_forest_topology(2, depth=3, arity=3, dx=2.5, dy=1.25, roe=0.4,
                              dt=5)
    nodes = t.nodes.all(order_by='address')
    connections = t.connections.all(order_by='from_addr')
    assert len(nodes) == 80
    assert len(connections) == 78

    # - ranges on levels 0, 1, 2 are the same and determined by sufficient
    # distances for level 1;
    # - range on level 3 is determined by sufficient distances for connecting
    # to parents on level 2.
    range_1 = 1.4 * sqrt(22.5**2 + 1.25**2)
    range_2 = 1.4 * sqrt(7.5**2 + 1.25**2)

    # Estimate positions and addresses by level:
    y = [3.75, 2.5, 1.25, 0]
    x1 = [np.asarray([32.5]),
          10.0 + np.arange(3) * 22.5,
          2.5 + np.arange(9) * 7.5,
          np.arange(27) * 2.5]
    x = [x1, [pos + 70 for pos in x1]]
    addr1 = [np.asarray([1]), np.arange(3) + 2, np.arange(9) + 5,
             np.arange(27) + 14]
    addr = [addr1, [a + 40 for a in addr1]]

    # Validate nodes level by level:
    for level in range(4):
        for tree in range(2):
            for index in range(3**level):
                address = addr[tree][level][index]
                expected_node = Node(
                    address, GATEWAY_NODE if level == 0 else SENSOR_NODE,
                    x[tree][level][index], y[level],
                    range_1 if level < 3 else range_2)
                assert expected_node == t.nodes.get(address)

    # Validate connections:
    for level, tree in product(range(3), range(2)):
        offset = 0 if tree == 0 else 41
        for index in range(3**level):
            address = addr[tree][level][index]
            children_addresses = addr[tree][level+1][(3*index):(3*(index+1))]
            for child_address in children_addresses:
                assert (child_address, address) in connections
