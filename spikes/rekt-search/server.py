#!/usr/bin/env python3
"""Read-only Rekt archive adapter. Python 3.11+, SQLite FTS5, no dependencies."""
import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import mimetypes
from pathlib import Path
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
from zoneinfo import ZoneInfo

NAME = re.compile(r'(rekt_(\d{4})_(\d{2})_(\d{2})_[A-Za-z]+_(AM|PM)_(\d{2})_(\d{2})_(\d{2})-[\w-]+)')
STAMP = re.compile(r'^\*\*\[(\d+:\d{2}(?::\d{2})?)\]\s*([^:\n]+):\*\*\s*', re.M)
CHUNK = re.compile(r'^## chunk (\d+).*$', re.M)
ZONE = ZoneInfo('America/New_York')


def normalized(text):
    words = re.findall(r'[^\W_]+', text.casefold(), re.UNICODE)
    # Both spellings share a single token; punctuation has no query syntax.
    return re.sub(r'\bwealth\s+box\b', 'wealthbox', ' '.join(words))


def connect(path):
    con = sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    return con


def chunk_seconds(value):
    digits = str(value).zfill(6)
    return int(digits[:-4]) * 3600 + int(digits[-4:-2]) * 60 + int(digits[-2:])


def sections(text, global_source, offset):
    stamps = list(STAMP.finditer(text)) if global_source else []
    if stamps:
        for i, match in enumerate(stamps):
            end = stamps[i + 1].start() if i + 1 < len(stamps) else len(text)
            # Stop at a following chunk heading, which is metadata rather than speech.
            heading = re.search(r'\n## ', text[match.end():end])
            if heading:
                end = match.end() + heading.start()
            quote = text[match.end():end].strip()
            parts = [int(n) for n in match[1].split(':')]
            seconds = sum(n * 60 ** j for j, n in enumerate(reversed(parts)))
            if quote:
                yield quote, seconds, 'exact', match[2]
    headings = list(CHUNK.finditer(text)) if global_source else []
    if headings:
        # Merged files have marked raw blocks or legacy plain speech bodies.
        for heading in headings:
            end_match = re.search(r'\n## chunk ', text[heading.end():])
            end = heading.end() + end_match.start() if end_match else len(text)
            block = text[heading.end():end]
            marker = re.search(r'\[NO DIARIZATION[^\]]*\]', block)
            if not STAMP.search(block):
                raw = (block[marker.end():] if marker else block).strip()
                if raw:
                    yield raw, chunk_seconds(heading[1]), 'approximate', None
    elif not stamps:
        raw = text.strip()
        if raw:
            yield raw, offset, 'approximate', None


def passages(text, limit=1200):
    """Exact slices with intact words and one word of boundary overlap."""
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text) and not text[end - 1].isspace() and not text[end].isspace():
            boundaries = list(re.finditer(r'\s+', text[start:end]))
            if boundaries:
                end = start + boundaries[-1].end()
            else:
                # An indivisible word can exceed the target passage length.
                boundary = re.search(r'\s', text[end:])
                end = end + boundary.start() if boundary else len(text)
        yield start, text[start:end]
        if end == len(text):
            break
        words = list(re.finditer(r'\S+', text[start:end]))
        overlap = start + words[-1].start() if words else end
        start = overlap if overlap > start else end


