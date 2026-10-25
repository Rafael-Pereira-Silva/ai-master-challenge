# Score e validação

Data de referência ("hoje"): 31/12/2017. As tabelas entre marcadores `AUTO` são geradas por `python -m scorer.docs` a partir de `solution/data/processed/backtest_metrics.json` (que `python -m scorer.validate` calcula dos dados). Os números do texto são conferidos contra o mesmo arquivo por `tests/test_docs_numbers.py`. A seção 9 (critério pré-registrado) foi escrita às 16:28 de 25/10/2026, antes de existir o código do backtest; o relato da ordem real está em `process-log/03_bloco-3.md`.

## 1. Resumo

O score responde a uma pergunta: dos negócios abertos hoje, quais valem a próxima hora do vendedor? Para cada negócio, a ferramenta estima a chance de ele ser ganho nos próximos 90 dias olhando só para a idade dele, isto é, há quanto tempo está aberto. A estimativa vem de como negócios da mesma idade se comportaram no passado. Negócios novos têm chances parecidas entre si; depois de uns 95 dias a chance cai rápido, e nenhum negócio do histórico foi ganho depois de 138 dias aberto. A chance multiplicada pelo preço de tabela dá o valor esperado, e o score de 0 a 100 é esse valor numa escala que não deixa o produto mais caro engolir os demais. Para saber se funciona, voltamos no tempo quatro vezes (30/06, 31/07, 31/08 e 30/09/2017), usando em cada uma só o que o CRM sabia naquele dia, e conferimos o que aconteceu depois. Em média, os 20% de negócios no topo do score concentraram 61% da receita que foi de fato ganha em seguida, contra 48% se o time ordenasse só pelo preço e 30% se ordenasse pelos mais recentes; um sorteio daria 20%. O score ficou à frente dos três nos quatro cortes, pelo critério que fixamos antes de olhar o resultado. Há três ressalvas. Primeira: se a pergunta for só "quem vai ganhar", e não "onde está o dinheiro", ordenar pelos mais recentes acerta mais em três dos quatro cortes. Segunda: entre os negócios que já foram encerrados (ganhos ou perdidos), o score não é melhor que ordenar pelo preço; a vantagem vem de tirar do topo os negócios parados há muito tempo. Terceira: hoje é fim de trimestre, e nos fins de trimestre testados os negócios do Foque com mais de 60 dias ganharam bem menos que os novos (69 dos 126 do Foque de hoje estão nessa faixa); trate o Foque de hoje com esse cuidado. Os dados são sintéticos, e parte do padrão que o score usa (o teto de 138 dias) provavelmente é do gerador, não do comércio real.

## 2. Fórmula

```
chance(idade)   = 1 / (1 + exp(-(b0 + b1 * max(0, idade - joelho) / 30))),   com b1 <= 0
valor esperado  = chance(idade) * preço de tabela
score           = 100 * ln(1 + VE / VE_min) / ln(1 + VE_max / VE_min)      (arredondado, de 0 a 100)
VE_min / VE_max = chance de um deal novo * menor / maior preço do catálogo
```

- **Chance.** Curva "platô + queda": constante até o `joelho`, depois cai. O `joelho` é o valor, numa grade de 0 a 180 dias em passos de 5, que dá o menor erro (log-verossimilhança negativa); `b1` nunca é positivo, então a chance não sobe com a idade, e ela é maior que zero em qualquer idade (não há corte duro). O treino usa fotos mensais do pipeline (fim de cada mês, de 31/03/2017 até 90 dias antes da data do modelo) e o desfecho de cada deal aberto nos 90 dias seguintes.
- **Valor.** O valor do deal aberto é o preço de tabela (`sales_price`); o `close_value` só serve como desfecho no backtest (DATA_QUALITY, seção 4).
- **Listas.** Foque: idade até o joelho. Reative: do joelho até o limite de Limpe, que é o maior ciclo já ganho até a data do modelo (nunca menor que o joelho). Limpe: acima disso. Qualifique: Prospecting, que não tem data de engajamento e por isso não tem chance nem score.
- **Vendedor.** Não entra em nenhuma conta (CLAUDE.md, decisão 4); um teste permuta os vendedores e confere que nenhum score muda.

