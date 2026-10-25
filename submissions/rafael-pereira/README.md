# Submissão — Rafael Pereira — Challenge 003

## Sobre mim

- **Nome:** Rafael Pereira
- **LinkedIn:** https://www.linkedin.com/in/rafael-pereira-30122003-
- **Challenge escolhido:** 003 — Lead Scorer

---

## Executive Summary

O que separa os deals do CRM é o frescor (há quanto tempo estão abertos), não os atributos: produto, setor, região e porte ficam todos entre 60% e 65% de win rate, enquanto na foto de 30/09/2017 os deals com até 30 dias foram ganhos em 50% dos casos e os com mais de 90 dias, em 0%. Em quatro datas passadas, os 20% de deals no topo do score concentraram em média 61,1% da receita que foi ganha depois, contra 48,1% se o time ordenasse só pelo valor, 29,7% pela recência e 20,0% num sorteio, e o critério fixado antes do teste passou sem ajuste. Hoje, 1.291 dos 1.589 deals em Engaging estão abertos há mais tempo que o maior ciclo já fechado, e a lista Limpe soma cerca de US$ 3,2 mi de valor de tabela provavelmente inflado. As ressalvas pesam: entre os deals já resolvidos o score só empata com o valor, a recência ganha em AUC em três dos quatro cortes e o dataset é sintético. Recomendo um sprint de limpeza da lista Limpe, confirmando cada deal com o cliente antes de encerrar, e uma rotina de segunda-feira com as listas Foque e Reative.

---

## Solução

Uma página estática, sem servidor, que o vendedor abre na segunda de manhã: escolhe o próprio nome e vê quatro listas (Foque, Reative, Limpe e Qualifique), cada deal com uma explicação de 2 a 4 frases, mais um "modo teste" que mostra o que o score teria recomendado numa data passada e o que de fato aconteceu. Por trás, um motor em Python (pandas, funções puras, pytest) gera os dados da página. Documentos: [escopo](docs/SCOPE.md), [qualidade dos dados](docs/DATA_QUALITY.md), [score e validação](docs/SCORING.md), [model card](docs/MODEL_CARD.md) e [decisões](docs/DECISIONS.md).

### Como rodar (setup)

1. **Abrir a ferramenta sem instalar nada.** Duplo-clique em [`solution/app/index.html`](solution/app/index.html) (funciona em `file://`, sem servidor e sem internet).
2. **Link publicado (GitHub Pages):** `https://<seu-usuario>.github.io/ai-master-challenge/submissions/rafael-pereira/solution/app/` **[ativar — Rafael]**. O nome de usuário do GitHub não é conhecido neste texto, então o endereço é um modelo; não inventei um link.
3. **Regenerar tudo a partir dos CSVs** (Python 3.11; testado com pandas 3.1, numpy 2.4, scipy 1.17 e pytest 9.1):

```
cd solution
pip install -r requirements.txt
python -m pytest
python -m scorer.build --reference-date 2017-12-31
```

4. **Verificação opcional da interface** (abre a página num navegador, confere contagens, filtros, layout em computador e celular, contraste e console):

```
pip install -r requirements-dev.txt
python tools/check_app.py --prefix final
```

O build é determinístico: rodar duas vezes gera os mesmos bytes. A data de referência ("hoje", 31/12/2017) é um parâmetro, não está fixa no código.

### Abordagem

