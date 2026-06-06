import csv

def test_hard_filter_has_rows():
    with open('examples/tuntun_hk/trace/hard_filter_table.csv', encoding='utf-8-sig') as f:
        assert sum(1 for _ in csv.DictReader(f)) > 0
