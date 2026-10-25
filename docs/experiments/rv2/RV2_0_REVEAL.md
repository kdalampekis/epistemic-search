# RV2-0 — reveal (open only after answering Parts 1 and 2)

## Part 1 — stance items

| id | case | premise | span | system | RV1 | RV1 notes |
| --- | ---: | --- | --- | --- | --- | --- |
| S01 | 8 | Determine whether the identified jobs are the same. | Acting Secretary of Labor | CONTRADICT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S02 | 7 | Establish the year that railroad ceased operating, if it cea | Westbridge was out of service on January 1, 1939 and was discontinued  | SUPPORT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S03 | 21 | Identify the real-world location or set used for the Overloo | The location used for the exterior of the Overlook Hotel was Timberlin | NEUTRAL | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S04 | 17 | Determine the father of the resolved person. | the Landgrave George II of Hesse-Darmstadt | SUPPORT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S05 | 19 | Identify the director of the intended film. | She is a film director | NEUTRAL | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S06 | 20 | The display brand-type associated with MacBook is Retina. | It offers a high-resolution Retina Display | SUPPORT | SUPPORT | Independent semantic reading supports this stance label. |
| S07 | 5 | Clemson defeated the Oklahoma Sooners in the game. | The West Virginia Mountaineers defeated the Clemson Tigers by a score  | CONTRADICT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S08 | 8 | Determine whether the identified jobs are the same. | He was replaced as party chairman by Markham Robinson in July 2008. | SUPPORT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S09 | 5 | The target event is a college football game. | Clemson defeated the No. 4 Oklahoma Sooners, 37–17, in the 2015 Orange | SUPPORT | SUPPORT | Independent semantic reading supports this stance label. |
| S10 | 3 | The requested answer is the name of that city. | Key West, Florida | NEUTRAL | SUPPORT | Independent semantic reading supports this stance label. |
| S11 | 20 | The display type associated with MacBook has higher resoluti | Retina Display is a brand name used by Apple for its series of IPS pan | SUPPORT | SUPPORT | Independent semantic reading supports this stance label. |
| S12 | 8 | Identify the job for which Edward C. Hugger served as an app | he served as Acting Secretary of Labor | SUPPORT | SUPPORT | Independent semantic reading supports this stance label. |
| S13 | 8 | Determine whether the identified jobs are the same. | Deputy Assistant Secretary for Operations in the U.S. Department of La | CONTRADICT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S14 | 10 | What is the birth date of the director of Divorce in Montevi | Manuel Romeo (September 21, 1891 – October 3, 1954 in Buenos Aires) | NEUTRAL | SUPPORT | Independent semantic reading supports this stance label. |
| S15 | 7 | Establish the year that railroad began operating. | the station was built around June, 1875 | NEUTRAL | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S16 | 3 | The islets are described as 60 miles west of a city. | a group of desert coral islets 60 miles west of Key West, Florida | SUPPORT | SUPPORT | Independent semantic reading supports this stance label. |
| S17 | 10 | What is the birth date of the director of Divorce in Montevi | directed by Manuel Romero | NEUTRAL | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S18 | 6 | Establish whether Ainslee Glen was the source or donor of th | it has been given to the people of Boston by the people of Nova Scotia | CONTRADICT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S19 | 7 | Establish the year that railroad ceased operating, if it cea | Westbridge used to operate as a freight station after its closing. | CONTRADICT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S20 | 11 | T_A is earlier than T_B. | released on March 13, 1942 | SUPPORT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S21 | 5 | The date on which the matching game was played is the reques | The 2012 Discover Orange Bowl was a postseason college football bowl g | SUPPORT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S22 | 7 | Establish the year that railroad ceased operating, if it cea | the station stop itself continued to operate until March 16, 1998. | SUPPORT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S23 | 19 | Determine the birthplace of that director. | Dana Blankstein- Cohen( born March 3, 1981) is the director of the Isr | NEUTRAL | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S24 | 5 | The target event is a college football game. | On December 5, 2015, the Tigers won the 2015 ACC Championship Game by  | SUPPORT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S25 | 4 | Identify the lights festival held on the Fylde Coast in Lanc | Blackpool Illuminations, an annual lights festival in Blackpool. | SUPPORT | SUPPORT | Independent semantic reading supports this stance label. |
| S26 | 12 | The place of birth of that director is identified. | written and directed by Oren Moverman | NEUTRAL | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S27 | 11 | T_B is earlier than T_A. | The film was released on March 13, 1942, by RKO Pictures. | SUPPORT | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |
| S28 | 6 | Establish whether Ainslee Glen was the source or donor of th | In 2016, a tree on Crown Lands was chosen to become the Boston Christm | NEUTRAL | SUPPORT | Independent semantic reading supports this stance label. |
| S29 | 11 | The director of The Mexican Spitfire's Baby is D_A. | directed by Leslie Goodwins | CONTRADICT | SUPPORT | Independent semantic reading supports this stance label. |
| S30 | 14 | The birth date of Kaalapani's director is established. | co-written and directed by Priyadarshan | NEUTRAL | NEUTRAL | Span does not establish or refute the assigned premise in the target entity/event context. |

