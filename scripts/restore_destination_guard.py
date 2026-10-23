#!/usr/bin/env python3
"""Reject ambiguous restore routing; accepts a marked local disposable DB only.

Reads credentials from the environment, never arguments or output. This does
not authorize production writes or replace the existing empty-target gate.
"""
from __future__ import annotations
import argparse
import ipaddress
import json
import os
import re
import sys
from urllib.parse import parse_qsl, unquote, urlsplit


class DestinationError(ValueError):
    pass


def validate_connection(env: dict[str, str]) -> dict[str, str]:
    if env.get('SWSI_RESTORE_TARGET_KIND') != 'local':
        raise DestinationError('only a marked local isolated target is supported; hosted-isolated is blocked')
    # libpq can take routing, service, passfile and options from PG* variables.
    # Reject all of them, including apparently empty values, before calling psql.
    if any(key.upper().startswith('PG') for key in env):
        raise DestinationError('inherited PG environment parameters must be unset')
    identity = env.get('SWSI_RESTORE_TARGET_ID', '')
    if not re.fullmatch(r'isolated-[0-9a-f]{32}', identity):
        raise DestinationError('a disposable target identity is required')
    raw = env.get('SWSI_RESTORE_TARGET_DB_URL', '')
    if not raw or len(raw) > 8192 or any(ord(c) < 33 or ord(c) == 127 for c in raw):
        raise DestinationError('invalid connection URI')
    try:
        url = urlsplit(raw)
        if url.scheme not in ('postgres', 'postgresql') or url.fragment:
            raise DestinationError('a PostgreSQL URI without a fragment is required')
        # No DNS, unix sockets, multiple hosts, encoded hosts or override params.
        if url.hostname not in ('127.0.0.1', '::1') or url.port is None or not 1 <= url.port <= 65535:
            raise DestinationError('target must use an explicit numeric loopback host and port')
        if url.username is None or not unquote(url.username):
            raise DestinationError('explicit database user is required')
        database = unquote(url.path[1:]) if url.path.startswith('/') else ''
        if not database or '/' in database or any(ord(c) < 32 or ord(c) == 127 for c in database):
            raise DestinationError('explicit single database name is required')
        pairs = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
        seen = set()
        for key, value in pairs:
            if key in seen:
                raise DestinationError('duplicate connection parameter')
            seen.add(key)
            if key == 'sslmode' and value in ('disable', 'require', 'verify-ca', 'verify-full'):
                continue
            if key == 'connect_timeout' and re.fullmatch(r'[0-9]{1,2}', value) and 1 <= int(value) <= 30:
                continue
            raise DestinationError('unsupported connection parameter')
    except (ValueError, UnicodeError) as exc:
        # Never reflect raw URI, parser exception, username or password.
        if isinstance(exc, DestinationError):
            raise
        raise DestinationError('invalid connection URI') from None
    return {'database': database, 'target_id': identity}


def validate_identity(payload: object, expected: dict[str, str]) -> None:
    if not isinstance(payload, dict) or set(payload) != {'database', 'target_id', 'server_addr'}:
        raise DestinationError('invalid target identity snapshot')
    if payload['database'] != expected['database'] or payload['target_id'] != expected['target_id']:
        raise DestinationError('isolated database identity mismatch')
    try:
        addr = ipaddress.ip_address(payload['server_addr'])
    except (ValueError, TypeError):
        raise DestinationError('target server address is missing or invalid') from None
    if not addr.is_loopback:
        raise DestinationError('database server must itself have a loopback listener')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-stdin', action='store_true')
    args = parser.parse_args()
    try:
        expected = validate_connection(dict(os.environ))
        if args.identity_stdin:
            raw = sys.stdin.buffer.read(8193)
            if not raw or len(raw) > 8192:
                raise DestinationError('missing or oversized target identity')
            validate_identity(json.loads(raw), expected)
    except (DestinationError, ValueError, TypeError):
        # Generic diagnostic deliberately cannot contain credentials or payloads.
        print('RESTORE DESTINATION REFUSED: routing or isolated identity validation failed', file=sys.stderr)
        return 64
    print('RESTORE DESTINATION IDENTITY OK' if args.identity_stdin else 'RESTORE DESTINATION ROUTING OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
