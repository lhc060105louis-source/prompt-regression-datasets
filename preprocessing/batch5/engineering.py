"""Convert the two pinned public engineering experiments to source-traceable candidates."""
import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import openpyxl


FDM = 'https://data.mendeley.com/datasets/zd6td6svd6/1'
FDM_FILES = 'https://data.mendeley.com/public-files/datasets/zd6td6svd6/files/'
MOTOR = 'https://archive.ics.uci.edu/dataset/607/synchronous+machine+data+set'
SOURCE_FILES = {
    'fdm-parameters.xlsx': (FDM_FILES + 'd25c271e-dfb9-4448-99ad-25eb6a7dd965/file_downloaded',
                            'fc85cbbe019090c55740d86e8bb451159443fa68100cd0a7c99dbdd75330a591'),
    'fdm-description.pdf': (FDM_FILES + '3b1f5da6-e3e7-4a6e-8f61-990ccfe4e31d/file_downloaded',
                            'e42d5421dba89d1596bbd07e80b7de9df20222c4c63df27c40d707d509c7d50e'),
    'synchronous-machine.zip': ('https://archive.ics.uci.edu/static/public/607/synchronous+machine+data+set.zip',
                                'e34f66b956cd086facbdaabb5587a6d26f513e9eacaf73ff5611710464f05580'),
}


def inventory(raw, name):
    url, expected = SOURCE_FILES[name]
    path = raw / name
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f'Source checksum mismatch for {name}')
    return dict(relativepath=name, url=url, sha256=actual, bytes=path.stat().st_size)


def cc_by(source):
    return {'name': 'CC BY 4.0', 'url': 'https://creativecommons.org/licenses/by/4.0/', 'evidence': {'url': source}}


def write_candidate(out, row):
    out.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')


