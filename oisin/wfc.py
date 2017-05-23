import random
from collections import defaultdict


class InconsistencyError(Exception):
    pass


class Collapser(object):
    def __init__(self, nodes, states):
        self.valid = {}
        self.dirty = {}
        self.states = frozenset(states)
        self.nodes = nodes
        for n in nodes:
            r = self.restrict(n)
            if r is None:
                self.valid[n] = self.states
            else:
                self.valid[n] = r
                if len(r) == 0:
                    raise InconsistencyError("Too restrictive at node %s" % n)
                self.tag_dirty(n)
        self.propagate()
        self.oldvalids = []

    def step(self):
        try:
            self.observe()
            self.propagate()
        except InconsistencyError:
            self.rewind()

    def rewind(self):
        while True:
            if not self.oldvalids:
                raise InconsistencyError("Rewound too far")
            self.valid, obs = self.oldvalids.pop()
            self.dirty = {}
            node, state = obs
            self.valid[node] = self.valid[node].difference([state])
            if len(self.valid[node]) == 0:
                raise InconsistencyError("No valid choices at node %s" % node)
            self.tag_dirty(node)
            try:
                self.propagate()
                return
            except InconsistencyError:
                pass

    def observe(self, node=None, value=None):
        if node is None:
            options = [x for x in self.valid if len(self.valid[x]) > 1]
            if not options:
                return
            node = min(options, key=lambda x: len(self.valid[x]))
        if value is None:
            value = self.choose_state(node)
        assert value in self.states
        if value not in self.valid[node]:
            raise InconsistencyError
        obs = (node, value)
        self.oldvalids.append((self.valid.copy(), obs))
        self.valid[node] = frozenset([value])
        self.tag_dirty(node)

    def choose_state(self, node):
        return random.choice(list(self.valid[node]))

    def propagate(self):
        up = True
        lastnode = -1
        while self.dirty:
            try:
                if up:
                    node = min(n for n in self.dirty if n >= lastnode)
                else:
                    node = max(n for n in self.dirty if n <= lastnode)
            except ValueError:
                up = not up
                continue
            nbs = self.dirty[node]
            lastnode = node
            del self.dirty[node]

            s = self.valid[node]
            n = len(s)
            for nb in nbs:
                s = s & self.conset(node, nb)
            if len(s) == 0:
                raise InconsistencyError("No valid choices at node %s" % node)
            elif len(s) != n:
                self.valid[node] = s
                self.tag_dirty(node)

    def tag_dirty(self, node):
        for nb in self.neighbours(node):
            assert node != nb
            s = self.dirty.get(nb, set())
            s.add(node)
            self.dirty[nb] = s

    def conset(self, node, nb):
        """Get a set of valid states for node, given the current states of nb"""
        states = set()
        for s in self.valid[nb]:
            cons = self.consistent(node, nb, s)
            states = states | cons
            if states == anything:
                break
        return states

    def resolved(self):
        for v in self.valid.values():
            if len(v) > 1:
                return False
        return True

    def report_valid(self):
        print([(node, len(self.valid[node])) for node in self.nodes])

    # implement these in subclasses

    def consistent(self, node, nb, s):
        """Get a set of valid states for node, given nb == s"""
        raise NotImplementedError

    def neighbours(self, node):
        """Get a list of nodes which can be directly affected by node"""
        raise NotImplementedError

    def restrict(self, node):
        """Get the set of possible states for a node (or None for any)"""
        return None


class MarkovCollapser(Collapser):
    def __init__(self, sentences, length):
        self.length = length
        nodes = range(length)
        states = self.read_tokens(sentences)
        Collapser.__init__(self, nodes, states)

    def read_tokens(self, sentences):
        self.starts = set()
        self.ends = set()
        self.nxt = defaultdict(set)
        self.prv = defaultdict(set)
        states = set()
        for sent in sentences:
            self.starts.add(sent[0])
            self.ends.add(sent[-1])
            for i, t1 in enumerate(sent[:-1]):
                t2 = sent[i + 1]
                self.nxt[t1].add(t2)
                self.prv[t2].add(t1)
                states.add(t1)
                states.add(t2)
        return states

    def restrict(self, node):
        if node == 0:
            return self.starts
        if node == self.length - 1:
            return self.ends

    def neighbours(self, node):
        if node == 0:
            return [1]
        if node == self.length - 1:
            return [self.length - 2]
        return [node - 1, node + 1]

    def consistent(self, node, nb, s):
        if node - nb == 1:
            return self.nxt[s]
        elif node - nb == -1:
            return self.prv[s]

    def sample(self):
        return [random.choice(list(self.valid[i])) for i in range(self.length)]


class FakeSet(object):
    def __rand__(self, other):
        assert not isinstance(other, FakeSet)
        return self & other

    def __ror__(self, other):
        assert not isinstance(other, FakeSet)
        return self | other


class Anything(FakeSet):
    def __and__(self, other):
        return other

    def __or__(self, other):
        return self


anything = Anything()


class Except(FakeSet):
    def __init__(self, ex):
        self.ex = ex

    def __and__(self, other):
        if isinstance(other, Except):
            return Except(self.ex | other.ex)
        if isinstance(other, Anything):
            return self
        return other - self.ex

    def __or__(self, other):
        if isinstance(other, Except):
            ex = self.ex & other.ex
            if ex:
                return Except(ex)
            else:
                return anything
        if isinstance(other, Anything):
            return self
        return Except(self.ex - other)
