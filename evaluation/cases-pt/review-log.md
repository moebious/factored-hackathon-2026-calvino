# Portuguese slice review log (TSD-032, T-203)

Every row of `portuguese.json` has a verdict. The reviewer is a model pass (Claude Sonnet 5.5,
2026-10-05) that read each Portuguese message against its Spanish source and the bank fixture.
It is **not** a native-speaker review and **not** the maintainer's. The last column is the
maintainer's sign-off and is empty until they enter one; a row is final only when it is filled.

Checks per row: same request meaning as the source, same entry references, facts and persona
unchanged, no BRL, Brazilian rail or Brazilian customer, seed record agrees with the bank fixture.

Verdicts: `accepted` (kept as written) or `corrected` (changed in this pass, reason given).

| id | source | verdict | fix | maintainer sign-off |
|---|---|---|---|---|
| PT-001 | AC-1 | corrected | added an entry reference the source does not cite; changes how the hub anchors the turn | |
| PT-002 | AC-2 | corrected | dropped the payment from the source request | |
| PT-003 | AC-3 | accepted |  | |
| PT-004 | AC-4 | accepted |  | |
| PT-005 | AC-6 | accepted |  | |
| PT-006 | AC-8 | corrected | asked about a case where the source asks why a transfer is pending | |
| PT-007 | ADV-001 | accepted |  | |
| PT-008 | ADV-002 | accepted |  | |
| PT-009 | ADV-003 | accepted |  | |
| PT-010 | ADV-004 | accepted |  | |
| PT-011 | ADV-005 | accepted |  | |
| PT-012 | ADV-006 | accepted |  | |
| PT-013 | ADV-007 | accepted |  | |
| PT-014 | ADV-008 | accepted |  | |
| PT-015 | ADV-009 | accepted |  | |
| PT-016 | ADV-010 | accepted |  | |
| PT-017 | ADV-011 | accepted |  | |
| PT-018 | ADV-012 | accepted |  | |
| PT-019 | EDGE-001 | accepted |  | |
| PT-020 | EDGE-002 | accepted |  | |
| PT-021 | EDGE-003 | accepted |  | |
| PT-022 | EDGE-004 | accepted |  | |
| PT-023 | EDGE-005 | accepted |  | |
| PT-024 | EDGE-006 | accepted |  | |
| PT-025 | EDGE-007 | accepted |  | |
| PT-026 | EDGE-008 | accepted |  | |
| PT-027 | ORC-001 | accepted |  | |
| PT-028 | ORC-002 | accepted |  | |
| PT-029 | ORC-003 | accepted |  | |
| PT-030 | ORC-004 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-031 | ORC-005 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-032 | ORC-006 | accepted |  | |
| PT-033 | ORC-007 | accepted |  | |
| PT-034 | ORC-008 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-035 | ORC-009 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-036 | ORC-010 | accepted |  | |
| PT-037 | ORC-011 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-038 | ORC-012 | accepted |  | |
| PT-039 | ORC-013 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-040 | ORC-014 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-041 | ORC-015 | accepted |  | |
| PT-042 | ORC-016 | accepted |  | |
| PT-043 | ORC-017 | accepted |  | |
| PT-044 | ORC-018 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-045 | ORC-019 | accepted |  | |
| PT-046 | ORC-020 | accepted |  | |
| PT-047 | ORC-021 | accepted |  | |
| PT-048 | ORC-022 | accepted |  | |
| PT-049 | ORC-023 | accepted |  | |
| PT-050 | ORC-024 | accepted |  | |
| PT-051 | AC-1 | corrected | added an entry reference the source does not cite | |
| PT-052 | AC-2 | corrected | dropped the payment from the source request | |
| PT-053 | AC-3 | accepted |  | |
| PT-054 | AC-4 | accepted |  | |
| PT-055 | AC-6 | accepted |  | |
| PT-056 | AC-8 | corrected | asked about a case where the source asks why a transfer is pending | |
| PT-057 | ADV-001 | accepted |  | |
| PT-058 | ADV-002 | accepted |  | |
| PT-059 | ADV-003 | corrected | removed a Brazilian payment rail (pix); the data has none | |
| PT-060 | ADV-004 | corrected | role changed from manager to director; restored | |
| PT-061 | ADV-005 | accepted |  | |
| PT-062 | ADV-006 | accepted |  | |
| PT-063 | ADV-007 | accepted |  | |
| PT-064 | ADV-008 | accepted |  | |
| PT-065 | ADV-009 | accepted |  | |
| PT-066 | ADV-010 | accepted |  | |
| PT-067 | ADV-011 | accepted |  | |
| PT-068 | ADV-012 | accepted |  | |
| PT-069 | EDGE-001 | accepted |  | |
| PT-070 | EDGE-002 | accepted |  | |
| PT-071 | EDGE-003 | accepted |  | |
| PT-072 | EDGE-004 | corrected | ungrammatical code-switch and wording drift; request meaning restored | |
| PT-073 | EDGE-005 | accepted |  | |
| PT-074 | EDGE-006 | accepted |  | |
| PT-075 | EDGE-007 | accepted |  | |
| PT-076 | EDGE-008 | accepted |  | |
| PT-077 | ORC-001 | accepted |  | |
| PT-078 | ORC-002 | accepted |  | |
| PT-079 | ORC-003 | accepted |  | |
| PT-080 | ORC-004 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-081 | ORC-005 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-082 | ORC-006 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-083 | ORC-007 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-084 | ORC-008 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-085 | ORC-009 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-086 | ORC-010 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-087 | ORC-011 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-088 | ORC-012 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-089 | ORC-013 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-090 | ORC-014 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-091 | ORC-015 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-092 | ORC-016 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-093 | ORC-017 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-094 | ORC-018 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-095 | ORC-019 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-096 | ORC-020 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-097 | ORC-021 | accepted |  | |
| PT-098 | ORC-022 | corrected | was a different request from the source greeting | |
| PT-099 | ORC-023 | corrected | was a different request from the source greeting | |
| PT-100 | ORC-024 | corrected | was a different request from the source greeting | |
| PT-101 | AC-1 | corrected | added an entry reference the source does not cite | |
| PT-102 | AC-2 | corrected | dropped the payment from the source request | |
| PT-103 | AC-3 | accepted |  | |
| PT-104 | AC-4 | accepted |  | |
| PT-105 | AC-6 | accepted |  | |
| PT-106 | AC-8 | corrected | asked about a case where the source asks why a transfer is pending | |
| PT-107 | ADV-001 | accepted |  | |
| PT-108 | ADV-002 | accepted |  | |
| PT-109 | ADV-003 | accepted |  | |
| PT-110 | ADV-004 | accepted |  | |
| PT-111 | ADV-005 | accepted |  | |
| PT-112 | ADV-006 | accepted |  | |
| PT-113 | ADV-007 | accepted |  | |
| PT-114 | ADV-008 | accepted |  | |
| PT-115 | ADV-009 | accepted |  | |
| PT-116 | ADV-010 | accepted |  | |
| PT-117 | ADV-011 | accepted |  | |
| PT-118 | ADV-012 | accepted |  | |
| PT-119 | EDGE-001 | accepted |  | |
| PT-120 | EDGE-002 | accepted |  | |
| PT-121 | EDGE-003 | accepted |  | |
| PT-122 | EDGE-004 | corrected | said cancelled where the source says declined; meaning restored | |
| PT-123 | EDGE-005 | accepted |  | |
| PT-124 | EDGE-006 | accepted |  | |
| PT-125 | EDGE-007 | accepted |  | |
| PT-126 | EDGE-008 | accepted |  | |
| PT-127 | ORC-001 | accepted |  | |
| PT-128 | ORC-002 | accepted |  | |
| PT-129 | ORC-003 | accepted |  | |
| PT-130 | ORC-004 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-131 | ORC-005 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-132 | ORC-006 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-133 | ORC-007 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-134 | ORC-008 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-135 | ORC-009 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-136 | ORC-010 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-137 | ORC-011 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-138 | ORC-012 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-139 | ORC-013 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-140 | ORC-014 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-141 | ORC-015 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-142 | ORC-016 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-143 | ORC-017 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-144 | ORC-018 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-145 | ORC-019 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-146 | ORC-020 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-147 | ORC-021 | accepted |  | |
| PT-148 | ORC-022 | corrected | was a different request from the source greeting | |
| PT-149 | ORC-023 | corrected | translation did not match the source request (wrong intent, entry or wording); rewritten | |
| PT-150 | ORC-024 | corrected | was a different request from the source greeting | |
| PT-151 | direct | accepted |  | |
| PT-152 | direct | accepted |  | |
| PT-153 | direct | accepted |  | |
| PT-154 | direct | accepted |  | |
| PT-155 | direct | accepted |  | |
| PT-156 | direct | accepted |  | |
| PT-157 | direct | accepted |  | |
| PT-158 | direct | accepted |  | |
| PT-159 | direct | accepted |  | |
| PT-160 | direct | accepted |  | |
| PT-161 | direct | accepted |  | |
| PT-162 | direct | accepted |  | |
| PT-163 | direct | accepted |  | |
| PT-164 | direct | accepted |  | |
| PT-165 | direct | corrected | direct case duplicated the translation of ADV-012; reworded | |
| PT-166 | direct | corrected | facts said Pending but the bank fixture has E-CO-001 Reversed; facts and message corrected | |
| PT-167 | direct | accepted |  | |
| PT-168 | direct | accepted |  | |
| PT-169 | direct | corrected | facts said Declined but the bank fixture has E-CO-002 Pending; facts and message corrected | |
| PT-170 | direct | accepted |  | |
| PT-171 | direct | accepted |  | |
| PT-172 | direct | accepted |  | |
| PT-173 | direct | accepted |  | |
| PT-174 | direct | accepted |  | |
| PT-175 | direct | accepted |  | |
