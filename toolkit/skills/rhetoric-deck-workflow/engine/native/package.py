from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import posixpath
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}
PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


def xml(data):
    return etree.fromstring(data, parser=PARSER)


def serialized(root):
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def read_parts(path):
    with ZipFile(path) as package:
        return {name: package.read(name) for name in package.namelist()}


def write_parts(path, parts):
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as package:
        for name, data in parts.items():
            package.writestr(name, data)


def rels_name(part):
    parent, name = posixpath.split(part)
    return f"{parent}/_rels/{name}.rels" if parent else f"_rels/{name}.rels"


def relationships(parts, part):
    data = parts.get(rels_name(part))
    if data is None:
        return {}
    return {
        node.get("Id"): {
            "type": node.get("Type", "").rsplit("/", 1)[-1],
            "target": posixpath.normpath(posixpath.join(posixpath.dirname(part), node.get("Target", ""))).lstrip("/"),
            "external": node.get("TargetMode") == "External",
        }
        for node in xml(data)
    }


def part_types(parts):
    root = xml(parts["[Content_Types].xml"])
    defaults = {node.get("Extension").lower(): node.get("ContentType") for node in root if etree.QName(node).localname == "Default"}
    overrides = {node.get("PartName").lstrip("/"): node.get("ContentType") for node in root if etree.QName(node).localname == "Override"}
    return {name: overrides.get(name, defaults.get(name.rsplit(".", 1)[-1].lower(), "")) for name in parts}


def slide_parts(parts):
    types = part_types(parts)
    presentation = next(name for name, kind in types.items() if kind.endswith("presentation.main+xml"))
    rels = relationships(parts, presentation)
    root = xml(parts[presentation])
    return [rels[node.get(f"{{{NS['r']}}}id")]["target"] for node in root.findall("p:sldIdLst/p:sldId", NS)]


def _shape_id(node):
    props = node.xpath('./*[local-name()="nvSpPr" or local-name()="nvPicPr" or local-name()="nvGraphicFramePr" or local-name()="nvGrpSpPr"]/*[local-name()="cNvPr"]')
    return props[0].get("id", "0") if props else "0"


def _bbox(node):
    transforms = node.xpath('./*[local-name()="spPr" or local-name()="grpSpPr"]/*[local-name()="xfrm"] | ./*[local-name()="xfrm"]')
    if not transforms:
        return {}
    off = transforms[0].find("a:off", NS)
    ext = transforms[0].find("a:ext", NS)
    return {"left": int(off.get("x", 0)), "top": int(off.get("y", 0)), "width": int(ext.get("cx", 0)), "height": int(ext.get("cy", 0))} if off is not None and ext is not None else {}


def _transform_record(node):
    return [{"tag": etree.QName(child).localname, "attributes": dict(child.attrib)} for child in node.iter()]


def _text(node):
    return "\n".join("".join(p.xpath('.//a:t/text()', namespaces=NS)) for p in node.findall("a:p", NS))


def _smartart_points(parts, data_part):
    root = xml(parts[data_part])
    result = []
    for point in root.findall("dgm:ptLst/dgm:pt", NS):
        body = point.find("dgm:t", NS)
        if body is not None and body.findall("a:p", NS):
            result.append((point.get("modelId", ""), _text(body)))
    return result


def _chart_data(root):
    series = []
    categories = []
    for ser in root.findall(".//c:ser", NS):
        cats = ser.xpath('./c:cat//c:pt/c:v/text()', namespaces=NS)
        if cats:
            categories = cats
        name = ser.xpath('./c:tx//c:v/text()', namespaces=NS)
        values = ser.xpath('./c:val//c:pt/c:v/text()', namespaces=NS)
        series.append({"name": name[0] if name else "", "values": [float(value) if value else None for value in values]})
    return {"categories": categories, "series": series}


