# Node disk pressure

## Symptoms

The node reports a DiskPressure condition and Kubernetes starts evicting
pods. New pods may fail to schedule or fail at image pull. `kubectl describe
node <node>` shows "DiskPressure=True" and the events log fills with
eviction messages.

Disk pressure is a node problem, not an app problem. Evicted pods are the
symptom; moving them around without freeing space just spreads it.

## Find what is filling the disk

Start with the filesystem summary: `df -h` on the node, then look at the
usual suspects.

**Container logs.** A chatty container writing to stdout for weeks will fill
the log directory under /var/log/pods. Check which pod is writing:
`du -sh /var/log/pods/* | sort -h | tail`.

**Image cache.** Nodes accumulate old image layers in the container runtime
storage (/var/lib/containerd on most of our nodes). Short lived CI nodes
collect these fast.

**emptyDir volumes.** A pod writing temp files into an emptyDir counts
against the node's disk, not its own quota, unless size limits are set.
Look for pods with large emptyDir usage in the node summary:
`kubectl get --raw /api/v1/nodes/<node>/proxy/stats/summary`.

**System logs and core dumps.** journald without a size cap and a pile of
core dumps in /var/crash are less common but worth the ten seconds it takes
to check.

## Cleanup steps

1. Cordon the node so nothing new lands on it while you work:
   `kubectl cordon <node>`.
2. Reclaim dead containers and unused images through the runtime:
   `crictl rmi --prune` removes images no container references.
3. If one pod's logs are the problem, fix the log volume at the source
   (lower the verbosity, fix the retry loop that is logging in a tight
   circle). Truncating the file buys minutes, not a fix.
4. When usage drops below the eviction threshold, uncordon the node and
   watch the condition clear: `kubectl uncordon <node>`.

Avoid deleting files out from under the runtime by hand in /var/lib. Let
the runtime account for what it owns.

## Prevention

Set log rotation on the kubelet (containerLogMaxSize and
containerLogMaxFiles) so one container cannot fill a node. Put size limits
on emptyDir volumes for batch style workloads like billing-worker, which
writes intermediate files. Alert at 75 percent disk usage on the node, not
at the eviction threshold; by then pods are already moving.
