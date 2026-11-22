# Contract: command-line interface

**Requirements**: FR-072, US6-AS1, US6-AS2 | **Design**: [../research.md](../research.md) R-13

## Invocation

```text
python -m gis_scorer <snapshot.json>
gis-scorer <snapshot.json>          # console script installed by `pip install -e .`
```

The CLI takes exactly one positional argument, a path to a UTF-8 JSON file whose top level is an
object (the snapshot). It has no other options apart from argparse's `-h/--help`.

## Outcomes

| Case | stdout | stderr | Exit |
|---|---|---|---|
| Valid snapshot | `ScoreResult.to_json()`: indented JSON with a trailing newline, byte-identical to the library's output for the same input | empty | **0** |
| Snapshot fails validation (FR-002) | empty | `gis_scorer: invalid snapshot`, then one `  <field>: <message>` line per error, in R-05 order | **1** |
| Malformed JSON | empty | `gis_scorer: invalid JSON: <parser message>` | **1** |
| Top level is not an object | empty | `gis_scorer: invalid snapshot` / `  <snapshot>: must be an object with string keys` | **1** |
| Duplicate key in an object | empty | `gis_scorer: invalid JSON: duplicate key '<key>'` | **1** |
| File missing, unreadable or not UTF-8 | empty | `gis_scorer: cannot read <path>: <reason>` | **2** |
| Wrong number of arguments | empty | argparse usage message | **2** |

Two further guarantees:

- **No partial output.** If the exit code is non-zero, stdout is empty.
- **Determinism.** The same file produces the same stdout bytes, whatever `PYTHONHASHSEED`, the
  locale or the time (R-11).

## Example

```console
$ python -m gis_scorer tests/fixtures/snapshots/invalid_piotroski.json
gis_scorer: invalid snapshot
  piotroski: must be an integer from 0 to 9
$ echo $?
1
```
