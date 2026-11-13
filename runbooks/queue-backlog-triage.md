# Queue backlog triage

## Symptoms

Messages pile up in the queue and the consumers, though running, fall
further behind. For billing-worker the sign is invoices processed late and
the reporting dashboard lagging the current time by a growing margin.

The number that matters is the age of the oldest message, not the raw
depth. A deep queue that is draining is fine. A queue whose oldest message
keeps getting older is a backlog, even at a modest depth, because it means
work is arriving faster than it is leaving and the gap compounds.

## Check consumer lag

Start with the queue itself. Note the depth, the oldest message age, and
two rates: messages in per minute and messages out per minute. If the out
rate sits below the in rate for more than a few minutes, the backlog grows
until something changes.

For RabbitMQ, `rabbitmqctl list_queues name messages messages_ready
consumers` shows depth and consumer count per queue. For Kafka, read the
LAG column:

`kafka-consumer-groups.sh --bootstrap-server <broker> --describe --group billing-workers`

Lag is per partition, so add it up and look at the spread. One partition
with most of the lag points at a hot key or a single stuck consumer rather
than a general capacity problem.

Then check the consumers before concluding anything about capacity.
Confirm the pods are up and not crash looping, and look at what a consumer
does with one message: if each message waits on a slow downstream call,
the consumers are blocked, not undersized. The database connection
saturation runbook covers the common case, where the thing the consumers
wait on is the database.

## Scale the consumers

If the consumers are healthy and simply outnumbered, scale them:

`kubectl scale deployment/billing-worker --replicas=6`

Two limits apply. On Kafka, consumers beyond the partition count have
nothing to read and sit idle, so raise partitions or accept the ceiling.
On RabbitMQ, check the prefetch count before scaling far: a high prefetch
lets one consumer hoard messages the others could be working on.

Scale in steps and watch the downstream as you go. Doubling consumers
roughly doubles the load they place on the database and on any API they
call. If the downstream is the real bottleneck, more consumers make the
backlog drain slower, not faster, and you will see the out rate fall as
you add replicas. That is the signal to stop scaling and fix the
downstream instead.

## Poison messages

A poison message is one that always fails: a malformed payload, a record
that no longer exists, a value the handler cannot parse. The consumer
takes it, fails, and takes it again, so one bad message can hold a whole
partition or queue behind it.

The signs are a redelivery count climbing on a single message, the same
error with the same message ID repeating in the logs, and lag growing
while the rest of the traffic processes normally. When you find it, move
the message to the dead letter queue and keep the payload. Do not delete
it and move on: the payload is the evidence the owning team needs to fix
the producer or the handler. File the ticket with the message ID, the
payload, and the error, then watch the dead letter queue depth for the
next hour in case the poison came in a batch.

## Verify and follow up

The backlog is clearing when the oldest message age falls steadily, not
just when the depth dips. Estimate the drain time so you can say when it
will be gone: backlog divided by the out rate minus the in rate. If that
estimate runs past the point where the delay starts hurting, say so in
the incident channel early, while there is still time to choose a
different fix.

Afterwards, check the alerting. An alert on oldest message age catches
the next backlog while it is still small. An alert on depth alone fires
on every healthy traffic spike and teaches people to ignore it, which is
worse than no alert.
