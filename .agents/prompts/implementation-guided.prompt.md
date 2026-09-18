# Guided implementation

## Purpose
Implement the approved ADA change in a disciplined, review-friendly way. This prompt is intended for the phase immediately after the design review has passed, when the task is clear, scoped, and ready to be coded.

## Context
Use the ADA codebase and the current architecture of the project. Prefer changes that are consistent with the existing modular design, the Streamlit frontend, and the core download/processing pipeline. Keep the solution simple, robust, and aligned with the project’s purpose.

## Inputs
Use the following data when available:
- approved change description
- affected files or modules
- review findings that were resolved before implementation
- acceptance criteria or expected behavior
- constraints or risks that must be handled

If the change is still ambiguous, ask for the missing details before coding.

## Required behavior
Implement the approved change in a controlled way:

1. Start from the exact scope that was reviewed and accepted.
2. Keep the implementation minimal and targeted.
3. Respect the existing project structure and naming conventions.
4. Preserve current behavior unless the change explicitly requires altering it.
5. Prefer incremental, testable improvements over broad refactors.
6. Update only the files strictly necessary to complete the change.
7. Handle edge cases and validation paths explicitly.
8. Keep the user flow coherent and avoid introducing UI confusion.

## Implementation rules
- Do not add unrelated features or speculative improvements.
- Do not refactor large sections unless required by the approved change.
- Keep functions focused and maintainable.
- If a visual improvement is involved, ensure it remains consistent with the design language of the app.
- If the change affects downloads, metadata processing, or file handling, validate the most important execution paths.
- If the task touches UX/UI, keep the interface simple, readable, and consistent.
- If there are risks, document them briefly and explain what was done to mitigate them.

## Output format
Return the implementation result in this structure:

### 1) What changed
Describe the functional change in a few clear bullets.

### 2) Files touched
List the files changed and what each one was used for.

### 3) Implementation notes
Explain the main technical decisions and why they were chosen.

### 4) Validation performed
List the checks or manual validations that were run or recommended.

### 5) Risks and follow-ups
Mention any remaining concerns or future improvements that were intentionally deferred.

### 6) Final status
State whether the change is complete, partial, or requires additional review.

## Quality constraints
- Favor correctness and clarity over cleverness.
- Keep the solution aligned with the project’s real goals.
- If the implementation must trade off simplicity against completeness, explain the trade-off clearly.
- Do not hide errors or silently ignore failure cases.
- Prefer explicit handling of user-facing states and validation paths.

## Example usage
- Implement the approved UX/UI change in ADA and keep the scope tight.
- Apply the reviewed improvement in the Streamlit flow without broad refactors.
- Implement the safe version of this improvement and list the files touched and checks performed.
- Carry out the approved change in ADA, preserving existing behavior and validating the main path.
- Implement the reviewed fix with minimal scope and explain the trade-offs clearly.
