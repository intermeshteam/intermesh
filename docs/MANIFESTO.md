# Why multi-agent systems fail in production

*(and why we built RFC-001)*

---

Every team building with AI agents hits the same wall, usually around the
third agent.

The first agent is easy. You pick a framework, write a system prompt, wire
up a tool or two, and it works. The second agent is still manageable — you
hardcode its address, maybe pass messages through a queue you already had
lying around. Then someone asks for a third agent, one that needs to talk
to both of the others, and the cracks show up all at once.

Where do agents find each other? What happens when one is mid-task and the
process restarts? Who proves that agent B is really agent B, and not
something pretending to be it? If a workflow moves money or deletes a
customer record, what's the record of what happened — one that survives
someone with disk access wanting it to say something else?

Nobody answers these questions on purpose. They get answered by accident,
under deadline pressure, differently in every codebase. That's the failure
mode: not that multi-agent systems don't work, but that everyone rebuilds
the same missing layer, badly, and incompatibly with everyone else's
version.

## The industry solved the wrong layer first

Frameworks like LangChain, CrewAI, and AutoGen solved a real problem: how
do you structure a single agent's reasoning, give it tools, and chain calls
together. That problem needed solving, and these projects did it well
enough that building one competent agent is now a weekend's work instead of
a research project.

But a framework that makes one agent easy doesn't make ten agents
coordinate. Discovery, identity, retries, encryption, audit — none of that
is a "reasoning" problem. It's a *networking* problem, and every framework
either ignores it or bolts on a partial answer scoped to its own agents
only. A LangChain chain and a CrewAI crew have no shared language. Wire
them together and you're not integrating two systems, you're inventing a
protocol between them from scratch, and doing it worse than if you'd
started from a protocol in the first place.

This is not a new problem. It's the oldest problem in distributed
computing, wearing a new hat.

## We've been here before

In the 1970s, every computer network spoke its own dialect. IBM's SNA
didn't talk to DEC's DECnet, which didn't talk to Xerox's XNS. Connecting
two networks meant a custom gateway, hand-built, for that specific pair.
Nobody could build software that assumed the network beneath it, because
there wasn't one network — there were dozens, and each vendor wanted you
locked into theirs.

TCP/IP won not because it was the cleverest design in the room, but because
it was *neutral*. It didn't come from IBM or DEC, so nobody had to trust a
competitor to adopt it. Once enough networks spoke it, refusing to speak it
became the expensive choice, and the fragmented alternatives died within a
decade.

Multi-agent AI is at the exact point networking was before TCP/IP. Every
vendor is building a version of agent-to-agent communication scoped to
their own ecosystem, and every one of them has an incentive for you to stay
inside it. That's a rational business strategy for a company. It is a bad
outcome for the field, because it means the standard that wins will be
whichever vendor's lock-in becomes the least worst option — not the one
best suited to being infrastructure.

Infrastructure has to be owned by no one for everyone to build on it. That
was true of TCP/IP, SMTP, and HTTP. It's true here too.

## What we actually built

RFC-001 is not another framework sitting where LangChain or CrewAI sit. It
sits *underneath* them — the layer they all assume exists and none of them
provides. Concretely:

**Discovery.** An agent announces what it can do; others find it by
capability, role, or metadata. `discover(capabilities=["translate"])`
replaces hardcoded addresses that break the moment something moves.

**End-to-end encryption, on by default.** RSA-2048-OAEP wraps a per-message
AES-256-GCM key. The hub routes ciphertext it cannot read. This matters
most exactly when it's least convenient: two competing organizations will
never agree to route sensitive data through infrastructure that can read
it, so a coordination layer that can't offer this guarantee simply won't
be used for the cases that need coordination most.

**Verifiable identity.** A SHA-256 fingerprint covers an agent's roles,
capabilities, and permissions. Tampering breaks the fingerprint and gets
rejected at registration — not audited after the fact, rejected before it
does anything.

**Authorization that a client can't grant itself.** At registration, an
agent without an API key picks its own roles — fine for agents exchanging
messages, catastrophic for a console that can revoke keys or disconnect
agents. So administrative authority requires proof the client didn't
generate: an identity backed by an API key, carried in a hub-signed JWT
claim a client can neither forge nor alter. This sounds like a small
detail. It's the difference between an access-control system and an honor
system.

