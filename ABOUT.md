# About the Statisticians Workbench — Open Source Edition

This repository is the **open source edition** of the Statisticians Workbench, an
application for working with datasets, building analysis recipes, managing databases,
and — increasingly — using AI assistance across that work.

The Workbench is also a **commercial product**. Its code is published here, in this
repository, as open source. The commercial product and this repository are two halves
of one project, and they are designed to coexist rather than compete.

## Two models, one product

At first glance there is an apparent conflict: a piece of software that is sold
commercially *and* published as open source. If the source is freely available, why
would anyone pay for the commercial version?

The conflict is not a real one. The two approaches serve **different audiences**, and
each one makes the other stronger.

## Who the commercial version is for

The commercial version exists for people who do **not** want to be their own system
administrator, release manager, or support team. It is the packaged, supported
product: installed from an installer, upgraded through a managed path, and backed by
someone to call when things go wrong.

For a person or organisation without a strong technical IT and statistics skill set,
the commercial version removes a whole class of concerns — installation,
configuration, database management, upgrade testing, and keeping the deployment
healthy. They get a product they can use, and support when it misbehaves.

## Who the open source version is for

The open source version exists for the technically adept: the people who are
comfortable reading, building, running, and changing the code. For them, open source
is not a cheaper copy of the product — it is the point of the product. They can:

- read exactly what the software does,
- run it on their own infrastructure,
- adapt it to their own needs, and
- contribute improvements back to the project.

They can use the code, and they can influence it.

## The safety net runs in both directions

The open source code also protects the commercial side in a way that matters more than
any licensing argument.

If the commercial side of the project ever hit business trouble — if it slowed,
changed direction, or disappeared — the open source code would still be here. The
software could still be built, run, and maintained by anyone who needed it. That is
the safety net the open source code gives to every commercial user: **the risk of
business problems on the commercial side is countered by the fact that the code is not
trapped behind that business.**

In short: the commercial product gives non-technical users a dependable, supported
package, and the open source code gives everyone — commercial users included — the
guarantee that the software itself cannot be taken away.

## How the code is developed

The code is developed in **Python** and **React** — a Python backend and a React
frontend.

This repository is a **replica** of our internal development repository. The two are
kept in step by our own internal processes: the replica is maintained and verified to
match the development tree, so what you see here is the real, working source — not a
stale or simplified copy of it.

This repository is also where we do our **issue tracking**. The issues management
tools here are the ones we rely on for problem tracking and enhancement requests. If
you have found a bug, or have an idea for an improvement, this is where it belongs.

## What the commercial side adds

The commercial side of the project is everything that turns the development work into
a product people can install and upgrade safely. Concretely, the commercial side:

- converts the development and support work into the code changes you see in this
  repository,
- packages that code into an easily deployed product,
- applies version management, and
- runs the full testing needed for deployment and upgrade across the target
  environments — **Linux, Windows, and macOS**.

That packaging, versioning, and cross-platform testing is the gap between "the source
code builds" and "a customer can install and upgrade it with confidence". The open
source repository gives you the first; the commercial side does the second.

## Platform support

One deliberate difference to be clear about: **this open source repository is Linux
only.**

The commercial product targets Linux, Windows, and macOS. The open source side of
things — this repository — is scoped to Linux. If you need the product on Windows or
macOS, that is what the commercial side is for.
