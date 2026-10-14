import json
from importlib.metadata import version
from pathlib import Path
import freesasa

rows = []
for tokens in [('43A',), ('043', '43'), ('12345678901234567890',), ('-9',), ('+43',)]:
    s = freesasa.Structure(classifier=freesasa.Classifier.getStandardClassifier('protor'),
                          options={'halt-at-unknown': True, 'skip-unknown': False})
    for i, token in enumerate(tokens):
        s.addAtom('CA', 'ALA', token, 'A', 8.0 * i, 1.0, 2.0)
    observed = [s.residueNumber(i) for i in range(s.nAtoms())]
    rows.append(dict(requested=tokens, observed=observed, atom_count=s.nAtoms()))
Path('/out/capability.json').write_text(json.dumps(dict(freesasa=version('freesasa'), cases=rows), indent=2)+'\n')
print(json.dumps(rows))