def _part_objects(parts, part, prefix=""):
    root = xml(parts[part])
    rels = relationships(parts, part)
    result = []
    for node in root.xpath('.//*[local-name()="sp" or local-name()="graphicFrame" or local-name()="pic"]'):
        sid = _shape_id(node)
        ref = prefix + f"sp_{sid}"
        base = {"shape_ref": ref, "object_id": f"{part}#{sid}", "part": part, "shape_id": sid, "bbox": _bbox(node)}
        body = node.find("p:txBody", NS)
        if body is not None:
            props = node.xpath('.//*[local-name()="cNvPr"]')
            name = props[0].get("name", "") if props else ""
            text = _text(body)
            retained = bool(prefix) and (node.find(".//p:ph", NS) is not None or node.find(".//a:fld", NS) is not None or text.strip().casefold() in {"huawei", "huawei confidential", "www.huawei.com"})
            run_lengths = [[len(run.find("a:t", NS).text or "") if run.find("a:t", NS) is not None else 0 for run in p.findall("a:r", NS)] for p in body.findall("a:p", NS)]
            result.append({**base, "kind": "shape", "text": text, "name": name, "paragraph_run_lengths": run_lengths, "action": "retained_chrome" if retained else "replace"})
        table = node.find(".//a:tbl", NS)
        if table is not None:
            for ri, row in enumerate(table.findall("a:tr", NS)):
                for ci, cell in enumerate(row.findall("a:tc", NS)):
                    body = cell.find("a:txBody", NS)
                    run_lengths = [[len(run.find("a:t", NS).text or "") if run.find("a:t", NS) is not None else 0 for run in p.findall("a:r", NS)] for p in body.findall("a:p", NS)] if body is not None else []
                    result.append({**base, "shape_ref": f"{ref}.cell_{ri}_{ci}", "object_id": f"{base['object_id']}.cell_{ri}_{ci}", "kind": "table_cell", "text": _text(body) if body is not None else "", "paragraph_run_lengths": run_lengths})
        chart = node.find(".//c:chart", NS)
        if chart is not None:
            related = rels.get(chart.get(f"{{{NS['r']}}}id"), {})
            target = related.get("target")
            if target in parts:
                result.append({**base, "shape_ref": ref + ".chart", "kind": "chart", "text": "", "chart_part": target, "chart_data": _chart_data(xml(parts[target])), "requires_replacement": True})
        diagrams = node.findall(".//dgm:relIds", NS)
        for diagram in diagrams:
            related = rels.get(diagram.get(f"{{{NS['r']}}}dm"), {})
            target = related.get("target")
            if target in parts:
                for model_id, text in _smartart_points(parts, target):
                    result.append({**base, "shape_ref": ref + ".dgm_" + model_id, "kind": "smartart_node", "node_id": model_id, "diagram_part": target, "text": text})
        if etree.QName(node).localname == "pic":
            blips = node.findall(".//a:blip", NS)
            media = []
            for blip in blips:
                target = rels.get(blip.get(f"{{{NS['r']}}}embed"), {}).get("target")
                if target in parts:
                    media.append({"part": target, "sha256": sha256(parts[target]).hexdigest()})
            crops = node.findall(".//a:srcRect", NS)
            crop = dict(crops[0].attrib) if crops else {}
            transforms = node.findall(".//a:xfrm", NS)
            transform_flags = dict(transforms[0].attrib) if transforms else {}
            result.append({**base, "kind": "picture", "text": "", "media": media, "crop": crop, "transform_flags": transform_flags, "preservation": "original_pixels_including_embedded_text"})
    return result


