"""Review CSVs offline by default; opt into network enrichment with --enrich."""
import argparse
import csv
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from data_quality import email_quality, spreadsheet_safe, spreadsheet_headers


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--enrich', action='store_true', help='Enable public web requests')
    parser.add_argument('--verify-mailboxes', action='store_true', help='Check DNS/MX and SMTP RCPT without sending mail')
    parser.add_argument('--mx-only', action='store_true', help='Check DNS mail routes without SMTP')
    parser.add_argument('--workers', type=int, default=10, choices=range(1, 101), metavar='1..100')
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        parser.error('Input and output must be different files')
    try:
        with args.input.open(encoding='utf-8-sig', newline='') as source:
            reader = csv.DictReader(source)
            columns = reader.fieldnames or []
            if 'company_name' not in columns or len(set(columns)) != len(columns):
                parser.error('CSV must have unique headers including company_name')
            rows = list(reader)
        seen, duplicates, valid = {}, 0, []
        for line, row in enumerate(rows, start=2):
            if None in row:
                parser.error(f'Unexpected extra CSV fields at line {line}')
            for key, value in row.items():
                row[key] = value or ''
            identity = tuple(row.get(key, '').strip().casefold()
                             for key in ('company_name', 'city', 'state', 'country', 'website'))
            row['DUPLICATE_OF'] = str(seen[identity]) if identity in seen and identity[0] else ''
            if row['DUPLICATE_OF']:
                duplicates += 1
            elif identity[0]:
                seen[identity] = line
            row['STATUS'] = 'reviewed_offline' if identity[0] else 'invalid_input'
            if identity[0]:
                valid.append(row)
        if args.enrich:
            from dataclasses import asdict
            from enricher_core import EnrichedCompany, run_enrichment
            inputs = [EnrichedCompany(**{key: row.get(key, '') for key in
                      ('company_name', 'city', 'state', 'country', 'website', 'email')}) for row in valid]
            for row, result in zip(valid, run_enrichment(inputs, workers=args.workers)):
                row.update({'ENRICHED_' + key.upper(): value for key, value in asdict(result).items()})
                row['STATUS'] = result.status
        for row in rows:
            email = row.get('ENRICHED_EMAIL', row.get('email', ''))
            website = row.get('ENRICHED_WEBSITE', row.get('website', '')).strip()
            try:
                domain = urlsplit(website if '://' in website else 'https://' + website).hostname or ''
            except ValueError:
                domain = ''
            row['EMAIL_STATUS'] = email_quality(email, domain)
        if args.verify_mailboxes or args.mx_only:
            from mailbox_verifier import run_verification
            emails = [row.get('ENRICHED_EMAIL', row.get('email', '')) for row in rows]
            checks = run_verification(emails, workers=min(args.workers, 4), smtp=not args.mx_only)
            for row, check in zip(rows, checks):
                row.update({'MAILBOX_STATUS': check.status, 'MAILBOX_REASON': check.reason,
                            'MAILBOX_MX': check.mx_host, 'MAILBOX_SMTP_CODE': check.smtp_code,
                            'MAILBOX_CATCH_ALL': '' if check.catch_all is None else str(check.catch_all).lower(),
                            'MAILBOX_CHECKED_AT': check.checked_at})
        headers = list(dict.fromkeys(columns + [key for row in rows for key in row]))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=args.output.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writerow(dict(zip(headers, spreadsheet_headers(headers))))
                writer.writerows({key: spreadsheet_safe(value) for key, value in row.items()} for row in rows)
            os.replace(temporary, args.output)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print(json.dumps({'rows': len(rows), 'duplicates': duplicates,
                          'network_enabled': args.enrich or args.verify_mailboxes or args.mx_only,
                          'output': str(args.output),
                          'mailbox_status': dict(Counter(row['MAILBOX_STATUS'] for row in rows))
                              if args.verify_mailboxes or args.mx_only else {},
                          'email_status': dict(Counter(row['EMAIL_STATUS'] for row in rows))}))
    except (OSError, UnicodeError, csv.Error) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
