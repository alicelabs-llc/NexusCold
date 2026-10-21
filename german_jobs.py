"""Resumable, encrypted checkpoints. CSV exports are deliberately ordinary files."""
import csv
import hashlib
import io
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from data_quality import spreadsheet_safe, spreadsheet_headers
from german_agent import inspect_rows, row_email_quality

MODES = ('offline', 'mx', 'smtp', 'enrich', 'enrich_smtp')
SOURCES = ('ddg', 'bing', 'google')


def read_csv(path):
    path = Path(path)
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError('CSV demasiado grande: límite 50 MiB por trabajo.')
    text = path.read_text(encoding='utf-8-sig')
    reader = csv.DictReader(io.StringIO(text, newline=''))
    headers = reader.fieldnames or []
    if not headers or any(not h.strip() for h in headers) or len(set(headers)) != len(headers):
        raise ValueError('El CSV necesita cabeceras únicas y no vacías.')
    rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError('Filas CSV con cantidad de columnas incorrecta.')
    return rows


def _atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _cipher(path, create=False):
    key_path = Path(str(path) + '.key')
    if not key_path.exists() and create:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(Fernet.generate_key())
    try:
        return Fernet(key_path.read_bytes())
    except (OSError, ValueError):
        raise ValueError('Falta la clave privada del checkpoint o es inválida. No se reemplazó el trabajo.') from None


def load_checkpoint(path):
    try:
        cipher = _cipher(path)
        with Path(path).open('rb') as stream:
            header = stream.readline()
            if not header.endswith(b'\n'):
                raise ValueError('Checkpoint incompleto: falta cabecera confirmada.')
            state = json.loads(cipher.decrypt(header.rstrip(b'\n')))
            if not isinstance(state, dict) or state.get('version') != 2:
                raise ValueError('Versión de checkpoint no admitida.')
            state.update(results=[], completed=0, _valid_bytes=stream.tell())
            while True:
                line = stream.readline()
                if not line or not line.endswith(b'\n'):
                    break  # Incomplete final append is uncommitted and safe to retry.
                event = json.loads(cipher.decrypt(line.rstrip(b'\n')))
                if (not isinstance(event, dict) or event.get('index') != len(state['results'])
                        or not isinstance(event.get('row'), dict)):
                    raise ValueError('Secuencia de checkpoint inconsistente.')
                state['results'].append(event['row'])
                state['completed'] += 1
                state['_valid_bytes'] = stream.tell()
            return state
    except (InvalidToken, json.JSONDecodeError, UnicodeError):
        raise ValueError('Checkpoint alterado o clave incorrecta.') from None


def _save_checkpoint(path, state, cipher):
    header = {k: v for k, v in state.items() if k not in ('results', 'completed', '_valid_bytes')}
    _atomic(path, cipher.encrypt(json.dumps(header, ensure_ascii=False).encode('utf-8')) + b'\n')


