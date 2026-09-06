import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location('readability', Path(__file__).resolve().parents[2]/'scripts/rdw_readability_audit.py')
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)


def obj(name, left, top, lines):
    return dict(object_path=name,text=name,left=left,top=top,width=100,height=80,
                bound_left=lines[0]['left'],bound_top=lines[0]['top'],bound_width=30,bound_height=20,lines=lines)


def line(left, top):
    return dict(text='test',left=left,top=top,width=30,height=10,font_size_pt=10/1.2)


def report(objects):
    return module.inspect_export(dict(page_count=1,artifact_sha256='test',pages=[dict(page_id='p01',text_bounds=objects)]))


def test_overlapping_empty_textboxes_do_not_fail_ink_test():
    result = report([obj('a',0,0,[line(2,2)]),obj('b',0,0,[line(50,35)])])
    assert result['counts']['cross_object_overlap_candidates'] == 0
    assert result['visual_acceptance'] == 'pending'


def test_actual_line_overlap_and_tight_leading_are_detected():
    result = report([obj('a',0,0,[line(2,2),line(2,12)]),obj('b',0,0,[line(10,8)])])
    assert result['counts']['tight_line_pairs'] == 1
    assert result['counts']['cross_object_overlap_candidates'] == 2


def test_missing_measurements_and_missing_pages_cannot_pass():
    item = obj('a',0,0,[line(2,2)])
    del item['lines']
    with pytest.raises(ValueError, match='line measurements'):
        report([item])
    with pytest.raises(ValueError, match='incomplete'):
        module.inspect_export(dict(page_count=2,pages=[]))


def test_office_line_height_includes_spacing_and_must_not_count_as_ink():
    first, second = line(2,2), line(2,22)
    first['height'] = 20  # Office includes the extra paragraph gap in BoundHeight.
    result = report([obj('a',0,0,[first,second])])
    assert result['counts']['tight_line_pairs'] == 0


def test_identical_overlaid_textboxes_are_still_an_overlap():
    result = report([obj('a',0,0,[line(2,2)]),obj('b',0,0,[line(2,2)])])
    assert result['counts']['cross_object_overlap_candidates'] == 1
