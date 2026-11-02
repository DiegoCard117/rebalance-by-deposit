# rebalance-by-deposit

[Read in English](README.md)

“Tenho X para investir hoje. O que compro para aproximar a carteira das metas,
sem vender nada?”

Aportes recorrentes permitem rebalancear sem vender posições e gerar impostos
ou taxas de venda. Esta biblioteca para Python 3.12+ foi extraída de um app em
produção. Usa apenas a biblioteca padrão, não tem dependências de runtime e
também calcula ganho de capital realizado por FIFO.

## Instalação e execução

Na raiz do repositório, com Python 3.12 ou superior:

```sh
python -m venv .venv
# Ative no Windows PowerShell: .venv\Scripts\Activate.ps1
# Ative no macOS/Linux: source .venv/bin/activate
pip install -e .[dev]
pytest
mypy src
python examples/demo.py
```

O extra opcional `dev` instala pytest e mypy. O pacote inclui `py.typed` e usa
o layout `src`.

## Uso

```python
from decimal import Decimal as D
from rebalance_by_deposit import Holding, plan_deposit

holdings = [
    Holding("AAA3", "acoes", D("4"), D("100")),
    Holding("BBB11", "fundos", D("3"), D("100")),
    Holding("TESOURO-X", "renda_fixa", D("3"), D("100")),
]
plan = plan_deposit(
    holdings,
    {"acoes": D("50"), "fundos": D("30"), "renda_fixa": D("20")},
    D("1000"),
)
for buy in plan.buys:
    print(buy.ticker, buy.quantity, buy.cost)
assert plan.spent + plan.left_over == D("1000")
```

`Holding`, `Buy`, `Plan`, `Trade` e `RealizedLot` são dataclasses congeladas.
`Plan.buys` contém uma linha por ticker, ordenada por ticker. Use
`Holding.fractional=True` para permitir quantidades com oito casas decimais.
Holdings repetidas do mesmo ticker precisam ter categoria, preço e modo fracionário
iguais; todas as quantidades existentes entram no valor da carteira.

## Algoritmo

1. Valida carteira não vazia, aporte positivo, metas não negativas que somem
   exatamente 100 e uma meta para cada categoria das holdings. Categorias sem
   ativos são permitidas, mas não podem receber compras.
2. Calcula o valor atual pelos preços informados. O total novo é o valor atual
   mais o aporte inteiro. Para cada categoria, calcula
   `falta = max(0, total_novo * meta / 100 - valor_atual_da_categoria)`.
3. Distribui o aporte proporcionalmente às faltas. Se a soma for zero, usa os pesos
   das metas. Arredonda os orçamentos para baixo em centavos para não exceder o caixa.
4. Percorre as categorias da maior falta para a menor. Divide cada orçamento
   igualmente entre os tickers distintos elegíveis, arredondando a parcela para
   baixo em centavos. Ignora preços menores ou iguais a zero na compra. Compra cotas
   inteiras arredondadas para baixo, ou frações com oito casas arredondadas para
   baixo. Não desconta taxas nas compras do aporte.
5. Recalcula as faltas usando o mesmo total novo. Escolhe a categoria com a maior
   falta positiva que consiga comprar algo. Compra uma cota do ativo elegível mais
   barato dela ou usa a sobra para comprá-lo, se for fracionário. Repete até nenhuma
   categoria abaixo da meta conseguir comprar. A precisão de oito casas e os
   centavos podem deixar uma pequena sobra. Uma cota inteira ou gastar toda a sobra
   no fracionário pode fazer a categoria ultrapassar a meta.
6. Agrupa compras por ticker. Custos usam centavos com `ROUND_HALF_UP`, calculados
   sobre a quantidade acumulada do ticker. Preserva sempre
   `spent + left_over == deposit`. Nunca sugere venda.

Empates entre categorias usam o nome; entre ativos de mesmo preço, o ticker.
Compras que custariam zero após arredondamento são ignoradas para garantir que
o laço da sobra avance. Valores não finitos e quantidades negativas são rejeitados.
Preços menores ou iguais a zero ainda entram na fórmula de valor atual informada;
forneça preços atuais confiáveis para obter alocações úteis.

