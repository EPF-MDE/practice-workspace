# Each kind of Store entry has a validating model that writes the JSON it always wrote

Every Store entry's payload was a plain dict, and what each kind held was only written in comments beside its kind. Nothing checked it: a caller could store a field under another name, and every reader indexed the dict by string. A Send is a GitHub comment that is never rewritten (ADR-0005), so the shapes cannot change under the entries already stored. **So each kind of entry has one Pydantic model in `app.store`, which every send takes and every read of the record returns, and which writes exactly the JSON the dicts wrote.**

- **Pydantic, not TypedDict.** What GitHub answers is untrusted input, parsed with a schema at the edge (CODING_STANDARDS.md), and a TypedDict validates nothing at runtime.
- **A field left at its default is not written.** An optional field is written only when it holds something, so no `null` or `false` key appears that the dicts never wrote. A Self-assessment level's `link` has no default, so it is written as `null` as before.
- **Reading is lenient on what it does not know.** A key no model names is ignored, so an older Engine reads entries a newer one wrote, as it skips an unknown kind. A drawing's `commit` is optional, since the memory Store writes none; the GitHub Store reads a drawing without one from the data branch's tip.
- **A Send whose payload does not parse is skipped**, like an unknown kind, rather than failing the Student's whole record.
- **Withdrawing a declaration is its own method and its own model**, still written as an empty payload under the `declaration` kind, so its versions count with the declarations'.
- **The model is the payload, read by type.** A record is asked for the entries of a model, such as `record.latest(AnswerPayload, competency, step)`, and returns entries typed by it. The kind stays the stored string; each model names its own.
- **The snapshot of the Evidence panel stays a dict.** `app.evidence_panel` imports the Store, so the Store cannot import its model without a cycle.
- **The order of keys may differ** from what an earlier Engine wrote for an Evidence Plan. No reader depends on it.

## Considered options

- **TypedDicts.** Rejected: no runtime check, and an absent key still reads as a `KeyError` far from the Store.
- **Strict reading, refusing an unknown key.** Rejected: it would drop entries an older or a newer Engine wrote.
