# Evaluation

Evaluation covers more than "the output looked good once."

## What is being evaluated

- Can the system identify meaningful workflow pain points from unstructured notes?
- Does the recommendation stay aligned with explicit business inputs?
- Are ROI and KPI assumptions transparent?
- Does the LLM path stay inside the expected schema?
- Does the app degrade safely when the provider fails?

## Automated coverage

The current suite covers four areas:

1. Parsing and chunking
   - document loading
   - CSV normalization
   - chunk creation for retrieval

2. Deterministic planning logic
   - seeded case produces a strong recommendation
   - thin input triggers clarifying questions
   - sensitive-data workflows surface privacy risk

3. LLM pipeline behavior
   - mocked OpenAI structured output is accepted and merged correctly
   - `auto` mode falls back to deterministic planning when the provider errors

4. HTTP contract
   - health endpoint exposes runtime mode
   - analysis endpoint returns a valid brief payload

Run the suite with:

```bash
make test
```

## Manual checks

Use these before showing the project live:

1. `make demo`
2. `make run`
3. Open the UI and submit the seeded student-org workflow
4. Confirm the response includes:
   - recommendation
   - score
   - annual savings
   - runtime mode
   - pilot brief markdown

## Live LLM smoke test

When an OpenAI key is available:

```bash
export OPENAI_API_KEY=your_key
export OPS_PILOT_AGENT_MODE=llm
make demo
```

Expected result:

- runtime mode should be `llm`
- `fallback=False`
- a request ID should be present in the runtime payload
- the brief should preserve deterministic ROI and score values while using more polished narrative language

## Quality rubric

Use this rubric when judging outputs:

| Dimension | What good looks like |
| --- | --- |
| Grounding | Recommendation references real evidence from the uploaded notes |
| Business value | ROI and KPIs are specific enough to act on |
| Risk awareness | Risks are concrete and mitigations are plausible |
| Scope control | The pilot recommendation is narrow and human-reviewed |
| Reliability | The system returns valid output or a safe fallback path |

## Known limitations

- Retrieval uses token overlap rather than embeddings
- No persistence layer for past workflow cases yet
- No auth or multi-tenant controls
- Real provider behavior still depends on external network and API quota
- LLM quality is constrained by the current schema and prompt design

