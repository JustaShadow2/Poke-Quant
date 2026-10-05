# Diagrams

Diagrams in this specification are authored **inline** in the relevant chapter as [Mermaid](https://mermaid.js.org/) code blocks, so they render directly on GitHub and stay version-controlled next to the prose they describe.

This folder holds **reusable source copies** of the larger diagrams (system context, container view, ERD, pipeline DAGs, key sequences) so they can be dropped into slide decks, whiteboard sessions, or an interview walkthrough without hunting through the chapters.

## Conventions

- One concept per file, named `NN-topic.mmd` (e.g., `01-container-view.mmd`).
- Keep node IDs `camelCase`/`PascalCase` (no spaces) so the source is portable across Mermaid renderers.
- The **inline** copy in the chapter is the source of truth if the two ever drift; this folder is a convenience mirror.

## Index

Populated as chapters are written. Primary diagrams and their home chapters:

- System context & container views → [`01-system-architecture.md`](../01-system-architecture.md)
- Ingestion / feature / training pipeline DAGs → [`01`](../01-system-architecture.md), [`05`](../05-machine-learning.md)
- Entity-relationship diagram → [`03-database-design.md`](../03-database-design.md)
- Prediction request sequence → [`01`](../01-system-architecture.md), [`08`](../08-explainable-ai.md)
- Similarity / analogue pipeline → [`09-similarity-search.md`](../09-similarity-search.md)
