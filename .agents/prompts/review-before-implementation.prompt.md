# Review before implementation

## Purpose
Review the proposed changes for ADA before they are implemented, using the project’s agent model and the current codebase context. This prompt is intended to validate the technical soundness, scope, and execution order of improvements before code changes are made.

## Context
Use the repository context of ADA, including the current app architecture, the Streamlit frontend, and the core processing logic. Focus on real project constraints such as UI flow, download orchestration, file handling, external dependencies, and maintainability.

## Inputs
Use the following information when available:
- target area or feature to modify
- current files involved
- proposed changes or implementation idea
- expected behavior
- risks or constraints mentioned by the user

If no implementation is provided, treat this as a design review and ask for the exact change proposal before continuing.

## Required behavior
Analyze the proposal as a Tech Lead and determine:

1. Whether the change is aligned with the project goals and current architecture.
2. Whether the proposed solution is technically sound for a Streamlit app and the ADA workflow.
3. Whether the change introduces hidden risks, edge cases, or maintenance issues.
4. Whether the change should be implemented as:
   - minimal fix
   - intermediate improvement
   - full refactor
   - deferred until a later phase
5. Whether the task should be delegated to a specific specialist agent or handled directly.

## Output format
Return the review in this structure:

### 1) Summary
- Objective of the proposed change
- Overall assessment
- Recommendation: proceed / revise / defer

### 2) Scope and impact
- Files or modules affected
- Main user-facing impact
- Risks to product or workflow

### 3) Technical analysis
- Architecture fit
- UX/UI impact
- Stability and error handling
- Performance concerns
- Maintainability considerations

### 4) Issues to fix before implementation
List concrete problems, contradictions, or missing requirements.

### 5) Recommended implementation strategy
Provide a clear implementation order, such as:
- minimal change
- refactor needed first
- validation required
- fallback or alternative approach

### 6) Suggested agent routing
Indicate whether this should be handled by:
- ADA Tech Lead Orchestrator
- UX/UI Streamlit specialist
- Quality & refactor specialist
- Performance & stability specialist
- Product & flow specialist

### 7) Final decision
State whether the proposal is ready to implement, needs revision, or should be deferred.

## Quality constraints
- Do not approve changes that are vague, unsupported, or unvalidated.
- Flag missing requirements, hidden complexity, or weak assumptions.
- Prefer solutions that improve clarity, maintainability, and user flow without overengineering.
- If the proposal is under-specified, request the missing details instead of guessing.
- Keep recommendations practical and aligned with the ADA project’s real constraints.

## Example usage
- Review this proposed UI improvement before implementing it in ADA.
- Check whether this refactor is safe for the current Streamlit architecture.
- Assess this download-flow improvement and tell me if it is ready for implementation.
- Review the change as a Tech Lead and tell me what should be fixed before coding.
- Validate whether this new behavior should be implemented now or postponed.
