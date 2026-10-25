# RV2-0 — blind spot-check of the RV1 labels

Reading order: this file (Part 1), then `RV2_0_CASES.md` (Part 2), then
`RV2_0_REVEAL.md`. Record your answers in
`responses.yaml` as you go. This file shows neither the system's nor the
RV1 assessor's stance, on purpose: otherwise your agreement would only measure anchoring.
The RV1 labels came from GPT-5.6 Sol (model-assisted, not human ground truth); this
check is how we find out whether they can be trusted.

## Part 1 — stance items

For each item decide the stance of the **span** toward the **premise**, judging the
premise about the *specific entity/event it names*:
`SUPPORT` (the span establishes it), `CONTRADICT` (the span shows it is false),
`NEUTRAL` (the span says nothing decisive about *this* premise, including when it is
about a different person, game, office, place or time), `UNSURE` (the premise is not
truth-apt or you cannot tell). The context shows where the span sits in the document.

### S01 — case 8

- **Question:** Edward C. Hugger and Alexander Acosta served at appointees for what job?
- **Reference answer:** Secretary of Labor
- **Premise P2:** Determine whether the identified jobs are the same.
- **Document:** *Edward C. Hugler*
- **Span:** “Acting Secretary of Labor”

> Edward Charles "Ed" Hugler (born February 7, 1950) is Deputy Assistant Secretary for Operations in the U.S. Department of Labor's Office of the Assistant Secretary for Administration and Management. That position has been his formal position at the United States Department of Labor since April 2000. However, he served as Acting Secretary of Labor from February 2–24, 2009, when Hilda Solis's nomination by President Barack Obama became bogged down during Senate confirmation hearings. He stepped down from the position when Solis was confirmed and sworn in as Secretary of Labor. Ed Hugler served as Acting Secretary of Labor from January 20, 2017 to April 28, 2017 until when Alexander Acosta was confirmed and sworn into office.

### S02 — case 7

- **Question:** During what years did the railroad that had a station stop in Ringling, Montana operate?
- **Reference answer:** from 1847 until 1980
- **Premise P2:** Establish the year that railroad ceased operating, if it ceased operating.
- **Document:** *Westbridge (LIRR station)*
- **Span:** “Westbridge was out of service on January 1, 1939 and was discontinued as a station stop.”

> Westbridge was a railroad station located on the Main Line of the Long Island Rail Road. It was located on the main line south of Jamaica Avenue. The station opened as a pair of sheltered sheds on June 28, 1916 and a ticket office at street level. The station's original name was High Bridge. Westbridge was out of service on January 1, 1939 and was discontinued as a station stop. However, Westbridge last appeared in an employee timetable on September 18, 1938. In 1916 there was a complaint by the Westbridge Civic Association to have one train in each direction to stop at Westbridge as they do at Forest Hills and Kew Gardens.There are still remnants of this station; at the south end crossing of Jamaica Avenue you can see where the platforms used to be, the concrete footstones are still there and can be seen along the west ...

### S03 — case 21

- **Question:** where is the hotel used in the movie the shining
- **Reference answer:** None
- **Premise P1:** Identify the real-world location or set used for the Overlook Hotel’s interior scenes, including its geographic location.
- **Document:** *https://giggster.com/guide/movie-location/where-was-the-shining-filmed*
- **Span:** “The location used for the exterior of the Overlook Hotel was Timberline Lodge, located on the south face of Mount Hood in Mount Hood National Forest, Clackamas County, Oregon.”

> ... t iconic scenes in The Shining.

