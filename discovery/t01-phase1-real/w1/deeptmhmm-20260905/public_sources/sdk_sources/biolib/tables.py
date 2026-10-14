from collections import OrderedDict

from biolib._internal.tables import BioLibTable as _BioLibTable
from biolib._shared.types.typing import Any, List


class BioLibTable(_BioLibTable):
    def __init__(self, columns_to_row_map: OrderedDict, rows: List[Any], title: str):
        print('Warning: biolib.tables.BioLibTable is deprecated and will be removed in late Q3 2026.')
        super().__init__(columns_to_row_map=columns_to_row_map, rows=rows, title=title)


__all__ = ['BioLibTable']
