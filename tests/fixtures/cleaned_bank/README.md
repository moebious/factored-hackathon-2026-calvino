# T-206 cleaned-table adapter fixture

Small, invented CSV rows matching the TSD-007 customer, product, and
transaction contracts. The fixture includes only MX, CO, and AR customers and
MXN, COP, ARS, and USD currencies; it is not copied from the organizer dataset.

It covers approved, declined, pending, and reversed statuses; under/over-Gate
amounts; known true and false fraud flags; and source-null amount, currency,
and fraud fields. Those nulls are deliberate. Tests verify that reads preserve
them and writes fail closed without inventing facts.

`CleanedTableAdapter` reads these files with DuckDB, runs the existing
aggregate TSD-007 audit, and writes only aggregate lineage metadata into the
test's temporary directory.
