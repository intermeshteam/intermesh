# Contributing to InterMesh Protocol

Thanks for your interest in InterMesh. We are building the open, neutral coordination
infrastructure for AI agents.

---

## Development setup

```bash
git clone https://github.com/intermeshteam/intermesh.git
cd intermesh

python3 -m venv venv
source venv/bin/activate
pip install -e ./sdk-python
pip install pytest pytest-asyncio

cd sdk-js && npm install && cd ..
```

## Running the tests

All tests must pass before a pull request can be merged:

```bash
pytest -v
```

## Engineering rules

1. **No regressions.** Every new feature ships with a unit test in `tests/`.
2. **E2E encryption is preserved.** No message content may transit the hub in plaintext.
3. **Cross-language parity.** Any protocol change must land in both `sdk-python/` and `sdk-js/`.
4. **Spec first.** Changing the message envelope or adding a message type requires an
   issue amending `docs/RFC-001-CORE-PROTOCOL.md` before code is written.
5. **No new runtime dependencies** without justification in the pull request description.

## Pull request checklist

- [ ] `pytest -v` passes
- [ ] Python ↔ Node.js interoperability verified when the protocol changed
- [ ] New tests added under `tests/`
- [ ] Docs updated (`docs/`, `README.md`) when behavior changed

## Code of conduct

All participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
