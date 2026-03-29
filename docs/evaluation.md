# Evaluation

Evaluation covers more than "the output looked good once."

## What is being evaluated

- Can the system identify meaningful workflow pain points from unstructured notes?
- Does the recommendation stay aligned with explicit business inputs?
- Are ROI and KPI assumptions transparent?
- Does post-pilot review compare actuals against the original targets credibly?
- Does the LLM path stay inside the expected schema?
- Does the app degrade safely when the provider fails?

## Automated coverage

The current suite covers four areas:

1. Parsing and chunking
   - document loading
   - CSV normalization
   - chunk creation for retrieval

2. Deterministic planning and review logic
   - seeded case produces a strong recommendation
   - thin input triggers clarifying questions
   - sensitive-data workflows surface privacy risk
   - strong post-pilot results produce a scale decision
   - thin post-pilot measurement triggers clarifying questions

3. LLM pipeline behavior
   - mocked OpenAI structured output is accepted and merged correctly
   - mocked OpenAI post-pilot review output is accepted and merged correctly
   - `auto` mode falls back to deterministic planning when the provider errors

4. HTTP contract
   - health endpoint exposes runtime mode
   - analysis endpoint returns a valid brief payload
   - review endpoint returns a valid post-pilot assessment

Run the suite with:

```bash
make test
```

## Manual checks

Use these before showing the project live:

1. `make demo`
2. `make review-demo`
3. `make run`
4. Open the UI and submit both the planning sample and the review sample
5. Confirm the response includes:
   - recommendation or decision
   - score or KPI attainment
   - annual savings or actual annualized savings
   - runtime mode
   - markdown artifact

## Live LLM smoke test

When an OpenAI key is available:

```bash
export OPENAI_API_KEY=your_key
export OPS_PILOT_AGENT_MODE=llm
make demo
make review-demo
```

Expected result:

- runtime mode should be `llm`
- `fallback=False`
- a request ID should be present in the runtime payload
- the brief should preserve deterministic ROI and score values while using more polished narrative language
- the post-pilot review should preserve deterministic KPI comparisons and decision labels while using more polished narrative language

## Quality rubric

Use this rubric when judging outputs:

| Dimension | What good looks like |
| --- | --- |
| Grounding | Recommendation references real evidence from the uploaded notes |
| Business value | ROI and KPIs are specific enough to act on |
| Measurement loop | Post-pilot decisions are tied to real measured outcomes, not vague impressions |
| Risk awareness | Risks are concrete and mitigations are plausible |
| Scope control | The pilot recommendation is narrow and human-reviewed |
| Reliability | The system returns valid output or a safe fallback path |

## Known limitations

- Retrieval uses token overlap rather than embeddings
- No persistence layer for past workflow cases yet
- No auth or multi-tenant controls
- Real provider behavior still depends on external network and API quota
- LLM quality is constrained by the current schema and prompt design