1. **Do problema da Head de RevOps ao que medir.** As duas dores são tempo jogado em deal que não fecha e deal bom esfriando sem alerta. Isso não pede "qual deal tem mais chance", pede "onde ponho minha próxima hora". Por isso a métrica primária é a receita ganha capturada pelos 20% do topo, e a AUC é reportada, mas não decide. Essa regra foi escrita no [escopo](docs/SCOPE.md) antes do código de avaliação.
2. **Os dados derrubaram a ideia óbvia.** Um score por atributos dá perto de 63% para todo deal. O que separa é o ciclo: nenhum deal foi ganho depois de 138 dias, e 81% dos Engaging já passaram disso. Antes de usar qualquer coisa, limpei o que quebra o join e o que vaza: "GTXPro" contra "GTX Pro" (1.480 deals sumiriam) e os 1.425 deals sem conta, todos abertos, que funcionariam como detector de zumbi ([qualidade dos dados](docs/DATA_QUALITY.md)).
3. **O score.** Chance de ganho em 90 dias olhando só a idade do deal (curva que fica plana até um "joelho" aprendido e depois cai, sem nunca subir), vezes o preço de tabela, numa escala de 0 a 100. Os limites das listas saem da curva e do maior ciclo já ganho, não de um "se idade > 138". O vendedor não entra, e nenhum atributo entrou depois do teste ([score e validação](docs/SCORING.md)).
4. **Validação sempre no tempo.** Quatro cortes passados (30/06, 31/07, 31/08 e 30/09/2017), cada um com um modelo que só vê o que o CRM sabia naquele dia, contra três baselines: valor, recência e sorteio. O critério para "vencer" foi fixado antes do primeiro número. Um teste troca tudo o que acontece depois do corte por valores aleatórios e exige que o modelo e os scores não mudem.
5. **Interface de decisão.** Frase de ação na primeira tela ("foque em N, reative M, limpe K"), uma lista por ação, explicação por deal e o modo teste, para a Head de RevOps ver o score contra a história antes de confiar nele.

### Resultados / Findings

Cinco achados, todos gerados por script a partir do `backtest_metrics.json`:

<!-- AUTO:readme-achados -->
- **Critério pré-registrado: PASSOU, sem ajuste.** O score vence valor, recência e o sorteio nos 4 cortes.
- **Receita média no top 20%:** score 61,1%, valor 48,1%, recência 29,7%, aleatório 20,0%.
- **A recência ganha em AUC** em 3 dos 4 cortes (30/06, 31/08 e 30/09); a maior folga é em 30/09/2017, com 0,83 contra 0,65 do score. O score só ganha em AUC em 31/07.
- **Entre os deals já resolvidos o score empata com o valor:** receita média no top 20% de 48,7% contra 49,0%, e a maior diferença em um corte é de 0,5 pp. A vantagem do backtest completo vem de tirar do topo os deals parados.
- **O Foque de hoje está otimista:** 69 dos 126 deals têm 61 dias ou mais, e nos fins de trimestre testados esses deals ganharam menos que os de até 30 dias (-17,4 pp em 30/06 e -41,3 pp em 30/09). O modelo não corrige isso.
<!-- /AUTO:readme-achados -->

**Backtest corte a corte** (a tabela completa, com ganhos capturados, bootstrap e calibração, está no [SCORING](docs/SCORING.md)):

<!-- AUTO:readme-backtest -->
| Corte | Receita no top 20%: score | valor | recência | aleatório | AUC do score | AUC da recência |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Média dos 4 cortes** | 61,1% | 48,1% | 29,7% | 20,0% | 0,64 | 0,70 |
| 30/06/2017 | 61,3% | 48,6% | 27,7% | 20,0% | 0,66 | 0,73 |
| 31/07/2017 | 57,9% | 48,7% | 12,8% | 20,1% | 0,64 | 0,58 |
| 31/08/2017 | 60,7% | 48,2% | 31,6% | 19,8% | 0,63 | 0,66 |
| 30/09/2017 | 64,8% | 47,1% | 46,8% | 20,3% | 0,65 | 0,83 |

Receita capturada pelos 20% de deals no topo da ordenação, como fração da receita que foi de fato ganha depois. Aleatório = média de 200 sorteios. Cada corte usa só o que o CRM sabia naquele dia.
<!-- /AUTO:readme-backtest -->

**As quatro listas de hoje (31/12/2017):**