Parâmetros de hoje e a regra das listas:

<!-- AUTO:scoring-hoje -->
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
<!-- /AUTO:scoring-hoje -->

Parâmetros do modelo ajustado em cada corte (cada um vê só os dados até a sua data):

<!-- AUTO:scoring-modelos -->
| Modelo ajustado até | Joelho (dias) | Chance de deal novo | Inclinação por 30 dias | Meia-vida depois do joelho (dias) | Limite de Limpe (dias) | Fotos | Linhas de treino | Taxa base de treino |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | 70 | 49,0% | -4,71 | 6,9 | 138 | 1 | 1.330 | 45,8% |
| 31/07/2017 | 100 | 46,9% | -5,60 | 5,7 | 138 | 2 | 2.948 | 45,0% |
| 31/08/2017 | 95 | 46,0% | -1,72 | 18,3 | 138 | 3 | 4.483 | 43,3% |
| 30/09/2017 | 90 | 45,6% | -1,96 | 16,0 | 138 | 4 | 6.169 | 41,2% |
| 31/12/2017 (hoje) | 95 | 39,9% | -2,59 | 11,3 | 138 | 7 | 13.100 | 33,2% |
<!-- /AUTO:scoring-modelos -->

## 3. Por que assim

- **Horizonte de 90 dias (um trimestre).** Os deals do dataset fecham no trimestre do engajamento ou no seguinte, e o win rate depende do mês dentro do trimestre (DATA_QUALITY, seção 2). Uma janela de 90 dias contém sempre exatamente um mês de fim de trimestre, o que neutraliza essa sazonalidade do gerador na chance estimada. O 90 foi escolhido conhecendo o dataset; é uma escolha de desenho divulgada (seção 4, risco 8), não um parâmetro otimizado.
- **Monotonicidade.** Um protótipo exploratório do planejador (logística segmentada sem restrição, treinada a partir de 28/02) produziu, para o corte de 30/06, uma curva que sobe com a idade até 90 dias. Isso não faz sentido para uma lista de prioridades e foi o motivo de impor `b1 <= 0`.
- **Primeira foto em 31/03/2017.** O primeiro fechamento do dataset é de 01/03/2017, e os fechamentos do primeiro trimestre são só de março (artefato de recorte, DATA_QUALITY, seção 2). Começar em 28/02 exigiria supor que o recorte removeu exatamente os fechados antes de 01/03. Esta regra foi escolhida depois de o planejador ver que 28/02 piora o corte de 30/06, então 28/02 é reportado como sensibilidade (seção 7) e não como alternativa equivalente.
- **Ordenação do Foque por valor esperado.** Dentro do platô a chance é a mesma para todo deal, então o valor esperado ordena pelo preço, e os empates saem por "faltam menos dias até o joelho". A justificativa é "a curva é plana até o joelho", e não "a chance é estável em cada data": por data ela não é (seção 10).
- **Faixas fixas do briefing contra joelho e limite aprendidos.** O briefing separou hoje em até 90 dias (110 deals), de 91 a 138 dias (188) e acima de 138 (1.291). O modelo aprende o joelho (95 dias hoje, não 90) e o limite de Limpe (138, o maior ciclo já ganho). Como o limite aprendido coincide com o do briefing, o Limpe fica igual (1.291). O joelho aprendido é cinco dias mais largo, então 16 deals passam de Reative para Foque: 126 e 172, no lugar de 110 e 188. O total de Foque mais Reative é o mesmo. A tabela da seção 2 mostra os dois conjuntos de contagens lado a lado.

## 4. Checagem de vazamento