def write_meta(out, slug, metadata):
    (out / f'{slug}.meta.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def build_fdm(raw, out):
    files = [inventory(raw, name) for name in ('fdm-parameters.xlsx', 'fdm-description.pdf')]
    source_name = '3d printing parametres dataset.xlsx'
    key = 'mean_peak_tensile_load'
    meta = dict(dataset_id='fdm_aktepe', dataset_family='aktepe_ergun_fdm', candidate_id='FDM',
                name='FDM printing configuration and peak tensile load', version='Mendeley Data V1 (2026-07-17)',
                source_url=FDM, source_files=files, license=cc_by(FDM),
                source_citation=dict(authors=['Elif Aktepe', 'Uçman Ergün'], doi='10.17632/zd6td6svd6.1',
                                     corresponding_paper='https://doi.org/10.3390/mi17070859'),
                tasks={key: dict(target_name='mean peak tensile load', unit='N', type='continuous',
                                 instruction='Estimate the mean peak tensile load measured for specimens made with this fused deposition modeling configuration.',
                                 field_description='printer_chamber is the open or closed printer type. material names the filament. layer_height_mm is the nominal layer thickness in millimetres. infill_pct is the infill percentage and infill_pattern is its layout. print_speed_mm_per_s is the print speed in millimetres per second. The output is the configuration-level mean of three specimens tested under the source study protocol.')},
                target_transform='source_configuration_mean_no_further_aggregation',
                split_policy='Unassigned. Keep each material family together when evaluating new polymers.',
                grouping_rule='PLA variants share a family. PETG and recycled PET form a polyester group. ABS, PP, and TPU each form a family.',
                excluded_input_columns=['Sample No', 'Roughness AVG', 'Hardness AVG', 'Peak Load (N)', 'Peak Stress (kPa)',
                                        'Strain at Break (mm/mm)', 'Modulus (MPa)', 'Width (mm)', 'Thickness (mm)'],
                quality_findings=['The workbook reports configuration-level values from physical experiments. Three specimens per configuration are represented by one aggregate observation; replicate-level variance is unavailable.',
                                  'Post-print dimensions and all mechanical or surface outcomes are excluded. Only the six manufacturing settings are model inputs.',
                                  'The source distinguishes printer chamber categories, which are confounded with printer hardware. There are only five polymer-family groups, with unequal group sizes.'],
                invalid_label_examples=0, excluded_source_rows=0)
    workbook = openpyxl.load_workbook(raw / 'fdm-parameters.xlsx', read_only=True, data_only=True)
    subject_ids, settings = set(), set()
    groups = Counter()
    try:
        sheet = workbook['Sayfa1']
        rows = iter(sheet.values)
        fields = [s.replace('\u200b', '').strip() for s in next(rows)]
        assert len(fields) == len(set(fields)) == 15
        with (out / 'fdm.jsonl').open('w', encoding='utf-8') as stream:
            for i, cells in enumerate(rows, 1):
                row = dict(zip(fields, cells))
                material = row['Material'].strip().casefold()
                family = 'pla' if material.startswith('pla') else {'petg': 'pet_family', 'rpet': 'pet_family'}.get(material, material)
                group = f'polymer/{family}'
                inputs = dict(printer_chamber=row['Printer Type'].strip().casefold(), material=material,
                              layer_height_mm=row['Layer Thickness (mm)'], infill_pct=row['Infill Density (%)'],
                              infill_pattern=row['Infill Pattern'].strip().casefold().replace('zig zag', 'zigzag'),
                              print_speed_mm_per_s=row['Speed (mm/s)'])
                assert inputs['printer_chamber'] in ('open', 'closed') and all(x is not None for x in inputs.values())
                label = row['Peak Load (N)']
                assert math.isfinite(label) and label > 0 and row['Sample No'] not in subject_ids
                subject_ids.add(row['Sample No'])
                settings.add(tuple(inputs.values()))
                groups[group] += 1
                ref = dict(file=source_name, sheet='Sayfa1', row=i, excel_row=i+1, sample_no=row['Sample No'], column='Peak Load (N)')
                write_candidate(stream, dict(task_key=key, input=inputs, label=label, group_key=group, split='unassigned', source_refs=[ref]))
    finally:
        workbook.close()
    count = len(subject_ids)
    assert count == len(settings) == 500 and len(groups) == 5
    meta.update(raw_rows_selected=count, candidate_task_examples=count, source_profile={'family_counts': dict(groups), 'unique_configurations': len(settings)})
    write_meta(out, 'fdm', meta)


def build_motor(raw, out):
    source = inventory(raw, 'synchronous-machine.zip')
    key = 'excitation_current'
    member = 'synchronous machine.csv'
    meta = dict(dataset_id='uci_607', dataset_family='uci_607', candidate_id='MOTOR', name='Synchronous Machine',
                version='UCI public archive (2026-11-26)', source_url=MOTOR, source_files=[source], license=cc_by(MOTOR),
                source_citation=dict(citation='Synchronous Machine (2021). UCI Machine Learning Repository.', doi='10.24432/C5W32R',
                                     experimental_reference='https://doi.org/10.22531/muglajsci.466308'),
                tasks={key: dict(target_name='synchronous motor excitation current', unit='A', type='continuous',
                                 instruction='Estimate the field excitation current of the experimental synchronous motor at this operating point.',
                                 field_description='load_current_a is the motor load current in amperes. power_factor is the measured dimensionless power factor at the same operating point.')},
                excluded_input_columns=['If', 'dIf', 'e'], target_transform='none_applied', invalid_label_examples=0, excluded_source_rows=0,
                grouping_rule='Group all points at the same load-current level.',
                split_policy='Unassigned. Hold out entire load-current levels to evaluate transfer across loads on the experimental setup.',
                quality_findings=['Across all source rows, If minus dIf equals exactly 1.180 A. dIf is excluded to prevent direct target leakage.',
                                  'The error column e equals 1 minus the power factor for all rows and is excluded.',
                                  'The source covers a single experimental setup. No independent machine or acquisition-session identifier is available.'])
    settings = set()
    groups = Counter()
    with ZipFile(raw / 'synchronous-machine.zip') as archive, archive.open(member) as binary, (out / 'motor.jsonl').open('w', encoding='utf-8') as stream:
        reader = csv.DictReader(io.TextIOWrapper(binary, encoding='ascii', newline=''), delimiter=';')
        assert reader.fieldnames == ['Iy', 'PF', 'e', 'dIf', 'If']
        for i, row in enumerate(reader, 1):
            values = {k: Decimal(v.replace(',', '.')) for k, v in row.items()}
            assert all(x.is_finite() for x in values.values())
            assert values['If'] - values['dIf'] == Decimal('1.180') and values['e'] + values['PF'] == 1
            load, pf = values['Iy'], values['PF']
            inputs = dict(load_current_a=float(load), power_factor=float(pf))
            group = f'load/{load.normalize():f}'
            ref = dict(file=member, row=i, column='If')
            write_candidate(stream, dict(task_key=key, input=inputs, label=float(values['If']), split='unassigned', group_key=group, source_refs=[ref]))
            settings.add((load,pf)); groups[group] += 1
    count = sum(groups.values())
    assert count == len(settings) == 557 and len(groups) == 31
    meta.update(raw_rows_selected=count, candidate_task_examples=count, source_profile={'load_group_counts': dict(groups), 'unique_operating_points': len(settings)})
    write_meta(out, 'motor', meta)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_dir', type=Path)
    parser.add_argument('out_dir', type=Path)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    build_fdm(args.raw_dir, args.out_dir)
    build_motor(args.raw_dir, args.out_dir)