<!-- AUTO:readme-hoje -->
| Lista | Idade do deal | Ação | Deals | Valor de tabela |
| :--- | :--- | :--- | ---: | ---: |
| Foque | até 95 dias | avançar | 126 | US$ 300.790 |
| Reative | 96 a 138 dias | retomar o contato | 172 | US$ 392.775 |
| Limpe | mais de 138 dias | confirmar e encerrar ou atualizar | 1.291 | US$ 3.198.664 |
| Qualifique | Prospecting (sem data) | qualificar | 500 | US$ 1.073.986 |
<!-- /AUTO:readme-hoje -->

O Limpe tem zero ganhos nos quatro cortes do backtest, por construção do dataset. A lista Reative teve de 0% a 23% de ganhos nos cortes: promete mais do que entregou em fim de trimestre.

**A interface** (computador e celular; dados reais, tirados por `tools/check_app.py`):

![Tela inicial, versão para computador](process-log/screenshots/final_inicio_1280.png)

![Tela inicial, versão para celular](process-log/screenshots/final_inicio_390.png)

Atributos testados e descartados (um por vez, com a regra fixada antes): produto, região, setor e porte. A região parecia ajudar dentro da amostra de treino e piorou fora dela em três dos quatro cortes, que é o motivo de a validação ser temporal.

### Recomendações

Para a Head de RevOps, em ordem de prioridade:

1. **Sprint de limpeza da lista Limpe.** São 1.291 deals e cerca de US$ 3,2 mi de valor de tabela. Limpe quer dizer confirmar com o cliente e então encerrar ou atualizar, não descartar: o deal parado pode ser CRM desatualizado. Feito isso, o pipeline passa a mostrar o que é vivo.
2. **Rotina de segunda-feira com Foque e Reative.** Cada vendedor abre o próprio brief, trabalha o Foque e dá um contato de retomada no Reative. Ao ler o Foque de hoje, desconfie dos deals com 61 dias ou mais: hoje é fim de trimestre, e nos fins de trimestre testados esses deals ganharam menos que os novos.
3. **Higiene do CRM.** Preencher a conta (1.425 deals não têm), registrar a data em que o deal entrou em Prospecting (os 500 não têm, e por isso não podem ser pontuados) e guardar o histórico de estágios. Sem isso, a lista Qualifique não tem prova e o score só enxerga "dias desde o engajamento".
4. **Não usar win rate por vendedor.** A diferença entre vendedores é compatível com ruído (qui-quadrado p=0,26). Cobrar ou premiar com base nela pune pessoas por acaso.
5. **Recalibrar com dados reais.** Este dataset é sintético. Rodar o mesmo backtest, com o mesmo critério fixado antes, num CRM real, a cada trimestre (regras de recalibração no [model card](docs/MODEL_CARD.md)).

### Limitações

- **Dataset sintético.** O teto de 138 dias, a regra de fechar no trimestre do engajamento ou no seguinte e os fechamentos rápidos no primeiro mês do trimestre são padrões do gerador. Estão documentados e não são explorados, mas o Limpe herda o teto de 138 dias; em CRM real um deal mais velho pode ser ganho.
- **A vantagem vem dos zumbis.** Entre os deals já resolvidos o score só empata com o valor. A ferramenta ajuda a limpar a fila e a priorizar por valor; não prova que escolha bem entre os deals vivos.
- **A recência ganha em AUC** em três dos quatro cortes. O score ganha onde importa para a pergunta da Head de RevOps (receita), não em quem vai ganhar.
- **O Foque de hoje está otimista** para os deals com 61 dias ou mais. Medido e documentado, não corrigido no modelo.
- **Corte de 30/06 com uma foto de treino só**, e a regra "fotos a partir de 31/03" foi escolhida depois de o planejador ver o protótipo. Com 28/02 o critério também passaria; a diferença está na [seção 7 do SCORING](docs/SCORING.md).
- **Censura:** deals abertos em 31/12/2017 contam como "não ganho". Prospecting não tem score nem backtest. Horizonte de 90 dias e passo da grade do joelho não tiveram sensibilidade medida.
- **Não há chat-exports.** A sessão foi autônoma e única; o registro do processo são os logs por bloco, o DECISIONS e o histórico de commits (ver [LEIA-ME](process-log/chat-exports/LEIA-ME.md)).
- **Git:** a máquina não tinha git nem gh. O repositório foi clonado e commitado com dulwich (biblioteca Python), por um helper fora da pasta; o autor dos commits é o Rafael, com o trailer `Co-Authored-By: Claude`.
- **Interrupção por limite de API.** Os executores pararam entre 16:28 e 19:01 de 25/10/2026, no meio do bloco 3. O critério pré-registrado e o rascunho do SCORING já estavam gravados e nenhum resultado de backtest tinha sido visto antes da retomada ([log do bloco 3](process-log/03_bloco-3.md)).
- **GitHub Pages não ativado:** depende do usuário do GitHub do Rafael (marcado no setup).