Para um corte T, o modelo e os scores só podem depender do que um CRM já teria registrado até o fim do dia T. Cada risco abaixo tem uma guarda no código e um teste; a prova central é o **teste de mutação do futuro**: tudo o que acontece depois de T (desfecho, datas, valores, contas, produtos, vendedores dos deals engajados depois) é trocado por valores aleatórios, e o modelo e os scores dos abertos em T têm de ficar idênticos, bit a bit. Um controle negativo (um modelo de corte posterior tem de mudar com a mutação) garante que a mutação mexe em algo que importa.

| # | Risco | Guarda | Teste |
|---|---|---|---|
| 1 | Estágio final (Won/Lost) usado como estado em T | `as_of(T)` reconstrói o estado a partir das datas | `test_as_of_hides_every_event_after_T`, `test_future_mutation_leaves_model_and_scores_unchanged` |
| 2 | Rótulo de treino com evento depois de T | só fotos com S + 90 dias <= T, com `assert` | `test_training_set_respects_the_horizon_for_every_cut` |
| 3 | Conta ausente equivale a "nunca fechou" (os 1.425 sem conta estão todos abertos) | `has_account` fora do modelo; atributos de conta só no subconjunto com conta | `test_account_columns_do_not_change_the_model_or_scores`; auditoria da seção 7 |
| 4 | `close_value` usado como valor do deal aberto | o valor é `sales_price` | `test_close_value_is_never_read` |
| 5 | Parâmetros (joelho, chance de deal novo, limite de Limpe, escala) ajustados com dados de depois de T | tudo ajustado por corte, a partir de `as_of(T)` | mutação do futuro; `test_limpe_limit_comes_from_wins_closed_up_to_T` |
| 6 | Explicações vindas de um modelo que viu o futuro | `explain` só recebe o modelo do corte | `test_explanation_uses_the_cut_model_not_a_global_one` |
| 7 | Prospecting no passado não é reconstruível | `as_of` descarta Prospecting; Qualifique só na data de referência | `test_prospecting_is_only_scored_when_asked_and_never_gets_a_score` (limite de cobertura, não vazamento) |
| 8 | Hiperparâmetros (horizonte, primeira foto, grade do joelho) escolhidos conhecendo os dados | divulgado; sensibilidade em 28/02 | sem teste unitário possível |
| 9 | Preço de catálogo estático | um preço por produto, premissa documentada | `test_each_product_has_a_single_list_price` |
| 10 | Colunas derivadas do arquivo (`age_days`, `cycle_days`, `is_open`) calculadas com a data de referência | `as_of` as recalcula em T | `test_as_of_recomputes_age_and_cycle_from_dates` |
| 11 | Vendedor ou manager entrando no score | o treino não tem essas colunas | `test_permuting_sales_agent_changes_no_score`, `test_training_set_has_no_seller_columns` |

Para ver se os testes pegam o vazamento de verdade, a 3a estragou uma guarda por vez em cópias do pacote (6 sabotagens): todas foram detectadas, por 2 a 9 testes cada. A sabotagem "treino sem a regra S + 90 <= T" não é pega pela mutação (o rótulo vira "não ganho", que enviesa mas não vaza), só pelos testes de horizonte; por isso as duas guardas do rótulo existem. **O que a checagem não cobre:** escolher o desenho (horizonte, primeira foto, grade) olhando os mesmos cortes que depois avaliam o modelo é um risco de ajuste ao teste que nenhum teste unitário elimina (risco 8).

## 5. Desenho do backtest e censura