def _append_result(path, index, row, cipher):
    event = json.dumps({'index': index, 'row': row}, ensure_ascii=False).encode('utf-8')
    with Path(path).open('ab') as stream:
        stream.write(cipher.encrypt(event) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def export_rows(path, rows, columns):
    headers = list(dict.fromkeys(columns + [key for row in rows for key in row]))
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writerow(dict(zip(headers, spreadsheet_headers(headers))))
    writer.writerows({k: spreadsheet_safe(v) for k, v in row.items()} for row in rows)
    _atomic(path, stream.getvalue().encode('utf-8-sig'))


def _process(row, mapping, mode, sources):
    result = dict(row)
    fields = {target: row.get(column, '').strip() if column else '' for target, column in mapping.items()}
    email = fields.get('email', '')
    effective_mapping = mapping
    if mode in ('enrich', 'enrich_smtp'):
        result.update(ENRICHED_EMAIL=email, ENRICHED_WEBSITE=fields.get('website', ''))
        effective_mapping = {**mapping, 'email': 'ENRICHED_EMAIL', 'website': 'ENRICHED_WEBSITE'}
    if mode in ('enrich', 'enrich_smtp') and fields.get('company_name'):
        from enricher_core import EnrichedCompany, run_enrichment
        record = run_enrichment([EnrichedCompany(**fields)], workers=1,
            discovery_sources=sources, registry_sources=(), waterfall=True, use_cache=False)[0]
        result.update({'ENRICHED_' + k.upper(): v for k, v in asdict(record).items()})
        result['STATUS'] = record.status
        email = record.email
    result['EMAIL_STATUS'] = row_email_quality(result, effective_mapping)
    if mode in ('mx', 'smtp', 'enrich_smtp'):
        from mailbox_verifier import run_verification
        check = run_verification([email], workers=1, smtp=mode != 'mx')[0]
        result.update({'MAILBOX_STATUS': check.status, 'MAILBOX_REASON': check.reason,
                       'MAILBOX_MX': check.mx_host, 'MAILBOX_SMTP_CODE': check.smtp_code,
                       'MAILBOX_CATCH_ALL': '' if check.catch_all is None else str(check.catch_all).lower(),
                       'MAILBOX_CHECKED_AT': check.checked_at})
    return result


def run_job(input_path, output_path, *, checkpoint=None, mode='offline', allow_network=False,
            mapping=None, sources=SOURCES, resume=False, stop_flag=None, progress_callback=None):
    source, output = Path(input_path).resolve(), Path(output_path).resolve()
    checkpoint = Path(checkpoint or str(output) + '.german').resolve()
    key_path = Path(str(checkpoint) + '.key')
    if len({source, output, checkpoint, key_path}) != 4:
        raise ValueError('Entrada, salida, checkpoint y clave deben ser archivos distintos.')
    if mode not in MODES or not sources or not set(sources) <= set(SOURCES):
        raise ValueError('Modo o fuentes no admitidos.')
    if mode != 'offline' and not allow_network:
        raise ValueError('Este trabajo consulta internet; activa allow_network explícitamente.')
    rows = read_csv(source)
    analysis = inspect_rows(rows)
    mapping = analysis['mapping'] if mapping is None else mapping
    if set(mapping) - set(analysis['mapping']) or any(c and c not in (rows[0] if rows else {}) for c in mapping.values()):
        raise ValueError('Mapeo desconocido o columna inexistente.')
    if not mapping.get('company_name'):
        raise ValueError('Mapea company_name a la columna que identifica la empresa.')
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    config = {'mode': mode, 'sources': list(sources), 'mapping': mapping}
    if resume:
        state = load_checkpoint(checkpoint)
        if state.get('version') != 2 or state.get('input_sha256') != fingerprint or state.get('config') != config:
            raise ValueError('El archivo o la configuración cambió: crea otro trabajo.')
        if not isinstance(state.get('results'), list) or state.get('completed') != len(state['results']) or state['completed'] > len(rows):
            raise ValueError('Checkpoint inconsistente.')
        cipher = _cipher(checkpoint)
        # Drop only an incomplete final record. Authenticated committed records were checked above.
        with checkpoint.open('r+b') as stream:
            stream.truncate(state.pop('_valid_bytes'))
    else:
        if checkpoint.exists():
            raise ValueError('El checkpoint existe; usa reanudar o elige otro nombre.')
        cipher = _cipher(checkpoint, create=True)
        state = {'version': 2, 'input_sha256': fingerprint, 'config': config, 'completed': 0, 'results': []}
        _save_checkpoint(checkpoint, state, cipher)
    for row in rows[state['completed']:]:
        if stop_flag and stop_flag():
            break
        result = _process(row, mapping, mode, sources)
        _append_result(checkpoint, state['completed'], result, cipher)
        state['results'].append(result)
        state['completed'] += 1
        if progress_callback:
            progress_callback(state['completed'], len(rows))
    export_rows(output, state['results'], list(rows[0]) if rows else [])
    report_mapping = ({**mapping, 'email': 'ENRICHED_EMAIL', 'website': 'ENRICHED_WEBSITE'}
                      if mode in ('enrich', 'enrich_smtp') else mapping)
    return {'completed': state['completed'], 'total': len(rows), 'finished': state['completed'] == len(rows),
            'output': str(output), 'checkpoint': str(checkpoint),
            'summary': inspect_rows(state['results'], mapping=report_mapping)}
