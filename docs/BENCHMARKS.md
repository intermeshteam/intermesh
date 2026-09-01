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

**One hub is one process.** Throughput here is what a single hub does.
Running two against the same PostgreSQL database does not double it — see
[the remote-hub guide](REMOTE-HUB.md#where-the-state-lives) for why.

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
