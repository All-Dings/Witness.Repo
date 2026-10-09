# Witness.Repo

Public number reservations and version evidence for All-Dings. The initial
evidence is migrated from committed Index history and a pinned World. Its first
Witness Commit establishes the independent history. A complete `World-Index.jsonl` and `0.txt` register form the
allocation authority used by All-Dings creation and import commands.

This repository has independent Git history. It is not a constitutive World
Source, and coordinated World commits and rebases do not rewrite it. Publication
is a separate step after the final World identity has been established.

## Read without All-Dings

Only Python 3.8 or newer and its standard library are needed:

```sh
python3 witness.py check
python3 witness.py list '*Parking*'
python3 witness.py list -verbose
python3 witness.py show 400007578
python3 witness.py show 400007578.V.0
python3 witness.py markdown > Dings_World_Index.md
```

`list` prints an aligned table of numbers, exact versions when available, public registration names,
files and recorded SHA1 hashes. `list -verbose` includes SHA256 hashes as well.
`show` displays both hash algorithms and selects one number at the pinned World or
an exact historical address such as `400007578.V.0`. Historical results retain
the recorded registration name; no historical canonical name is inferred.
The first Column shows the exact Version, or the reserved Number when no
Version evidence is available; there is no separate redundant Number Column.
`markdown` generates a readable view ordered by Number from the JSONL;
it is not an independently authored index.
Piping output into `head` ends quietly when the consumer closes the pipe.
Time Columns are provided by All-Dings, not by the standalone reader:

```sh
dings-gpt index list 400007578
dings-gpt index list 400007578.V.0 -verbose
```

`index list` reads `Witness.Repo/World-Index.jsonl` by default and shows
World BCT plus SHA1. `-verbose` adds Witness BCT and SHA256. Use
`-index PATH/0.txt` to inspect a legacy Index explicitly. `index check` checks
Witness reservations and register consistency; registration Names may differ
from current canonical Names after a rename. An explicit legacy Index also
checks Name agreement.

`check` validates the structure and the linked history hash. It does **not**
rehash original files, authenticate an external witness, or certify readiness
for allocation. An independent observer must retain the fetched Git evidence.

## Format 2

`World-Index.jsonl` is an append-only journal. Its immutable `Witness_Index`
header has `Format_Version: 2` and `Initial_Reservation_Count`. The next records
are the numerically ordered, unique reservations from the initial migration.
Subsequent `Reservation` and `Dings_Version` records are appended in writing order.
Each JSON object occupies exactly one UTF-8 line. Keys are sorted, with compact
separators and a final newline.

The header pins the original `0.txt` commit and SHA256, the committed World
and its Git commit and fingerprint, the Access authority commit, and the count
and SHA256 of `Index-History.jsonl`. There is no build timestamp: repeated
generation against unchanged authorities produces identical bytes. The header's
World describes the initial migration, not the latest appended Version. Counts
and hashes of the initial history and Version sidecars remain unchanged.

Every reservation contains `Number` and `In_Current_Index`. A number found
in reachable Index history also has `First_Index_Commit`, meaning the first
occurrence in the recorded ancestor-first traversal, not proof of the original
creation date. Numbers absent from today's Index remain reserved. Numbers
present only in the selected World are also retained, without inferring names.

Optional `Name` has `Name_Source: Legacy_Index` for the migrated Index or
`Name_Source: Registration` for a new reservation. It records the public Name
at registration, rather than tracking later canonical Manifest Names. Legacy heading Sections
are not exported. Duplicate current entries have no chosen name.

Optional `Version` and `Version_Fingerprint` identify the exact Dings version
in the pinned World. `Files` contains selectors, byte sizes and recorded
`Hash_List` values (`SHA-1` or `SHA-256` with prefixed digests). These are
World-record evidence, not freshly measured local file hashes. A legacy
parenthesized checksum from `0.txt` is separately stored as
`Legacy_Hash_Assertion`; its file association and bytes are not verified.

