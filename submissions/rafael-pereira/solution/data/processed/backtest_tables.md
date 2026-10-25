# Tabelas do backtest

Gerado por `python -m scorer.validate`; não editar à mão.

## Critério pré-registrado, corte a corte

| Corte | Score | Valor | Recência | Aleatório (média) | Aleatório (p95) | Margem sobre o melhor baseline | Vence os 4? |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | 61,3% | 48,6% | 27,7% | 20,0% | 23,4% | +12,6 pp | sim |
| 31/07/2017 | 57,9% | 48,7% | 12,8% | 20,1% | 23,4% | +9,2 pp | sim |
| 31/08/2017 | 60,7% | 48,2% | 31,6% | 19,8% | 23,0% | +12,5 pp | sim |
| 30/09/2017 | 64,8% | 47,1% | 46,8% | 20,3% | 24,4% | +17,7 pp | sim |

Receita capturada no top 20%. Empate é diferença de até 0,01 e não vence. Resultado: **PASSOU**.
- curva platô + queda: passou; receita média do score nos cortes: 61,1%.

## Backtest: corte × método

| Corte | Método | AUC | Ganhos capturados no top 20% | Receita capturada no top 20% |
| :--- | :--- | ---: | ---: | ---: |
| 30/06/2017 | Score (valor esperado) | 0,66 | 25,8% | **61,3%** |
| 30/06/2017 | Ordenar por valor | 0,48 | 19,6% | 48,6% |
| 30/06/2017 | Mais recentes primeiro | **0,73** | **29,3%** | 27,7% |
| 30/06/2017 | Aleatório (média de sorteios) | 0,50 (0,47 a 0,52) | 19,9% (18,1% a 21,8%) | 20,0% (16,8% a 23,4%) |
| 30/06/2017 | Só a chance (diagnóstico) | 0,70 | 26,9% | 26,8% |
| 31/07/2017 | Score (valor esperado) | **0,64** | **25,1%** | **57,9%** |
| 31/07/2017 | Ordenar por valor | 0,51 | 20,5% | 48,7% |
| 31/07/2017 | Mais recentes primeiro | 0,58 | 12,2% | 12,8% |
| 31/07/2017 | Aleatório (média de sorteios) | 0,50 (0,48 a 0,52) | 20,0% (18,1% a 22,0%) | 20,1% (17,2% a 23,4%) |
| 31/07/2017 | Só a chance (diagnóstico) | 0,64 | 24,7% | 24,6% |
| 31/08/2017 | Score (valor esperado) | 0,63 | 26,4% | **60,7%** |
| 31/08/2017 | Ordenar por valor | 0,50 | 20,4% | 48,2% |
| 31/08/2017 | Mais recentes primeiro | **0,66** | **34,0%** | 31,6% |
| 31/08/2017 | Aleatório (média de sorteios) | 0,50 (0,48 a 0,52) | 19,9% (18,1% a 22,0%) | 19,8% (16,4% a 23,0%) |
| 31/08/2017 | Só a chance (diagnóstico) | 0,66 | 25,7% | 25,8% |
| 30/09/2017 | Score (valor esperado) | 0,65 | 27,9% | **64,8%** |
| 30/09/2017 | Ordenar por valor | 0,48 | 19,4% | 47,1% |
| 30/09/2017 | Mais recentes primeiro | **0,83** | **43,6%** | 46,8% |
| 30/09/2017 | Aleatório (média de sorteios) | 0,50 (0,48 a 0,53) | 20,2% (17,5% a 22,5%) | 20,3% (16,1% a 24,4%) |
| 30/09/2017 | Só a chance (diagnóstico) | 0,70 | 28,6% | 28,6% |

Em negrito, o melhor entre score, valor, recência e aleatório. No aleatório, entre parênteses, o intervalo de p5 a p95 de 200 sorteios.

## Média dos cortes

