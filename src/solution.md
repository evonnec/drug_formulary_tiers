## time to execute solution.py: 83.33s ##

(.venv) MacBook-Air:~/Documents/GitHub/data-code-challenge2$ time /opt/homebrew/bin/python3 /Users/evonne/Documents/GitHub/data-code-challenge2/src/solution.py 00022170
Table-1: 
        formulary_id  tier_level_value    rxcui
0           00022169                 5  2548736
1           00022169                 4  2272630
2           00022169                 4  2272622
3           00022169                 4  2272636
4           00022169                 4  2272624
...              ...               ...      ...
1583458     00022169                 5  2178407
1583459     00022169                 5  2548766
1583460     00022169                 5  2548767
1583461     00022169                 5  2548769
1583462     00022169                 5  2548742

[1583463 rows x 3 columns]

Part 3: `formulary_id` = '00022170'

Table-2: 
          formulary_id_target  tier_level_value_target    rxcui formulary_id  tier_level_value
1                    00022169                        5  2548736     00022170                 5
458                  00022170                        5  2548736     00022170                 5
915                  00022171                        5  2548736     00022170                 5
1372                 00022172                        5  2548736     00022170                 5
1829                 00022173                        1  2548736     00022170                 5
...                       ...                      ...      ...          ...               ...
514808255            00022155                        4  2286261     00022170                 4
514808371            00022157                        3  2286261     00022170                 4
514808487            00022159                        4  2286261     00022170                 4
514808603            00022162                        4  2286261     00022170                 4
514808719            00022163                        3  2286261     00022170                 4

[1171546 rows x 5 columns]

table A add tier diff col 
          formulary_id_target  tier_level_value_target    rxcui formulary_id  tier_level_value  tier_difference
1                    00022169                        5  2548736     00022170                 5                0
458                  00022170                        5  2548736     00022170                 5                0
915                  00022171                        5  2548736     00022170                 5                0
1372                 00022172                        5  2548736     00022170                 5                0
1829                 00022173                        1  2548736     00022170                 5               -4
...                       ...                      ...      ...          ...               ...              ...
514808255            00022155                        4  2286261     00022170                 4                0
514808371            00022157                        3  2286261     00022170                 4               -1
514808487            00022159                        4  2286261     00022170                 4                0
514808603            00022162                        4  2286261     00022170                 4                0
514808719            00022163                        3  2286261     00022170                 4               -1

[1171546 rows x 6 columns]

table B add tier diff col 
          formulary_id_target  tier_level_value_target    rxcui formulary_id  tier_level_value  tier_difference
1829                 00022173                        1  2548736     00022170                 5               -4
6856                 00022187                        1  2548736     00022170                 5               -4
8227                 00022191                        2  2548736     00022170                 5               -3
9141                 00022193                        2  2548736     00022170                 5               -3
17367                00022216                        1  2548736     00022170                 5               -4
...                       ...                      ...      ...          ...               ...              ...
514805703            00022587                        3  2286261     00022170                 4               -1
514806399            00022053                        2  2286261     00022170                 4               -2
514806747            00022086                        1  2286261     00022170                 4               -3
514808371            00022157                        3  2286261     00022170                 4               -1
514808719            00022163                        3  2286261     00022170                 4               -1

[635668 rows x 6 columns]

table A drop col 
          formulary_id_target    rxcui formulary_id  tier_difference
1                    00022169  2548736     00022170                0
458                  00022170  2548736     00022170                0
915                  00022171  2548736     00022170                0
1372                 00022172  2548736     00022170                0
1829                 00022173  2548736     00022170               -4
...                       ...      ...          ...              ...
514808255            00022155  2286261     00022170                0
514808371            00022157  2286261     00022170               -1
514808487            00022159  2286261     00022170                0
514808603            00022162  2286261     00022170                0
514808719            00022163  2286261     00022170               -1

[1171546 rows x 4 columns]

table B drop col 
          formulary_id_target    rxcui formulary_id  tier_difference
1829                 00022173  2548736     00022170               -4
6856                 00022187  2548736     00022170               -4
8227                 00022191  2548736     00022170               -3
9141                 00022193  2548736     00022170               -3
17367                00022216  2548736     00022170               -4
...                       ...      ...          ...              ...
514805703            00022587  2286261     00022170               -1
514806399            00022053  2286261     00022170               -2
514806747            00022086  2286261     00022170               -3
514808371            00022157  2286261     00022170               -1
514808719            00022163  2286261     00022170               -1

[635668 rows x 4 columns]

Table-3 for A: 
              tier_difference
formulary_id                 
00022170            -0.864735

Table-3 for B: 
              tier_difference
formulary_id                 
00022170             -1.59372

/opt/homebrew/bin/python3  00022170  75.95s user 83.33s system 38% cpu 6:57.47 total