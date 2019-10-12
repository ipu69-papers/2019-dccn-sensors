import numpy as np
import pytest
from numpy.random.mtrand import exponential

from senere import simulate_network, build_tree_topology


@pytest.mark.skip
def test_unconnected_nodes():
    """Test a network with unconnected N nodes, having the same reliability
     and restore exponential distributions with rates A and B respectively.

     We also assume that restore starts after the K-th node is down and
     takes the same time, no matter how many stations are being restored.
     """
    num_nodes = 5             # number of stations in the network
    num_critical_errors = 1   # number of stations being down to start repair
    mean_operability = 100.0  # mean time before an accident
    mean_repair = 20.0        # mean time a repair takes

    # First, we estimate the expected stationary distribution of the number
    # of operable nodes in the network using a simple Markov chain. Here
    # the probability `p_n` that `n` stations are operable is estimated as:
    # `p_n = a^n * b / (a + b)^(n+1)` for n < N,
    # `p_N = a^N / (a + b)^N,
    # where a = 1/A - failure rate, b = 1/B - repair rate:
    # FIXME: HERE WE ASSUME THAT REPAIR STARTS AFTER THE FIRST FAILURE!!
    failure_rate = 1.0 / mean_operability
    repair_rate = 1.0 / mean_repair
    analytic_p = np.zeros(num_nodes + 1)
    analytic_p[0] = repair_rate / (failure_rate + repair_rate)
    for n in range(1, num_nodes):
        analytic_p[n] = analytic_p[n - 1] * (
                failure_rate / (repair_rate + failure_rate))
    analytic_p[num_nodes] = analytic_p[num_nodes - 1] * (
            failure_rate / repair_rate)

    # Second, we build the topology:
    topology = build_tree_topology(depth=0, num_trees=num_nodes)

    # Then, we launch the simulation:
    sim_ret = simulate_network(
        topology, num_runs=10, stime_limit=10e6,
        failure_interval=exponential(mean_operability),
        repair_interval=exponential(mean_repair))

    # Finally, we compare the collected data:
    assert np.allclose(analytic_p, sim_ret.num_failed_stationary_distribution)
