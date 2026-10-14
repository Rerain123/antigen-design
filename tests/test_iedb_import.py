"""MySQL export parsing must not conflate nulls, escapes, or binary fields."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('iedb_import',Path(__file__).parents[1]/'scripts/import_iedb_snapshot.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_rows_preserve_mysql_values_and_column_order():
    raw=b"(1,'NULL',NULL,'a\\'b\\n\\\\c'),(2,'x',3,'it''s');\n"
    assert list(module.rows(raw,[3,2,1,0],4))==[["a'b\n\\c",None,'NULL','1'],["it's",'3','x','2']]


def test_unselected_binary_is_not_decoded():
    assert list(module.rows(b"(1,'\x89\\0\xff','protein');",[0,2],3))==[['1','protein']]


@pytest.mark.parametrize('raw',[b"(1,'x'); DROP TABLE source;",b"(1,'unterminated);",b"(1,2,3);",b"(1,func());",b"(1,2)"])
def test_malformed_values_fail_closed(raw):
    with pytest.raises(ValueError):list(module.rows(raw,[0,1],2))
