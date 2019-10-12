class Network:
    def __init__(self, topology):
        self.__topology = topology

    @property
    def topology(self):
        return self.__topology

    def connect(self):
        """Connect nodes to gates via either shortest paths or static routes.
        """
        if self.topology.static_connections:
            pass


    def turn_off(self, node):
        """Turn node off and remove all its connections.
        """
        pass

    def turn_on(self, target):
        """Turn one or multiple nodes on.
        """
        pass

    def get_offline_nodes(self):
        """Get a list of all nodes either turned off or lost their connections.
        """
        pass