def inspect_package(path):
    parts = read_parts(path)
    types = part_types(parts)
    presentation_part = next(name for name, kind in types.items() if kind.endswith("presentation.main+xml"))
    dimensions = xml(parts[presentation_part]).find("p:sldSz", NS)
    width, height = int(dimensions.get("cx")), int(dimensions.get("cy"))
    pages = []
    for i, slide in enumerate(slide_parts(parts), 1):
        objects = _part_objects(parts, slide)
        shared_parts = []
        for relation in relationships(parts, slide).values():
            if relation["type"] == "slideLayout" and not relation["external"]:
                shared_parts.append(relation["target"])
                shared_parts.extend(r["target"] for r in relationships(parts, relation["target"]).values() if r["type"] == "slideMaster" and not r["external"])
        groups = [{"shape_id": _shape_id(group), "transforms": [_transform_record(t) for t in group.xpath('./*[local-name()="grpSpPr"]/*[local-name()="xfrm"]')]} for group in xml(parts[slide]).xpath('.//*[local-name()="grpSp"]')]
        pages.append({"page_id": f"p{i:02d}", "slide_part": slide, "objects": objects, "shared_parts": shared_parts, "group_geometry": groups})
    shared = []
    used_shared = {part for page in pages for part in page["shared_parts"]}
    for part, kind in types.items():
        if kind.endswith("slideMaster+xml") or kind.endswith("slideLayout+xml"):
            objects = _part_objects(parts, part, prefix=f"part_{sha256(part.encode()).hexdigest()[:12]}.")
            for obj in objects:
                bbox = obj["bbox"]
                outside = bool(bbox) and (bbox["left"] >= width or bbox["top"] >= height or bbox["left"] + bbox["width"] <= 0 or bbox["top"] + bbox["height"] <= 0)
                if part not in used_shared or outside:
                    obj["action"] = "retained_nonvisible"
                obj["used_by_pages"] = [p["page_id"] for p in pages if part in p["shared_parts"]]
            shared.extend(objects)
    diagram_geometry = {}
    for part, kind in types.items():
        if kind.endswith("diagramDrawing+xml"):
            diagram_geometry[part] = [{"model_id": shape.get("modelId"), "bbox": _bbox(shape)} for shape in xml(parts[part]).xpath('.//*[local-name()="sp"]')]
    return {"format": "rdw_native_inventory", "version": "2.0", "page_count": len(pages), "slide_size": {"width": width, "height": height}, "pages": pages, "shared_objects": shared, "diagram_geometry": diagram_geometry,
            "media": [{"part": name, "sha256": sha256(data).hexdigest()} for name, data in parts.items() if types.get(name, "").startswith("image/")],
            "part_types": types}


def sanitize_package(source, destination):
    """Clear editable text, never formatting, chart values, pixels or metadata."""
    parts = read_parts(source)
    types = part_types(parts)
    inventory = inspect_package(source)
    for name, kind in types.items():
        if not name.endswith(".xml"):
            continue
        # Chart data remains internal until mandatory evidence-backed replacement.
        if kind.endswith("chart+xml"):
            continue
        visible = any(kind.endswith(suffix) for suffix in ("slide+xml", "slideMaster+xml", "slideLayout+xml", "notesSlide+xml", "diagramData+xml", "diagramDrawing+xml"))
        if not visible:
            continue
        root = xml(parts[name])
        shared_part = kind.endswith("slideMaster+xml") or kind.endswith("slideLayout+xml")
        retained_ids = {obj["shape_id"] for obj in inventory["shared_objects"] if obj["part"] == name and obj.get("action") != "replace"} if shared_part else set()
        for node in root.findall(".//a:t", NS):
            owners = node.xpath('ancestor::*[local-name()="sp"]')
            if owners and _shape_id(owners[-1]) in retained_ids:
                continue
            node.text = ""
        for node in root.findall("p:timing", NS) + root.findall("p:transition", NS):
            root.remove(node)
        parts[name] = serialized(root)
    write_parts(destination, parts)


def _replace_body(body, text):
    """Keep paragraph and run properties; do not enlarge or move the object."""
    paragraphs = body.findall("a:p", NS)
    original = [deepcopy(p) for p in paragraphs]
    lines = text.splitlines() or [""]
    while len(paragraphs) < len(lines):
        paragraph = deepcopy(original[min(len(paragraphs), len(original) - 1)]) if original else etree.Element(f"{{{NS['a']}}}p")
        body.append(paragraph)
        paragraphs.append(paragraph)
    for index, paragraph in enumerate(paragraphs):
        value = lines[index] if index < len(lines) else ""
        nodes = paragraph.findall(".//a:t", NS)
        if not nodes:
            run = etree.SubElement(paragraph, f"{{{NS['a']}}}r")
            nodes = [etree.SubElement(run, f"{{{NS['a']}}}t")]
        weights = [len(node.text or "") for node in nodes]
        if not sum(weights):
            weights = [1] * len(nodes)
        cumulative = consumed = 0
        for position, node in enumerate(nodes):
            cumulative += weights[position]
            end = len(value) if position == len(nodes) - 1 else round(len(value) * cumulative / sum(weights))
            node.text = value[consumed:end]
            consumed = end