| Método | AUC | Ganhos capturados no top 20% | Receita capturada no top 20% |
| :--- | ---: | ---: | ---: |
| Score (valor esperado) | 0,64 | 26,3% | 61,1% |
| Ordenar por valor | 0,49 | 20,0% | 48,1% |
| Mais recentes primeiro | 0,70 | 29,8% | 29,7% |
| Aleatório (média de sorteios) | 0,50 | 20,0% | 20,0% |
| Só a chance (diagnóstico) | 0,67 | 26,5% | 26,5% |

Média simples dos 4 cortes. Brier da chance: 0,185 contra 0,226 da taxa média de treino (log-loss 0,524 contra 0,644), sobre ganhos em 90 dias.

## Categorias por corte

| Corte | Lista | Deals | Ganhos até 31/12/2017 | Receita ganha | % da receita | Valor de tabela | Valor esperado |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | Foque | 1.229 | 48,5% | US$ 1.408.140 | 97,7% | US$ 3.052.647 | US$ 1.497.018 |
| 30/06/2017 | Reative | 308 | 4,2% | US$ 33.310 | 2,3% | US$ 754.694 | US$ 63.434 |
| 30/06/2017 | Limpe | 149 | 0,0% | US$ 0 | 0,0% | US$ 409.466 | US$ 1 |
| 31/07/2017 | Foque | 1.794 | 40,5% | US$ 1.754.307 | 97,8% | US$ 4.314.984 | US$ 2.025.293 |
| 31/07/2017 | Reative | 188 | 8,0% | US$ 39.383 | 2,2% | US$ 486.553 | US$ 52.991 |
| 31/07/2017 | Limpe | 275 | 0,0% | US$ 0 | 0,0% | US$ 697.655 | US$ 28 |
| 31/08/2017 | Foque | 1.600 | 36,2% | US$ 1.322.400 | 91,2% | US$ 3.656.630 | US$ 1.681.256 |
| 31/08/2017 | Reative | 257 | 22,6% | US$ 127.744 | 8,8% | US$ 693.697 | US$ 177.540 |
| 31/08/2017 | Limpe | 408 | 0,0% | US$ 0 | 0,0% | US$ 1.038.920 | US$ 12.532 |
| 30/09/2017 | Foque | 1.684 | 33,2% | US$ 1.251.928 | 100,0% | US$ 3.831.024 | US$ 1.746.930 |
| 30/09/2017 | Reative | 195 | 0,0% | US$ 0 | 0,0% | US$ 559.328 | US$ 97.310 |
| 30/09/2017 | Limpe | 530 | 0,0% | US$ 0 | 0,0% | US$ 1.373.138 | US$ 5.919 |

## Calibração

| Corte | Deals | Brier do modelo | Brier da constante | Log-loss do modelo | Log-loss da constante |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | 1.686 | 0,189 | 0,239 | 0,529 | 0,672 |
| 31/07/2017 | 2.257 | 0,199 | 0,234 | 0,560 | 0,661 |
| 31/08/2017 | 2.265 | 0,184 | 0,220 | 0,526 | 0,634 |
| 30/09/2017 | 2.409 | 0,169 | 0,209 | 0,483 | 0,611 |