- **Cortes.** 30/06, 31/07, 31/08 e 30/09/2017 (rolling-origin). Em cada um, o modelo é ajustado só com `as_of(T)`; os cortes mais cedo têm menos fotos de treino (o de 30/06 tem uma só).
- **População.** Os Engaging abertos em T, incluindo os zumbis. Prospecting fica de fora (sem data de engajamento).
- **Desfecho.** Vem dos dados completos: ganho até 31/12/2017 (`y`), receita ganha (`close_value` dos Won) e ganho dentro dos 90 dias seguintes ao corte (`y_90`, usado só em Brier e log-loss). Os quatro cortes têm a janela de 90 dias completa antes de 31/12/2017.
- **Métodos comparados.** Score (valor esperado); ordenar por **valor** (preço de tabela); **recência** (os mais novos primeiro); **aleatório** (200 sorteios, sementes 0 a 199, com p5 e p95). Como diagnóstico, a chance sozinha, sem o preço.
- **Métricas.** AUC; ganhos capturados no top 20% (por contagem de deals); receita capturada no top 20% (a métrica primária). Empates de score são tratados pelo valor esperado sob desempate aleatório, e não pela ordem do arquivo.
- **Censura.** Os deals ainda abertos em 31/12/2017 contam como "não ganho até 31/12". Isso é uma suposição: um deal aberto pode ainda fechar. A tabela de sensibilidade da seção 7 separa os que de fato podem fechar (abertos em 31/12 com idade ainda dentro do limite de Limpe: zero nos cortes de junho e julho, 81 no de agosto e 183 no de setembro) dos zumbis que o dataset nunca fecha. E mostra o resultado só com os resolvidos.

## 6. Resultados

Receita capturada no top 20%, corte a corte, contra o critério pré-registrado:

<!-- AUTO:scoring-criterio -->
| Corte | Score | Valor | Recência | Aleatório (média) | Aleatório (p95) | Margem sobre o melhor baseline | Vence os 4? |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30/06/2017 | 61,3% | 48,6% | 27,7% | 20,0% | 23,4% | +12,6 pp | sim |
| 31/07/2017 | 57,9% | 48,7% | 12,8% | 20,1% | 23,4% | +9,2 pp | sim |
| 31/08/2017 | 60,7% | 48,2% | 31,6% | 19,8% | 23,0% | +12,5 pp | sim |
| 30/09/2017 | 64,8% | 47,1% | 46,8% | 20,3% | 24,4% | +17,7 pp | sim |

Receita capturada no top 20%. Empate é diferença de até 0,01 e não vence. Resultado: **PASSOU**.
- curva platô + queda: passou; receita média do score nos cortes: 61,1%.
<!-- /AUTO:scoring-criterio -->

Tabela principal (corte × método):

<!-- AUTO:scoring-backtest -->
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
<!-- /AUTO:scoring-backtest -->

Média dos cortes:

<!-- AUTO:scoring-media -->
| Método | AUC | Ganhos capturados no top 20% | Receita capturada no top 20% |
| :--- | ---: | ---: | ---: |
| Score (valor esperado) | 0,64 | 26,3% | 61,1% |
| Ordenar por valor | 0,49 | 20,0% | 48,1% |
| Mais recentes primeiro | 0,70 | 29,8% | 29,7% |
| Aleatório (média de sorteios) | 0,50 | 20,0% | 20,0% |
| Só a chance (diagnóstico) | 0,67 | 26,5% | 26,5% |

Média simples dos 4 cortes. Brier da chance: 0,185 contra 0,226 da taxa média de treino (log-loss 0,524 contra 0,644), sobre ganhos em 90 dias.
<!-- /AUTO:scoring-media -->

**Onde o score ganha.** Na receita capturada, em todos os cortes, com folga: de 9,2 pontos percentuais a 17,7 pontos percentuais sobre o melhor baseline. O score troca um pouco de taxa de acerto por mais receita: a chance sozinha, sem o preço, captura só 26,5% da receita em média, bem abaixo do score (61,1%) e perto da recência (29,7%). Quem põe a receita é o preço.

