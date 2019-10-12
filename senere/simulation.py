import numpy as np
from pydesim import Model, simulate, Trace

from senere.network import Network
from senere.options import defaults


__all__ = [
    'simulate_network',
    'average_pmfs',
]


def average_pmfs(vectors):
    if not vectors:
        raise ValueError
    max_order = max(len(v) for v in vectors)
    num_vectors = len(vectors)
    vectors = (np.hstack((v, np.zeros(max_order - len(v)))) for v in vectors)
    return sum(vectors) / num_vectors


class _SimRet:
    def __init__(self, results):
        _rs = list(results)
        self.num_failed_pmf = average_pmfs([r.num_failed.pmf() for r in _rs])
        self.num_offline_pmf = average_pmfs([r.num_offline.pmf() for r in _rs])


class ModelData(Model):
    def __init__(self, sim):
        super().__init__(sim)
        # Topology comprises:
        # - `nodes`: each having position, properties
        # - `static_connections`: optional dictionary with static connections
        # We use it as a template for network creation.
        self.network = Network(sim.params.topology)
        self.network.connect()
        self.repair_started = False
        self.failed_nodes = []

        # Statistics:
        self.num_failed = Trace()
        self.num_offline = Trace()

        # Record initial trace data:
        t = sim.stime
        self.num_failed.record(t, 0)
        self.num_offline.record(t, len(self.network.get_offline_nodes()))

    def handle_failure(self, node):
        """Handle node failure. Upon failure the following actions take place:

        1) a node is marked as turned off in the network;

        2) if repair hasn't started yet, we check whether enough nodes
           already failed:
           if num_offline_nodes > num_offline_till_repair, start the repair.
        """
        self.network.turn_off(node)
        self.failed_nodes.append(node)

        # We treat all offline nodes as broken, while some of them are
        # offline since the routers they were connected to became unavailable:
        num_offline_nodes = len(self.network.get_offline_nodes())
        if (num_offline_nodes > self.sim.params.num_offline_till_repair and
                not self.repair_started):
            self.schedule_repair()

        # Record statistics:
        self.num_failed.record(self.sim.stime, len(self.failed_nodes))
        self.num_failed.record(self.sim.stime, num_offline_nodes)

    def handle_repair_finished(self):
        """Handle repair of all nodes finished.

        Here we assume that during repair all failed nodes were fixed,
        so we schedule their failures again.
        """
        self.network.turn_on(self.failed_nodes)
        self.network.connect()
        self.failed_nodes = []
        self.repair_started = False

        # Record statistics:
        t = self.sim.stime
        self.num_failed.record(t, 0)
        self.num_offline.record(t, len(self.network.get_offline_nodes()))

    def schedule_failure(self, node):
        """Schedule next failure event for a given node.

        :param node: network node
        """
        interval = self.sim.params.failure_interval()
        self.sim.schedule(interval, self.handle_failure, args=(node,))

    def schedule_repair(self):
        """Schedule next repair duration. Since all broken nodes are
        repaired at once, we do not distinguish nodes here.

        If the repair has already started, we ignore this call and
        silently quit.
        """
        if not self.repair_started:
            interval = self.sim.params.repair_interval()
            self.sim.schedule(interval, self.handle_repair_finished)
            self.repair_started = True


def simulate_network(topology, **kwargs):
    stime_limit = kwargs.get('stime_limit', defaults['stime_limit'])
    num_runs = kwargs.get('num_runs', defaults['num_runs'])
    results = []
    for i_run in range(num_runs):
        results.append(simulate(ModelData, stime_limit=stime_limit, params={
            'topology': topology,
        }))
    return _SimRet(results)
