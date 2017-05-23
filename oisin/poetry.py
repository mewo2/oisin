from collections import defaultdict, namedtuple
import re
import pronouncing

from . import wfc

__all__ = [
    "PoemCollapser",
    "Foot",
    "iamb",
    "trochee",
    "brach",
    "amphibrach",
    "anapest",
    "dactyl",
    "sonnet",
    "petrarch",
    "ottava",
    "limerick",
    "ballad",
    "couplet",
    "verse",
    "blank",
    "iambic",
    "Line",
    "balladize",
    "stepthrough"
]
pronouncing.init_cmu()

prons = dict()

for k, v in pronouncing.pronunciations:
    if k not in prons:
        prons[k] = v


def syllrhyme(word):
    try:
        p = prons[word.lower()]
    except KeyError:
        return 0, ""
    return pronouncing.syllable_count(p), pronouncing.rhyming_part(p)


def rhyme(word, cache={}):
    try:
        return cache[word]
    except KeyError:
        pass
    p = prons[word.lower()]
    r = pronouncing.rhyming_part(p)
    if r.endswith('M'):
        r = r[:-1] + 'N'
    cache[word] = r
    return r


weak = set(["a", "an", "the", "to", "of", "said", "but", "and", "in"])


def stressed(word, syll, cache={}):
    if word == '*':
        return True
    try:
        return cache[word, syll]
    except KeyError:
        pass
    stress = pronouncing.stresses(prons[word.lower()])
    if '0' not in stress:
        stress = re.sub('2', '0', stress)
    result = word not in weak and (len(stress) == 1 or stress[syll] != '0')
    cache[word, syll] = result
    return result


def unstressed(word, syll, cache={}):
    if word == '*':
        return True
    try:
        return cache[word, syll]
    except KeyError:
        pass
    stress = pronouncing.stresses(prons[word.lower()])
    if '0' not in stress:
        stress = re.sub('2', '0', stress)
    result = len(stress) == 1 or stress[syll] == '0'
    cache[word, syll] = result
    return result


def subseqs(seq, length, pad=None):
    subs = []
    for i in range(len(seq) - length + 1):
        subs.append(tuple(seq[i:i + length]))
    if pad is not None:
        for i in range(length - 1, 0, -1):
            subs.append(tuple(seq[-i:]) + tuple(pad[:length - i]))
    return subs


def wordseqs(sent, length):
    sylls = []
    for w in sent:
        if w.lower() not in prons:
            return []
        n, _ = syllrhyme(w)
        sylls.extend([(w, i) for i in range(n)])
    return subseqs(sylls, length, [('*', i) for i in range(length)])