Once-restricted identities publish only their reservation. Names,
versions, files and legacy checksum assertions are omitted conservatively.
Publication checks newly recorded evidence against the committed Access authority.

`Dings-Versions.jsonl` contains numerically ordered `Dings_Version` records
for all available public versions in the pinned World Git tree. Each record
contains `Number`, exact `Version`, `Version_Fingerprint` and `Files` with
recorded byte sizes and hashes. The Index header links this file by
`Versions_SHA256` and `Version_Count`; `check` validates it and its agreement
with the initial reservation records. Later Version evidence is appended to
`World-Index.jsonl`; the initial sidecar is not rewritten. Missing historical
versions are reported explicitly.
Hashes describe the exact recorded bytes, which may include historical
asset pointers or stubs; they do not automatically describe today's asset bytes.

Version records and their current Reservation projection retain the producing
`World` address and `World_Fingerprint`. `World_BCT` copies that immutable
World record's `Source_Time`, preserving the historic commit's BCT rather than
the later bulk-import Git commit time. Missing source times remain unknown.
`Witness_BCT` remains `null` when no independent observation time is recorded.
A Witness Git Commit does not substitute its own date for the producing World
BCT. Neither reader needs Git to display stored World time evidence. The standalone reader intentionally
does not add BCT columns.

`Index-History.jsonl` has one `Index_Source` record for every reachable Git
commit touching `0.txt`, including branches merged into the selected HEAD.
Each record contains the original commit, its recorded Unix commit time, the
SHA256 of the original Index bytes (or `Absent: true`), number count, historical
parse-error count, and proven `World_List` associations. Only explicit World
Git-event provenance supplies associations; an empty list means unproven.
Raw historical names, commit messages and private World metadata are not copied.
Original Git commits remain the evidence; newly created Witness commits are
never backdated. Rewritten or unreachable histories are outside this migration.

`Migration-Report.json` retains current syntax/duplicate findings by number and
line, plus coverage counts. Historical parse errors remain counted per source
proof. Unrecognized numeric entry lines are conservatively retained as number
reservations. Legacy Name reconciliation with Manifests is available through an explicit
`dings-gpt index check -index PATH/0.txt`.

## Generate a candidate

In an All-Dings workspace with committed, consistent Repo 0, World.Repo and
Access.Repo:

```sh
dings-gpt index migrate -verbose
dings-gpt index migrate -apply -verbose
```

The first command reports the plan. The second writes this bundle under
`.Dings/Repositories/System/Witness.Repo`. Neither commits nor pushes it.
Existing different evidence is rejected; use `-output` with a new directory
to compare another candidate. Identical reruns leave files unchanged.
The standalone reader and this README are exported from the source repository
alongside the generated data, so there is one maintained implementation.

## Allocation and registration

`dings new`, `work new`, `blog new`, new Event-Channels, `import big file`
and `import text file` share `Dings_Lib_Witness.Reserve_Numbers`. The default
start is `100000000000`; the header may configure `Start_Number`. Explicit
`-dings-number` reserves one free Number. Import `-start-id` is an optional
lower bound. Legacy Sections no longer define allocation ranges. New automatic
allocation follows the highest registered Number at or above the selected start;
gaps and historical reservations are never reused automatically.

A shared writer lock protects reservations and Version additions. A durable
intent records each target's original length and SHA256 and the exact bytes to
append. The writer appends to JSONL and, for new reservations, to `0.txt`, then
fsyncs both. An interrupted write, including a partial JSONL line, is completed
by appending only the missing bytes before another allocation. Changed original
content or an unexpected suffix is rejected before recovery changes either file.
The lock and recovery intent are local coordination files under `.git` (or the
workspace disposable Var directory when there is no Git checkout).

`Journal_Index` replays the journal into an in-memory map of occupied Numbers
and latest recorded Versions. Standalone `witness.py` uses this view and requires
no Arrow dependency. Display order is numeric, independently of append order.