def index(args):
    root, audio_root, db = map(lambda p: Path(p).resolve(), (args.transcripts, args.audio_root, args.db))
    if db.is_relative_to(root) or db.is_relative_to(audio_root):
        raise ValueError('Scratch database must be outside source archives')
    db.parent.mkdir(parents=True, exist_ok=True)
    groups = {}
    empty = skips = errors = 0
    # Only text and canonical merged sources; never mutate or ingest JSON/audio.
    for path in sorted(root.rglob('*')):
        if not path.is_file() or not (path.suffix == '.txt' or path.name.endswith('.global.merged.md') or path.name.startswith('MERGED-')):
            continue
        try:
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                skips += 1
                continue
            text = path.read_text(encoding='utf-8')
            if not text.strip() or '_No words transcribed for any chunk' in text:
                empty += 1
                continue
            match = NAME.search(path.name) or NAME.search(text[:2000])
            if not match:
                skips += 1
                continue
            stem = match[1].split('__')[0]
            hour = int(match[6])
            if not 1 <= hour <= 12:
                raise ValueError('Invalid capture hour')
            capture = dt.datetime(int(match[2]), int(match[3]), int(match[4]), hour % 12 + (12 if match[5] == 'PM' else 0), int(match[7]), int(match[8]), tzinfo=ZONE)
            chunk = re.search(r'__(\d+)_\d+min', path.name)
            is_global = path.name.endswith('.global.merged.md')
            priority = 3 if is_global else 2 if path.name.startswith('MERGED-') else 1
            groups.setdefault(stem, []).append((priority, resolved, text, chunk_seconds(chunk[1]) if chunk else 0, capture))
        except (OSError, UnicodeError, ValueError):
            errors += 1
    con = sqlite3.connect(db)
    con.executescript('''DROP TABLE IF EXISTS passages_fts; DROP TABLE IF EXISTS passages; DROP TABLE IF EXISTS recordings; DROP TABLE IF EXISTS metadata;
    CREATE TABLE recordings (recording_id TEXT PRIMARY KEY, date TEXT, capture_datetime TEXT, source_recording TEXT, audio_path TEXT, audio_kind TEXT, audio_start REAL);
    CREATE TABLE passages (id INTEGER PRIMARY KEY, recording_id TEXT, text TEXT, source_path TEXT, offset_seconds REAL, timing TEXT, speaker TEXT);
    CREATE VIRTUAL TABLE passages_fts USING fts5(words);
    CREATE TABLE metadata (value TEXT);
    CREATE INDEX passage_recording ON passages(recording_id);
    CREATE INDEX capture_date ON recordings(date);''')
    alternatives = 0
    for stem, sources in sorted(groups.items()):
        best = max(s[0] for s in sources)
        chosen = [s for s in sources if s[0] == best]
        if best > 1:
            chosen = chosen[:1]
        alternatives += len(sources) - len(chosen)
        rid = hashlib.sha256(stem.encode()).hexdigest()[:24]
        capture = chosen[0][4]
        full = audio_root / capture.strftime('%Y-%m') / (stem + '.aac')
        audio_path, kind, audio_start = None, None, 0
        if full.is_file() and full.resolve().is_relative_to(audio_root):
            audio_path, kind = str(full.resolve()), 'full recording'
        else:
            # Resolve once at indexing, never scan or construct paths from HTTP input.
            for candidate in sorted((audio_root / capture.strftime('%Y-%m')).glob(stem + '__*.aac')):
                chunk = re.search(r'__(\d+)_', candidate.name)
                if chunk and candidate.resolve().is_relative_to(audio_root):
                    audio_path, kind, audio_start = str(candidate.resolve()), 'chunk only', chunk_seconds(chunk[1])
                    break
        rows = []
        for priority, path, text, offset, _ in chosen:
            for quote, seconds, timing, speaker in sections(text, priority > 1, offset):
                # Keep whole words and aliases across exact source slices.
                for start, excerpt in passages(quote):
                    if normalized(excerpt):
                        rows.append((rid, excerpt, str(path), seconds, timing if start == 0 else 'approximate', speaker))
        if not rows:
            skips += len(chosen)
            continue
        con.execute('INSERT INTO recordings VALUES (?,?,?,?,?,?,?)', (rid, capture.date().isoformat(), capture.isoformat(), stem, audio_path, kind, audio_start))
        for row in rows:
            cursor = con.execute('INSERT INTO passages(recording_id,text,source_path,offset_seconds,timing,speaker) VALUES (?,?,?,?,?,?)', row)
            con.execute('INSERT INTO passages_fts(rowid,words) VALUES (?,?)', (cursor.lastrowid, normalized(row[1])))
    stats = dict(zip(('recordings', 'min_date', 'max_date'), con.execute('SELECT count(*), min(date), max(date) FROM recordings').fetchone()))
    stats.update(passages=con.execute('SELECT count(*) FROM passages').fetchone()[0], empty_sources=empty, errors=errors, skips=skips, deduplicated_sources=alternatives, indexed_at=dt.datetime.now(dt.timezone.utc).isoformat(), timezone=str(ZONE), audio_root=str(audio_root), transcript_root=str(root))
    stats['dates'] = [{'date': r[0], 'recordings': r[1]} for r in con.execute('SELECT date,count(*) FROM recordings GROUP BY date ORDER BY date')]
    con.execute('INSERT INTO metadata VALUES (?)', (json.dumps(stats),))
    con.commit()
    con.close()
    # Keep CLI evidence compact; full per-date coverage remains in /api/status.
    print(json.dumps({k: v for k, v in stats.items() if k != 'dates'}, indent=2))


SELECT = 'SELECT p.*, r.* FROM passages p JOIN recordings r USING(recording_id)'


def result(row):
    value = dict(row)
    value.pop('audio_path', None)
    value['audio_available'] = bool(row['audio_path']) and (row['audio_kind'] == 'full recording' or row['audio_start'] <= row['offset_seconds'] < row['audio_start'] + 300)
    value['audio_url'] = '/api/audio/' + row['recording_id'] if value['audio_available'] else None
    value['audio_offset_seconds'] = max(0, row['offset_seconds'] - row['audio_start'])
    return value


