import csv

def test_er_brb_has_dd_or_post_dd_stage():
    with open('examples/tuntun_hk/trace/er_brb_scoring_table.csv', encoding='utf-8-sig') as f:
        stages = {r.get('stage') for r in csv.DictReader(f)}
    assert stages & {'dd', 'post_dd', 'deep_dd'}
