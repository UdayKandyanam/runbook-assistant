# Rolling back a bad deployment

## When to roll back

Roll back when the new version is causing user facing errors and you do not
have a fix you trust within minutes. Error rate up since the deploy,
latency doubled, crash loops in the new pods: those are rollback signals.
Debugging a broken release in production while users hit errors is rarely
the right call. You can debug the same build in staging afterwards with
nobody watching the clock.

Do not roll back blindly when the release included a database migration.
Check the After a rollback section first.

## Roll back with kubectl

1. Find the previous revision:
   `kubectl rollout history deployment/<name>`
2. Roll back to it:
   `kubectl rollout undo deployment/<name>`
   or to a specific revision:
   `kubectl rollout undo deployment/<name> --to-revision=<n>`
3. Watch it land:
   `kubectl rollout status deployment/<name>`

For storefront-web and checkout-api, which are managed by Argo CD, prefer
syncing the application back to the previous commit in git instead of
running rollout undo by hand. A manual undo and the git state will fight
each other on the next sync. In Argo CD, roll back by reverting the release
commit, or use the History and Rollback view to sync to the earlier
revision, then let the revert commit follow.

## Verify the rollback worked

Confirm the old image is running: `kubectl describe deployment/<name>` and
check the image tag matches the previous release. Then watch the error rate
and latency for the service return to their pre-deploy levels. A rollback
that leaves error rates high means the deploy was not the cause, or not the
only cause, and you should say so in the incident channel rather than
rolling back further on a guess.

## After a rollback

Write down what the symptom was, which revision you rolled back to, and
when error rates recovered. Link the release that introduced the problem so
the team can reproduce it in staging. If the release carried a database
migration, confirm the old code runs correctly against the migrated schema;
most of our migrations are backward compatible by convention, and the ones
that are not must say so in the release notes. File the follow up before
closing the incident, while the details are still in front of you.
