"""Convert the JSON run file passed on stdin to a csv"""
from __future__ import print_function
import json

import sys


data = json.load(sys.stdin)

titles = data['tests'].itervalues().next().keys()
titles.insert(0, titles.pop(titles.index("name")))

print(", ".join(titles))

for i, result in data['tests'].items():

    for title in titles:
        print(result[title], end=' ')
        print(", ", end=' ')
    print()