class PoemCollapser(wfc.Collapser):
    def __init__(self, corpus, scheme, length=3):
        self.scheme = scheme
        self.corpus = corpus
        self.length = length

        self.starts = set()
        self.ends = set()
        states = set()
        self.statepos = defaultdict(list)
        n = len(corpus)
        for i, sent in enumerate(corpus):
            seqs = wordseqs(sent, length)
            if len(seqs) < length:
                continue
            states.update(seqs)
            self.starts.add(seqs[0])
            self.ends.add(seqs[-length])
            for state in seqs:
                self.statepos[state].append((i + 1.) / (n + 2.))
        nodes = range(sum(line.syllcount for line in scheme))

        self.prefix = defaultdict(set)
        self.suffix = defaultdict(set)
        for s in states:
            for i in range(1, length):
                self.prefix[s[:i]].add(s)
                self.suffix[s[-i:]].add(s)
                for s2 in states:
                    if s2[-i][0] == '*' and s2[-i][1] > 0:
                        self.suffix[s[:i]].add(s2)

        for i in range(1, length):
            seq = tuple(('*', j) for j in range(i, length))
            for j in range(1, length):
                self.prefix[seq[:j]] = wfc.anything

        for s in self.starts:
            for i in range(1, length):
                self.prefix[tuple(('*', j) for j in range(i))].add(s)
                for e in self.ends:
                    suf = e[-i:] + tuple(('*', j) for j in range(length - i))
                    assert suf in states, (i, e, suf)
                    self.suffix[s[:length - i]].add(suf)

        breaks = [0]
        for line in scheme:
            breaks.append(breaks[-1] + line.syllcount)
        self.breaks = breaks[1:]

        rhymesets = defaultdict(list)
        syll = -1
        for line in scheme:
            syll += line.syllcount
            rhymesets[line.rhyme].append(syll)
        self.rhymes = defaultdict(list)
        for rs in rhymesets.values():
            for s in rs:
                self.rhymes[s] = [x for x in rs if x != s]

        self.rhymeswith = defaultdict(set)
        for s in states:
            rhymepart = rhyme(s[0][0])
            self.rhymeswith[rhymepart].add(s)

        wfc.Collapser.__init__(self, nodes, states)

    def neighbours(self, node):
        nbs = [
            x for x in range(node - self.length + 1, node + self.length)
            if x != node and 0 <= x <= self.nodes[-1]
        ]
        if node in self.rhymes:
            nbs += [n for n in self.rhymes if n != node]
        return nbs

    def consistent(self, node, nb, s):
        if node == nb:
            return wfc.anything
        if abs(node - nb) > self.length:
            rhymepart = rhyme(s[0][0])
            if node in self.rhymes[nb]:
                return set(x for x in self.rhymeswith[rhymepart]
                           if not x[0][0].endswith(
                               s[0][0]) and not s[0][0].endswith(x[0][0]))
            else:
                return wfc.Except(self.rhymeswith[rhymepart])
        elif node > nb:
            n = node - nb
            return self.prefix[s[n:]]
        elif node < nb:
            n = nb - node
            return self.suffix[s[:-n]]

    def restrict(self, node):
        states = self.states
        if node == 0:
            states = self.starts
        sylls = 0
        for line in self.scheme:
            if node == sylls:
                states = set([s for s in states if s[0][1] == 0])
            sylls += line.syllcount
        pos = node
        for line in self.scheme:
            if pos >= line.syllcount:
                pos -= line.syllcount
            else:
                break
        linepos = pos
        linelength = line.syllcount
        # iambic
        for foot in line.feet:
            if pos >= len(foot):
                pos -= len(foot)
            else:
                break
        try:
            if foot[pos] == '-':
                states = set([s for s in states if stressed(*s[0])])
            elif foot[pos] == '.':
                states = set([s for s in states if unstressed(*s[0])])
        except:
            print(pos, foot)
            raise

        if linepos in [0, 1, linelength - 3, linelength - 2]:
            states = set([s for s in states if s[1] != ('*', 0)])
        if node == self.nodes[-1]:
            states = set([s for s in states if s[1] == ('*', 0)])

        if states != self.states:
            return states

    def score_state(self, node, state):
        prox = min(
            abs((node + 0.5) / len(self.nodes) - d)
            for d in self.statepos[state])
        used = sum(1 / len(self.valid[n]) for n in self.nodes
                   if state in self.valid[n])
        return int(used), prox

    def choose_state(self, node):
        states = self.valid[node]
        return min(states, key=lambda s: self.score_state(node, s))

    def sample(self):
        breaks = [0]
        for line in self.scheme:
            breaks.append(breaks[-1] + line.syllcount)
        breaks = breaks[1:]
        poem = []
        line = []
        cap = True
        for node in self.nodes:
            if node in breaks:
                poem.append(line)
                line = []
                cap = True
            if len(self.valid[node]) > 1:
                line.append('***')
            else:
                value = list(self.valid[node])[0]
                word, syll = value[0]
                if cap:
                    word = word[0].upper() + word[1:]
                    cap = False
                if syll == 0:
                    line.append(word)
                if value[1] == ('*', 0):
                    line[-1] = line[-1] + '.'
                    cap = True
        poem.append(line)
        return poem


class Foot(tuple):
    pass


iamb = Foot('.-')
trochee = Foot('-.')
dactyl = Foot('-..')
amphibrach = Foot('.-.')
anapest = Foot('..-')
brach = Foot('-')


class Line(namedtuple("Line", "feet rhyme")):
    @property
    def syllcount(self):
        return sum(len(f) for f in self.feet)


def iambic(n, scheme):
    return [Line([iamb] * n, r) for r in scheme]


sonnet = iambic(5, 'ababcdcdefefgg')
petrarch = iambic(5, 'abbaabbacdecde')
ottava = iambic(5, 'abababcc')

limerick1 = Line([amphibrach, amphibrach, iamb], 'a')
limerick2 = Line([amphibrach, iamb], 'b')

limerick = [limerick1, limerick1, limerick2, limerick2, limerick1]

couplet = iambic(5, 'aa')
ballad = iambic(4, 'a') + iambic(3, 'b') + iambic(4, 'a') + iambic(3, 'b')
verse = iambic(5, 'abcb')
blank = iambic(5, 'abcd')


def balladize(tokens, meter=ballad, step=10, refrain=None, order=3):
    start = 0
    end = step
    stanzas = []
    while end < len(tokens):
        while end < len(tokens):
            try:
                sents = tokens[start:end]
                if refrain:
                    sents.append(refrain)
                pc = PoemCollapser(sents, meter, order)
                if refrain:
                    refstates = wordseqs(refrain, order)
                    for i in range(len(refstates)):
                        pc.observe(pc.nodes[-(i + 1)], refstates[-(i + 1)])
                    pc.propagate()
                tries = 0
                while not pc.resolved() and tries < 40:
                    pc.step()
                    tries += 1
                if tries >= 40:
                    raise wfc.InconsistencyError
            except wfc.InconsistencyError:
                end += step
                continue
            stanza = '\n'.join([' '.join(line) for line in pc.sample()])
            print("Sentences %d-%d: stanza %d" %
                  (start + 1, end, len(stanzas) + 1))
            print(stanza)
            print()
            stanzas.append(stanza)
            start = end
            end = start + step
    return stanzas


def stepthrough(lines, meter, order=3, verbose=False):
    pc = PoemCollapser(lines, meter, order)

    pc.propagate()

    poems = []
    tries = 0
    while not pc.resolved() and tries < 500:
        tries += 1
        pc.step()
        poem = '\n'.join([' '.join(line) for line in pc.sample()])
        poems.append(poem)
        if verbose:
            print()
            print("== Step %d ==" % tries)
            print(poem)
            print()
    return poems