| Corte | Idade | Deals | Chance média do modelo | Ganhos em 90 dias (observado) |
| :--- | :--- | ---: | ---: | ---: |
| 30/06/2017 | 0 a 30 dias | 692 | 49,0% | 51,2% |
| 30/06/2017 | 31 a 60 dias | 454 | 49,0% | 44,5% |
| 30/06/2017 | 61 a 90 dias | 190 | 32,9% | 21,6% |
| 30/06/2017 | 91 a 120 dias | 133 | 0,8% | 0,0% |
| 30/06/2017 | 121 a 150 dias | 103 | 0,0% | 0,0% |
| 30/06/2017 | 151 dias ou mais | 114 | 0,0% | 0,0% |
| 31/07/2017 | 0 a 30 dias | 720 | 46,9% | 24,3% |
| 31/07/2017 | 31 a 60 dias | 522 | 46,9% | 53,8% |
| 31/07/2017 | 61 a 90 dias | 461 | 46,9% | 45,6% |
| 31/07/2017 | 91 a 120 dias | 198 | 30,6% | 22,7% |
| 31/07/2017 | 121 a 150 dias | 133 | 0,3% | 0,0% |
| 31/07/2017 | 151 dias ou mais | 223 | 0,0% | 0,0% |
| 31/08/2017 | 0 a 30 dias | 662 | 46,0% | 29,2% |
| 31/08/2017 | 31 a 60 dias | 587 | 46,0% | 21,3% |
| 31/08/2017 | 61 a 90 dias | 317 | 46,0% | 51,7% |
| 31/08/2017 | 91 a 120 dias | 211 | 34,1% | 32,2% |
| 31/08/2017 | 121 a 150 dias | 128 | 8,7% | 2,3% |
| 31/08/2017 | 151 dias ou mais | 360 | 0,7% | 0,0% |
| 30/09/2017 | 0 a 30 dias | 679 | 45,6% | 48,0% |
| 30/09/2017 | 31 a 60 dias | 545 | 45,6% | 33,8% |
| 30/09/2017 | 61 a 90 dias | 460 | 45,6% | 6,7% |
| 30/09/2017 | 91 a 120 dias | 118 | 25,4% | 0,0% |
| 30/09/2017 | 121 a 150 dias | 123 | 4,6% | 0,0% |
| 30/09/2017 | 151 dias ou mais | 484 | 0,2% | 0,0% |

## Bootstrap

| Corte | Score menos valor | Score menos recência |
| :--- | ---: | ---: |
| 30/06/2017 | +12,6 pp (IC +9,6 pp a +15,8 pp) | +33,6 pp (IC +26,9 pp a +40,8 pp) |
| 31/07/2017 | +9,2 pp (IC +6,9 pp a +11,7 pp) | +45,1 pp (IC +39,5 pp a +50,5 pp) |
| 31/08/2017 | +12,5 pp (IC +9,4 pp a +15,2 pp) | +29,1 pp (IC +22,4 pp a +35,1 pp) |
| 30/09/2017 | +17,7 pp (IC +14,9 pp a +21,0 pp) | +17,9 pp (IC +10,4 pp a +25,3 pp) |

Diferença na receita capturada no top 20%, em pontos percentuais; IC de 2,5% a 97,5% por 1.000 reamostragens dos deals do corte (semente 0).

## Foque por idade

| Corte | Idade (dentro do Foque do corte) | Deals | Chance do modelo | Ganhos em 90 dias (observado) |
| :--- | :--- | ---: | ---: | ---: |
| 30/06/2017 | 0 a 30 dias | 692 | 49,0% | 51,2% |
| 30/06/2017 | 31 a 60 dias | 454 | 49,0% | 44,5% |
| 30/06/2017 | 61 dias ou mais | 83 | 49,0% | 33,7% |
| 31/07/2017 | 0 a 30 dias | 720 | 46,9% | 24,3% |
| 31/07/2017 | 31 a 60 dias | 522 | 46,9% | 53,8% |
| 31/07/2017 | 61 dias ou mais | 552 | 46,9% | 43,5% |
| 31/08/2017 | 0 a 30 dias | 662 | 46,0% | 29,2% |
| 31/08/2017 | 31 a 60 dias | 587 | 46,0% | 21,3% |
| 31/08/2017 | 61 dias ou mais | 351 | 46,0% | 50,4% |
| 30/09/2017 | 0 a 30 dias | 679 | 45,6% | 48,0% |
| 30/09/2017 | 31 a 60 dias | 545 | 45,6% | 33,8% |
| 30/09/2017 | 61 dias ou mais | 460 | 45,6% | 6,7% |