**Onde a recência ganha, sem rodeio.** Em AUC e em captura de ganhos, nos cortes de 30/06, 31/08 e 30/09 (a AUC da recência chega a 0,83 em 30/09, contra 0,65 do score, e a captura de ganhos a 43,6%, contra 27,9%). O score só ganha em AUC no corte de 31/07. Em receita, a recência perde para o score nos quatro cortes, mas em 30/09 chega a 46,8%, quase igual ao valor (47,1%). Não testei a causa. É coerente com o padrão do gerador que o DATA_QUALITY documenta (os deals fecham no trimestre do engajamento ou no seguinte, e os fechamentos rápidos se concentram no primeiro mês do trimestre): num fim de trimestre, quem foi engajado há 61 a 90 dias e continua aberto já passou da janela em que o gerador costuma fechar.

**Onde a recência desaba.** Em 31/07 ela captura 12,8% da receita, abaixo do sorteio (20,1%), e só 12,2% dos ganhos. Nesse corte, os deals de até 30 dias (engajados em julho) ganharam 24,3% nos 90 dias seguintes, contra 53,8% dos de 31 a 60 dias (tabela da seção 10). Ordenar pelos mais novos põe no topo os que menos ganham.

**A chance sozinha também tem um erro de previsão do plano.** O plano de execução antecipava que a chance sozinha nunca ordenaria melhor que a recência, porque a chance é monótona na idade. Isso falhou em 31/07: a AUC da chance sozinha é 0,64, contra 0,58 da recência. Dentro do platô a chance é constante (um empate, que vale meio acerto), e a recência, nesse corte, ordena ao contrário do desfecho dentro do platô; o empate sai melhor que a ordem errada.

**Brier e log-loss.** A chance supera a constante (a taxa média de treino) nos quatro cortes, tanto em Brier quanto em log-loss (tabela de calibração abaixo). Isso não decide o critério.

**Categorias.** Quase toda a receita ganha depois do corte vem do Foque; o Limpe, por construção do dataset, nunca ganha (zero ganhos nos quatro cortes):

<!-- AUTO:scoring-categorias -->
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
<!-- /AUTO:scoring-categorias -->

**Calibração.** A chance do modelo é a média das fotos de treino e só acompanha bem o corte quando a posição no trimestre é parecida com a média. Nas faixas de 61 a 90 dias dos cortes de fim de trimestre ela erra feio para cima:

<!-- AUTO:scoring-calibracao -->
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
<!-- /AUTO:scoring-calibracao -->

**Bootstrap.** A diferença do score para valor e recência, com intervalo de confiança por reamostragem dos deals:

<!-- AUTO:scoring-bootstrap -->
| Corte | Score menos valor | Score menos recência |
| :--- | ---: | ---: |
| 30/06/2017 | +12,6 pp (IC +9,6 pp a +15,8 pp) | +33,6 pp (IC +26,9 pp a +40,8 pp) |
| 31/07/2017 | +9,2 pp (IC +6,9 pp a +11,7 pp) | +45,1 pp (IC +39,5 pp a +50,5 pp) |
| 31/08/2017 | +12,5 pp (IC +9,4 pp a +15,2 pp) | +29,1 pp (IC +22,4 pp a +35,1 pp) |
| 30/09/2017 | +17,7 pp (IC +14,9 pp a +21,0 pp) | +17,9 pp (IC +10,4 pp a +25,3 pp) |

Diferença na receita capturada no top 20%, em pontos percentuais; IC de 2,5% a 97,5% por 1.000 reamostragens dos deals do corte (semente 0).
<!-- /AUTO:scoring-bootstrap -->

Os intervalos não incluem zero em nenhum corte, mas os quatro cortes usam os mesmos deals em datas diferentes e não são amostras independentes. O bootstrap reamostra deals, não épocas.

## 7. Sensibilidades e auditoria

<!-- AUTO:scoring-sensibilidade -->
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
<!-- /AUTO:scoring-sensibilidade -->

