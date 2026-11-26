"""Project the original UCI WiFi positioning and gas-sensor archives to candidates."""
import argparse
import csv
import hashlib
import io
import json
import math
import re
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


SOURCES = {
    'uji': (310, 'ujiindoorloc', '10.24432/C5MS59'),
    'gas': (487, 'gas+sensor+array+temperature+modulation', '10.24432/C5S302'),
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def metadata(slug, raw_dir, name, authors):
    uid, path, doi = SOURCES[slug]
    source_url = f'https://archive.ics.uci.edu/dataset/{uid}/{path}'
    archive = raw_dir / f'{slug}.zip'
    return {
        'dataset_id': f'uci_{uid}', 'candidate_id': {'uji': 'U1', 'gas': 'G1'}[slug],
        'name': name, 'source_url': source_url, 'version': 'UCI public archive snapshot 2026-11-26',
        'source_citation': {'doi': doi, 'authors': authors},
        'license': {'name': 'CC BY 4.0', 'url': 'https://creativecommons.org/licenses/by/4.0/',
                    'evidence': {'url': source_url}},
        'source_files': [{'relativepath': archive.name, 'bytes': archive.stat().st_size,
                          'sha256': digest(archive),
                          'url': f'https://archive.ics.uci.edu/static/public/{uid}/{path}.zip'}],
        'invalid_label_examples': 0,
    }


def write_record(stream, record):
    stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n')


def save_meta(out_dir, slug, meta):
    (out_dir / f'{slug}.meta.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def wifi(raw_dir, out_dir):
    meta = metadata('uji', raw_dir, 'UJIIndoorLoc', ['Joaquín Torres-Sospedra', 'Raúl Montoliu',
                    'Adolfo Martínez-Usó', 'Tomar Arnau', 'Joan Avariento'])
    tasks = {'map_x': 'LONGITUDE', 'map_y': 'LATITUDE'}
    meta['tasks'] = {
        key: {'target_name': key, 'unit': 'm', 'type': 'continuous',
              'instruction': f'Estimate the indoor map {key[-1]} coordinate of this WiFi scan at Universitat Jaume I.',
              'field_description': 'observed_ap_rssi_dbm maps detected WiFi access point identifiers to received signal strength in dBm. An omitted access point was not detected. Map coordinates are in the source campus reference system.'}
        for key in tasks}
    ap_keys = [f'WAP{i:03d}' for i in range(1, 521)]
    excluded = Counter()
    rows = Counter()
    with zipfile.ZipFile(raw_dir / 'uji.zip') as archive, (out_dir / 'uji.jsonl').open('w', encoding='utf-8') as out:
        for source_file, split in [('trainingData.csv', 'train'), ('validationData.csv', 'test')]:
            member = 'UJIndoorLoc/' + source_file
            with archive.open(member) as binary:
                reader = csv.DictReader(io.TextIOWrapper(binary, encoding='utf-8-sig'))
                assert reader.fieldnames[:520] == ap_keys
                for index, row in enumerate(reader, 1):
                    rows[source_file] += 1
                    signals = {k: int(row[k]) for k in ap_keys if row[k] != '100'}
                    if not signals:
                        excluded[source_file] += 1
                        continue
                    assert all(-104 <= signal <= 0 for signal in signals.values())
                    timestamp = int(row['TIMESTAMP'])
                    user, phone = row['USERID'], row['PHONEID']
                    capture_group = f'{user}/{phone}/{timestamp // 86400}'
                    ref = {'file': member, 'row': index, 'user_id': user, 'phone_id': phone, 'unix_time': timestamp}
                    for key, column in tasks.items():
                        label = float(row[column]); assert math.isfinite(label)
                        write_record(out, {'task_key': key, 'input': {'observed_ap_rssi_dbm': signals},
                                           'label': label, 'source_refs': [ref], 'split': split, 'source_split': source_file,
                                           'group_key': capture_group, 'quality_flags': []})
    assert rows == {'trainingData.csv': 19937, 'validationData.csv': 1111} and excluded == {'trainingData.csv': 76}
    meta.update(raw_rows_selected=sum(rows.values()), excluded_source_rows=sum(excluded.values()),
                candidate_task_examples=2 * (sum(rows.values()) - sum(excluded.values())),
                source_profile={'raw_rows_by_file': dict(rows), 'all_undetected_rows_excluded': dict(excluded)},
                grouping_rule='User, phone and UTC day; overlaps in WiFi input are linked in standardization.',
                split_policy='Official reference file as train and official validation/test file as test; original source filename retained.',
                excluded_input_columns=['LONGITUDE','LATITUDE','FLOOR','BUILDINGID','SPACEID','RELATIVEPOSITION','USERID','PHONEID','TIMESTAMP'],
                target_transform='none_applied', quality_findings=[
                    '76 training rows have no detected access points. All source evaluation occurrences are retained, including multiplicity after deduplication.',
                    'Both coordinate components share the same input and group. Published coordinates in metres are copied without reprojection. Unit reference: https://doi.org/10.1109/IPIN.2014.7275492',
                    'No campus maps, real MAC addresses, floor or space identifiers, companion coordinate, user or phone attributes are included in model input.'])
    save_meta(out_dir, 'uji', meta)


GAS_HEADER = ['Time (s)', 'CO (ppm)', 'Humidity (%r.h.)', 'Temperature (C)',
              'Flow rate (mL/min)', 'Heater voltage (V)'] + [f'R{i} (MOhm)' for i in range(1, 15)]


def summarize_gas_window(member, slot, window):
    indices, measurements = zip(*window)
    cols = list(zip(*measurements))
    times, co = cols[:2]
    # Avoid a nominal window with absent acquisition at the beginning, end or interior.
    start = slot * 900 + 450
    if times[0] - start > 2 or start + 300 - times[-1] > 2 or any(not 0 <= b - a <= 2 for a, b in zip(times, times[1:])) or indices[-1] - indices[0] + 1 != len(window):
        return None
    def mean(values):
        return math.fsum(values) / len(values)
    def readings(values):
        return {'mean': mean(values), 'min': min(values), 'max': max(values)}
    if not all(math.isfinite(v) for column in cols for v in column):
        raise ValueError(f'Nonfinite raw value in {member} slot {slot}')
    flags = []
    if min(co) != max(co):
        flags.append('reference_concentration_varied_within_window')
    if any(min(column) <= 0 for column in cols[6:]):
        flags.append('nonpositive_resistance_in_window')
    signals = {f'R{i}': readings(values) for i, values in enumerate(cols[6:], 1)}
    return {'task_key': 'mean_co_concentration',
            'input': {'sensor_resistance_megohm': signals,
                      'relative_humidity_pct_mean': mean(cols[2]), 'temperature_c_mean': mean(cols[3])},
            'label': mean(co), 'source_refs': [{'file': member, 'row': indices[0], 'row_end_inclusive': indices[-1],
            'time_start_s': times[0], 'time_end_s': times[-1]}],
            'quality_flags': flags, 'group_key': member, 'entity_id': member.split('.')[0],
            'time_key': (datetime.strptime(member[:-4], '%Y%m%d_%H%M%S') + timedelta(seconds=times[-1])).isoformat(timespec='milliseconds'),
            'source_measurements_in_window': len(window), 'exposure_slot': slot, 'split': 'unassigned'}


def gas(raw_dir, out_dir):
    meta = metadata('gas', raw_dir, 'Gas sensor array temperature modulation', ['Javier Burgués'])
    row_counts = {}; window_counts = {}; excluded_slots = {}; flags = Counter(); selected_rows = 0
    time_reversals = []
    with zipfile.ZipFile(raw_dir / 'gas.zip') as outer, tempfile.TemporaryFile() as tmp:
        # The UCI distribution contains an inner zip of readings. Copying once avoids seeking a compressed member.
        import shutil
        with outer.open('gas-sensor-array-temperature-modulation.zip') as inner:
            shutil.copyfileobj(inner, tmp)
        with zipfile.ZipFile(tmp) as archive, (out_dir / 'gas.jsonl').open('w', encoding='utf-8') as out:
            names = sorted(n for n in archive.namelist() if re.fullmatch(r'\d{8}_\d{6}\.csv', n))
            assert len(names) == 13
            for name in names:
                row_counts[name] = 0; window_counts[name] = 0
                windows = {}; last_time = -math.inf
                with archive.open(name) as stream:
                    assert next(stream).decode('ascii').strip().split(',') == GAS_HEADER
                    for i, line in enumerate(stream, 1):
                        row_counts[name] += 1
                        t = float(line.split(b',', 1)[0])
                        if t < last_time:
                            time_reversals.append({'file': name, 'row': i, 'previous_time_s': last_time, 'time_s': t})
                        last_time = t; slot = int(t // 900)
                        if 1 <= slot <= 100 and 450 <= t - 900 * slot < 750:
                            measurements = tuple(map(float, line.split(b',')))
                            assert len(measurements) == 20
                            windows.setdefault(slot, []).append((i, measurements))
                missing = []
                for slot in range(1, 101):
                    window = windows.get(slot, [])
                    record = summarize_gas_window(name, slot, window) if window else None
                    if record is None:
                        missing.append(slot)
                        continue
                    write_record(out, record)
                    selected_rows += len(window); window_counts[name] += 1
                    flags.update(record['quality_flags'])
                excluded_slots[name] = missing
    meta.update(raw_rows_selected=sum(row_counts.values()), excluded_source_rows=sum(row_counts.values())-selected_rows,
                candidate_task_examples=sum(window_counts.values()), dataset_family='uci_487',
                grouping_rule='All exposure windows from the same experiment start file share a group.',
                split_policy='Unassigned. For cross-date evaluation use entire files in chronological order, e.g. first 8 for train, next 2 for validation and last 3 for test.',
                excluded_input_columns=['Time (s)', 'CO (ppm)', 'Flow rate (mL/min)', 'Heater voltage (V)'],
                target_transform='arithmetic_mean_of_source_co_in_fixed_window',
                source_profile={'raw_rows_by_file':row_counts, 'source_rows_in_published_windows':selected_rows,
                                'valid_windows_by_file':window_counts, 'incomplete_slots_by_file':excluded_slots,
                                'within_window_flags':dict(flags), 'raw_time_reversals':time_reversals},
                quality_findings=['The UCI landing-page count is nominal; the published source-row counts above are from reading all thirteen files.',
                   'Each nominal 15-minute exposure yields a fixed five-minute sensor window at offsets [450,750) seconds. Slot zero is the initial purge. Slot 1 starts at elapsed 900 seconds. Slot assignment and input selection use only elapsed time.',
                   'Both labels and inputs summarize exactly the same contiguous time window; this is a contemporaneous lab calibration task. The ppm label is the mean reference from the exposure protocol. Device uncertainty is not used as target variance.',
                   'Windows missing either edge by over 2 seconds, containing a reversal or acquisition gap over 2 seconds, or covering nonconsecutive source rows are omitted. Negative or zero resistance, where present, is retained and flagged.',
                   'The source protocol samples ten nominal CO levels between 0 and 20 ppm. The number of distinct prepared labels is limited by those levels.',
                   'The published rows from one laboratory and one sensor array do not cover new devices.'],
                tasks={'mean_co_concentration':{'instruction':'Estimate the mean carbon monoxide concentration in a laboratory gas chamber during this five-minute window.',
                       'target_name':'mean_co_concentration','type':'continuous','unit':'ppm',
                       'field_description':'sensor_resistance_megohm lists the arithmetic mean, minimum and maximum resistance in megaohms of each metal oxide sensor over a five-minute window. R1 through R7 are Figaro TGS 3870-A04 sensors and R8 through R14 are FIS SB-500-12 sensors. relative_humidity_pct_mean and temperature_c_mean give mean relative humidity in percent and mean chamber temperature in degrees Celsius over the same window.'}})
    meta['source_citation']['requested_papers'] = [
        'Burgués, Jiménez-Soto & Marco (2018). Estimation of the limit of detection in semiconductor gas sensors through linearized calibration models. Analytica Chimica Acta 1013, 13–25.',
        'Burgués & Marco (2018). Multivariate estimation of the limit of detection by orthogonal partial least squares in temperature-modulated MOX sensors. Analytica Chimica Acta 1019, 49–64.']
    save_meta(out_dir, 'gas', meta)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_dir', type=Path)
    parser.add_argument('out_dir', type=Path)
    parser.add_argument('--only', choices=['uji','gas'])
    args = parser.parse_args(); args.out_dir.mkdir(exist_ok=True, parents=True)
    if args.only in (None, 'uji'):
        wifi(args.raw_dir, args.out_dir)
    if args.only in (None, 'gas'):
        gas(args.raw_dir, args.out_dir)