---

## Process Log — Como usei IA

> **Este bloco é obrigatório.** Sem ele, a submissão é desclassificada.

### Ferramentas usadas

| Ferramenta | Para que usou |
|------------|--------------|
| Claude (app), Sonnet 5.5 e depois Opus 5.5 | Fase 0: ler o repositório, comparar os 4 challenges, explorar os dados e validar a hipótese de frescor (modelos citados em `00_fase0_exploracao.md`) |
| Claude Code com Opus 5.5 (orquestrador) | Preparar o ambiente, dividir o trabalho em blocos, disparar os executores (até 3 em paralelo), conferir cada entrega e commitar |
| Subagente Claude Opus 5.5 (planejador, somente leitura) | Escrever o plano de execução com a especificação de cada bloco e rodar protótipos descartáveis (`process-log/plano_execucao_opus.md`) |
| Subagentes Claude Sonnet e Haiku (executores) | Executar os blocos: Haiku no bloco 0; Sonnet nos blocos 1 a 5 (cada log declara o executor) |
| Subagente de contexto limpo (revisor, bloco 6) | Revisão independente: avalia a submissão contra os critérios do challenge sem ter visto o processo (planejado; relatório em `process-log/06_revisao-independente.md` quando existir) |

### Workflow

0. **Fase 0 e bloco 0 (setup).** No app do Claude: leitura do repositório, escolha do 003 e exploração dos dados, com a hipótese de frescor validada em duas fotos do pipeline. Depois, o orquestrador montou o ambiente (venv, clone via dulwich, Playwright usando o Edge do sistema) e um executor Haiku criou a estrutura e reproduziu a fase 0 contra o briefing.
1. **Bloco 1, escopo.** Um executor Sonnet escreveu o escopo e respondeu sozinho às 4 perguntas em aberto do briefing, cada uma com alternativa descartada e evidência.
2. **Bloco 2, dados.** Limpeza, três investigações com critério escrito antes do resultado (o win rate de 82% no 1º trimestre, os vendedores sem deals e `close_value` contra o preço de tabela) e a infraestrutura "todo número vem de script": os documentos têm blocos regenerados e um teste que confere cada número da prosa.
3. **Bloco 3, score e validação.** Primeiro a checagem de vazamento, escrita antes do código; depois features, score e explicação; por fim o backtest com o critério registrado antes de qualquer número de desempenho. Um segundo executor escreveu em paralelo as primitivas de métrica.
4. **Bloco 4, ferramenta.** Um executor construiu a interface e o script de verificação contra dados falsos, em paralelo ao motor, a partir de um contrato de dados escrito antes; depois o build real gerou os dados e a página foi verificada com Playwright no Edge, com screenshots.
5. **Bloco 5, documentação.** Este README e o model card, com todos os números vindos de blocos regenerados e conferidos por teste.
6. **Bloco 6, revisão independente (planejado; vem depois deste texto).** Dois revisores de contexto limpo avaliam a submissão (o segundo sem ver a primeira revisão), as críticas com nota baixa são corrigidas sem mudar o modelo, e o texto do PR é preparado.