**Tasks that survive a restart.** State persists. A task interrupted by a
crash or a deploy is reassigned when its executor reconnects, instead of
evaporating along with the process that was tracking it.

**Tamper-evident audit.** Every event chains into the last via its hash.
Edit one entry directly in the database, after the fact, and the chain
breaks — loudly, at the next startup, not silently forever. An audit log
that can be quietly rewritten was never actually an audit log.

**Federation.** Hubs peer across organizational boundaries. Your agent can
delegate to a partner's without either side standing up shared
infrastructure or trusting the other with more than the task requires.

**Framework adapters that add nothing.** `from_langchain` wraps an existing
LangChain runnable; `from_callable` and the `@nexus_service` decorator turn
any Python function into a discoverable agent, which is how the CrewAI,
AutoGen and LlamaIndex examples bridge their own frameworks. None of this
imports the frameworks themselves, on purpose — installing Nexus never
drags in a hundred transitive dependencies, and the bridge doesn't shatter
every time one of them ships a breaking major version, which by their own
release histories is often.

None of this is exotic. Every piece here is something a serious production
deployment eventually builds for itself. The only novel part is building
it once, as a protocol, instead of once per team, forever.

## Why this, why now

Multi-agent systems were a research curiosity until about eighteen months
ago. They're now something companies put in front of real workflows —
customer data, financial transactions, infrastructure decisions. That shift
changes what "good enough" means. A prototype can hardcode an address and
skip the audit trail. Production infrastructure cannot, and the industry is
crossing that line faster than the standards for doing it safely are
being built.

That's the actual argument for urgency, and we want to be precise about
it: not that some competitor will "win" agent coordination if we don't move
fast — that framing treats this as a market to capture rather than a
problem to solve — but that the window for a *neutral* answer is finite.
Every vendor currently shipping agents has a reason to prefer that
coordination happen inside their walls. Left long enough, one of those
walled versions becomes the default by sheer distribution, the way a
proprietary standard can win on momentum even when a better open one
exists. TCP/IP had that window too, and it wasn't open forever.

## What we're not claiming

We're not claiming this is finished. It isn't. There's no TLS by default —
put the hub behind `wss://` before anything sensitive touches it, because
end-to-end encryption protects payloads, not who's-talking-to-whom
metadata. State lives in one hub's database; multiple hubs sharing state
needs work we haven't done. Key rotation currently ejects every connected
agent; there's no overlap window yet. A resumed task can run twice, so
executors have to be idempotent — that's a real constraint, not a footnote.
And the framework adapters have been verified against test doubles that
reproduce each framework's calling convention, not yet against the real
libraries, because we couldn't get them installed in this environment to
check. One sharp edge there: `from_langchain` falls back to a chain's
synchronous `invoke()` when no `ainvoke` exists, and calls it on the event
loop — which freezes the agent for the duration of the inference. If your
chain is synchronous, wrap it with `from_callable` and `asyncio.to_thread`
instead, the way the examples in `examples/frameworks/` do. We'd rather
tell you that plainly than have you discover it in production.

We're also not claiming multi-agent coordination is a solved problem once
you adopt a protocol. Coordination failures that come from bad task
decomposition, unclear ownership, or agents given contradictory goals — no
protocol fixes that. What RFC-001 fixes is narrower and, we think, more
foundational: the plumbing failures that have nothing to do with your
agents' logic and everything to do with the fact that nobody standardized
how agents find each other, prove who they are, or leave a record that
can't be quietly rewritten.

## The point

TCP/IP didn't win because it was owned by the biggest company. It won
because it was owned by none of them, which meant everyone could build on
it without betting their business on a competitor's goodwill.

That's the bet here. Not that Nexus is the cleverest possible design — a
reasonable critique of any part of it is welcome, and the RFC is public
specifically so it can be argued with — but that the coordination layer for
AI agents has to be something nobody owns, or it will end up being
something one company owns, and everyone else will spend the next decade
paying rent on infrastructure that should have been a public good from the
start.

The code is on GitHub. The spec is [RFC-001](RFC-001-CORE-PROTOCOL.md). Read
it, break it, tell us where it's wrong.

---

*Nexus Protocol is open source under Apache 2.0. `pip install nexus-mesh` /
`npm install nexus-mesh`.*
