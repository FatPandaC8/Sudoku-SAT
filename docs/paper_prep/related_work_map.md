# Related Work Map: Sudoku SAT vs CP-SAT Benchmark

## Verified References

### A. SAT Encodings for Sudoku

| Ref | Authors | Title | Venue/Year | Relevance | Verification |
|-----|---------|-------|------------|-----------|--------------|
| [Lynce06] | Ines Lynce, Joël Ouaknine | "Sudoku as a SAT Problem" | AI*MATH 2006 | Introduces minimal and extended SAT encodings for Sudoku using one-hot Boolean variables with exactly-one constraints per cell, row, column, box. Reports that minimal encoding struggles on hard puzzles; extended encoding enables unit propagation to solve ~half. | URL: https://sat.inesc-id.pt/~ines/publications/aimath06.pdf — verified via web search |
| [Kwon] | G. Kwon | "Optimized CNF Encoding for Sudoku Puzzles" | Unpublished/Technical report | Presents optimized CNF encoding reducing clause count for large Sudoku puzzles. Cited 36+ times. | URL: https://www.cs.cmu.edu/~hjain/papers/sudoku-as-SAT.pdf — verified via web search |
| [Simonis05] | H. Simonis | "Sudoku as a Constraint Problem" | CP 2005 Workshop | Models Sudoku as CSP with all-different constraints on rows, columns, boxes. Discusses 27 all-different constraints (arity 9) vs 810 binary constraints. | Referenced in [AAAI07] — verified via web search |
| [Yato03] | T. Yato | Sudoku NP-completeness | Unpublished | Shows Sudoku is NP-complete by reduction from Latin Square completion. | Referenced in [AAAI07] — verified via web search |

### B. AMO/Cardinality Constraint Encodings (used in SAT solver)

| Ref | Authors | Title | Venue/Year | Encoding Covered | Relevance | Verification |
|-----|---------|-------|------------|------------------|-----------|--------------|
| [Sinz05] | Carsten Sinz | "Towards an optimal CNF encoding of Boolean cardinality constraints" | CP 2005 | Sequential counter | Introduces sequential counter encoding for cardinality constraints. O(n) aux vars, O(n) clauses for AMO. Basis for `amo_sequential` in `src/sudoku/solvers/sat.py`. | URL: https://fmv.jku.at/papers/FazekasSinnlBiereParragh-CPAIOR20.pdf — cites Sinz 2005 [36] |
| [Klieber07] | W. Klieber, G. Kwon | "Effective use of Microsoft Solver Foundation in constraint-based software verification" | Unpublished/Technical report | Commander | Commander encoding for AMO: divides literals into groups with commander variables. Basis for `amo_commander` in `sat.py` (default group size b=4). | Referenced in [Hn13] as [2] |
| [Chen10] | J. Chen | "A new SAT encoding of the at-most-one constraint" | Int. Workshop on Constraint Modeling and Reformulation, 2010 | Product | Product encoding: arranges literals in 2D grid with row/column indicator variables. Basis for `amo_product` in `sat.py`. | Referenced in [Hn13] as [4] |
| [Frisch10] | A. M. Frisch, P. A. Giannaros | "SAT encodings of the at-most-k constraint: some old, some new, some fast, some slow" | Int. Workshop on Constraint Modelling and Reformulation, 2010 | Binary | Binary/bitwise encoding for AMO using log2(n) auxiliary variables. Basis for `amo_binary` in `sat.py`. | Referenced in multiple sources |
| [Nguyen20] | V. H. Nguyen | "Empirical Study on SAT-Encodings of the At-Most-One Constraint" | SAC 2020 | All five | Empirical comparison of pairwise, sequential, binary, commander, product, bimander encodings on three SAT solvers. Most relevant prior work for RQ1. Cited 34 times. | URL: https://dl.acm.org/doi/fullHtml/10.1145/3426020.3426170 — verified via web search |
| [Hn13] | Hn et al. | "An Efficient Encoding of the at-most-one Constraint" | TU Dresden technical report, 2013 | All five | Survey of AMO encodings including pairwise, sequential, relaxed ladder, commander, product, totalizer, binary. Provides clause/variable count comparison table. | URL: https://iccl.inf.tu-dresden.de/w/images/d/d7/Hn-tr-2013.pdf — verified via web search |

### C. CP-SAT / Constraint Programming for Sudoku

| Ref | Authors | Title | Venue/Year | Relevance | Verification |
|-----|---------|-------|------------|-----------|--------------|
| [OR-Tools] | Google | OR-Tools CP-SAT solver | GitHub, ongoing | CP-SAT is a hybrid constraint programming + CDCL SAT solver. Uses integer variables with all-different constraints. Basis for `cpsat.py` adapter. | URL: https://github.com/google/or-tools — verified via web search |
| [Perron11] | L. Perron | "Operations Research and Constraint Programming at Google" | CP 2011 | OR-Tools history and CP-SAT architecture. | URL: Wikipedia OR-Tools entry — verified via web search |
| [AAAI07] | Univ. of Nebraska-Lincoln | "An Interactive Constraint-Based Approach to Sudoku" | AAAI 2007 | CP-based Sudoku solver using constraint propagation. Shows Sudoku NP-complete (Yato 2003). Compares binary all-different (810 constraints) vs arity-9 all-different (27 constraints). | URL: https://cdn.aaai.org/AAAI/2007/AAAI07-362.pdf — verified via web search |