### Onde a IA errou e como corrigi

Só episódios registrados em `process-log/` e em `docs/DECISIONS.md`.

**Na fase 0, com o Rafael:**

- **Métrica otimista (fase 0, com Rafael).** O primeiro cálculo de poder preditivo por categoria usou target encoding dentro da própria amostra e deu um valor inflado. Foi marcado como inflado, e a decisão foi exigir backtest temporal para qualquer número de desempenho.
- **Win rate de 82% no 1º trimestre tratado como possível insight (fase 0, com Rafael).** Foi rebaixado a suspeita de artefato de recorte e investigado no bloco 2, que confirmou: os fechamentos do trimestre são só de março.
- **Plano inicial com score por atributos (fase 0, com Rafael).** O plano assumia win rate por produto ou setor. Os dados mostraram todos entre 60% e 65%, e o plano pivotou para o frescor.

**Na execução autônoma:**

- **Erro do briefing sobre o MG Special (autocorreção na execução autônoma).** O briefing dizia que o produto tinha o maior volume de deals, e o primeiro rascunho do escopo repetiu a frase. Antes de publicar, o executor conferiu nos dados: o GTX Basic tem mais deals, e o MG Special é o segundo. O escopo e o `facts.json` foram corrigidos; o briefing, insumo da fase 0, foi mantido e a divergência ficou registrada.
- **Justificativa do plano para a pergunta 3 refutada (autocorreção na execução autônoma).** O plano dizia que a chance de ganho é estável enquanto o deal é jovem. As duas fotos do briefing mostram a chance caindo desde cedo. A decisão (ordenar o Foque por valor esperado) foi mantida e a justificativa trocada; o bloco 3 confirmou que a chance é plana no agregado das fotos e cai cedo nas de fim de trimestre.
- **Generalização indevida (autocorreção na execução autônoma).** Uma versão do escopo dizia que "fora da amostra os atributos têm AUC ≈ 0,50". Isso vale só para as variáveis numéricas; para as categorias só existia o valor inflado da fase 0. O texto passou a dizer exatamente isso.
- **Protótipo não monotônico (autocorreção na execução autônoma).** O protótipo do planejador (logística sem restrição) gerou, para o corte de 30/06, uma curva que sobe com a idade até 90 dias, o que não faz sentido para uma lista de prioridades. A inclinação passou a ser limitada a zero ou negativa. Foi uma correção de desenho antes do backtest, e a regra de começar as fotos em 31/03 foi decidida depois de ver esse protótipo, o que está declarado como limitação.
- **Tolerância pós-hoc na investigação 2a (autocorreção na execução autônoma).** O executor escolheu a tolerância de 7 dias da terceira condição depois de ver as folgas na exploração (2, 5, 3, 7 e 4 dias), e a maior vale exatamente 7. O documento declara que a condição vale no limite e não é um teste independente, e traz um reforço sem tolerância. As outras duas condições sustentam o veredito sozinhas.
- **`beats` com ponto flutuante (autocorreção na execução autônoma).** Na comparação de métricas, 0,61 menos 0,60 vale 0,010000000000000009 em ponto flutuante, maior que 0,01, então um empate de exatamente 1 ponto percentual contaria como vitória. Corrigido com uma folga de 1e-12 e coberto por teste.
- **Teste de vazamento que não provava nada (autocorreção na execução autônoma).** Um teste de "modelo sem a guarda vazaria" comparava contagens que já eram diferentes por construção e passaria com a guarda quebrada. Foi trocado por um teste que mostra que as escolhas ingênuas mudam com o futuro mutado e o modelo do código não muda, e seis guardas foram estragadas de propósito para ver os testes falharem de verdade.
- **Previsão do plano falsa (autocorreção na execução autônoma).** O plano previa que a chance sozinha nunca ordenaria melhor que a recência em AUC. Em 31/07 a AUC da chance sozinha é 0,64 e a da recência, 0,58. Está no SCORING como erro de previsão do plano.
- **Rascunho do SCORING com afirmações que não batiam (autocorreção na execução autônoma).** O verificador de números acusou valores sem fonte, e uma conferência manual achou frases erradas ("três fotos" com 28/02 quando são duas; a recência "a 0,2 pp do valor" quando é 0,3). Tudo foi corrigido antes de fechar.
- **`pytest` que travou sem causa conhecida (autocorreção na execução autônoma).** Uma execução da suíte passou de 10 minutos enquanto outro executor editava um arquivo de teste. O processo foi encerrado, a suíte rodou sem esse arquivo e depois inteira (passou). A causa não foi diagnosticada, e o log diz isso em vez de dar um motivo inventado.
- **Contraste e telas vazias (autocorreção na execução autônoma).** O script de contraste achou a linha âmbar da lista Reative abaixo do contraste mínimo de elementos de interface contra o fundo branco, e a aba padrão fixa em Foque deixava vazia a tela do vendedor com mais deals. A cor foi escurecida e a aba padrão passou a ser a primeira lista com deals.

