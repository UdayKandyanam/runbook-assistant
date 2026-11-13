# Database connection saturation

## Symptoms

The application starts failing with "too many clients already" from
PostgreSQL, or its own pool errors: "connection pool exhausted", timeouts
waiting for a free connection. Requests queue up and latency climbs across
every endpoint that touches the database at once, not just one feature.

Connection saturation usually arrives right after something scaled: more
replicas, a new service pointed at the same database, or a deploy that
changed pool settings.

## Check the current state

Count connections by database and state:

```sql
SELECT datname, state, count(*)
FROM pg_stat_activity
GROUP BY datname, state
ORDER BY count(*) DESC;
```

Compare the total against `SHOW max_connections;`. Then find which
application user and host the connections belong to:

```sql
SELECT usename, client_addr, count(*)
FROM pg_stat_activity
GROUP BY usename, client_addr
ORDER BY count(*) DESC;
```

A wall of connections in state "idle" from one service means it is holding
connections without using them: a leak, or a pool sized far beyond what the
service needs.

## Find the source

**Scaled replicas, same pool size.** Each pod opens its own pool. Twenty
replicas with a pool of 30 is 600 potential connections against a
max_connections of 500. The deploy that raised the replica count for
billing-worker is the usual trigger here.

**Leaked connections.** Code paths that open a connection and return early
on error without closing it bleed connections slowly. The count grows over
hours and resets when the pods restart. That sawtooth pattern in the graph
is the tell.

**Long transactions.** A few connections stuck "idle in transaction" for
minutes hold locks and block others. The count may look fine while the
queue grows. Check `pg_stat_activity` ordered by transaction start time.

## Mitigate

Restarting the offending service clears its connections and buys time, but
say in the incident channel that it is a mitigation, not a fix. Lower the
replica count or the pool size on the service that overshot. Terminate
genuinely stuck sessions with `pg_terminate_backend(pid)` after confirming
they belong to the affected service. Resist raising max_connections as the
first move: each connection costs memory, and a higher ceiling can turn a
connection problem into a database memory problem.

## Longer term

Put a pooler such as PgBouncer in front of services with many replicas, in
transaction pooling mode. Set the pool size from the replica math, and put
that math in the service's deployment review checklist. Alert at 70 percent
of max_connections sustained for ten minutes; saturation pages are always
about a deploy that happened an hour earlier, and the alert should fire
before users notice.
