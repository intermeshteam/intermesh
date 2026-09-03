# Capacity: what one hub sustains, and what it does when it cannot

Written because a hub that accepts everything is not the same as a hub that
can do everything. Before this, a saturated hub queued silently, latency
climbed, and clients died on a WebSocket ping timeout — with no signal
anywhere saying the hub was the problem.

## Measured ceiling

| | |
|---|---|
| Sustained tasks on one hub | **~11 /s** |
| Healthy zone, end-to-end encrypted | **≤ 8 /s**, p50 under a second |
| Independent of fleet size | 78 agents and 234 agents hit the same ceiling |

The last row is the useful one: **the hub is the bound, not the number of
agents.** Adding agents does not add task throughput. Adding hubs does —
see [the cluster benchmark](BENCHMARKS.md#across-a-cluster).

Requests (`ask`) are far cheaper than tasks: 1 500/s against 11/s. A task
goes through persistence, guardrails, escrow and the Merkle audit log; a
request does not. If a workload can be expressed as requests, it will scale
roughly a hundred times further.

## What the hub does when it is over the line

```bash
python3 server/hub.py --max-tasks-per-sec 8
```

A submission past the budget is **refused**, not queued. The sender gets an
error whose content is machine-readable:

```json
{
  "code": "HUB_SATURATED",
  "reason": "rate_limited",
  "retry_after_ms": 121,
  "queue_depth": 8,
  "in_flight": 8,
  "hub_tasks_per_sec_limit": 8,
  "task_id": "…"
}
```

`reason` is one of `rate_limited`, `in_flight_limit`, `task_queue_full`.
`retry_after_ms` is how long until a token is actually available — retrying
sooner makes the congestion you just hit worse.

### Settings

| Variable | Flag | Default | What it bounds |
|---|---|---|---|
| `INTERMESH_MAX_TASKS_PER_SEC` | `--max-tasks-per-sec` | 10 | Submissions per second, hub-wide |
| `INTERMESH_MAX_TASKS_IN_FLIGHT` | `--max-tasks-in-flight` | 200 | Accepted and not yet finished |
| `INTERMESH_MAX_TASK_QUEUE_DEPTH` | `--max-task-queue-depth` | 100 | Accepted but not yet picked up |
| `INTERMESH_BACKPRESSURE_ENABLED` | `--no-backpressure` | on | Kill switch |

The defaults come from the measurement above, not from intuition. A
deployment that measures something else on its own hardware should raise
them — which is why they are settings rather than constants.

### Reading the load

`hub.info` carries a `load` block, so saturation is visible before clients
start timing out:

```json
"load": {
  "in_flight": 12, "queue_depth": 4,
  "accepted_total": 100, "rejected_total": 440,
  "rejected_by_reason": {"rate_limited": 304, "task_queue_full": 136},
  "saturation": {"in_flight_pct": 6, "queue_depth_pct": 4}
}
```

`saturation` is the pair to watch. `rejected_by_reason` tells you *which*
wall you are hitting, and the three walls call for different answers.

## Anti-patterns

**Relying on the per-agent quota to protect the hub.** `max_tasks_per_minute`
(60) stops one agent running away. It does nothing about a hundred
well-behaved agents at a third of their quota each — that is 200/s, twenty
times what a hub sustains. The two limits are not substitutes.

**Retrying immediately on refusal.** `retry_after_ms` exists because a tight
retry loop converts a brief overload into a sustained one. Honour it.

**Submitting to an agent that is offline.** The task is accepted and sits in
the queue. Enough of those and `queue_depth` reaches its ceiling, at which
point the hub refuses *everything* — including work for agents that are
perfectly available. Check with `discover` first, or expect
`task_queue_full`.

**Using tasks where a request would do.** A hundredfold difference in
throughput is not a rounding error.

**Treating the ceiling as a per-agent figure.** It is not. Eleven per second
is the hub, whether five agents or five hundred are connected.

## What backpressure does not protect

**The message loop.** The gate runs when a submission is dequeued and
parsed. A client flooding faster than the hub reads its socket still backs
up in the transport, where this has no reach. Rate-limit at the edge — a
reverse proxy — if untrusted clients can reach the hub.

**Work already accepted.** Nothing is cancelled retroactively. Lowering the
budget slows admissions; it does not shed what is already in flight.

**Other hubs.** Each hub has its own budget. A cluster of five sustains
roughly five times one — but a client hammering a single hub is refused by
that hub alone, and re-attaching elsewhere is the client's decision.

## Two things found while building this

**Every rejection was written to the Merkle audit chain.** That made
refusing expensive exactly when the hub is overloaded — the opposite of
what a refusal is for. Entry into saturation is now logged once per
ten-second window; the exact count lives in the counters, where it costs
nothing.

**One rejection failed every task the sender had in flight.** The SDK
failed all pending tasks on any `error` message. That was survivable while
errors were rare; with backpressure they are routine, and a single refusal
would have destroyed unrelated work. A refusal now names its task, and only
that task fails.

## Re-running the measurement

```bash
python3 scripts/benchmark.py --agents 200 --tasks 1000
python3 scripts/cluster_benchmark.py --dsn postgresql://... --hubs 5 --agents 1000
```

Do not take the numbers here on faith on hardware that is not this one.
They were measured on 8 cores, loopback, no TLS — see
[BENCHMARKS.md](BENCHMARKS.md) for what that bounds.