- **Primeira foto em 28/02.** O critério passaria do mesmo jeito. Só o corte de 30/06 muda de verdade: o joelho vai de 70 para 125 dias e a receita capturada cai 7,4 pontos percentuais. É o corte mais frágil, porque tem uma só foto de treino na regra principal e duas com 28/02.
- **Só resolvidos.** Quando se tiram os deals ainda abertos em 31/12, o score deixa de ser melhor que ordenar por valor: 49,7% contra 49,9%, 48,5% contra 48,8%, 48,6% contra 49,1% e 48,2% contra 48,2% de receita (a AUC dos três métodos fica em torno de 0,5). Na população de deals que fecharam, a chance por idade não separa ganhos de perdas. A vantagem do score sobre o valor nos cortes completos vem de identificar os zumbis: deals abertos há mais que o maior ciclo já ganho, que o dataset nunca fecha. Esse padrão (nenhum ciclo acima de 138 dias) é provável artefato do gerador (DATA_QUALITY, seção 1). O score sobre a população completa é a leitura honesta do que a ferramenta faz na prática (limpar a fila), mas não prova que ela preveja ganhos entre deals que de fato se resolvem.

<!-- AUTO:scoring-auditoria -->
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
<!-- /AUTO:scoring-auditoria -->

- **"E se houvesse vazamento?"** Um modelo ajustado com os dados até 31/12/2017 e avaliado nos cortes passados, rotulado VAZADO e nunca reportado como resultado, não melhora o score: a receita vazada é igual ou menor que a honesta em todos os cortes, e a AUC cai em 30/06. Como o score só usa a idade, a curva ajustada com o futuro é basicamente a mesma curva suavizada (joelho de 95 dias em todos os cortes), então esse tipo de vazamento de parâmetros custa pouco. Isso não prova que o modelo esteja livre de vazamento; a proteção está nas guardas e nos testes da seção 4, não neste número.
- **`has_account` sozinho.** Na população dos cortes, nenhum deal sem conta foi ganho depois (zero em todos), e a AUC de `has_account` sozinho (0,72 a 0,79) é maior que a do score em todos os cortes. Por isso é proibido: parece o melhor preditor, mas só identifica deals que nunca fecham no dataset, e um modelo que o usasse venceria o backtest sem entender nada do negócio.

## 8. Atributos testados e descartados

Um atributo por vez, sobre a curva de idade com o joelho fixo, com one-hot (categoria de referência a mais frequente) e penalidade L2 de 1,0 só nos coeficientes do atributo. Produto e região usam todos os deals; setor e porte (tercil de funcionários, calculado nas contas) só os deals com conta, no treino e na avaliação, contra a curva só de idade ajustada no mesmo subconjunto. Regra pré-registrada: entra só se melhorar o log-loss em todos os cortes e não piorar a receita no top 20% em nenhum. O vendedor não é testado.

<!-- AUTO:scoring-atributos -->
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
<!-- /AUTO:scoring-atributos -->

**Nenhum atributo entra.** Produto, setor e porte pioram o log-loss em pelo menos um corte (porte melhora em três de quatro por margens de milésimos), e todos pioram a receita no top 20% em algum corte. A região é o caso instrutivo: dentro da amostra de treino ela parece ajudar (o Δ log-loss no treino é o mais negativo da tabela de diagnóstico), mas fora da amostra piora em três dos quatro cortes. No treino do corte de 30/09, a região Central ganhava bem mais que as outras entre os deals jovens; depois do corte, a diferença desapareceu e até se inverteu. É a razão de a validação ser sempre temporal (CLAUDE.md, decisão 6).

## 9. Critério pré-registrado e se houve ajuste

**Escrito antes do backtest** (25/10/2026, 16:28; o primeiro número de desempenho só apareceu às 19:05, depois de uma interrupção por limite de uso da API, registrada em `process-log/03_bloco-3.md`).

**Métrica primária.** Receita capturada no top 20%: fração da receita ganha (o `close_value` dos Won) que cai nos 20% de maior score, por contagem de deals, com empates tratados pelo valor esperado sob desempate aleatório.

