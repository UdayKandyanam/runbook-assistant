# Pod CrashLoopBackOff triage

## Symptoms

A pod sits in CrashLoopBackOff and the restart count keeps climbing. The
deployment behind it never becomes ready, so traffic keeps going to the old
pods (or nowhere, on a first deploy). `kubectl get pods` shows the pod age
growing while the restart count grows with it.

CrashLoopBackOff is a symptom, not a cause. The container starts, exits, and
Kubernetes waits longer between each retry. Your job is to find out why the
container exits.

## First checks

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

## Common causes

**Bad configuration.** The app exits immediately with a clear error in the
previous logs, something like "missing required env var". Compare the
ConfigMap and Secret keys against what the new image expects.

**Failing dependency.** The app starts, tries to reach its database or a
downstream service, times out, and exits. Logs show connection errors a few
seconds after start. Check the dependency before touching the deployment.

**Out of memory.** Exit code 137, and `kubectl top pod` or the metrics from
before the crash show memory at the limit. Raising the limit buys time;
finding the leak is the actual fix.

**Failing probes.** A liveness probe that is too aggressive can kill a slow
starting container and look like a crash loop. If the logs show the app
starting fine and then receiving a SIGTERM, look at the probe settings
before anything else.

## Fix and verify

Fix the cause at the source: correct the ConfigMap, restore the dependency,
or roll back the deployment if the new build is broken (see the rollback
runbook). Do not paper over a crash loop by raising restart tolerances;
there is no such knob and the pod would still be down.

Verify with `kubectl rollout status deployment/<name>` and watch one full
probe cycle. A pod that stays up for two minutes can still be in a slow
loop, so give it five.

## When to escalate

Escalate to the service owner when the crash follows a code change and the
logs point inside the application, or when the failing dependency belongs
to another team. Bring the exit code, the previous logs, and what changed
in the last deploy. That saves the first ten minutes of the call.
