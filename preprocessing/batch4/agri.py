"""Convert two pinned agricultural archives to the batch-3 candidate format.

Usage: python agri.py RAW_DIR OUT_DIR
Fetch the URLs in SOURCES into RAW_DIR using the corresponding local filenames.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile

SOURCES = {
    'paddy.zip': ('https://archive.ics.uci.edu/static/public/1186/paddy%2Bdataset.zip',
                  'c37f626578443068558799d2ce2c8740ec0dcfa67f35516b7581a806904c4041'),
    'faostat-qcl.zip': ('https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip',
                       'c5835418c18f9322e7decbd6800f93a216eaae3cdfa31acb08f0518c0c6d6853'),
}
PADDY_TARGET = 'Paddy yield(in Kg)'
PADDY_DROP = (PADDY_TARGET, 'Trash(in bundles)')
PADDY_TEXT = {'Agriblock', 'Variety', 'Soil Types', 'Nursery'}
PADDY_PAGE = 'https://archive.ics.uci.edu/dataset/1186/paddy+dataset'
QCL_PAGE = 'https://www.fao.org/faostat/en/#data/QCL'
FAO_TERMS = 'https://www.fao.org/contact-us/terms/db-terms-of-use/en/'
CC_BY = 'https://creativecommons.org/licenses/by/4.0/'
CROPS = {'56': 'Maize (corn)', '27': 'Rice', '15': 'Wheat'}


def archive_info(raw, filename):
    url, expected = SOURCES[filename]
    path = raw / filename
    sha = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            sha.update(block)
    if sha.hexdigest() != expected:
        raise ValueError(f'{filename}: different source vintage, expected {expected}')
    return {'relativepath': filename, 'url': url, 'bytes': path.stat().st_size, 'sha256': expected}


def write_json(out, data):
    out.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')


def emit(file, sample):
    file.write(json.dumps(sample, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n')


def number(value):
    result = float(value.strip())
    if not math.isfinite(result):
        raise ValueError(f'Unexpected nonfinite value {value}')
    return int(result) if result.is_integer() else result


def paddy(raw, out):
    source = archive_info(raw, 'paddy.zip')
    member = 'paddydataset.csv'
    designs = defaultdict(set)
    blocks = Counter()
    rows = 0
    with ZipFile(raw / 'paddy.zip') as archive, archive.open(member) as archive_file, \
         io.TextIOWrapper(archive_file, encoding='utf-8-sig', newline='') as csv_file, \
         (out / 'paddy.jsonl').open('w', encoding='utf-8') as candidate_file:
        reader = csv.DictReader(csv_file)
        fields = [key.strip() for key in reader.fieldnames]
        assert len(fields) == len(set(fields)) == 45 and all(key in fields for key in PADDY_DROP)
        for rows, row in enumerate(reader, 1):
            row = {key.strip(): value.strip() for key, value in row.items()}
            inputs = {}
            for key, value in row.items():
                if key in PADDY_DROP:
                    continue
                inputs[key] = value if key in PADDY_TEXT or key.startswith('Wind Direction_') else number(value)
            label = number(row[PADDY_TARGET])
            assert label > 0
            block = inputs['Agriblock']
            blocks[block] += 1
            designs[tuple(inputs.values())].add(label)
            emit(candidate_file, {'task_key': 'paddy_output_kg', 'input': inputs, 'label': label,
                                  'group_key': block, 'entity_id': block, 'split': 'unassigned',
                                  'source_refs': [{'file': member, 'row': rows}]})
    write_json(out / 'paddy.meta.json', {
        'dataset_id': 'uci_1186', 'dataset_family': 'uci_paddy_1186', 'name': 'Paddy Dataset',
        'candidate_id': 'B4-PADDY', 'source_url': PADDY_PAGE, 'creators': ['Muthukumaran Subramaniyan'],
        'source_citation': {'authors': ['Muthukumaran Subramaniyan'], 'year': 2023, 'doi': '10.24432/C55W3J'},
        'version': 'UCI archive dated 2025-07-15, accessed 2026-11-26', 'source_files': [source],
        'license': {'name': 'CC BY 4.0', 'url': CC_BY, 'evidence': {'url': PADDY_PAGE}},
        'raw_rows_selected': rows, 'candidate_task_examples': rows, 'excluded_source_rows': 0,
        'invalid_label_examples': 0, 'target_transform': 'reported_total_kg_no_transformation',
        'grouping_rule': 'All rows of the same Agriblock share one group. The source provides no farm identifier or year.',
        'split_policy': 'Unassigned. Use whole Agriblock holdouts, for example four training blocks and one each for validation and test.',
        'excluded_input_columns': list(PADDY_DROP), 'source_profile': {
            'source_columns': fields, 'raw_region_counts': dict(blocks), 'distinct_inputs': len(designs),
            'distinct_input_label_pairs': sum(map(len, designs.values())),
            'inputs_with_multiple_labels': sum(len(labels) > 1 for labels in designs.values())},
        'quality_findings': [
            'The release web page states 2790 rows. Its CSV contains 2789 data rows plus a header.',
            'Input names and categorical strings were trimmed. Both total output and the potential harvest byproduct Trash(in bundles) were excluded from input.',
            'Management inputs repeat across equal area values, and many weather features repeat by block. Different reported yields for identical input are retained.',
            'Day-120 summaries define an end-of-season estimation task. Reported labels are total kilograms per record, without a per-hectare conversion.'],
        'tasks': {'paddy_output_kg': {'target_name': 'paddy_output_kg', 'unit': 'kg',
            'type': 'continuous', 'instruction': 'Estimate total paddy output for this planting using the recorded inputs and observed growing-season conditions.',
            'field_description': 'Hectares is planting area. Agriblock, Variety, Soil Types and Nursery identify the region, crop variety, soil and nursery type. Seedrate, LP manure, nursery area, weed control, fertilizer and pest-control values are source-recorded inputs with source units where supplied. Rain and AI columns are source water variables in mm. Days in a field name identify its growing-season window. Temperature, wind speed in knots, wind direction and humidity give the reported weather summaries.'}}})


def faostat(raw, out):
    source = archive_info(raw, 'faostat-qcl.zip')
    history = defaultdict(dict)
    # The China total includes its reporting areas. Belgium-Luxembourg is a combined area.
    # Exclude predecessor entities where a geographically overlapping successor series exists.
    excluded_areas = {15, 51, 62, 186, 206, 228, 248, 351}
    stats = Counter()
    flags = Counter()
    with ZipFile(raw / 'faostat-qcl.zip') as archive:
        member, = [name for name in archive.namelist() if 'Normalized' in name and name.endswith('.csv')]
        with archive.open(member) as archive_file, io.TextIOWrapper(archive_file, encoding='utf-8-sig', newline='') as csv_file:
            for rownum, row in enumerate(csv.DictReader(csv_file), 1):
                stats['bulk_rows'] += 1
                area = int(row['Area Code'])
                crop = row['Item Code']
                if crop not in CROPS or row['Element'] != 'Yield':
                    continue
                stats['all_selected_crop_yield_rows'] += 1
                if area >= 5000 or area in excluded_areas:
                    stats['excluded_area_rows'] += 1
                    continue
                stats['scoped_yield_rows'] += 1
                flags[row['Flag']] += 1
                if row['Flag'] not in ('A', 'E') or row['Note']:
                    stats['excluded_flag_or_note'] += 1
                    continue
                assert row['Item'] == CROPS[crop] and row['Unit'] == 'kg/ha' and row['Element Code'] == '5412'
                year = int(row['Year'])
                value = number(row['Value'])
                assert value >= 0 and year == int(row['Year Code'])
                series = history[area, crop]
                if year in series:
                    raise ValueError(f'Repeated area/crop/year: {area}, {crop}, {year}')
                series[year] = (value, rownum, row['Flag'], row['Area'])

    counts = Counter()
    years = set()
    with (out / 'faostat.jsonl').open('w', encoding='utf-8') as candidate_file:
        for (area, crop), observations in sorted(history.items()):
            for year, (label, rownum, flag, area_name) in sorted(observations.items()):
                prev = list(range(year - 3, year))
                if any(y not in observations for y in prev):
                    stats['insufficient_consecutive_history'] += 1
                    continue
                group = f'{area}/{crop}'
                old = [observations[y] for y in prev]
                inputs = {'reporting_area': area_name, 'crop': CROPS[crop], 'target_year': year,
                          'prior_annual_yields_kg_per_ha': [{'year': y, 'yield_kg_per_ha': v[0]} for y, v in zip(prev, old)]}
                quality_flags = []
                if flag == 'E':
                    quality_flags.append('estimated_target')
                if any(v[2] == 'E' for v in old):
                    quality_flags.append('estimated_history')
                emit(candidate_file, {'task_key': 'next_annual_crop_yield', 'input': inputs, 'label': label,
                    'group_key': group, 'entity_id': group, 'time_key': str(year), 'split': 'unassigned',
                    'source_refs': [{'file': member, 'row': rownum, 'history_rows': [v[1] for v in old]}],
                    'quality_flags': quality_flags, 'source_flag': flag, 'history_source_flags': [v[2] for v in old]})
                years.add(year)
                counts[CROPS[crop]] += 1
    write_json(out / 'faostat.meta.json', {
        'dataset_id': 'faostat_qcl', 'dataset_family': 'faostat_qcl', 'name': 'FAOSTAT QCL cereal yields',
        'candidate_id': 'B4-FAOSTAT', 'source_url': QCL_PAGE, 'creators': ['Food and Agriculture Organization of the United Nations'],
        'source_citation': {'authors': ['Food and Agriculture Organization of the United Nations'],
            'citation': 'FAO. 2025. FAOSTAT: Production: Crops and livestock products. Accessed on 26 November 2026. https://www.fao.org/faostat/en/#data/QCL. Licence: CC-BY-4.0.'},
        'version': 'QCL bulk release dated 2025-12-31 in the FAOSTAT catalogue; observations through 2024',
        'source_files': [source], 'catalogue_url': 'https://bulks-faostat.fao.org/production/datasets_E.json',
        'license': {'name': 'CC BY 4.0 with FAO Statistical Database Terms of Use', 'url': CC_BY,
            'evidence': {'url': FAO_TERMS}, 'notes': 'Attribute FAO, identify adaptation, respect third-party exceptions and FAO conditions including non-endorsement and no use in promotion. Selected A and E flagged observations. X (external organization) is excluded from both targets and inputs.'},
        'raw_rows_selected': stats['scoped_yield_rows'], 'candidate_task_examples': sum(counts.values()),
        'excluded_source_rows': stats['excluded_flag_or_note'],
        'invalid_label_examples': 0, 'source_profile': {**stats, 'candidate_counts_by_crop': dict(counts),
            'scoped_source_flags': dict(flags), 'target_year_range': [min(years), max(years)], 'history_length_years': 3,
            'selected_area_series': len(history), 'excluded_additional_fao_area_codes': sorted(excluded_areas)},
        'grouping_rule': 'Reporting area code and FAO crop code define an annual series. Retain the target year and source rows for all prior observations.',
        'split_policy': 'Unassigned. For a time holdout, split all series at common target years, such as train through 2015, validation 2016–2019, test 2020–2024. Earlier years may supply observed history. An area holdout requires keeping every crop for that area together.',
        'excluded_input_columns': ['target-year yield', 'target-year area harvested', 'target-year production', 'target and history source flags', 'post-target observations'],
        'target_transform': 'source_kg_per_ha_no_conversion',
        'quality_findings': ['Three consecutive prior values and a target are required. Windows can overlap across consecutive years.',
            'This is a retrospective lagged task from one published vintage. Revisions and publication lags preclude a real-time backtest claim.',
            'The subset includes country and territory reporting areas. Regional aggregates and explicitly identified overlapping combined/predecessor areas are omitted.',
            'A denotes an official figure and E an estimated one. Flags are retained outside input. Data have been filtered and reshaped by the repository authors.'],
        'tasks': {'next_annual_crop_yield': {'instruction': 'Estimate this reporting area’s next annual yield for the specified cereal crop, using its three preceding annual yields.',
            'field_description': 'reporting_area is the FAOSTAT country or territory name. crop is the cereal. target_year is the year of the requested yield. prior_annual_yields_kg_per_ha lists the three preceding annual observations, in chronological order, each measured in kilograms per harvested hectare.',
            'target_name': 'next_annual_crop_yield', 'unit': 'kg/ha', 'type': 'continuous'}}})


if __name__ == '__main__':
    raw, out = map(Path, sys.argv[1:])
    out.mkdir(parents=True, exist_ok=True)
    paddy(raw, out)
    faostat(raw, out)