No exemplo acima, a carteira atual vale 1.000: 400 em ações, 300 em fundos e
300 em renda fixa. O aporte de 1.000 leva o total novo a 2.000:

| Categoria | Atual | Meta | Valor desejado | Falta / orçamento | Compra a 100 | Antes | Depois |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ações | 400 | 50% | 1.000 | 600 | 6 | 40% | 50% |
| Fundos | 300 | 30% | 600 | 300 | 3 | 30% | 30% |
| Renda fixa | 300 | 20% | 400 | 100 | 1 | 30% | 20% |

Os 1.000 são gastos. Quando sobra caixa, `allocation_after` inclui essa sobra no
denominador, mas não cria uma categoria de caixa: os percentuais podem somar menos
de 100. Cada percentual é arredondado independentemente para duas casas. Uma
carteira de valor zero informa percentuais iniciais iguais a zero.

## Por que Decimal?

Ponto flutuante binário não representa exatamente muitos valores monetários.
Passe valores `Decimal` construídos de strings, como `D("19.99")`, nunca floats.
Preços, quantidades, metas, custos e cálculos usam `Decimal`. Dinheiro tem duas
casas decimais; quantidades fracionárias de compra têm oito. A biblioteca usa o
contexto Decimal atual do Python, com 28 dígitos significativos por padrão;
quem trabalhar com números excepcionalmente grandes pode aumentar a precisão.

## Ganho realizado por FIFO

```python
from datetime import date
from decimal import Decimal as D
from rebalance_by_deposit import Trade, realized_gains

rows = realized_gains([
    Trade("AAA3", date(2024, 1, 1), "buy", D("10"), D("10"), D("2")),
    Trade("AAA3", date(2025, 1, 1), "sell", D("4"), D("15"), D("1")),
])
assert rows[0].cost_basis == D("40.80")
assert rows[0].proceeds == D("59.00")
assert rows[0].gain == D("18.20")
assert rows[0].long_term
```

As operações são agrupadas internamente por ticker e processadas por dia, com
compras antes de vendas no mesmo dia. Outros empates preservam a ordem de entrada.
Compras geram lotes com custo por cota `(quantidade * preço + taxas) / quantidade`.
Vendas usam receita por cota `(quantidade * preço - taxas) / quantidade` e consomem
os lotes mais antigos primeiro, produzindo uma linha `RealizedLot` por lote
consumido. Receita e custo são arredondados separadamente para centavos com
`ROUND_HALF_UP`; o ganho é a diferença. Arredondar por lote pode produzir diferença
de centavos em relação a arredondar a venda inteira. FIFO não arredonda quantidades.
`holding_days` é a diferença entre as datas e `long_term` indica pelo menos
365 dias. Vender mais que a posição disponível gera `ValueError`, sem inventar lote.

## Para ler mais

Artigos sobre o algoritmo:

- [Rebalanceando uma carteira sem vender nada: o algoritmo do aporte](https://medium.com/@diegocardoso117/rebalanceando-uma-carteira-sem-vender-nada-o-algoritmo-do-aporte-d3c2667f8dbc)
- [Rebalanceando a carteira só com o próximo aporte (sem vender)](https://medium.com/@diegocardoso117/rebalanceando-a-carteira-s%C3%B3-com-o-pr%C3%B3ximo-aporte-sem-vender-718315aa4a42)

## Limitações

Não é recomendação de investimento. O planejador não considera impostos, taxas
de corretagem na compra, lote mínimo além de uma cota, liquidez, variações de preço,
câmbio ou eventos corporativos. Informe tudo na mesma moeda. FIFO calcula ganho,
não imposto devido; a marca de 365 dias é uma classificação fixa, não uma regra
tributária de determinada jurisdição. O algoritmo é uma heurística determinística,
não um otimizador para atingir metas exatas. Categorias que já estão na meta ou
acima dela não recebem compras na etapa da sobra.

Licença MIT, copyright 2026 DiegoCard117.
