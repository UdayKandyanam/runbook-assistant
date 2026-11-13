# Expired certificates

## Symptoms

Clients fail TLS handshakes with errors like "x509: certificate has expired
or is not yet valid". Browsers show a hard warning for web endpoints. Other
services calling the endpoint over HTTPS start logging connection failures
at the exact hour the certificate expired, which is the giveaway: a clean
cliff in the error graph, not a gradual rise.

Internal endpoints fail quieter. Watch for the calling service's error logs
rather than user reports.

## Check the expiry date

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

## Renewal steps

Most of our certificates are issued by cert-manager and renew on their own.
An expired one usually means renewal has been failing silently.

1. Read the Certificate and its Order: the events usually name the problem,
   a broken DNS challenge, a rate limit from the issuer, or a webhook that
   is down.
2. Fix that cause first. Deleting the Certificate to force a retry before
   fixing the cause just repeats the failure.
3. To force a renewal attempt once the cause is fixed:
   `kubectl cert-manager renew <name> -n <namespace>` (or delete the Secret
   and let cert-manager reissue, if the plugin is not installed).
4. Confirm the new Secret landed and the ingress or service picked it up.
   Some workloads hold the old certificate until restart; roll the
   deployment if the dates still show the old expiry:
   `kubectl rollout restart deployment/<name>`.

## Verify

Repeat the openssl check against the endpoint and confirm `notAfter` is in
the future and the issuer matches what you expect. Then check the calling
service's error rate; handshake errors should stop within a minute or two.

## Prevention

Alert on certificate expiry 30 days out, per endpoint, and route it to the
team that owns the endpoint. Renewal failures should page when 14 days
remain, not when users start reporting. Keep a list of certificates that
are issued manually; those are the ones that expire at 2 a.m. during a
holiday, because no automation is watching them.