**O score vence se**, em cada um dos 4 cortes (30/06, 31/07, 31/08 e 30/09/2017), a receita capturada no top 20% for maior que a de ordenar por valor, maior que a de ordenar pelos mais recentes, e maior que a média e o percentil 95 de 200 sorteios aleatórios (sementes 0 a 199).

**Empate.** Diferença de até 0,01 (1 ponto percentual) é empate, e empate não vence.

**Não decidem.** AUC, captura de ganhos e Brier são reportados, mas não entram na decisão.

**Ajuste único, só se o critério falhar.** Trocar a curva "platô + queda" por faixas de 15 dias de idade, com a taxa de cada faixa suavizada por uma pseudo-contagem de 20 deals rumo à taxa média de treino, forçada a não crescer (algoritmo PAVA, pesos = n + 20) e interpolada linearmente entre os pontos médios das faixas. Mesma janela, mesmo horizonte de 90 dias, nada mais muda. Roda-se uma vez.

**Se ainda falhar.** Fica o modelo de melhor média na métrica primária e a falha é documentada com números. Sem novas tentativas e sem trocar de métrica.

**Regra para atributos.** Um atributo só entra no score se melhorar o log-loss da chance de ganho em 90 dias em todos os cortes e não piorar a receita capturada no top 20% em nenhum. O vendedor não é testado.

**Resultado: PASSOU, e o ajuste não foi aplicado.** A tabela da seção 6 mostra o critério corte a corte. O ajuste único (faixas de 15 dias e PAVA) está implementado e testado, mas **não foi rodado**, porque a regra só o autoriza se o critério falhar. Corrigir o código sem mudar o modelo não conta como ajuste; nenhum bug que mudasse o resultado apareceu depois da primeira rodada do backtest (o registro dos erros de teste está no log).

**O que o pré-registro garante, e o que não.** A regra, o desempate e o ajuste único não mudaram depois de ver o resultado. Mas o critério não foi fixado às cegas: o planejador tinha rodado um protótipo e o plano trazia valores esperados próximos dos obtidos, então já se sabia que o score tendia a passar. A métrica primária foi escolhida porque a dor é onde pôr a hora do vendedor, e não por ser a que o score ganha (a recência ganha em AUC).

## 10. O que não funcionou e por quê

- **A curva não monotônica do protótipo.** A logística sem restrição subia com a idade no corte de 30/06. Corrigido com `b1 <= 0`; foi uma correção de desenho antes do backtest, não um ajuste pós-resultado.
- **A chance estável "em cada data".** A justificativa do plano era que a chance de ganho fica estável enquanto o deal é jovem. No agregado das fotos é verdade, mas por data não é: depende da posição da foto no trimestre. A tabela abaixo mostra, dentro do Foque de cada corte, a taxa de ganho em 90 dias por idade.
- **Reative fraco nos fins de trimestre.** No corte de 30/09, os 195 deals de Reative não tiveram nenhum ganho, e a chance do modelo na faixa de 91 a 120 dias era de 25,4%. No de 30/06, ganharam 4,2%. A lista Reative promete mais do que entregou em fim de trimestre.
- **Corte de 30/06 com uma foto só.** O modelo desse corte vê 1.330 linhas de uma só foto e escolhe joelho de 70 dias; com a primeira foto em 28/02 o joelho vai a 125 e a receita cai 7,4 pontos percentuais. Ele sustenta o critério, mas é o menos estável dos quatro.
- **P < recência em AUC e captura de ganhos** na maioria dos cortes (seção 6), e a antecipação do plano de que isso valeria sempre falhou em 31/07.
- **Região** parecia ajudar no treino e não ajudou fora da amostra (seção 8).
- **Só resolvidos.** O score não bate o valor entre os deals que fecharam (seção 7). Isto é o que mais pesa contra a tese de "frescor": a idade ajuda a achar o que está morto, não a escolher entre o que está vivo.

**Foque de 61 dias ou mais contra os novos, por corte** (o risco levantado na 3a e verificado aqui, sem mexer no modelo):

