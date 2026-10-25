# Model card — Lead Scorer

Data de referência ("hoje"): 31/12/2017. As tabelas entre marcadores `AUTO` são geradas por `python -m scorer.docs` a partir de `solution/data/processed/backtest_metrics.json`; os números da prosa são conferidos contra os mesmos arquivos por `tests/test_docs_numbers.py`. Detalhes e provas: [SCORING.md](SCORING.md), [DATA_QUALITY.md](DATA_QUALITY.md) e [SCOPE.md](SCOPE.md).

## 1. Propósito e uso pretendido

Ajudar o vendedor, na segunda de manhã, a decidir onde pôr a próxima hora: quais deals abertos **focar**, quais **reativar** e quais **limpar** do CRM (mais a lista Qualifique, para o Prospecting, que não tem score). O manager usa a mesma tela, filtrada, no 1:1 semanal. Quem responde pelo uso é a Head de RevOps.

O score é uma ordenação de prioridade. Ele não prevê "este deal vai fechar": ele diz que, entre deals abertos, os do topo concentram mais da receita que costuma ser ganha em seguida.

## 2. Uso NÃO pretendido

- **Avaliar ou ranquear vendedores.** O vendedor está fora do score de propósito, e a diferença de win rate entre vendedores é compatível com ruído (p=0,26). A "Carteira do time" mostra só contagens.
- **Forecast financeiro.** O valor esperado serve para ordenar, não para somar. O valor do deal é o preço de tabela, e a chance é uma média de fotos passadas, não uma calibração por data.
- **Encerrar deals automaticamente.** Limpe quer dizer confirmar com o cliente e encerrar ou atualizar. O deal parado pode ser CRM desatualizado, e uma ferramenta que fecha sozinha transforma o erro do score em perda real.

## 3. Dados e período

- **Origem:** dataset público "CRM Sales Predictive Analytics" (Kaggle, CC0), **sintético**: 8.800 deals, 85 contas, 7 produtos e 35 vendedores no cadastro, dos quais só 30 têm deals.
- **Período:** engajamentos de out/2016 a dez/2017; fechamentos de mar/2017 a dez/2017 (o primeiro é de 01/03/2017; a investigação 2a mostra que o início é um recorte da amostra, não o começo do negócio).
- **Fotos de treino:** o modelo aprende com fotos mensais do pipeline, de 31/03/2017 em diante (na data de hoje, sete fotos e 13.100 linhas). Cada linha é um deal aberto naquele dia, com o desfecho nos 90 dias seguintes. O modelo de cada corte do backtest só vê o que o CRM sabia naquele dia (teste de mutação do futuro, SCORING seção 4).
- **O que entra no score:** a idade do deal (dias desde o engajamento) e o preço de tabela do produto. Mais nada. Produto, região, setor e porte foram testados e não entraram (SCORING seção 8).

## 4. Desempenho

Receita capturada pelos 20% de deals no topo da ordenação, como fração da receita realmente ganha depois do corte (métrica primária, fixada antes do backtest):

<!-- AUTO:mc-desempenho -->
|  | Receita no top 20%: score | valor | recência | aleatório | AUC do score | AUC da recência |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Média dos 4 cortes | 61,1% | 48,1% | 29,7% | 20,0% | 0,64 | 0,70 |
| Pior corte (31/07/2017) | 57,9% | 48,7% | 12,8% | 20,1% | 0,64 | 0,58 |

Pior corte = o de menor margem do score sobre o melhor baseline. Critério pré-registrado: **PASSOU**, sem ajuste.
<!-- /AUTO:mc-desempenho -->

Leitura honesta:

- O score vence valor, recência e sorteio nos quatro cortes. O resultado depende do preço: a chance sozinha, sem o preço, captura bem menos receita.
- **Em AUC a recência ganha** em três dos quatro cortes, com 0,83 contra 0,65 do score em 30/09. Se a pergunta for só "quem vai ganhar", e não "onde está o dinheiro", ordenar pelos mais novos acerta mais, exceto em 31/07, onde a recência cai abaixo do sorteio.
- **Entre os deals já resolvidos (ganhos ou perdidos) o score empata com o valor.** A vantagem vem de tirar do topo os zumbis, não de escolher o melhor entre os vivos.
- A tabela completa, o bootstrap e a calibração estão no SCORING.

## 5. Limitações