| Corte | 61 dias ou mais menos 0 a 30 dias | IC de 2,5% a 97,5% |
| :--- | ---: | ---: |
| 30/06/2017 | -17,4 pp | -27,8 pp a -6,9 pp |
| 31/07/2017 | +19,2 pp | +14,1 pp a +24,4 pp |
| 31/08/2017 | +21,3 pp | +15,1 pp a +27,4 pp |
| 30/09/2017 | -41,3 pp | -45,8 pp a -36,8 pp |

Foque de hoje (126 deals) por idade: 0 a 30 dias: 18, 31 a 60 dias: 39, 61 dias ou mais: 69.

## Sensibilidades

**Primeira foto de treino em 28/02/2017**

| Corte | Joelho (foto de 28/02) | Joelho (principal) | Linhas de treino | AUC | Ganhos no top 20% | Receita no top 20% | Receita vs. principal |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | 125 | 70 | 2.515 | 0,56 | 22,2% | 53,9% | -7,4 pp |
| 31/07/2017 | 100 | 100 | 4.133 | 0,61 | 25,1% | 57,9% | +0,1 pp |
| 31/08/2017 | 120 | 95 | 5.668 | 0,63 | 26,1% | 60,1% | -0,6 pp |
| 30/09/2017 | 95 | 90 | 7.354 | 0,64 | 27,4% | 64,0% | -0,7 pp |

Com a primeira foto em 28/02/2017 o critério passaria; receita média do score: 59,0%.

**Só deals resolvidos (fechados até 31/12/2017)**

| Corte | Abertos no corte | Resolvidos até 31/12 | Ainda abertos em 31/12 | Desses, com idade em 31/12 dentro do limite de Limpe | Receita no top 20%: score / valor / recência / aleatório | AUC: score / valor / recência |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | 1.686 | 970 | 716 | 0 | 49,7% / 49,9% / 17,7% / 19,9% | 0,49 / 0,49 / 0,50 |
| 31/07/2017 | 2.257 | 1.139 | 1.118 | 0 | 48,5% / 48,8% / 19,9% / 19,9% | 0,51 / 0,51 / 0,53 |
| 31/08/2017 | 2.265 | 893 | 1.372 | 81 | 48,6% / 49,1% / 17,0% / 19,9% | 0,49 / 0,50 / 0,44 |
| 30/09/2017 | 2.409 | 935 | 1.474 | 183 | 48,2% / 48,2% / 19,4% / 19,8% | 0,48 / 0,48 / 0,50 |

## Auditoria

**Modelo ajustado com o futuro (VAZADO; nunca é resultado)**

| Corte | Rótulo | Joelho do modelo vazado | AUC vazado | Receita vazada | AUC honesto | Receita honesta | Receita: vazado menos honesto |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | VAZADO | 95 | 0,59 | 57,7% | 0,66 | 61,3% | -3,6 pp |
| 31/07/2017 | VAZADO | 95 | 0,63 | 57,6% | 0,64 | 57,9% | -0,3 pp |
| 31/08/2017 | VAZADO | 95 | 0,64 | 60,4% | 0,63 | 60,7% | -0,2 pp |
| 30/09/2017 | VAZADO | 95 | 0,66 | 64,4% | 0,65 | 64,8% | -0,4 pp |

**`has_account` sozinho (proibido como variável)**

| Corte | Com conta | Sem conta | AUC de `has_account` sozinho | Ganhos depois (com conta) | Ganhos depois (sem conta) | Ganhos entre os sem conta |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | 1.202 | 484 | 0,72 | 50,7% | 0,0% | 0 |
| 31/07/2017 | 1.497 | 760 | 0,75 | 49,6% | 0,0% | 0 |
| 31/08/2017 | 1.331 | 934 | 0,79 | 47,9% | 0,0% | 0 |
| 30/09/2017 | 1.401 | 1.008 | 0,77 | 39,9% | 0,0% | 0 |

## Atributos

Δ log-loss negativo é melhora (log-loss de 90 dias, contra a curva só de idade no mesmo subconjunto).