<!-- AUTO:scoring-foque-idade -->
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
<!-- /AUTO:scoring-foque-idade -->

Nos dois cortes de fim de trimestre, os deals do Foque com 61 dias ou mais ganharam bem menos que os de até 30 dias: 17,4 pontos percentuais a menos em 30/06 e 41,3 pontos percentuais a menos em 30/09. Nos cortes de 31/07 e 31/08 aconteceu o contrário (19,2 pontos percentuais e 21,3 pontos percentuais a mais), porque os deals novos desses meses ganham menos. Os intervalos de confiança não incluem zero em nenhum dos quatro. A curva do modelo é plana até o joelho e diz o mesmo para todo o Foque. Como hoje (31/12/2017) é fim de trimestre, 69 dos 126 deals do Foque têm 61 dias ou mais, a faixa que nos dois fins de trimestre testados rendeu menos. O modelo não explora a posição no trimestre (decisão do bloco 2: padrões do gerador não são explorados), de modo que o Foque de hoje provavelmente está otimista nesses deals. Esse efeito está medido, não corrigido.

**Por que a curva é plana dentro do Foque** (resposta à revisão independente nº 1, que apontou que um deal de 12 dias e um de 94 dias do mesmo produto recebem o mesmo score; ver `process-log/06_revisao-independente.md`):

<!-- AUTO:foque-plato-sinal -->
Dentro do Foque (o platô da curva, até 95 dias), a diferença de ganhos em 90 dias entre os deals de 61 dias ou mais e os de 0 a 30 dias foi de -17,4 pp em 30/06, +19,2 pp em 31/07, +21,3 pp em 31/08 e -41,3 pp em 30/09. O sinal troca entre os cortes (2 negativos e 2 positivos), então dentro do platô não há uma inclinação estável a aprender, e é isso que justifica a curva plana até o joelho em vez de premiar os mais novos. O salto está no joelho: é depois dele que a chance cai.
<!-- /AUTO:foque-plato-sinal -->

## 11. Limitações

- **Dados sintéticos.** O dataset é gerado; em CRM real, o decaimento seria mais suave. O teto de 138 dias é provável artefato do gerador e o Limpe herda esse artefato (o limite aprendido é o maior ciclo já ganho). Em dados reais, um deal com mais de 138 dias pode ser ganho.
- **A vantagem vem dos zumbis.** Entre os deals resolvidos, o score não é melhor que o preço (seção 7). A ferramenta ajuda a limpar a fila e a priorizar por valor; não ordena bem o que está vivo.
- **Posição no trimestre.** A chance média das fotos erra para cima nas faixas mais velhas do Foque nos fins de trimestre, e hoje é um fim de trimestre (seção 10).
- **Censura.** Deals abertos em 31/12/2017 contam como "não ganho". Para os cortes de agosto e setembro, uma parte deles ainda pode fechar (seção 7), e isso subestima o ganho desses cortes.
- **Cortes sobrepostos.** Os quatro cortes usam os mesmos deals em datas vizinhas; o critério "vence em todos" tem menos força do que quatro testes independentes.
- **Escolhas de desenho vistas com os dados.** Horizonte, primeira foto e grade do joelho foram escolhidos sabendo do protótipo (seção 4, risco 8). A sensibilidade a 28/02 foi medida; as do horizonte e do passo da grade não foram.
- **Joelho pouco identificado.** A verossimilhança perto do melhor joelho é achatada: vizinhos a 5 dias custam pouco, então o joelho vale com margem de uns 5 a 10 dias.
- **Preço de tabela.** O valor esperado usa o preço de tabela; nos ganhos, o valor fechado fica perto dele em média, mas varia por deal (DATA_QUALITY, seção 4).
- **Prospecting.** Sem data de engajamento, não tem chance, score nem backtest. Qualifique é uma lista sem prova.
- **Vendedor.** Fora do score por decisão. Não se testou se haveria ganho em usá-lo.
