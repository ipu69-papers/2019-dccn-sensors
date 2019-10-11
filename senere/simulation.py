import numpy as np


class _SimRet:
    def __init__(self):
        self.num_failed_stationary_distribution = np.zeros(1)


def simulate_network(topology, **kwargs):
    return _SimRet()