- **Dataset sintético.** Em CRM real o decaimento seria mais suave. O que o gerador impõe e o score herda: a regra de fechar no trimestre do engajamento (Q) ou no seguinte (Q+1), o teto de 138 dias (nenhum deal foi ganho depois disso) e fechamentos rápidos no primeiro mês do trimestre. Estão documentados e não são explorados, mas o Limpe herda o teto de 138 dias.
- **Censura.** Deals ainda abertos em 31/12/2017 contam como "não ganho" no backtest. Em agosto e setembro uma parte deles ainda pode fechar, o que subestima o ganho desses cortes.
- **Contas faltantes.** 1.425 deals não têm conta, todos abertos. Por isso `has_account` é proibido como variável: sozinho ele tem AUC maior que a do score, e só porque identifica quem nunca fecha no dataset.
- **Prospecting sem score.** Os 500 deals em Prospecting não têm data de engajamento, então não há idade, chance, score nem backtest. Qualifique é uma lista sem prova.
- **Corte de 30/06 com uma foto de treino só** (1.330 linhas). O joelho da curva muda bastante se a primeira foto for 28/02 (de 70 para 125 dias), e a receita capturada cai 7,4 pp. É o corte mais frágil.
- **Regra de 31/03 escolhida depois de ver o protótipo.** A justificativa é a priori (DATA_QUALITY, seção 2), mas a escolha foi feita depois de o planejador ver o efeito em 28/02. Por isso 28/02 é reportado como sensibilidade.
- **Posição no trimestre.** O modelo usa a média das fotos. Nos fins de trimestre, os deals do Foque com 61 dias ou mais ganharam menos que os novos (em 30/09, 6,7% contra 48,0%), e hoje é um fim de trimestre: 69 dos 126 deals do Foque estão nessa faixa. **O Foque de hoje provavelmente está otimista para eles.** Medido, não corrigido.
- **Reative fraco em fim de trimestre.** A lista teve de 0% a 23% de ganhos nos cortes.
- **Horizonte (90 dias) e passo da grade do joelho** foram escolhidos sabendo do dataset e não tiveram sensibilidade medida.

## 6. Riscos e mitigação

| Risco | Como aparece | Mitigação |
|---|---|---|
| **Profecia autorrealizável** | Deal em Limpe deixa de ser trabalhado e, por isso, nunca ganha, o que "confirma" o score | Limpe significa **confirmar com o cliente** e então encerrar ou atualizar, nunca descartar. O texto do card e o brief dizem isso. A recalibração (seção 7) usa os desfechos novos, inclusive dos deals que foram reativados |
| **Viés contra vendedores** | Um vendedor com muitos deals velhos parece "pior" e é cobrado por isso | O vendedor não entra no score. Há teste de permutação: trocar os vendedores de lugar não muda nenhum score (`test_permuting_sales_agent_changes_no_score`). Nenhuma tela mostra taxa de vitória por vendedor |
| **Valor estático** | O valor esperado usa o preço de tabela, não o valor negociado | Nos 4.238 ganhos, a razão `close_value` / preço de tabela tem média 0,996, e a média por produto fica entre 0,985 e 1,004 (DATA_QUALITY, seção 4). Em CRM real, rever com o valor da proposta |
| **Confiar numa ordem que errou na história** | O Foque de hoje parece mais seguro do que é | A interface mostra o modo teste, com o que o score teria dito em datas passadas e o que aconteceu; o aviso do Foque de 61 dias ou mais está nas Limitações |

## 7. Quando recalibrar

Recalibrar (rodar `python -m scorer.validate` e `python -m scorer.build` com a base nova) em qualquer um destes casos:

1. **A cada trimestre**, porque o modelo aprende com fotos mensais e o padrão do trimestre pesa (SCORING, seção 10).
2. **Quando a taxa de ganho em 90 dias de alguma faixa de idade se mover mais que X pp** em relação à que o modelo usa. X é um parâmetro documentado:

<!-- AUTO:mc-recalibracao -->
X = 10 pp (`config.RECALIBRATION_SHIFT_PP`). Teste de bom senso no backtest: entre as 24 faixas de idade com pelo menos 100 deals (corte x faixa), 7 teriam acendido o alerta, isto é, a chance do modelo ficou a mais de 10 pp da taxa de ganho em 90 dias observada. O alerta não é raro.
<!-- /AUTO:mc-recalibracao -->

3. **Ao migrar para um CRM real com histórico de estágios.** O modelo atual só vê a data de engajamento e o desfecho; com o histórico de estágios dá para medir tempo parado por etapa, que é uma idade melhor do que "dias desde o engajamento". O teto de 138 dias e a regra Q/Q+1 devem desaparecer ou mudar, e o critério pré-registrado precisa ser rodado de novo, com cortes novos.

## 8. Dono e revisão

- **Dono:** RevOps (a Head de RevOps, como patrocinadora, designa a pessoa responsável pelo modelo).
- **Revisão:** trimestral, junto com a recalibração: conferir o critério pré-registrado nos cortes mais recentes, a lista de atributos testados e se os alertas da seção 7 dispararam.
- **O que o dono deve olhar primeiro:** se a receita capturada pelo score no top 20% continua acima da de ordenar só pelo valor, e se os deals do Limpe que foram confirmados e reabertos mudam o desfecho (um Limpe que ganha é evidência contra o teto de 138 dias).