| Atributo | Subconjunto | Níveis | Δ log-loss 30/06/2017 | Δ log-loss 31/07/2017 | Δ log-loss 31/08/2017 | Δ log-loss 30/09/2017 | Melhora em todos? |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| produto | todos os deals | 7 | 0,0060 | 0,0017 | -0,0003 | 0,0007 | não |
| região | todos os deals | 3 | -0,0158 | 0,0321 | 0,0596 | 0,0645 | não |
| setor | só deals com conta | 10 | 0,0061 | 0,0039 | 0,0029 | 0,0028 | não |
| porte | só deals com conta | 3 | -0,0007 | -0,0004 | -0,0001 | 0,0004 | não |

| Atributo | Subconjunto | Níveis | Δ receita top 20% 30/06/2017 | Δ receita top 20% 31/07/2017 | Δ receita top 20% 31/08/2017 | Δ receita top 20% 30/09/2017 | Não piora em nenhum? | Entra? |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| produto | todos os deals | 7 | -0,5 pp | +0,2 pp | -0,3 pp | -0,1 pp | não | não |
| região | todos os deals | 3 | +2,5 pp | -4,7 pp | -4,2 pp | -6,1 pp | não | não |
| setor | só deals com conta | 10 | -0,8 pp | -0,8 pp | +0,2 pp | -0,3 pp | não | não |
| porte | só deals com conta | 3 | +1,3 pp | +0,8 pp | +0,0 pp | -0,1 pp | não | não |

Diagnóstico, que não decide: o mesmo Δ log-loss medido dentro da amostra de treino.

| Atributo | Subconjunto | Δ log-loss no treino 30/06/2017 | Δ log-loss no treino 31/07/2017 | Δ log-loss no treino 31/08/2017 | Δ log-loss no treino 30/09/2017 |
| :--- | :--- | ---: | ---: | ---: | ---: |
| produto | todos os deals | -0,0057 | -0,0030 | -0,0006 | -0,0004 |
| região | todos os deals | -0,0191 | -0,0237 | -0,0305 | -0,0288 |
| setor | só deals com conta | -0,0048 | -0,0038 | -0,0030 | -0,0018 |
| porte | só deals com conta | -0,0003 | -0,0002 | -0,0004 | -0,0005 |

## Modelos por corte

| Modelo ajustado até | Joelho (dias) | Chance de deal novo | Inclinação por 30 dias | Meia-vida depois do joelho (dias) | Limite de Limpe (dias) | Fotos | Linhas de treino | Taxa base de treino |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | 70 | 49,0% | -4,71 | 6,9 | 138 | 1 | 1.330 | 45,8% |
| 31/07/2017 | 100 | 46,9% | -5,60 | 5,7 | 138 | 2 | 2.948 | 45,0% |
| 31/08/2017 | 95 | 46,0% | -1,72 | 18,3 | 138 | 3 | 4.483 | 43,3% |
| 30/09/2017 | 90 | 45,6% | -1,96 | 16,0 | 138 | 4 | 6.169 | 41,2% |
| 31/12/2017 (hoje) | 95 | 39,9% | -2,59 | 11,3 | 138 | 7 | 13.100 | 33,2% |

## Hoje

| Lista | Regra | Deals | Valor de tabela | Valor esperado |
| :--- | :--- | ---: | ---: | ---: |
| Foque | idade até 95 dias | 126 | US$ 300.790 | US$ 119.977 |
| Reative | 96 a 138 dias | 172 | US$ 392.775 | US$ 45.854 |
| Limpe | mais de 138 dias | 1.291 | US$ 3.198.664 | US$ 5.717 |
| Qualifique | Prospecting (sem data) | 500 | US$ 1.073.986 | — |

| Lista | Faixas fixas do briefing (90 e 138 dias) | Joelho e limite aprendidos |
| :--- | ---: | ---: |
| Foque | 110 | 126 |
| Reative | 188 | 172 |
| Limpe | 1.291 | 1.291 |
