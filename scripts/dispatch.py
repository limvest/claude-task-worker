#!/usr/bin/env python3
"""Run isolated Claude packets; return compact receipts, never full transcripts."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import selectors
import subprocess
import tempfile
import time

PROMPT = '''Read TASK.md and perform exactly its one bounded task using only this packet. Do not reconstruct or request the wider project or prior conversation. The packet's stated purpose is authoritative; do not invent missing domain behavior. Preserve public contracts and existing tests. Work only in this directory; do not access parent projects, credentials, settings, networks or production. Run an allowed acceptance command only when TASK.md requests verification and its entrypoint exists or the task explicitly asks you to create it. Allowed commands are permissions, not mandatory steps. For documentary or analysis-only tasks with no harness, run no tests. For implementation, prefer one focused check and do not repeat a full inherited suite unless the task requires it. Do not add shell suffixes or pipelines. Implement a real requested improvement, or record that no defect is evidenced. Write changed files and RESULT.md (problem, changes, exact tests actually run, remaining blockers). Keep final response short. If permissions or safety prevent a step, report it; do not bypass them. Do not claim full-product completion from isolated tests.'''
EXCLUDED = {'.git', '.claude', '.codex', '__pycache__', 'node_modules', '.venv', '.env'}

def dump(path, data):
    tmp = path.with_name(path.name + '.pending')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)

def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Symlink not permitted in packet: ' + str(p))
        if p.is_file():
            data = p.read_bytes()
            result[p.relative_to(root).as_posix()] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    return result

def copy_packet(src, dst):
    if not (src / 'TASK.md').is_file():
        raise ValueError('Packet requires TASK.md: ' + str(src))
    if src.is_symlink():
        raise ValueError('Packet directory must not be a symlink')
    # Inspect even excluded entries so symbolic links never silently escape scope.
    inventory(src)
    shutil.copytree(src, dst, ignore=lambda _, names: [n for n in names if n in EXCLUDED or n.endswith('.pyc')])

def stop(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)

def observed_models(event):
    """Only answering-model fields, never configured model or model-written text."""
    models = set()
    if event.get('type') == 'assistant':
        model = event.get('message', {}).get('model')
        if isinstance(model, str) and model:
            models.add(model)
    if event.get('type') == 'stream_event':
        inner = event.get('event', {})
        if inner.get('type') == 'message_start':
            model = inner.get('message', {}).get('model')
            if isinstance(model, str) and model:
                models.add(model)
    if event.get('type') == 'result':
        models.update(k for k in (event.get('modelUsage') or {}) if isinstance(k, str) and k)
    return models


def monitor(proc, prompt, timeout, output, receipt, rec):
    deadline = time.monotonic() + timeout
    proc.stdin.write(prompt.encode())
    proc.stdin.close()
    buffer = b''
    result = None
    with selectors.DefaultSelector() as selector:
        selector.register(proc.stdout, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            ready = selector.select(min(remaining, 0.25))
            if not ready:
                continue
            chunk = os.read(proc.stdout.fileno(), 65536)
            buffer += chunk
            lines = buffer.split(b'\n')
            buffer = lines.pop()
            if not chunk and buffer:
                lines.append(buffer)
                buffer = b''
            for line in lines:
                output.write(line.decode('utf-8', errors='replace') + '\n')
                output.flush()
                try:
                    event = json.loads(line)
                except (ValueError, UnicodeError):
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get('type') == 'result':
                    result = event
                    rec['safety_stops'] = event.get('safety_stops')
                models = observed_models(event)
                if models:
                    rec['actual_models'] = sorted(set(rec['actual_models']) | models)
                    mismatch = sorted(models - {rec['requested_model']})
                    if mismatch:
                        rec.update(state='model_mismatch', model_mismatch=mismatch,
                                   model_detection={'event_type': event.get('type'), 'at': time.time()},
                                   output_accepted=False)
                        dump(receipt, rec)
                        stop(proc)
                        return result
                    dump(receipt, rec)
            if not chunk:
                proc.wait(timeout=max(0.001, deadline - time.monotonic()))
                return result


def compact(record):
    return {k: record[k] for k in ('task', 'state', 'exit_code', 'seconds', 'changed', 'deleted', 'permission_denials', 'is_error', 'requested_model', 'requested_effort', 'actual_models', 'safety_stops', 'packet_files', 'packet_bytes', 'output_accepted', 'model_mismatch', 'model_detection') if k in record}

def run_one(packet, batch, args):
    name = packet.name
    folder = batch / name
    rec = {'task': name, 'state': 'preparing', 'packet': str(packet), 'workspace': str(folder),
           'requested_model': args.model, 'requested_effort': args.effort}
    receipt = batch / (name + '.receipt.json')
    started = time.time()
    try:
        copy_packet(packet, folder)
        before = inventory(folder)
        rec.update(packet_files=len(before), packet_bytes=sum(v['bytes'] for v in before.values()),
                   largest_inputs=sorted([{'path': p, 'bytes': v['bytes']} for p, v in before.items()],
                                         key=lambda x: x['bytes'], reverse=True)[:5])
        cmd = [args.claude_bin, '-p', '--output-format', 'stream-json', '--verbose', '--include-partial-messages', '--no-session-persistence',
               '--restricted', '--tools', 'Read,Edit,Write,Bash', '--allowedTools',
               'Read', 'Edit', 'Write', *['Bash(' + c + ')' for c in args.allow_command],
               '--permission-mode', 'acceptEdits', '--strict-mcp-config', '--effort', args.effort]
        if args.model:
            cmd += ['--model', args.model]
        with (batch / (name + '.claude.jsonl')).open('w') as output, (batch / (name + '.stderr.txt')).open('w') as errors:
            proc = subprocess.Popen(cmd, cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, start_new_session=True)
            rec.update(state='running', pid=proc.pid, started=started, before=before, actual_models=[], output_accepted=False)
            dump(receipt, rec)
            try:
                data = monitor(proc, PROMPT + '\nAllowed test commands: ' + json.dumps(args.allow_command), args.timeout, output, receipt, rec)
                rec['exit_code'] = proc.returncode
                if rec['state'] == 'running':
                    rec['state'] = 'completed' if proc.returncode == 0 else 'failed'
            except subprocess.TimeoutExpired:
                stop(proc)
                rec.update(state='timed_out', exit_code=proc.returncode)
                data = None
            except BaseException:
                stop(proc)
                raise
        after = inventory(folder)
        rec.update(after=after, changed=[p for p in after if before.get(p) != after[p]], deleted=[p for p in before if p not in after])
        if data is not None:
            dump(batch / (name + '.claude.json'), data)
            rec.update(is_error=data.get('is_error'), permission_denials=len(data.get('permission_denials') or []),
                       safety_stops=data.get('safety_stops'), num_turns=data.get('num_turns'), usage=data.get('usage'),
                       total_cost_usd_reported=data.get('total_cost_usd'))
            if data.get('is_error') and rec['state'] == 'completed':
                rec['state'] = 'failed'
        elif rec['state'] == 'completed':
            rec.update(state='failed', output_parse_error=True)
        if rec['state'] == 'completed' and not rec['actual_models']:
            rec['state'] = 'model_unverified'
        rec['output_accepted'] = rec['state'] == 'completed'
    except Exception as exc:
        rec.update(state='failed', error=type(exc).__name__ + ': ' + str(exc))
    rec['seconds'] = round(time.time() - started, 1)
    dump(receipt, rec)
    print(json.dumps(compact(rec), ensure_ascii=False), flush=True)
    return rec

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    run = sub.add_parser('run')
    run.add_argument('--packet', action='append', type=Path, required=True)
    run.add_argument('--jobs', type=int, default=3)
    run.add_argument('--effort', choices=['low', 'medium', 'high', 'xhigh', 'max'], default='medium')
    run.add_argument('--model', default='claude-opus-5-5')
    run.add_argument('--timeout', type=float, default=1800)
    run.add_argument('--allow-command', action='append', default=None)
    run.add_argument('--claude-bin', default='claude')
    status = sub.add_parser('status')
    status.add_argument('--batch', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'status':
        for p in sorted(args.batch.glob('*.receipt.json')):
            rec = json.loads(p.read_text())
            view = compact(rec)
            if rec['state'] == 'running':
                try:
                    os.kill(rec['pid'], 0)
                    view['process_present'] = True
                except ProcessLookupError:
                    view['process_present'] = False
                except PermissionError:
                    view['process_present'] = 'unknown_permission'
            print(json.dumps(view, ensure_ascii=False))
        return
    if args.jobs < 1 or args.timeout <= 0:
        parser.error('jobs and timeout must be positive')
    if not args.model or not args.model.startswith('claude-'):
        parser.error('--model requires an explicit canonical Claude model ID')
    packets = [p.absolute() for p in args.packet]
    if len({p.name for p in packets}) != len(packets):
        parser.error('Packet basenames must be unique')
    args.allow_command = args.allow_command or ['python3 -I -S -B run_tests.py']
    batch = Path(tempfile.mkdtemp(prefix='claude-task-worker-'))
    print(json.dumps({'batch': str(batch), 'tasks': [p.name for p in packets]}), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        records = list(pool.map(lambda p: run_one(p, batch, args), packets))
    raise SystemExit(0 if all(r['state'] == 'completed' for r in records) else 1)

if __name__ == '__main__':
    main()
