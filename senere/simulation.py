import numpy as np
from pydesim import Model, simulate, Trace, Logger

from senere.network import Network
from senere.options import defaults


__all__ = [
    'simulate_network',
    'average_pmfs',
]


def pmf_to_array(pmf):
    if not pmf:
        return np.asarray([])
    order = max(pmf.keys()) + 1
    result = np.zeros(order)
    for key, value in pmf.items():
        result[key] = value
    return result


def average_pmfs(pmfs):
    if not pmfs:
        raise ValueError
    vectors = [pmf_to_array(pmf) for pmf in pmfs]
    max_order = max(len(v) for v in vectors)
    num_vectors = len(vectors)
    vectors = (np.hstack((v, np.zeros(max_order - len(v)))) for v in vectors)
    return sum(vectors) / num_vectors


class _SimRet:
    def __init__(self, results):
        _rs = [r.data for r in results]
        n = len(_rs)
        self.num_failed_pmf = average_pmfs([r.num_failed.pmf() for r in _rs])
        self.num_offline_pmf = average_pmfs([r.num_offline.pmf() for r in _rs])
        self.operable = sum(r.operable.timeavg() for r in _rs) / n

        self.runs = results


class ModelData(Model):
    def __init__(self, sim):
        super().__init__(sim)

        # Topology comprises:
        # - `nodes`: each having position, properties
        # - `static_connections`: optional dictionary with static connections
        # We use it as a template for network creation.
        self.network = Network(sim.params.topology)
        self.repair_started = False
        self.failed_nodes = []
        self.routing_mode = sim.params.routing_mode
        sim.logger.level = sim.params.log_level

        # Statistics:
        self.num_failed = Trace()
        self.num_offline = Trace()
        self.operable = Trace()

        # Record initial trace data:
        t = sim.stime
        self.num_failed.record(t, 0)
        self.num_offline.record(t, len(self.network.get_offline_nodes()))
        self.operable.record(t, 1)

        # Build network routes:
        self.network.build_routing_table(self.routing_mode)
        for sensor in self.network.sensors():
            self.schedule_failure(sensor)

    def handle_failure(self, node):
        """Handle node failure. Upon failure the following actions take place:

        1) a node is marked as turned off in the network;

        2) if repair hasn't started yet, we check whether enough nodes
           already failed:
           if num_offline_nodes > num_offline_till_repair, start the repair.
        """
        self.network.turn_off(node)
        self.failed_nodes.append(node)

        # If static routing is used, no actual re-routing will take place.
        # However, in case of dynamic routing using, this can lead to
        # network reconfiguration and new alternative paths
        self.network.build_routing_table(self.routing_mode)

        # Count failed and offline nodes and record statistics:
        num_offline_nodes = len(self.network.get_offline_nodes())
        num_failed_nodes = len(self.failed_nodes)
        self.num_failed.record(self.sim.stime, num_failed_nodes)
        self.num_offline.record(self.sim.stime, num_offline_nodes)

        # We treat all offline nodes as broken, while some of them are
        # offline since the routers they were connected to became unavailable:
        self.sim.logger.debug(f'node {node} failed. {num_failed_nodes} nodes '
                              f'failed, {num_failed_nodes} are offline. '
                              f'Failed nodes: {self.failed_nodes}')
        if (num_offline_nodes >= self.sim.params.num_offline_till_repair and
                not self.repair_started):
            self.schedule_next_repair()
            self.operable.record(self.sim.stime, 0)

    def handle_repair_finished(self, node):
        """Handle repair of all nodes finished.

        Here we assume that during repair all failed nodes were fixed,
        so we schedule their failures again.
        """
        # Turn on the repaired node, rebuild a routing table and schedule the
        # next failure:
        self.sim.logger.debug(f'node {node} repair finished')
        self.network.turn_on(node)
        self.network.build_routing_table(self.routing_mode)
        self.schedule_failure(node)

        # Remove the repaired node from the failed list, count failed and
        # offline nodes:
        self.failed_nodes.remove(node)
        num_failed = len(self.failed_nodes)
        num_offline = len(self.network.get_offline_nodes())

        # Record statistics:
        t = self.sim.stime
        self.num_failed.record(t, num_failed)
        self.num_offline.record(t, num_offline)

        # Check whether there are other failed nodes. If they exist, schedule
        # the next repair. Otherwise, mark repair end.
        if num_failed > 0:
            self.schedule_next_repair()
        else:
            self.repair_started = False
            self.operable.record(t, 1)

    def schedule_failure(self, node):
        """Schedule next failure event for a given node.

        :param node: network node
        """
        interval = self.sim.params.failure_interval()
        self.sim.schedule(interval, self.handle_failure, args=(node,))

    def schedule_next_repair(self):
        """Schedule next repair duration. Since all broken nodes are
        repaired at once, we do not distinguish nodes here.
        """
        if not self.failed_nodes:
            raise RuntimeError('can not schedule repair - no failed nodes')

        # Select a random node to repair, and schedule repair end:
        node_index = np.random.randint(len(self.failed_nodes))
        node = self.failed_nodes[node_index]

        if not self.repair_started:
            interval = self.sim.params.repair_interval()
            self.repair_started = True
        else:
            interval = self.sim.params.cons_repair_interval()

        self.sim.logger.debug(f'started node {node} repair for {interval}s')
        self.sim.schedule(interval, self.handle_repair_finished,
                          args=(node,))


def simulate_network(topology, failure_interval, repair_interval,
                     num_offline_till_repair=2, **kwargs):
    stime_limit = kwargs.get('stime_limit', defaults['stime_limit'])
    num_runs = kwargs.get('num_runs', defaults['num_runs'])
    log_level = kwargs.get('log_level', Logger.Level.ERROR)
    routing_mode = {'static': Network.STATIC, 'dynamic': Network.DYNAMIC
                    }[kwargs.get('routing_mode', 'static')]
    cons_repair_interval = kwargs.get('cons_repair_interval', repair_interval)
    results = []
    for i_run in range(num_runs):
        results.append(simulate(ModelData, stime_limit=stime_limit, params={
            'topology': topology,
            'routing_mode': routing_mode,
            'failure_interval': failure_interval,
            'repair_interval': repair_interval,
            'num_offline_till_repair': num_offline_till_repair,
            'log_level': log_level,
            'cons_repair_interval': cons_repair_interval,
        }))
    return _SimRet(results)
