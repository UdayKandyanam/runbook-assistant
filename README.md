# Runbook Assistant

A small tool that answers platform questions from a folder of markdown
runbooks and shows where each answer came from.

## Why I built it

Platform teams answer the same questions every week. How do I check why a
pod keeps restarting. What do I do when the certificate expires. When do I
roll back.

The answers already exist. They sit in runbooks scattered across wikis,
repos, and shared drives, and finding the right one at 3 a.m. is the slow
part. I wanted something that reads the runbooks I already have, answers in
their words, and points at the exact section it used. If the runbooks do
not cover a question, it should say that plainly instead of making
something up.

## How it works

Each runbook is split into sections at its markdown headings. The sections
are indexed with BM25, a ranking function I implemented in
`runbook_assistant/index.py` rather than pulling in a search library. A
question is scored against every section, and the answer is built from the
best matches.

Answers are extractive. The tool quotes the sections it found and names the
source file and heading for each one, so you can open the runbook and read
the rest in context. When the best score is too low, or the trailing
matches are far weaker than the best one, the tool refuses: the runbooks do
not cover that.

## Quick start

You need Python 3.10 or newer. The core has no dependencies.

```bash
git clone https://github.com/udaykandyanam/runbook-assistant.git
cd runbook-assistant
python -m runbook_assistant list
python -m runbook_assistant ask "A pod is in CrashLoopBackOff and keeps restarting. What should I check first?"
```

Point it at your own runbooks with `--runbooks`:

```bash
python -m runbook_assistant ask "How do I roll back a bad deployment?" --runbooks /path/to/runbooks
```

Add `--format json` when you want the answer as structured data: question,
whether it was answered, and a sources list with file, heading, score, and
text for each excerpt.

To run the tests:

```bash
pip install -e ".[dev]"
pytest
```

## Sample questions

Real output from the runbooks in this repo.

### CrashLoopBackOff

```
$ python -m runbook_assistant ask "A pod is in CrashLoopBackOff and keeps restarting. What should I check first?"

From crashloopbackoff.md > Symptoms:
A pod sits in CrashLoopBackOff and the restart count keeps climbing. The
deployment behind it never becomes ready, so traffic keeps going to the old
pods (or nowhere, on a first deploy). `kubectl get pods` shows the pod age
growing while the restart count grows with it.

CrashLoopBackOff is a symptom, not a cause. The container starts, exits, and
Kubernetes waits longer between each retry. Your job is to find out why the
container exits.

From crashloopbackoff.md > First checks:
1. Look at the logs from the previous run, not the current one. The current
   container may not have produced anything yet:
   `kubectl logs <pod> --previous`
2. Check the exit code and the last state:
   `kubectl describe pod <pod>` and read the "Last State" block.
3. Exit code 1 usually means the app itself failed. Exit code 137 means the
   kernel killed it, which points at memory. Exit code 143 is a SIGTERM, so
   check whether something is deleting the pod.

For checkout-api, the usual culprit after a deploy is a config change: a
missing environment variable or a ConfigMap key that was renamed.
```

### Expired certificate

````
$ python -m runbook_assistant ask "Clients are failing TLS handshakes with x509 certificate expired errors. How do I check the expiry date?"

From expired-certificates.md > Symptoms:
Clients fail TLS handshakes with errors like "x509: certificate has expired
or is not yet valid". Browsers show a hard warning for web endpoints. Other
services calling the endpoint over HTTPS start logging connection failures
at the exact hour the certificate expired, which is the giveaway: a clean
cliff in the error graph, not a gradual rise.

Internal endpoints fail quieter. Watch for the calling service's error logs
rather than user reports.

From expired-certificates.md > Check the expiry date:
Ask the endpoint directly what certificate it is serving:

```
openssl s_client -connect storefront-web.example.internal:443 -servername storefront-web.example.internal </dev/null 2>/dev/null | openssl x509 -noout -dates -subject -issuer
```

The `notAfter` line is the expiry. If the date is in the past, you have your
cause. If the date looks fine, the problem is elsewhere: a stale secret the
ingress has not reloaded, or a client trusting the wrong CA.

For certificates managed in the cluster, check the Certificate resource:
`kubectl get certificate -A` shows READY and expiry per certificate, and
`kubectl describe certificate <name> -n <namespace>` shows the last issuance
events.
````

### A question the runbooks do not cover

```
$ python -m runbook_assistant ask "How do I bake a sourdough loaf with a crisp crust?"

The runbooks I have do not cover that. I would rather say so than guess: check with the team that owns the service, and consider adding a runbook for it afterwards.
```

## Runbook format

Any folder of markdown files works. The loader reads every `.md` file in
the folder and splits it at ATX headings (`#`, `##`, and so on). Each
heading becomes one searchable section, and the file name plus heading is
the citation. The first `#` heading in a file is treated as the runbook
title. Plain paragraphs, lists, and code blocks inside a section all stay
part of that section.

The bundled set in `runbooks/` covers pod CrashLoopBackOff triage, node
disk pressure, expired certificates, rolling back a bad deployment, and
database connection saturation. Swap in your own folder and the assistant
answers from yours instead.

## Optional: HTTP API

There is a thin FastAPI adapter in `app.py` if you would rather call this
over HTTP. The core package does not need it.

```bash
pip install -e ".[api]"
uvicorn app:app
curl localhost:8000/health
curl -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "How do I roll back a bad deployment?"}'
```

Set `RUNBOOKS_DIR` to serve a different folder of runbooks.

## Design choices

**Standard library only for the core.** Runbooks live on jump hosts and
incident laptops. A tool that needs one `pip install` of a framework stack
is a tool that is missing when you need it. BM25 is about eighty lines, so
I wrote it and tested the ranking order directly.

**Extractive answers instead of free-form generation.** An incident is the
wrong place for a paraphrase that might have drifted from the procedure.
Quoting the section keeps the commands exact, and the citation lets the
reader check the source in seconds. The tradeoff is real: the answer reads
like the runbook, because it is the runbook.

**A refusal path.** The score threshold and the relative cutoff for weak
trailing matches exist so the tool can say "not covered" instead of
returning the least wrong section. A wrong answer delivered confidently
costs more than no answer.

## Limits

BM25 matches words, not meaning. A question phrased with none of the
runbook's vocabulary will score low even when a relevant section exists,
and the tool will refuse. It also cannot combine steps from two procedures
into one plan; it returns the sections, and stitching them together is
still your job. Section quality is runbook quality. A vague runbook gives
a vague answer with a very precise citation.

## Roadmap

1. Synonym and abbreviation handling for common ops terms, so "OOM" finds
   the section that talks about memory limits.
2. A `serve` command that watches the runbooks folder and re-indexes on
   change, for teams that edit runbooks during an incident.
3. Per-team runbook packs, so a platform team and an app team can keep
   separate folders and query them together with the source still clear.

## License

MIT, see LICENSE.