def replace_smartart(parts, data_part, node_id, text):
    root = xml(parts[data_part])
    points = root.findall("dgm:ptLst/dgm:pt", NS)
    point = next((p for p in points if p.get("modelId") == node_id), None)
    if point is None:
        raise ValueError(f"Unknown SmartArt modelId: {node_id}")
    body = point.find("dgm:t", NS)
    if body is None:
        raise ValueError(f"SmartArt node has no text body: {node_id}")
    _replace_body(body, text)
    # Presentation points map data nodes to the cached drawing model ids.
    cache_ids = {node_id}
    for candidate in points:
        properties = candidate.find("dgm:prSet", NS)
        if properties is not None and properties.get("presAssocID") == node_id:
            cache_ids.add(candidate.get("modelId"))
    parts[data_part] = serialized(root)
    updated = 0
    drawing_parts = {rel["target"] for rel in relationships(parts, data_part).values() if rel["type"] == "diagramDrawing" and not rel["external"]}
    extension_ids = [node.get("relId") for node in root.xpath('.//*[local-name()="dataModelExt"]') if node.get("relId")]
    # Office stores the drawing relationship on the slide, with its rId in
    # the data model extension, rather than necessarily on the data part.
    for owner in slide_parts(parts):
        rels = relationships(parts, owner)
        if not any(rel["target"] == data_part and not rel["external"] for rel in rels.values()):
            continue
        drawing_parts.update(rels[rid]["target"] for rid in extension_ids if rid in rels and rels[rid]["type"] == "diagramDrawing" and not rels[rid]["external"])
    for drawing_part in drawing_parts:
        if drawing_part not in parts:
            continue
        drawing = xml(parts[drawing_part])
        for shape in drawing.xpath('.//*[local-name()="sp"]'):
            if shape.get("modelId") not in cache_ids:
                continue
            bodies = shape.xpath('./*[local-name()="txBody"]')
            if bodies:
                _replace_body(bodies[0], text)
                updated += 1
        parts[drawing_part] = serialized(drawing)
    return updated


def smartart_cache_audit(path):
    parts = read_parts(path)
    types = part_types(parts)
    issues = []
    checked = 0
    for data_part, kind in types.items():
        if not kind.endswith("diagramData+xml"):
            continue
        root = xml(parts[data_part])
        point_text = dict(_smartart_points(parts, data_part))
        associations = {}
        for point in root.findall("dgm:ptLst/dgm:pt", NS):
            properties = point.find("dgm:prSet", NS)
            if properties is not None and properties.get("presAssocID"):
                associations[point.get("modelId")] = properties.get("presAssocID")
        for owner in slide_parts(parts):
            rels = relationships(parts, owner)
            if not any(r["target"] == data_part for r in rels.values() if not r["external"]):
                continue
            for rel in rels.values():
                if rel["type"] != "diagramDrawing" or rel["external"] or rel["target"] not in parts:
                    continue
                drawing = xml(parts[rel["target"]])
                for shape in drawing.xpath('.//*[local-name()="sp"]'):
                    model = shape.get("modelId")
                    node = associations.get(model, model)
                    bodies = shape.xpath('./*[local-name()="txBody"]')
                    if node in point_text and bodies:
                        checked += 1
                        if _text(bodies[0]).strip() != point_text[node].strip():
                            issues.append({"code": "smartart_cache_mismatch", "loc": f"{data_part}#{node}"})
    return {"pass": not issues, "checked_cache_shapes": checked, "issues": issues}


