"""User-authorized, single bounded Claude CLI read-only review. Never installs anything."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

from .prepare import ROOT, digest, write_json


def main():
    cli=Path(r'C:\Users\UVW-U\AppData\Roaming\npm\claude.cmd')
    prompt=ROOT/'analyzer_v3/review_prompt.md'
    run=ROOT/'output/pilots/E122/20260909_v3_p03/review'
    run.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output=run/(stamp+'_claude.json')
    errors=run/(stamp+'_stderr.txt')
    files=[ROOT/'MAIN.md',ROOT/'PLAN.md',ROOT/'CLAUDE.md']+list((ROOT/'analyzer_v3').rglob('*.py'))+list((ROOT/'analyzer_v3/static').glob('*'))
    before={str(p.relative_to(ROOT)):digest(p) for p in files}
    command=[str(cli),'-p','--model','claude-opus-5','--tools','Read,Grep,Glob',
             '--allowedTools','Read,Grep,Glob','--permission-mode','plan','--permission-prompts','none',
             '--safe-mode','--restricted','--strict-mcp-config','--disable-slash-commands','--no-chrome',
             '--no-session-persistence','--max-budget-usd','3','--output-format','json']
    # .cmd is intentionally run through Windows cmd, with prompt sent via stdin (never command interpolation).
    invocation=['cmd.exe','/d','/s','/c',subprocess.list2cmdline(command)]
    started=time.monotonic()
    with output.open('wb') as out,errors.open('wb') as err:
        process=subprocess.Popen(invocation,cwd=ROOT,stdin=subprocess.PIPE,stdout=out,stderr=err)
        print('Claude Opus 5 read-only review started. Log: '+str(output),flush=True)
        try:
            process.communicate(prompt.read_bytes(),timeout=600)
        except subprocess.TimeoutExpired:
            # Terminate only this runner's own child process tree, not other Claude sessions.
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
            process.communicate()
            print('Review timed out after 10 minutes; no success claimed.',flush=True)
    after={str(p.relative_to(ROOT)):digest(p) for p in files}
    write_json(run/(stamp+'_audit.json'),dict(command=command,exit_code=process.returncode,
                 duration_seconds=round(time.monotonic()-started,2),before_sha256=before,after_sha256=after,
                 files_changed=[p for p in before if before[p]!=after[p]],stdout_file=output.name,stderr_file=errors.name))
    print('Claude exit: '+str(process.returncode),flush=True)
    if errors.stat().st_size:
        print(errors.read_text(encoding='utf-8',errors='replace')[:3000],flush=True)
    if process.returncode:
        print(output.read_text(encoding='utf-8',errors='replace')[:3000],flush=True)


if __name__=='__main__':
    main()