Check [Filming Locations](https://giggster.com/book/filming)

Leaving The Overlook Hotel scene in The Shining
-----------------------------------------------

Timberline Lodge, Mount Hood National Forest, Oregon

![Image 7: Leaving The Overlook Hotel scene in The Shining](https://dir.giggster.com/assets/539e7ee2-0da0-4c46-a588-eb0ea33d8a74/539e7ee2-0da0-4c46-a588-eb0ea33d8a74.jpg?fit=cover&width=1600&quality=80)

The location used for the exterior of the Overlook Hotel was Timberline Lodge, located on the south face of Mount Hood in Mount Hood National Forest, Clackamas County, Oregon. The lodge is situated off Timberline Highway, which runs parallel to Highway 26, and can be accessed via West Leg Road. The lodge was built in the 1930s and is still a popular ski resort.

The snowcat scene where Wendy and Danny escape in the film is in front of the resort. It’s a dark and stormy night, perfect for the ending of the movie. Jack is left behind and freezes in the maze outside the hotel. You can hear him yelling, “Wait!” but the au ...

### S04 — case 17

- **Question:** Who is George Ii, Landgrave Of Hesse-Darmstadt's father?
- **Reference answer:** Louis V, Landgrave of Hesse-Darmstadt
- **Premise P1:** Determine the father of the resolved person.
- **Document:** *Louis VI, Landgrave of Hesse-Darmstadt*
- **Span:** “the Landgrave George II of Hesse-Darmstadt”

> Louis VI of Hesse-Darmstadt  (25 January 1630 – 24 April 1678) was Landgrave of Hesse-Darmstadt from 1661 to 1678.He was the eldest of three sons of the Landgrave George II of Hesse-Darmstadt and Sophia Eleonore of Saxony.

### S05 — case 19

- **Question:** Where was the director of film The Foursome born?
- **Reference answer:** Toronto, Ontario
- **Premise P2:** Identify the director of the intended film.
- **Document:** *Dana Blankstein*
- **Span:** “She is a film director”

> Dana Blankstein- Cohen( born March 3, 1981) is the director of the Israeli Academy of Film and Television.She is a film director, and an Israeli culture entrepreneur.

### S06 — case 20

- **Question:** MacBook offers what brand-type of displays that are higher-resolution than other portable computers?
- **Reference answer:** Retina
- **Premise P2:** The display brand-type associated with MacBook is Retina.
- **Document:** *MacBook (Retina)*
- **Span:** “It offers a high-resolution Retina Display”

> The MacBook is a line of Macintosh portable computers introduced in March 2015 by Apple Inc. The MacBook has a similar appearance to the MacBook Air, but is thinner and lighter, and is available in colours called space grey, silver, gold, and rose gold. It offers a high-resolution Retina Display, a Force Touch trackpad, a redesigned keyboard, and only two ports: a headphone jack and a USB 3.1 Type-C port for charging, data transfer and video output.

### S07 — case 5

- **Question:** What is the date played of this college football game at Sun Life Stadium in Miami Gardens, Florida, where Clemson defeated the No. 4 Oklahoma Sooners, 37-17?
- **Reference answer:** December 31, 2015
- **Premise P2:** Clemson defeated the Oklahoma Sooners in the game.
- **Document:** *2012 Orange Bowl*
- **Span:** “The West Virginia Mountaineers defeated the Clemson Tigers by a score of 70–33.”

> The 2012 Discover Orange Bowl was a postseason college football bowl game on Wednesday, January 4, 2012, at Sun Life Stadium in Miami Gardens, Florida. The West Virginia Mountaineers defeated the Clemson Tigers by a score of 70–33. West Virginia tied or broke eight separate team and individual bowl game records, while the combined 69 points West Virginia and Clemson scored in the first half set another new record. The game was part of the 2011–2012 Bowl Championship Series of the 2011 NCAA Division I FBS football season and was the concluding game of the season for both teams.

### S08 — case 8

- **Question:** Edward C. Hugger and Alexander Acosta served at appointees for what job?
- **Reference answer:** Secretary of Labor
- **Premise P2:** Determine whether the identified jobs are the same.
- **Document:** *Edward C. Noonan*
- **Span:** “He was replaced as party chairman by Markham Robinson in July 2008.”

> Edward C. "Ed" Noonan (born Edward Clifford Davis September 25, 1948 in Prescott, Arizona) was the chairman of the American Independent Party. He was replaced as party chairman by Markham Robinson in July 2008. At the same meeting, national affiliation of the party was changed to America's Independent Party, which was the new political party of Alan Keyes. Noonan attended Santa Barbara City College, served four years in the U.S. Army, then attended Sacramento City College, American River College and Sacramento State College. Noonan is married to Patricia Hansen, and they have a son, E. Justin Noonan who ran for California State Treasurer in 2006. He is ...

### S09 — case 5

- **Question:** What is the date played of this college football game at Sun Life Stadium in Miami Gardens, Florida, where Clemson defeated the No. 4 Oklahoma Sooners, 37-17?
- **Reference answer:** December 31, 2015
- **Premise P6:** The target event is a college football game.
- **Document:** *2015 Clemson Tigers football team*
- **Span:** “Clemson defeated the No. 4 Oklahoma Sooners, 37–17, in the 2015 Orange Bowl”

> ... hrough 2008 season. They played their home games at Memorial Stadium, also known as "Death Valley." Clemson competed in the Atlantic Division of the Atlantic Coast Conference. On December 5, 2015, the Tigers won the 2015 ACC Championship Game by defeating the North Carolina Tar Heels, 45–37, capping their first undefeated regular season since winning the national title in 1981. Ranked No. 1 throughout the College Football Playoff (CFP) rankings, Clemson defeated the No. 4 Oklahoma Sooners, 37–17, in the 2015 Orange Bowl to advance to the College Football Playoff National Championship. On January 11, 2016, the No. 2 Alabama Crimson Tide (13–1) defeated the No. 1 Clemson Tigers (14–0) in the 2016 national championship, 45–40. Both Clemson and Alabama finished the season 14–1.

### S10 — case 3

- **Question:** The USS Tortuga was named after the Dry Tortugas, a group of desert coral islets 60 miles west of which city with the motto "One Human Family"?
- **Reference answer:** Key West
- **Premise P3:** The requested answer is the name of that city.
- **Document:** *USS Tortuga (LSD-26)*
- **Span:** “Key West, Florida”

> USS "Tortuga" (LSD-26) was a "Casa Grande"-class dock landing ship in the United States Navy. She was the first Navy ship to be named for the Dry Tortugas, a group of desert coral islets 60 miles west of Key West, Florida, which were discovered in 1513 by Spanish explorer Ponce de Leon.

### S11 — case 20

- **Question:** MacBook offers what brand-type of displays that are higher-resolution than other portable computers?
- **Reference answer:** Retina
- **Premise P1:** The display type associated with MacBook has higher resolution than displays on other portable computers.
- **Document:** *Retina Display*
- **Span:** “Retina Display is a brand name used by Apple for its series of IPS panel displays that have a higher pixel density than traditional displays.”

> Retina Display is a brand name used by Apple for its series of IPS panel displays that have a higher pixel density than traditional displays. Apple has applied to register the term "Retina" as a trademark in regard to computers and mobile devices with the United States Patent and Trademark Office, Canadian Intellectual Property Office, and in Jamaica. On November 27, 2012 the US Patent and Trademark office approved Apple's application and "Retina" is now a registered trademark for computer equipment.

### S12 — case 8

- **Question:** Edward C. Hugger and Alexander Acosta served at appointees for what job?
- **Reference answer:** Secretary of Labor
- **Premise P3:** Identify the job for which Edward C. Hugger served as an appointee.
- **Document:** *Edward C. Hugler*
- **Span:** “he served as Acting Secretary of Labor”

> Edward Charles "Ed" Hugler (born February 7, 1950) is Deputy Assistant Secretary for Operations in the U.S. Department of Labor's Office of the Assistant Secretary for Administration and Management. That position has been his formal position at the United States Department of Labor since April 2000. However, he served as Acting Secretary of Labor from February 2–24, 2009, when Hilda Solis's nomination by President Barack Obama became bogged down during Senate confirmation hearings. He stepped down from the position when Solis was confirmed and sworn in as Secretary of Labor. Ed Hugler served as Acting Secretary of Labor from January 20, 2017 to April 28, 2017 until when Alexander Acosta was confirmed and sworn into office.

### S13 — case 8

- **Question:** Edward C. Hugger and Alexander Acosta served at appointees for what job?
- **Reference answer:** Secretary of Labor
- **Premise P2:** Determine whether the identified jobs are the same.
- **Document:** *Edward C. Hugler*
- **Span:** “Deputy Assistant Secretary for Operations in the U.S. Department of Labor's Office of the Assistant Secretary for Administration and Management”

> Edward Charles "Ed" Hugler (born February 7, 1950) is Deputy Assistant Secretary for Operations in the U.S. Department of Labor's Office of the Assistant Secretary for Administration and Management. That position has been his formal position at the United States Department of Labor since April 2000. However, he served as Acting Secretary of Labor from February 2–24, 2009, when Hilda Solis's nomination by President Barack Obama became bogged down during Senate confirmation hearings. He stepped down from the position when Solis was confirmed and sworn in as Secretary of Labor. Ed Hugler served as Acting Secretary of Labor from January 20, 20 ...

### S14 — case 10

- **Question:** Which film has the director who is older, Divorce In Montevideo or The Western Whirlwind?
- **Reference answer:** Divorce In Montevideo
- **Premise P7:** What is the birth date of the director of Divorce in Montevideo?
- **Document:** *Manuel Romero*
- **Span:** “Manuel Romeo (September 21, 1891 – October 3, 1954 in Buenos Aires)”

> Manuel Romeo (September 21, 1891 – October 3, 1954 in Buenos Aires) was an Argentine film director, screenwriter, dramatist and score composer, and one of the influential directors in the cinema of Argentina of the classic era.He directed and wrote over films between 1931 and 1951 even composing the musical scores for several.He was a pioneer of Variety Theatre, and one of the few tango lyrical writers that has reached timeless classical success.When he was a teenager, he began his journalist job in the Magacine ...

### S15 — case 7

- **Question:** During what years did the railroad that had a station stop in Ringling, Montana operate?
- **Reference answer:** from 1847 until 1980
- **Premise P1:** Establish the year that railroad began operating.
- **Document:** *Quogue (LIRR station)*
- **Span:** “the station was built around June, 1875”

> Quogue was a station stop along the Montauk Branch of the Long Island Rail Road and the station was built around June, 1875. During construction the station was moved by the village "on a Sunday morning" from its original and current location to a location on Old Depot Road. The second depot was built around 1882 and later was moved to a private location around 1905. The third depot was built around 1905 and at some point was elevated for the bridge over the former New York State Route 113. The station house was razed around April, 1964 but the station stop itself co ...

### S16 — case 3

- **Question:** The USS Tortuga was named after the Dry Tortugas, a group of desert coral islets 60 miles west of which city with the motto "One Human Family"?
- **Reference answer:** Key West
- **Premise P4:** The islets are described as 60 miles west of a city.
- **Document:** *USS Tortuga (LSD-26)*
- **Span:** “a group of desert coral islets 60 miles west of Key West, Florida”

> USS "Tortuga" (LSD-26) was a "Casa Grande"-class dock landing ship in the United States Navy. She was the first Navy ship to be named for the Dry Tortugas, a group of desert coral islets 60 miles west of Key West, Florida, which were discovered in 1513 by Spanish explorer Ponce de Leon.

### S17 — case 10

- **Question:** Which film has the director who is older, Divorce In Montevideo or The Western Whirlwind?
- **Reference answer:** Divorce In Montevideo
- **Premise P7:** What is the birth date of the director of Divorce in Montevideo?
- **Document:** *Divorce in Montevideo*
- **Span:** “directed by Manuel Romero”

> Divorce in Montevideo is a Argentine comedy film directed by Manuel Romero.The tango film premiered in Buenos Aires and starred Enrique Serrano.

### S18 — case 6

- **Question:** Why does the City of Boston get their christmas tree from Ainslee Glen Nova Scotia?
- **Reference answer:** for their assistance after the 1917 Halifax Explosion
- **Premise P3:** Establish whether Ainslee Glen was the source or donor of the particular tree, and why it was selected.
- **Document:** *Boston Christmas Tree*
- **Span:** “it has been given to the people of Boston by the people of Nova Scotia”

> The Boston Christmas Tree is the City of Boston, Massachusetts' official Christmas tree. A tree has been lit each year since 1941, and since 1971 it has been given to the people of Boston by the people of Nova Scotia in thanks for their assistance after the 1917 Halifax Explosion. The tree is lit in the Boston Common throughout the Christmas season.

### S19 — case 7

- **Question:** During what years did the railroad that had a station stop in Ringling, Montana operate?
- **Reference answer:** from 1847 until 1980
- **Premise P2:** Establish the year that railroad ceased operating, if it ceased operating.
- **Document:** *Westbridge (LIRR station)*
- **Span:** “Westbridge used to operate as a freight station after its closing.”

> ... stbridge last appeared in an employee timetable on September 18, 1938. In 1916 there was a complaint by the Westbridge Civic Association to have one train in each direction to stop at Westbridge as they do at Forest Hills and Kew Gardens.There are still remnants of this station; at the south end crossing of Jamaica Avenue you can see where the platforms used to be, the concrete footstones are still there and can be seen along the westbound side. Westbridge used to operate as a freight station after its closing. There is currently some old wood which lays alongside the outer edge of the roadbed which is most likely from the Wooden shelter that used to be on the platform. Some current maps and atlases still have Westbridge listed as a freight only station to this day; quite to the contrary that freight is no longer used here. While this station was open, one could see BMT trains on the BMT Jamaica Line overhead from the main line tracks when the trains r ...

### S20 — case 11

- **Question:** Which film has the director born earlier, The Mexican Spitfire'S Baby or Chhalia?
- **Reference answer:** The Mexican Spitfire'S Baby
- **Premise P3:** T_A is earlier than T_B.
- **Document:** *Mexican Spitfire at Sea*
- **Span:** “released on March 13, 1942”

> Mexican Spitfire at Sea is a 1942 American comedy film directed by Leslie Goodwins and written by Charles E. Roberts and Jerome Cady.It is the sequel to the 1941 film" The Mexican Spitfire's Baby".The film stars Lupe Vélez, Leon Errol, Charles' Buddy' Rogers, ZaSu Pitts, Elisabeth Risdon and Florence Bates.The film was released on March 13, 1942, by RKO Pictures.

### S21 — case 5

- **Question:** What is the date played of this college football game at Sun Life Stadium in Miami Gardens, Florida, where Clemson defeated the No. 4 Oklahoma Sooners, 37-17?
- **Reference answer:** December 31, 2015
- **Premise P1:** The date on which the matching game was played is the requested answer.
- **Document:** *2012 Orange Bowl*
- **Span:** “The 2012 Discover Orange Bowl was a postseason college football bowl game on Wednesday, January 4, 2012, at Sun Life Stadium in Miami Gardens, Florida.”

> The 2012 Discover Orange Bowl was a postseason college football bowl game on Wednesday, January 4, 2012, at Sun Life Stadium in Miami Gardens, Florida. The West Virginia Mountaineers defeated the Clemson Tigers by a score of 70–33. West Virginia tied or broke eight separate team and individual bowl game records, while the combined 69 points West Virginia and Clemson scored in the first half set another new record. The game was part of the 2011–2012 Bowl Championship Series of the 2011 NCAA Division I FBS football season and was the concluding game of the season for both teams.

### S22 — case 7

- **Question:** During what years did the railroad that had a station stop in Ringling, Montana operate?
- **Reference answer:** from 1847 until 1980
- **Premise P2:** Establish the year that railroad ceased operating, if it ceased operating.
- **Document:** *Quogue (LIRR station)*
- **Span:** “the station stop itself continued to operate until March 16, 1998.”

> ... as built around June, 1875. During construction the station was moved by the village "on a Sunday morning" from its original and current location to a location on Old Depot Road. The second depot was built around 1882 and later was moved to a private location around 1905. The third depot was built around 1905 and at some point was elevated for the bridge over the former New York State Route 113. The station house was razed around April, 1964 but the station stop itself continued to operate until March 16, 1998. This station, along with nine others around that time were closed due to low ridership, which did not make it very cost-effective to build high-level platforms to support the new C3 railcars the LIRR was procuring at the time.

### S23 — case 19

- **Question:** Where was the director of film The Foursome born?
- **Reference answer:** Toronto, Ontario
- **Premise P3:** Determine the birthplace of that director.
- **Document:** *Dana Blankstein*
- **Span:** “Dana Blankstein- Cohen( born March 3, 1981) is the director of the Israeli Academy of Film and Television.”

> Dana Blankstein- Cohen( born March 3, 1981) is the director of the Israeli Academy of Film and Television.She is a film director, and an Israeli culture entrepreneur.

### S24 — case 5

- **Question:** What is the date played of this college football game at Sun Life Stadium in Miami Gardens, Florida, where Clemson defeated the No. 4 Oklahoma Sooners, 37-17?
- **Reference answer:** December 31, 2015
- **Premise P6:** The target event is a college football game.
- **Document:** *2015 Clemson Tigers football team*
- **Span:** “On December 5, 2015, the Tigers won the 2015 ACC Championship Game by defeating the North Carolina Tar Heels, 45–37”

> The 2015 Clemson Tigers football team represented Clemson University in the 2015 NCAA Division I FBS football season. The Tigers were led by head coach Dabo Swinney in his seventh full year and eighth overall since taking over midway through 2008 season. They played their home games at Memorial Stadium, also known as "Death Valley." Clemson competed in the Atlantic Division of the Atlantic Coast Conference. On December 5, 2015, the Tigers won the 2015 ACC Championship Game by defeating the North Carolina Tar Heels, 45–37, capping their first undefeated regular season since winning the national title in 1981. Ranked No. 1 throughout the College Football Playoff (CFP) rankings, Clemson defeated the No. 4 Oklahoma Sooners, 37–17, in the 2015 Orange Bowl to advance to the College Football Playoff National Championship. On January 11, 2016, the No. 2 Alabama Crimson Tide (13–1) defeated the No. 1 Clemson Tigers (14–0) in the 2016 national championship, 45–40. Both Cl ...

### S25 — case 4

- **Question:** What professional dancers twice turned on a lights festival taking place on the Fylde Coast in Lancashire?
- **Reference answer:** Audrey Mossom
- **Premise P1:** Identify the lights festival held on the Fylde Coast in Lancashire.
- **Document:** *Audrey Mossom*
- **Span:** “Blackpool Illuminations, an annual lights festival in Blackpool.”

> Elsie Audrey Mossom (3 September 1920, Preston – 1 September 2009, Hastings) was an English teen celebrity and later a professional dancer. She was crowned the 10th Railway Queen of Great Britain at the Railway Carnival and Pageant held at Belle Vue, Manchester in August 1935 when she was 15 years old. Later in 1935, she turned on the Blackpool Illuminations, an annual lights festival in Blackpool. 50 years later, she again turned on the Blackpool Illuminations.

### S26 — case 12

- **Question:** What is the place of birth of the director of film Time Out Of Mind (2014 Film)?
- **Reference answer:** Israeli
- **Premise P3:** The place of birth of that director is identified.
- **Document:** *Time Out of Mind (2014 film)*
- **Span:** “written and directed by Oren Moverman”

> Time Out of Mind is a 2014 American drama film written and directed by Oren Moverman and starring Richard Gere, Jena Malone, Ben Vereen, Kyra Sedgwick, and Steve Buscemi.It was released on September 11, 2015, by IFC Films.

### S27 — case 11

- **Question:** Which film has the director born earlier, The Mexican Spitfire'S Baby or Chhalia?
- **Reference answer:** The Mexican Spitfire'S Baby
- **Premise P5:** T_B is earlier than T_A.
- **Document:** *Mexican Spitfire at Sea*
- **Span:** “The film was released on March 13, 1942, by RKO Pictures.”

> Mexican Spitfire at Sea is a 1942 American comedy film directed by Leslie Goodwins and written by Charles E. Roberts and Jerome Cady.It is the sequel to the 1941 film" The Mexican Spitfire's Baby".The film stars Lupe Vélez, Leon Errol, Charles' Buddy' Rogers, ZaSu Pitts, Elisabeth Risdon and Florence Bates.The film was released on March 13, 1942, by RKO Pictures.

### S28 — case 6

- **Question:** Why does the City of Boston get their christmas tree from Ainslee Glen Nova Scotia?
- **Reference answer:** for their assistance after the 1917 Halifax Explosion
- **Premise P3:** Establish whether Ainslee Glen was the source or donor of the particular tree, and why it was selected.
- **Document:** *Ainslie Glen, Nova Scotia*
- **Span:** “In 2016, a tree on Crown Lands was chosen to become the Boston Christmas Tree.”

> Ainslie Glen (Scottish Gaelic: "Gleann nam Màgan" ) is a small community in the Canadian province of Nova Scotia, located in Inverness County on Cape Breton Island. In 2016, a tree on Crown Lands was chosen to become the Boston Christmas Tree.

### S29 — case 11

- **Question:** Which film has the director born earlier, The Mexican Spitfire'S Baby or Chhalia?
- **Reference answer:** The Mexican Spitfire'S Baby
- **Premise P4:** The director of The Mexican Spitfire's Baby is D_A.
- **Document:** *The Mexican Spitfire's Baby*
- **Span:** “directed by Leslie Goodwins”

> The Mexican Spitfire's Baby is a 1941 American comedy film directed by Leslie Goodwins and written by Charles E. Roberts and Jerome Cady.It is the sequel to the 1940 film" Mexican Spitfire Out West".The film stars Lupe Vélez, Leon Errol, Charles' Buddy' Rogers, ZaSu Pitts, Elisabeth Risdon and Fritz Feld.The film was released on November 28, 1941, by RKO Pictures.

### S30 — case 14

- **Question:** Which film has the director born later, Kaalapani or Strictly Modern?
- **Reference answer:** Kaalapani
- **Premise P3:** The birth date of Kaalapani's director is established.
- **Document:** *Kaalapani*
- **Span:** “co-written and directed by Priyadarshan”

> Kaalapani is a 1996 Indian Malayalam- language epic historical period drama film co-written and directed by Priyadarshan.Set in 1915, the film focuses on the lives of Indian freedom fighters incarcerated in the Cellular Jail( or" Kālā Pānī") in Andaman and Nicobar Islands during the British Raj.The ensemble cast includes Mohanlal, Prabhu Ganesan, Tabu, Amrish Puri, Nedumudi Venu, Sreenivasan, Tinnu Anand, Annu Kapoor, Alex Draper, Sankaradi, and Vineeth.The film was produced by Mohanlal for Pranavam Arts in association with R. Mohan's Shogun Films.The film is abou ...