All-Dings uses the same standard-library JSONL reader for internal identity
checks, Name maps and allocation. It keeps only Numbers, registration Names and
current Versions in a process-local Memory view, without retaining File hashes.
Unchanged files reuse that view. Every changed file is replayed completely,
including after manual Git checkout, truncation or rewriting a prefix while
appending new records. Invalid records or a concurrent file change reject the
read instead of returning the old view. No persistent derived index, cache
checksum or Build is required. Full `index list`, historical Version output and
`index check` read the complete JSONL evidence.

Automatic Number allocation reads the Header and the most recent Reservation or
World checkpoint from the journal tail. Its optional `Watermark` is the highest
occupied Number, stored as a canonical Number String. New reservations update
it, including batches and explicit higher Numbers. Explicit lower Numbers leave
it unchanged. Legacy records without a Watermark fall back to a complete replay.
Exact Number selection and `index check` still reconcile all Numbers and the
readable register. Full replay also verifies recorded Watermarks. Reset/Rebase
recompute unpublished Watermarks, so checkout and history rewriting need no
separate allocation file. Durable append recovery retains its prefix checksums.

`Dings_Lib_Witness.Append_Versions` accepts public Version evidence selected by
its caller from committed World records. Identical retries add nothing;
conflicting evidence for an existing Version Address is rejected. The highest
recorded Version for a Number supplies its current view; older Versions remain
available by exact Address. Version additions never change registration Names
or `0.txt`. The reservation and Version primitives do not commit or push.

`world commit` subsequently runs independent Witness publication. It reads only
the committed World Versions produced since the last Witness checkpoint and
appends their public Dings-Version File hashes and World BCT. A `World_Witness`
record closes each World with its fingerprint, Source time and public Version
count. This also records Worlds that produce no public File evidence. Each
completed World receives its own Witness Git Commit, outside the World itself.

`dings-gpt index update` finishes missing Worlds in order. Retrying does not
append duplicate Versions. A local durable Git publication intent handles a
failed Commit and a crash immediately after successful Commit. Unrelated staged
Witness changes are never included. World and Witness writers share the World
operation lock; a shared Access-authority lock holds the public projection stable.
Once-restricted Numbers keep only their reservation; newly restricted unpublished
evidence blocks publication until reconciled. No Source bytes are copied.

If Witness publication fails, the Source and World Commits remain completed.
The commit command reports `Witness: Pending`, exits with findings, and instructs
the user to run `dings-gpt index update`. The first update validates and commits
the prepared migration bundle when Witness HEAD is unborn. This never pushes.

Each new Number adds `NUMBER.md NAME`, omitting non-public Names. Existing lines
are never rewritten for renames, Versions or rebases. Source creation is
preflighted, but a failure after reservation leaves the Number occupied. Bulk
callers can reserve a batch without a Source scan or semantic Build per Number.
The current CLI file imports still import one File at a time; batch Source
creation and deferred projection are a separate import slice.

`list`, canonical Name resolution and version-identity checks read Witness;
current SM Names take precedence for canonical local Name resolution. JSONL
carries no legacy Sections. Semantic relationships belong in Manifests and SM.

## First publication and subsequent updates

Migration exports the initial `0.txt` layout, suppresses non-public Names and
includes historical reservations. At the first Witness commit, remove the old
`0/0.txt` from Repository 0 as part of the coordinated cutover. The original
Git history remains in Repository 0: a transfer between repositories does not
carry file history. The header and `Index-History.jsonl` retain that provenance.
Readers can inspect subsequent additions with `git log -p -- 0.txt`.

JSONL reservations and readable additions belong in the same Witness commit.
New reservations alone do not claim Version or File evidence. Previously observed Witness history must remain
intact. `index migrate` prepares initial evidence; it cannot overwrite an
existing Index with different evidence or replace later registrations.
Rewriting an already witnessed World fingerprint requires explicit reconciliation;
`index update` rejects the mismatch and preserves the existing evidence.