def chart_workbook_audit(path):
    """Compare the cache with its generated editable workbook, without Office."""
    parts = read_parts(path)
    issues = []
    checked = 0
    spreadsheet_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    for chart_part, kind in part_types(parts).items():
        if not kind.endswith("chart+xml"):
            continue
        cache = _chart_data(xml(parts[chart_part]))
        if not cache["series"]:
            continue
        workbooks = [r["target"] for r in relationships(parts, chart_part).values() if r["type"] == "package" and not r["external"] and r["target"].endswith(".xlsx")]
        if not workbooks:
            issues.append({"code": "chart_workbook_missing", "loc": chart_part})
            continue
        for workbook_part in workbooks:
            checked += 1
            with ZipFile(BytesIO(parts[workbook_part])) as workbook:
                shared = []
                if "xl/sharedStrings.xml" in workbook.namelist():
                    shared = ["".join(node.xpath('.//*[local-name()="t"]/text()')) for node in xml(workbook.read("xl/sharedStrings.xml"))]
                sheet = next((name for name in workbook.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")), None)
                if sheet is None:
                    issues.append({"code": "chart_worksheet_missing", "loc": workbook_part})
                    continue
                cells = {}
                for cell in xml(workbook.read(sheet)).iter(f"{{{spreadsheet_ns}}}c"):
                    value = cell.find(f"{{{spreadsheet_ns}}}v")
                    raw = value.text if value is not None else None
                    cell_type = cell.get("t")
                    if cell_type == "s":
                        parsed = shared[int(raw)] if raw is not None else ""
                    elif cell_type == "inlineStr":
                        parsed = "".join(cell.xpath('.//*[local-name()="t"]/text()'))
                    elif raw is None:
                        parsed = None
                    elif cell_type == "str":
                        parsed = raw
                    else:
                        parsed = float(raw)
                    cells[cell.get("r")] = parsed
                workbook_data = {"categories": [str(cells.get(f"A{i + 2}", "")) for i in range(len(cache["categories"]))], "series": []}
                for si, series in enumerate(cache["series"]):
                    col = ""
                    number = si + 2
                    while number:
                        number, remainder = divmod(number - 1, 26)
                        col = chr(65 + remainder) + col
                    workbook_data["series"].append({"name": str(cells.get(col + "1", "")), "values": [cells.get(f"{col}{i + 2}") for i in range(len(series["values"]))]})
                if workbook_data != cache:
                    issues.append({"code": "chart_workbook_cache_mismatch", "loc": chart_part})
    return {"pass": not issues, "checked_workbooks": checked, "issues": issues}


def update_smartart_file(path, replacements):
    parts = read_parts(path)
    results = []
    for item in replacements:
        count = replace_smartart(parts, item["diagram_part"], item["node_id"], item["text"])
        results.append({**item, "cache_shapes_updated": count})
    write_parts(path, parts)
    return results


def update_shared_text_file(path, replacements):
    parts = read_parts(path)
    roots = {}
    for item in replacements:
        root = roots.setdefault(item["part"], xml(parts[item["part"]]))
        shape = next((node for node in root.xpath('.//*[local-name()="sp"]') if _shape_id(node) == item["shape_id"]), None)
        if shape is None or shape.find("p:txBody", NS) is None:
            raise ValueError(f"Missing shared text shape: {item['part']}#{item['shape_id']}")
        _replace_body(shape.find("p:txBody", NS), item["text"])
    for part, root in roots.items():
        parts[part] = serialized(root)
    write_parts(path, parts)


def visible_texts(path):
    inventory = inspect_package(path)
    records = []
    for page in inventory["pages"]:
        for item in page["objects"]:
            loc = f"{page['page_id']}.{item['shape_ref']}"
            if item["kind"] == "chart":
                data = item["chart_data"]
                records.append((loc, "\n".join(data["categories"] + [s["name"] for s in data["series"]])))
                for series in data["series"]:
                    records.extend((loc, str(value)) for value in series["values"] if value is not None)
            elif item.get("text"):
                records.append((loc, item["text"]))
    records.extend((item["shape_ref"], item["text"]) for item in inventory["shared_objects"] if item.get("text") and item.get("action") == "replace")
    parts = read_parts(path)
    for part, kind in part_types(parts).items():
        if kind.endswith("chart+xml"):
            root = xml(parts[part])
            # Chart/axis rich titles and custom labels are visible too, even
            # when their text is outside the category/series data caches.
            records.extend((part, text) for text in root.xpath('.//a:t/text()', namespaces=NS) if text.strip())
    return records


def audit_output(source, output, inventory=None):
    before = inventory or inspect_package(source)
    after = inspect_package(output)
    media_before = sorted(item["sha256"] for item in before["media"])
    media_after = sorted(item["sha256"] for item in after["media"])
    geometry = []
    objects = []
    for first, second in zip(before["pages"], after["pages"]):
        after_map = {item["shape_ref"]: item for item in second["objects"]}
        for item in first["objects"]:
            target = after_map.get(item["shape_ref"])
            unchanged = target is not None and item["bbox"] == target["bbox"]
            if item["kind"] == "picture" and target is not None:
                unchanged = unchanged and item.get("crop") == target.get("crop") and item.get("transform_flags") == target.get("transform_flags") and [m["sha256"] for m in item.get("media", [])] == [m["sha256"] for m in target.get("media", [])]
            geometry.append({"page_id": first["page_id"], "shape_ref": item["shape_ref"], "pass": unchanged})
            objects.append({"page_id": first["page_id"], "shape_ref": item["shape_ref"], "kind": item["kind"], "present": target is not None, "text": target.get("text", "") if target else ""})
    same_pages = len(before["pages"]) == len(after["pages"]) and [p["slide_part"] for p in before["pages"]] == [p["slide_part"] for p in after["pages"]]
    issues = []
    if not same_pages:
        issues.append({"code": "page_order_changed", "loc": "pages"})
    if media_before != media_after:
        issues.append({"code": "media_changed", "loc": "media"})
    if before.get("slide_size") != after.get("slide_size"):
        issues.append({"code": "slide_size_changed", "loc": "slide_size"})
    if before.get("diagram_geometry") != after.get("diagram_geometry"):
        issues.append({"code": "diagram_geometry_changed", "loc": "diagrams"})
    for first, second in zip(before["pages"], after["pages"]):
        if first.get("group_geometry") != second.get("group_geometry"):
            issues.append({"code": "group_geometry_changed", "loc": first["page_id"]})
    issues.extend({"code": "geometry_changed", "loc": f"{item['page_id']}.{item['shape_ref']}"} for item in geometry if not item["pass"])
    return {"format": "rdw_native_audit", "version": "2.0", "page_count": after["page_count"], "page_order_preserved": same_pages,
            "media_preserved": media_before == media_after, "geometry": geometry, "native_objects": objects,
            "issues": issues, "pass": not issues}


def readback_audit(output, skeleton, content):
    inventory = inspect_package(output)
    pages = {p["page_id"]: {obj["shape_ref"]: obj for obj in p["objects"]} for p in inventory["pages"]}
    shared = {obj["shape_ref"]: obj for obj in inventory["shared_objects"]}
    specs = {page["page_id"]: {slot["slot_id"]: slot for slot in page["slots"]} for page in skeleton["pages"]}
    records = []
    for page in content["pages"]:
        for slot in page["slots"]:
            ref = specs[page["page_id"]][slot["slot_id"]]["shape_ref"]
            obj = pages.get(page["page_id"], {}).get(ref) or shared.get(ref)
            expected = slot.get("value")
            if isinstance(expected, list):
                expected = "\n".join(expected)
            actual = (obj.get("chart_data") if obj["kind"] == "chart" else obj.get("text", "")) if obj else None
            if isinstance(expected, dict) and actual is not None:
                wanted = {"categories": expected.get("categories", []), "series": expected.get("series", [])}
                passed = wanted == actual
            else:
                passed = expected is not None and str(expected).strip() == str(actual).strip()
            records.append({"page_id": page["page_id"], "slot_id": slot["slot_id"], "shape_ref": ref, "pass": passed, "expected": expected, "actual": actual})
    expected_pages = [p["page_id"] for p in skeleton["pages"]]
    actual_pages = [p["page_id"] for p in inventory["pages"]]
    issues = [{"code": "replacement_mismatch", "loc": f"{r['page_id']}.{r['slot_id']}"} for r in records if not r["pass"]]
    if expected_pages != actual_pages:
        issues.append({"code": "page_coverage_mismatch", "loc": "pages"})
    cache = smartart_cache_audit(output)
    issues.extend(cache["issues"])
    workbooks = chart_workbook_audit(output)
    issues.extend(workbooks["issues"])
    return {"format": "rdw_readback_audit", "version": "2.0", "pass": not issues, "issues": issues, "slots": records, "smartart_cache": cache, "chart_workbooks": workbooks}
