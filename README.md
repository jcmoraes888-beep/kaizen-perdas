# App Kaizen de Perdas

App web para registrar perdas de produção **por máquina e por motivo**, e transformar esse registro em painel com farol e Pareto. Inspirado num projeto Kaizen real que reduziu o desperdício em 30% no primeiro mês.

> Todos os dados deste repositório são **fictícios** (fábrica de embalagens com 10 máquinas).

## Telas

1. **Registro de perda:** o operador informa máquina, turno, material, kg perdidos e o motivo.
2. **Painel:** perda total em kg e R$, perda % contra a meta (4%) e farol verde/amarelo/vermelho por máquina.
3. **Pareto:** perdas por motivo ou por máquina, com % acumulado e leitura automática dos itens que somam 80%.
4. **Diagnóstico + A3:** por máquina, mostra perda por motivo, tendência semanal e tipo de ação sugerida. Um botão gera um rascunho de **relatório A3 com IA** (OpenAI), com Ishikawa, 5 Porquês e plano de ação.

## Como rodar

```bash
pip install -r requirements.txt
python gerar_dados.py      # opcional: o app cria a base fictícia sozinho se ela não existir
streamlit run app.py       # abre o app no navegador
```

### Chave da OpenAI (para o A3)

1. Copie `.env.exemplo` para `.env`
2. Coloque a sua chave em `OPENAI_API_KEY=`
3. Reinicie o app

No Streamlit Community Cloud, coloque a chave em **Settings → Secrets**:

```toml
OPENAI_API_KEY = "sua-chave"
```

O `.env` está no `.gitignore` e nunca deve ser publicado.

## Estrutura dos dados

| Tabela | Conteúdo |
| --- | --- |
| perdas | Cada apontamento: data, turno, máquina, operador, material, kg, motivo |
| producao | kg utilizado por máquina por dia (base para a perda %) |
| maquinas | AUTO 1 a AUTO 10, meta de perda |
| motivos | Motivo e tipo de ação (Operacional / Mecânica / Material) |
| materiais | Lâmina PET e bobina, com custo por kg |

## Próximas fases

- Exportar o A3 em Word/PDF
- Deploy no Streamlit Community Cloud

## Stack

Python · Streamlit · pandas · Plotly · SQLite · OpenAI API