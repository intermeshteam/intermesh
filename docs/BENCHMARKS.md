# Measured throughput

There were no numbers before. These are produced by
[`scripts/benchmark.py`](../scripts/benchmark.py), which anyone can re-run.

```bash
python3 scripts/benchmark.py --agents 200 --requests 2000 --tasks 1000
```

## Results

Linux, 8 cores, Python 3.14, loopback, no TLS, in-memory state.

| Scenario | Agents | Throughput | p50 | p95 | p99 |
|---|---|---|---|---|---|
| Requests, no encryption | 200 | **1 467 /s** | 66 ms | 77 ms | 79 ms |
| Tasks, no encryption | 200 | **614 /s** | 159 ms | 217 ms | 250 ms |
| Requests, E2E encrypted | 50 | **427 /s** | 109 ms | 137 ms | 171 ms |
| Tasks, E2E encrypted | 50 | **326 /s** | 145 ms | 173 ms | 182 ms |

Agents connect at roughly 13–15 per second. 200 concurrent agents ran with
no errors; that is the largest figure measured, not a ceiling — the ceiling
was not reached.

Tasks are slower than requests because they go through persistence, the
guardrails and the Merkle audit log. That is the more representative number
for real use.


## Across a cluster

Five hubs of one organisation, sharing a PostgreSQL database and a signing
key, with agents spread round-robin across them. Every request and every task
below **crosses from one hub to another** — the sender and the target are
never on the same hub.

```bash
python3 scripts/cluster_benchmark.py --dsn postgresql://... \
        --hubs 5 --agents 1000 --requests 3000 --tasks 1500
```

Linux, 8 cores, Python 3.14, loopback, no TLS, shared PostgreSQL.

| Scenario | Agents | Throughput | p50 | p95 | p99 |
|---|---|---|---|---|---|
| Cross-hub requests, no encryption | 1 000 | **1 503 /s** | 95 ms | 128 ms | 142 ms |
| Cross-hub tasks, no encryption | 1 000 | **413 /s** | 355 ms | 450 ms | 509 ms |
| Cross-hub requests, E2E encrypted | 1 000 | **285 /s** | 420 ms | 702 ms | 743 ms |
| Cross-hub tasks, E2E encrypted | 1 000 | **236 /s** | 578 ms | 724 ms | 756 ms |

1 000 agents connected with no failures, 200 per hub. Not a ceiling — the
ceiling was not reached. Agents register at 13.8/s unencrypted and 12.3/s
encrypted; the difference is the RSA keypair each encrypting agent generates
before it connects (68 ms measured on this machine).

End-to-end encryption costs **5.3× on requests** and **1.75× on tasks** here.
Tasks absorb it better because their fixed cost — persistence, guardrails,
audit log — is larger to begin with.

### Losing a hub

`hub-2` killed under sustained load, taking its 200 agents with it. The
remaining four hubs were measured for 90 seconds afterwards.

| | Before | After |
|---|---|---|
| Throughput | 1 317 req/s | 1 138 req/s (−14 %) |
| p50 | 112 ms | 128 ms |
| p95 | 209 ms | 231 ms |
| **Errors** | **0** | **0** |

96 694 requests after the kill, none failed. Success stayed at 100 % in every
10-second slice for the full 90 seconds — there is no degradation window to
wait out. Throughput falls by about as much as the agents lost.

**What this does not measure:** the 200 agents that went down with the hub.
They are excluded from the traffic on purpose, so that what is measured is
the health of the survivors. Whether a lost agent re-attaches to a sibling
hub on its own is a separate question this benchmark does not answer — and
it is the number a recovery plan needs.

## Read these numbers honestly

**This is an upper bound.** One machine, loopback, no TLS. A real deployment
adds network latency, transport encryption, and agents that do not share a
CPU. Treat these as the ceiling the software imposes, not the throughput you
will see.

**Encryption roughly halves throughput.** The cost is asymmetric RSA per
message, paid on the agents rather than the hub — so it scales with the
number of agents, not with the hub.

## Limits worth knowing

**60 tasks per minute, per agent.** A guardrail, not a bug
(`max_tasks_per_minute` in the guardrail policy). The benchmark spreads
submissions across several orchestrators for this reason; measuring from a
single agent would measure the guardrail rather than the hub.

**Task cost is capped at $100** by default in the same policy. A task above
it is rejected before reaching any other check.

**One hub is one process.** The figures above are what a single hub does.
Five hubs on the same machine reach roughly the same aggregate (see the
cluster section) — but that measures eight shared cores, not the clustering
itself. Whether five hubs on five machines multiply the throughput is
untested; nothing here answers it.

## What the benchmark found

Writing it was worth more than the numbers.

**A hardcoded 15-agent cap.** The hub refused the 16th agent, before even
looking at the API key — so an enterprise key made no difference. It is now
`--max-agents`, unlimited by default.

**A deadlock in the SDK, and a silent encryption failure with it.** Replying
to a request was done inside the agent's own listen loop. Encrypting the
reply needs the caller's public key, fetched with a `WHO_IS` whose answer
only that loop can process — while it was blocked waiting for it. The
lookup timed out every time, costing 3 seconds per request, and the reply
then went out **in plaintext** because no key was available. Requests were
encrypted; responses were not.

Handling requests outside the loop fixed both: 3.01 s → 0.007 s, and
responses are now actually encrypted.

**Two measurement bugs, found by distrusting a flat number.** The first
failure test sent a fixed batch of requests and killed a hub three seconds
in. At 1 300 requests per second the batch drained in under two, so the hub
died after the traffic had finished: the run reported every request as
"before the kill" and measured nothing. Load is now driven by a duration.

The second was worse because it produced a plausible answer. Agents are
collected by `asyncio.gather`, which returns them in completion order — so
`agents[k]` is not the agent named `w{k}`. The benchmark checked that
`agents[target]` sat on a different hub, then addressed the message to
`w{target}`, a different agent entirely. During the failure test one target
in five was on the hub that had just been killed, and the run reported a
steady 20 % failure rate that looked exactly like a cluster that never
recovers.

Nothing but the flatness gave it away: 79 %, 82 %, 80 %, 79 %, 79 % — a real
degradation does not hold to the point over ninety seconds, and 1/5 is
suspiciously close to one hub in five. Addressing agents by their own
qualified name rather than by list position took the failure rate to zero.
The benchmark now refuses to run if position and hub disagree.