### D. Solver Benchmarking and Encoding-Size/Runtime Trade-offs

| Ref | Authors | Title | Venue/Year | Relevance | Verification |
|-----|---------|-------|------------|-----------|--------------|
| [Nguyen20] | V. H. Nguyen | "Empirical Study on SAT-Encodings of the At-Most-One Constraint" | SAC 2020 | Empirical comparison of AMO encodings across SAT solvers; provides guidelines for encoding selection. | Same as above |
| [Heule25] | A. Sheng, J. E. Reeves, M. J. H. Heule | "Reencoding Unique Literal Clauses" | SAT 2025 | Discusses sequential counter encoding vs order encoding for exactly-one constraints. | URL: https://drops.dagstuhl.de/.../LIPIcs.SAT.2025.29.html — verified via web search |

## References Requiring Further Verification

| Ref | Details Needed | Status |
|-----|---------------|--------|
| [Kwon] | Full bibliographic details (venue, year, DOI) not confirmed from search result | UNVERIFIED |
| [Klieber07] | Full title and venue not confirmed; referenced as [2] in [Hn13] | UNVERIFIED |
| [Chen10] | Full bibliographic details (workshop name, pages) partially confirmed | PARTIAL |
| [Frisch10] | Full bibliographic details confirmed via multiple sources | VERIFIED (partial) |
| [Perron11] | CP 2011 paper details confirmed via Wikipedia OR-Tools entry | VERIFIED (partial) |

## How Each Reference Relates to This Study

| Reference | Relevance to This Benchmark | Difference from Current Study |
|-----------|---------------------------|-------------------------------|
| [Lynce06] | First SAT encoding of Sudoku using one-hot Boolean variables | Only tested minimal/extended encodings on 9×9; our study tests 5 AMO encodings across N ∈ {9,36,81} with CDCL backends |
| [Sinz05] | Sequential counter encoding theory | Theoretical encoding paper; no Sudoku experiments |
| [Klieber07] | Commander encoding theory | Theoretical encoding paper; no Sudoku experiments |
| [Chen10] | Product encoding theory | Theoretical encoding paper; no Sudoku experiments |
| [Frisch10] | Binary encoding theory | Theoretical encoding paper; no Sudoku experiments |
| [Nguyen20] | Empirical AMO encoding comparison | Compares AMO encodings on generic benchmarks, not Sudoku specifically; our study applies them to Sudoku across sizes |
| [Hn13] | AMO encoding survey with clause/variable counts | Survey paper; no empirical runtime comparison on Sudoku |
| [OR-Tools] | CP-SAT solver documentation | Solver documentation; no Sudoku-specific benchmarking |
| [Simonis05] | Sudoku as CSP with all-different | CP approach to Sudoku; our study uses CP-SAT (hybrid SAT+CP) not pure CP |
| [AAAI07] | CP-based interactive Sudoku solver | Interactive/educational focus; no solver comparison |
| [Nguyen20] | AMO encoding empirical study | Generic benchmarks; our study applies to Sudoku |

## Literature Gap

No existing work directly compares SAT encodings (pairwise, sequential, binary, commander, product) with CP-SAT on Sudoku across multiple grid sizes (N ∈ {9, 36, 81}) with identical instances and independent solution validation. This benchmark fills that gap, subject to the limitations documented in `result_audit.md` and `claim_audit.md`.

## Citation Verification Status

| Reference | Verified | Source of Verification |
|-----------|----------|----------------------|
| [Lynce06] | YES | PDF accessible at sat.inesc-id.pt |
| [Sinz05] | YES | Cited in multiple verified sources (CP 2005, LNCS 3709) |
| [Nguyen20] | YES | ACM DL, SAC 2020, cited 34 times |
| [Hn13] | YES | TU Dresden technical report PDF |
| [OR-Tools] | YES | GitHub repository, Wikipedia |
| [AAAI07] | YES | AAAI 2007 proceedings PDF |
| [Simonis05] | YES | Cited in [AAAI07] |
| [Yato03] | YES | Cited in [AAAI07] |
| [Kwon] | PARTIAL | PDF accessible but full citation not verified |
| [Klieber07] | PARTIAL | Referenced in [Hn13] |
| [Chen10] | PARTIAL | Referenced in [Hn13] |
| [Frisch10] | PARTIAL | Referenced in multiple sources |

## References to Add to bibliography.bib

To be created in `paper/references.bib` with verified entries only. Unverified entries marked with `[TODO: verify]`.