### O que eu adicionei que a IA sozinha não faria

[RASCUNHO — Rafael revisar] Este texto foi escrito pelo Claude a partir do registro da fase 0 (`00_fase0_exploracao.md`); só você pode confirmar, corrigir ou cortar.

- **Escolher o 003 pelo ângulo de governança de IA.** Entre quatro challenges, o Claude estimou esforço e risco de cada um; a decisão foi sua, porque o escopo é fechado, o entregável é verificável e a explicabilidade e a validação conversam com o seu histórico em governança.
- **Não contornar o bloqueio do Kaggle.** A rede do ambiente bloqueou o download. Em vez de tentar um desvio, você usou os CSVs que já tinha baixado.
- **Exigir backtest temporal.** Quando o primeiro cálculo de poder preditivo saiu inflado (dentro da amostra), a regra "nenhuma métrica dentro da amostra é resultado" foi sua.
- **Tirar o vendedor do score.** A diferença entre vendedores era compatível com ruído, e usá-la penalizaria pessoas injustamente. A decisão virou a regra 4 do projeto, com teste de permutação.
- **Não transformar 138 dias em regra.** Você leu o teto de ciclo como provável artefato do gerador sintético e decidiu tratá-lo como "nunca observado", com a curva aprendida dos dados.
- **Pedir um model card.** O documento de limites, riscos e recalibração veio do seu ângulo de governança.
- **Não usar Streamlit.** Por ser o default do baseline, e porque uma página estática abre com um clique.

---

## Evidências

- [x] Screenshots da ferramenta com dados reais: [computador](process-log/screenshots/final_inicio_1280.png) e [celular](process-log/screenshots/final_inicio_390.png). Screenshots das conversas com IA: não há.
- [ ] Screen recording do workflow
- [ ] Chat exports — não há, porque a sessão foi autônoma e única (explicação em [`process-log/chat-exports/LEIA-ME.md`](process-log/chat-exports/LEIA-ME.md)). O registro do processo está nos itens abaixo.
- [x] Git history: um commit por bloco, feito com dulwich (a máquina não tinha git), autor Rafael Pereira com o trailer `Co-Authored-By: Claude`.
- [x] Outro: process log narrativo por bloco (de [00](process-log/00_bloco-0.md) a [05](process-log/05_bloco-5.md), mais [a fase 0](process-log/00_fase0_exploracao.md) e [o plano de execução do Opus](process-log/plano_execucao_opus.md)); [DECISIONS](docs/DECISIONS.md), com uma linha por decisão, a alternativa descartada e o motivo; scripts da fase 0 em [`process-log/scripts/`](process-log/scripts/eda.py).
- [ ] Outro: revisões independentes de contexto limpo (bloco 6), em `process-log/06_revisao-independente.md`, que será acrescentado depois deste texto.

---

_Submissão enviada em: [preencher ao abrir o PR]_