Items from the agreeing strata (SUPPORT→SUPPORT, NEUTRAL→NEUTRAL) are controls:
they test whether you disagree where the system and the RV1 assessor agree.

## Part 2 — RV1 root-cause conclusions

### Case 5 — RV1 conclusions

- **epistemic_search**: primary `STANCE_ERROR`, secondary ['CONTROLLER_ERROR']
  - rationale: Evidence from the unrelated 2012 Orange Bowl was treated as support/contradiction for the target 2015 game, creating a false conflict that consumed the search budget.
- **premise_only**: primary `DECOMPOSITION_ERROR`, secondary ['RETRIEVAL_ERROR']
  - rationale: The proof contains no concrete game-date fact and the premise-only controller searches a meta premise rather than retrieving the 2015 Orange Bowl date.

- decomposition judged semantically correct: NO; unnecessary premises: YES

### Case 6 — RV1 conclusions

- **epistemic_search**: primary `DECOMPOSITION_ERROR`, secondary ['STANCE_ERROR']
  - rationale: The answer-bearing aid/gratitude facts were already supported, but unnecessary P3 was required by the AND proof and also received a spurious contradiction.
- **premise_only**: primary `DECOMPOSITION_ERROR`, secondary ['CONTROLLER_ERROR']
  - rationale: The controller repeatedly searches unnecessary P3 even though the first-round documents contain the reason asked by the question.

- decomposition judged semantically correct: YES; unnecessary premises: YES

### Case 8 — RV1 conclusions

- **epistemic_search**: primary `STANCE_ERROR`, secondary none
  - rationale: Evidence about Hugler’s other job titles and an unrelated Edward Noonan was treated as contradiction/support for the shared-office premise, producing a false MIXED state.
- **premise_only**: primary `NO_IDENTIFIED_FAILURE`, secondary none
  - rationale: The generated answer correctly identifies Secretary of Labor and explains Acting versus confirmed service; exact-match mismatch is stylistic.

- decomposition judged semantically correct: YES; unnecessary premises: NO

### Case 12 — RV1 conclusions

- **epistemic_search**: primary `UNCERTAIN`, secondary none
  - rationale: The benchmark asks for place of birth but the retrieved/gold page states only that Oren Moverman is Israeli-American and based in New York; the reference answer “Israeli” appears semantically mismatched to the question.
- **premise_only**: primary `UNCERTAIN`, secondary none
  - rationale: The same benchmark ambiguity prevents a clean attribution of the abstention to the method.

- decomposition judged semantically correct: NO; unnecessary premises: NO

### Case 17 — RV1 conclusions

- **epistemic_search**: primary `STANCE_ERROR`, secondary ['ANSWER_GENERATION_ERROR']
  - rationale: Evidence about Louis V being the son of George I is incorrectly treated as support for George II’s father, and the answer generator then outputs George I.
- **premise_only**: primary `RETRIEVAL_ERROR`, secondary ['CONTROLLER_ERROR']
  - rationale: The retrieved pages do not directly establish George II’s father and repeated search fails to reach the benchmark bridge evidence.

- decomposition judged semantically correct: YES; unnecessary premises: NO