class Handler(BaseHTTPRequestHandler):
    def json(self, data, status=200):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        try:
            self.dispatch()
        except (ValueError, OverflowError) as exc:
            self.json({'error': str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def dispatch(self):
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if path == '/':
            payload = Path(__file__).with_name('index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)
            return
        with connect(self.server.db) as con:
            if path == '/api/status':
                self.json(json.loads(con.execute('SELECT value FROM metadata').fetchone()[0]))
                return
            if path == '/api/search':
                params = parse_qs(parsed.query, keep_blank_values=True)
                get = lambda k, default='': params.get(k, [default])[0]
                bounds, values = [], []
                for field, operator in [('from', '>='), ('to', '<=')]:
                    value = get(field)
                    if value:
                        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                            raise ValueError(f'{field} must be YYYY-MM-DD')
                        dt.date.fromisoformat(value)
                        bounds.append('r.date ' + operator + ' ?')
                        values.append(value)
                if get('from') and get('to') and get('from') > get('to'):
                    raise ValueError('From date must be on or before To date')
                where = ' WHERE ' + ' AND '.join(bounds) if bounds else ''
                coverage = dict(con.execute('SELECT count(*) recordings,min(date) min_date,max(date) max_date FROM recordings r' + where, values).fetchone())
                tokens = normalized(get('q')[:1000]).split()[:30]
                search_bounds, search_values = list(bounds), list(values)
                if tokens:
                    search_bounds.append('p.id IN (SELECT rowid FROM passages_fts WHERE passages_fts MATCH ?)')
                    search_values.append(' AND '.join('"' + t + '"' for t in tokens))
                elif get('q').strip():
                    search_bounds.append('0')
                sw = ' WHERE ' + ' AND '.join(search_bounds) if search_bounds else ''
                total = con.execute('SELECT count(*) FROM passages p JOIN recordings r USING(recording_id)' + sw, search_values).fetchone()[0]
                offset = max(0, int(get('offset', '0')))
                limit = min(100, max(1, int(get('limit', '40'))))
                rows = con.execute(SELECT + sw + ' ORDER BY r.capture_datetime DESC,p.offset_seconds,p.id LIMIT ? OFFSET ?', search_values + [limit, offset]).fetchall()
                self.json({'results': [result(r) for r in rows], 'total': total, 'coverage': coverage, 'offset': offset, 'limit': limit})
                return
            match = re.fullmatch(r'/api/(recording|audio)/([a-f0-9]{24})', path)
            if match:
                recording = con.execute('SELECT * FROM recordings WHERE recording_id=?', (match[2],)).fetchone()
                if not recording:
                    self.json({'error': 'Recording not indexed'}, 404)
                    return
                if match[1] == 'recording':
                    rows = con.execute(SELECT + ' WHERE recording_id=? ORDER BY offset_seconds,p.id', (match[2],)).fetchall()
                    data = result(rows[0])
                    data['passages'] = [result(r) for r in rows]
                    self.json(data)
                else:
                    self.audio(con, recording)
                return
            self.json({'error': 'Not found'}, 404)

    def audio(self, con, recording):
        if not recording['audio_path']:
            self.json({'error': 'No indexed audio'}, 404)
            return
        path = Path(recording['audio_path'])
        root = Path(json.loads(con.execute('SELECT value FROM metadata').fetchone()[0])['audio_root'])
        if not path.resolve().is_relative_to(root) or not path.is_file():
            self.json({'error': 'Indexed audio unavailable'}, 404)
            return
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        header = self.headers.get('Range')
        if header:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
            if not match or not any(match.groups()):
                self.range_error(size)
                return
            if match[1]:
                start = int(match[1]); end = min(size - 1, int(match[2])) if match[2] else size - 1
            else:
                length = int(match[2]); start = max(0, size - length)
                if not length:
                    self.range_error(size)
                    return
            if start >= size or end < start or not size:
                self.range_error(size)
                return
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', mimetypes.guess_type(str(path))[0] or 'audio/aac')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(max(0, end - start + 1)))
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        with path.open('rb') as audio:
            audio.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                block = audio.read(min(65536, remaining))
                if not block:
                    break
                self.wfile.write(block)
                remaining -= len(block)

    def range_error(self, size):
        self.send_response(416)
        self.send_header('Content-Range', f'bytes */{size}')
        self.send_header('Content-Length', '0')
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    build = subs.add_parser('index')
    build.add_argument('--transcripts', required=True)
    build.add_argument('--audio-root', required=True)
    build.add_argument('--db', required=True)
    serve = subs.add_parser('serve')
    serve.add_argument('--db', required=True)
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=19502)
    args = parser.parse_args()
    if args.command == 'index':
        index(args)
    else:
        address = ipaddress.ip_address(args.host)
        if not (address.is_loopback or address in ipaddress.ip_network('100.64.0.0/10')):
            parser.error('Bind only a loopback or Tailscale address; public/wildcard binds are forbidden')
        with connect(args.db) as con:
            con.execute('SELECT value FROM metadata').fetchone()
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        server.db = args.db
        print(f'Archive search: http://{args.host}:{args.port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
