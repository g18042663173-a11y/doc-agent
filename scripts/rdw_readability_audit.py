"""Screen Office line bounds for overflow, cross-object overlap and tight leading.

This is a review aid, never a substitute for looking at every rendered slide.
It uses actual Office lines, not overlapping empty textbox rectangles.
"""
from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path


def inspect_export(export: dict) -> dict:
    if (not export.get('pages') or len(export['pages']) != export.get('page_count')
            or len({p['page_id'] for p in export['pages']}) != len(export['pages'])):
        raise ValueError('Missing or incomplete page inventory')
    pages = []
    for page in export['pages']:
        overflow, tight, overlaps = [], [], []
        objects = page['text_bounds']
        if any('lines' not in obj for obj in objects):
            raise ValueError('Actual Office line measurements are required; re-export with version 2.1')
        for obj in objects:
            excess = max(obj['left']-obj['bound_left'], obj['top']-obj['bound_top'],
                         obj['bound_left']+obj['bound_width']-obj['left']-obj['width'],
                         obj['bound_top']+obj['bound_height']-obj['top']-obj['height'])
            if excess > 0.75:
                overflow.append({'object_path': obj['object_path'], 'text': obj['text'], 'excess_pt': round(excess, 3)})
            for first, second in zip(obj['lines'], obj['lines'][1:]):
                if first.get('font_size_pt', 0) <= 0 or second.get('font_size_pt', 0) <= 0:
                    raise ValueError('Resolved line font sizes are required for leading review')
                # BoundHeight includes leading and paragraph-after space in Office,
                # so adjacent line rectangles touch even with generous spacing.
                # Use measured line advance against a nominal font-height reference.
                # This is explicitly a heuristic candidate, never measured glyph ink.
                reference = first['font_size_pt'] * 1.2
                gap = second['top']-first['top']-reference
                threshold = max(2.0, min(first['font_size_pt'],second['font_size_pt'])*0.12)
                if gap < threshold-0.1:
                    tight.append({'object_path': obj['object_path'], 'lines': [first['text'],second['text']],
                                  'estimated_leading_gap_pt': round(gap,3), 'review_threshold_pt': round(threshold,3)})
        for first, second in combinations(objects, 2):
            # Merged table cells can occur multiple times in Office's cell grid.
            if ('/r' in first['object_path'] and '/r' in second['object_path']
                    and first['lines'] == second['lines']
                    and all(first[k] == second[k] for k in ('left','top','width','height'))):
                continue
            for a in first['lines']:
                for b in second['lines']:
                    width = min(a['left']+a['width'],b['left']+b['width'])-max(a['left'],b['left'])
                    height = min(a['top']+a['height'],b['top']+b['height'])-max(a['top'],b['top'])
                    if width > 0.75 and height > 0.75:
                        overlaps.append({'objects':[first['object_path'],second['object_path']],
                                         'lines':[a['text'],b['text']], 'intersection_pt':[round(width,3),round(height,3)]})
        pages.append({'page_id':page['page_id'], 'measured_text_objects':len(objects),
                      'overflow_candidates':overflow, 'tight_line_pairs':tight, 'cross_object_overlap_candidates':overlaps})
    return {'format':'rdw_readability_screen','version':'1.0', 'artifact_sha256':export['artifact_sha256'],
            'visual_acceptance':'pending', 'scope':'Office line bounding boxes plus a nominal 1.2x font-height leading heuristic; charts, inherited assets and visible ink require visual review',
            'pages':pages, 'counts':{name:sum(len(p[name]) for p in pages) for name in
                                    ('overflow_candidates','tight_line_pairs','cross_object_overlap_candidates')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect_export(json.loads(args.export.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['counts']))
