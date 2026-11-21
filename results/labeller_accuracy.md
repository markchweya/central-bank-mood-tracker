# Labeller accuracy: local models (Ollama)

Reference labels: 200 paragraphs in [validation/labels.csv](../validation/labels.csv), labelled by Claude Opus 5.5 (not by a person) with the same guide the model gets. Rows of each table are reference labels, columns are model labels. Prompts v2 and v3 were tuned on the first 60 rows only; every number below is on the other 140 (test) rows unless marked.

## Summary

| Model, prompt | Stance | Outlook | Stance macro-F1 | Outlook macro-F1 | Policy paragraphs given a stance | Hawk/dove right (sign flips) | Outlook direction right (sign flips) | Directional outlook where reference had none or neutral |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| llama3.2:3b, v1 (all 200 rows) | 22% | 47% | 0.18 | 0.41 | | | | |
| llama3.2:3b, v2 | 81% | 66% | 0.53 | 0.40 | 24 / 34 | 6 / 13 (4) | 9 / 38 (1) | 11 |
| gemma4:latest, v2 | 78% | 70% | 0.45 | 0.50 | 17 / 34 | 4 / 13 (1) | 14 / 38 (1) | 10 |
| llama3.2:3b, v3 | 81% | 61% | 0.55 | 0.52 | 26 / 34 | 5 / 13 (2) | 27 / 38 (4) | 32 |
| **gemma4:latest, v3** | **84%** | **73%** | **0.63** | **0.62** | **30 / 34** | **6 / 13 (1)** | 23 / 38 (**0**) | 17 |

**Choice for the full run: gemma4:latest with prompt v3.** It is best or tied on every column except the last two. llama3.2 v3 finds more outlook directions but gets four of them backwards and adds 32 false ones, which would swamp the index. The v2 prompts add fewer false outlooks (10-11 against 17) but miss most real ones. gemma4 v3 never reverses an outlook, and gives a stance to 30 of 34 policy paragraphs, against 17 with v2.

**What v3 changed:** v2 asked for one "main topic" and both models filed policy-framework paragraphs (minutes, independence, operating systems) as off-topic and skipped outlooks in paragraphs about risks or crises. v3 asks two yes/no questions instead: does the paragraph discuss monetary policy, and does it make a claim about how the economy is doing. It was tuned in two rounds on the 60 dev rows; the first round over-detected outlooks, the second tightened that question.

**Still weak:** only 6 of 13 clearly hawkish or dovish paragraphs get the right direction; most of the rest come out neutral, which dampens the index rather than biasing it. With 13 such paragraphs the estimate is rough. Speed: gemma4 takes about 8-12s a paragraph on this laptop, against about 7s for llama3.2.

## gemma4:latest, v3, test split

```
ollama / gemma4:latest, prompt v3, test split: 140 reference-labelled paragraphs

stance: accuracy 84%, macro-F1 0.63
model      dovish  hawkish  neutral  none
reference                                
dovish          3        0        1     0
hawkish         1        3        4     1
neutral         2        1       15     3
none            1        0        9    96

outlook: accuracy 73%, macro-F1 0.62
model      negative  neutral  none  positive
reference                                   
negative         11        0     6         0
neutral           4        6     2         4
none              4        4    73         5
positive          0        1     8        12
```

## llama3.2:3b, v3, test split

```
ollama / llama3.2:3b, prompt v3, test split: 140 reference-labelled paragraphs

stance: accuracy 81%, macro-F1 0.55
model      dovish  hawkish  neutral  none
reference                                
dovish          2        1        1     0
hawkish         1        3        4     1
neutral         2        1       11     7
none            3        0        6    97

outlook: accuracy 61%, macro-F1 0.52
model      negative  neutral  none  positive
reference                                   
negative         12        0     3         2
neutral           4        4     0         8
none              9       11    55        11
positive          2        1     3        15
```

## gemma4:latest, v2, test split

```
ollama / gemma4:latest, prompt v2, test split: 140 reference-labelled paragraphs

stance: accuracy 78%, macro-F1 0.45
model      dovish  hawkish  neutral  none
reference                                
dovish          1        0        1     2
hawkish         1        3        4     1
neutral         1        2        4    14
none            1        0        4   101

outlook: accuracy 70%, macro-F1 0.50
model      negative  neutral  none  positive
reference                                   
negative          7        0    10         0
neutral           5        3     5         3
none              1        3    81         1
positive          1        1    12         7

```

## llama3.2:3b, v2, test split

```
ollama / llama3.2:3b, prompt v2, test split: 140 reference-labelled paragraphs

stance: accuracy 81%, macro-F1 0.53
model      dovish  hawkish  neutral  none
reference                                
dovish          1        2        0     1
hawkish         2        5        2     0
neutral         3        1        8     9
none            1        0        6    99

outlook: accuracy 66%, macro-F1 0.40
model      negative  neutral  none  positive
reference                                   
negative          4        0    13         0
neutral           4        2     6         4
none              3        2    81         0
positive          1        0    15         5

```

## llama3.2:3b, v1, all rows

```
ollama / llama3.2:3b on 200 reference-labelled paragraphs

stance: accuracy 22%, macro-F1 0.18
model    dovish  hawkish  neutral  none
reference                              
dovish        1        7        2     0
hawkish       2        6        3     0
neutral       0       11       30     0
none         15       31       84     8

outlook: accuracy 47%, macro-F1 0.41
model     negative  neutral  none  positive
reference                                  
negative        23        1     0         3
neutral          9        2     0         9
none            38       16    43        25
positive         3        1     1        26

```
