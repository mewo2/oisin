import re
from collections import defaultdict, Counter

numbers = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
    "1st": "first",
    "2nd": "second",
    "3rd": "third"
}
spellings = {
    'recieve': 'receive',
    'pheonix': 'phoenix',
    'desfense': 'defense',
    'dmg': 'damage'
}

def capitalizations(text):
    words = re.split("[^0-9a-zA-Z']", text)
    counts = defaultdict(Counter)
    for w in words:
        counts[w.lower()][w] += 1
    return {w:counts[w].most_common(1)[0][0] for w in counts}


def tokenize(text):
    caps = capitalizations(text)
    text = text.lower()
    text = re.sub(r'\bmt\.', 'mount', text)
    text = re.sub(r'(mrs?)\.', r'\1', text)
    text = re.sub(r"[^0-9a-z\s.!\?\!']", " ", text)
    text = re.sub(r"\b[0-9]+(th|nd|rd)?", lambda x: numbers.get(x, " "), text)
    tokens = [x.split() for x in re.split(r"\n\n|[\.\?!]", text)]
    tokens = [[re.sub("(^')|('$)", "", w) for w in sent] for sent in tokens]
    tokens = [[spellings.get(x, x) for x in sent if x] for sent in tokens]
    tokens = [sent for sent in tokens if len(sent) > 2]
    tokens = [[caps.get(w, w) for w in sent] for sent in tokens]
    return tokens


def interleave(*args):
    everything = []
    for arg in args:
        n = len(arg)
        for i, line in enumerate(arg):
            everything.append(((i + 1.) / (n + 2.), line))
    return [line for _, line in sorted(everything)]


def load(filename):
    return tokenize(open(filename).read())
    