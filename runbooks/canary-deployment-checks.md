# Canary deployment checks

## Before the canary starts

Confirm the basics before any traffic moves: what percentage the canary
starts at, how long each step lasts, and who is allowed to stop it. For
checkout-api and storefront-web the canary runs through Argo Rollouts, and
`kubectl argo rollouts get rollout <name> -n <namespace>` shows the current
step and the replica counts for the stable and canary versions side by
side.

Take a baseline first. Record the error rate, the p95 latency, and the
checkout completion rate for the stable version over the last hour. During
the canary you compare against those numbers, not against a feeling that
things look fine.

## What to watch during the canary

Watch the canary pods and the stable pods as two separate services,
because in the dashboards they are two separate sets of numbers:

- Error rate on the canary version against the error rate on the stable
  version over the same minutes. A rise that only exists on the canary is
  the release. A rise on both is something else.
- p95 and p99 latency per version. Latency regressions often show up
  before errors do.
- Pod restarts and probe failures on the canary pods. A canary pod in
  CrashLoopBackOff serves no traffic and skews every other number, so
  check the pods themselves before trusting the graphs.
- One business signal for the service. For checkout-api that is the
  checkout completion rate. Technical graphs can look fine while the
  thing users actually do quietly gets worse.

Give each step at least ten minutes of real traffic. A canary checked
during a quiet five minutes has told you almost nothing.

## Signals that mean stop

Stop the canary and roll back when any of these holds:

- The canary error rate is more than double the stable error rate for five
  minutes, or climbing step over step.
- A new error type appears on the canary that the stable version never
  produces.
- p95 latency on the canary is up by half or more against the baseline.
- Canary pods are crash looping or failing readiness probes.
- The business signal drops outside its normal range for the time of day.

One person makes the stop call, and it should be the person watching the
canary. Stopping early costs a redeploy. Stopping late costs users.

## How to stop and roll back

Abort the rollout first so the weight does not keep rising:

`kubectl argo rollouts abort rollout/<name> -n <namespace>`

Then send traffic back to the stable version and take the canary version
down:

`kubectl argo rollouts undo rollout/<name> -n <namespace>`

For services deployed as plain Deployments with the canary weight set on
the ingress, set the weight back to zero, scale the new version to zero
replicas, and confirm in the ingress status that all traffic is on the
stable version again. Watch the error rate return to the baseline before
calling it done. The deployment rollback runbook covers the general
rollback steps and the database migration check, which applies here too:
if the canary carried a migration, confirm the stable code runs correctly
against the migrated schema before you finish.

## After the canary

Write down the highest weight the canary reached, the signal that decided
it, and who made the call. If you aborted, link the failing graph in the
release ticket and name the build that should not be promoted again. Do
not restart the same build as a fresh canary and hope for a different
result. If the canary promoted cleanly, note how long each step took, so
the next release has a realistic schedule to plan against.
