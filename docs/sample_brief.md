# Sample Brief

Below is a representative deterministic brief generated from the seeded student organization workflow.

## Student org event follow-up: AI Pilot Brief

### Problem Statement

The `Student org event follow-up` workflow relies on manual coordination that creates avoidable delay, inconsistent follow-up, and reporting overhead for a small team. The desired outcome is to reduce coordination overhead and make follow-up more reliable without removing the human lead from approvals.

### Current State

The team currently manages `Student org event follow-up` through a largely manual workflow. Common friction includes manual data handling and slow handoffs, which slows follow-up and makes the process harder to scale.

### Why Now

This workflow is a reasonable pilot target because it appears to consume about 6.5 hours each week and should be reducible with a narrow, human-reviewed automation layer.

### Proposed AI Pilot

Create a small-team copilot that ingests the workflow notes and structured inputs, identifies the next action, drafts the required summary or recommendation, and records a pilot brief with ROI, KPIs, and risks before any broader rollout.

### Evidence

- `club_ops_notes.md`: The student organization runs one event planning meeting every Tuesday and creates around 22 follow-up tasks per week.
- `club_ops_notes.md`: Rewrite and follow-up work takes about 6.5 hours per week, and sponsor follow-up can take 48 hours.
- `club_metrics.csv`: Baseline metrics show 22 weekly follow-up items, 6.5 manual hours, 48 turnaround hours, and 15% rework.

### Opportunity Score

- Recommendation: `Pilot now`
- Total score: `80/100`
- Impact / Effort / Risk / Confidence: `5 / 3 / 3 / 4`

### ROI Estimate

- Baseline manual effort: `6.5 hours/week`
- Projected savings: `2.8 hours/week`
- Cycle time reduction: `33%`
- Annual hours saved: `145.6`
- Annual cost savings: `$3,203`

### KPIs

- Reduce manual effort from 6.5 to 3.7 hours per week
- Cut average cycle time from 48 to 32 hours
- Reach 95% on-time completion for the pilot sample
- Reduce rework below 10%

### Risks

- Source inconsistency: start with one canonical intake format
- Team adoption: keep a human reviewer in the loop
- Over-automation of edge cases: route ambiguous cases back to the team lead

### Rollout Plan

1. Week 1 baseline: track current volume, manual effort, cycle time, and rework
2. Week 2 prototype: test on historical examples
3. Weeks 3-4 pilot: run on a limited live sample with human approval
4. Review: compare pilot metrics to baseline and decide whether to scale
