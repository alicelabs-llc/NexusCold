"""Command line entry point for Germán. No network unless the selected action opts in."""
import argparse
import asyncio
import csv
import json
import os
from pathlib import Path
from german_agent import inspect_rows, ModelConfig, ask_german, DEFAULT_MODEL
from german_jobs import read_csv, run_job, MODES, SOURCES


def main(argv=None):
    parser = argparse.ArgumentParser(description='Germán — operador local de NexusCold')
    sub = parser.add_subparsers(dest='command', required=True)
    review = sub.add_parser('review', help='Analizar CSV sin red ni modelo')
    review.add_argument('input', type=Path)
    run = sub.add_parser('run', help='Ejecutar o reanudar un trabajo con checkpoint cifrado')
    run.add_argument('input', type=Path)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--checkpoint', type=Path)
    run.add_argument('--mode', choices=MODES, default='offline')
    run.add_argument('--allow-network', action='store_true')
    run.add_argument('--resume', action='store_true')
    run.add_argument('--sources', nargs='+', choices=SOURCES, default=list(SOURCES))
    run.add_argument('--mapping', help='Objeto JSON: campo canónico -> columna del CSV')
    ask = sub.add_parser('ask', help='Preguntar a Ollama; solo transmite métricas y tu pregunta')
    ask.add_argument('input', type=Path)
    ask.add_argument('question')
    ask.add_argument('--endpoint', default='http://127.0.0.1:11434')
    ask.add_argument('--model', default=DEFAULT_MODEL)
    ask.add_argument('--allow-remote', action='store_true')
    auth = sub.add_parser('domain', help='Consultar publicación SPF/DMARC exacta por DNS')
    auth.add_argument('domain')
    auth.add_argument('--allow-network', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'review':
            result = inspect_rows(read_csv(args.input))
        elif args.command == 'run':
            result = run_job(args.input, args.output, checkpoint=args.checkpoint, mode=args.mode,
                allow_network=args.allow_network, resume=args.resume, sources=tuple(args.sources),
                mapping=json.loads(args.mapping) if args.mapping else None)
        elif args.command == 'ask':
            config = ModelConfig(args.endpoint, args.model, args.allow_remote, os.environ.get('NEXUS_GERMAN_TOKEN', ''))
            result = {'answer': asyncio.run(ask_german(args.question, inspect_rows(read_csv(args.input)), config))}
        else:
            if not args.allow_network:
                raise ValueError('El diagnóstico de dominio consulta DNS; añade --allow-network.')
            from domain_auth import check_domain
            result = asyncio.run(check_domain(args.domain))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except (ValueError, OSError, csv.Error, asyncio.TimeoutError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
