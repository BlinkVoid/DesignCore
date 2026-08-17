# Legibility rules

What the vision pass judges against. Deterministic lint catches geometry; these
are the judgments it cannot make.

## One diagram answers one question

The spec's `question:` field is load-bearing. If stating it needs the word
"and", the diagram is two diagrams — split it. A diagram that cannot state its
question should be deleted, not fixed.

## The entry point is obvious

A reader should find where to start within two seconds. If the eye lands
somewhere arbitrary, set `emphasis: primary` on the true starting node or change
`direction` so reading order matches the flow.

## Consistent altitude

Never mix "what talks to what" with "how it is deployed". One diagram sits at
one level of abstraction. A node representing a whole subsystem next to a node
representing a single process is the most common version of this mistake.

## Label edges that are not obvious

Label an edge when the relationship is ambiguous; leave it bare when it is not.
`Client -> API` labelled "calls" adds nothing. `Worker -> Queue` labelled
"retries on failure" earns its space.

## Emphasis is scarce

At most two `primary` nodes per diagram. Emphasis works by contrast — mark a
third and it means nothing. `muted` is for context the reader needs to see but
should not focus on.

## Grouping carries meaning

A group must denote something real: a trust boundary, a deployment unit, an
ownership line. Decorative grouping is noise, and it costs layout space that
would otherwise separate nodes.

## Density

`designcore lint` enforces a per-kind node ceiling and reports `TOO_DENSE` as an
error. Treat it as the design telling you the diagram is answering more than one
question. Splitting is almost always better than raising the threshold.
