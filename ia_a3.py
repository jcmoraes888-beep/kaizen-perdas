"""
Fase 3 - Geração do rascunho de A3 com a API da OpenAI (saída estruturada).

A IA não devolve mais um texto livre: ela é obrigada a responder num JSON que segue
o schema da classe A3 abaixo (Structured Outputs, strict). O app recebe campos com
tipo garantido e monta o Markdown, a tabela do plano de ação e os downloads a partir deles.

A chave é lida, nesta ordem:
  1. st.secrets["OPENAI_API_KEY"]   (Streamlit Cloud)
  2. variável de ambiente / arquivo .env  (computador local)

O modelo pode ser trocado no .env com OPENAI_MODEL=nome-do-modelo
(precisa ser um modelo com suporte a Structured Outputs, ex.: gpt-4o-mini, gpt-4o, gpt-4.1).
"""

import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, create_model

load_dotenv()

MODELO_PADRAO = "gpt-4o-mini"
VERSAO_INSTRUCOES = "5"  # 5 = Ishikawa separado em motivos/hipóteses e 5 porquês fixos; invalida o cache


# ---------------------------------------------------------------------------
# Schema do A3 — é isto que a IA é obrigada a devolver
# ---------------------------------------------------------------------------
Categoria6M = Literal["Método", "Máquina", "Material", "Mão de obra", "Medição", "Meio ambiente"]
TipoAcao = Literal["Operacional", "Mecânica", "Material"]
Responsavel = Literal["Supervisor de produção", "Líder de turno", "Manutenção",
                      "Qualidade", "PCP", "Compras"]


class MotivoPerda(BaseModel):
    motivo: str
    kg: float
    pct: float = Field(description="% do total de perda da máquina")


class SituacaoAtual(BaseModel):
    perda_kg: float
    perda_rs: float
    perda_pct: float = Field(description="% do material utilizado")
    meta_pct: float
    motivos: list[MotivoPerda] = Field(description="Todos os motivos registrados, do maior para o menor kg")
    destaque_turnos: str | None = Field(
        description="Frase destacando a diferença entre turnos se ela passar de 20%; null caso contrário")


class Meta(BaseModel):
    descricao: str = Field(description="Ex.: 'Reduzir a perda para abaixo de 4,0%'")
    ganho_kg: float = Field(description="Ganho em kg no período se a meta for atingida")
    ganho_rs: float = Field(description="Ganho em R$ no período se a meta for atingida")
    conta: str = Field(description="A conta que leva ao ganho, mostrada passo a passo")


class MotivoIshikawa(BaseModel):
    categoria: Categoria6M
    motivo: str = Field(description="Um motivo registrado, escrito exatamente como nos dados")


class Hipotese(BaseModel):
    categoria: Categoria6M
    causa: str = Field(description="Causa provável de chão de fábrica, ainda a validar")


_RESPOSTA = "Só a resposta, sem repetir a pergunta 'Por quê?'"


class CincoPorques(BaseModel):
    problema: str = Field(description="A causa principal (motivo com maior kg)")
    porque_1: str = Field(description=_RESPOSTA + " — por que o problema acontece")
    porque_2: str = Field(description=_RESPOSTA + " — por que a resposta 1 acontece")
    porque_3: str = Field(description=_RESPOSTA + " — por que a resposta 2 acontece")
    porque_4: str = Field(description=_RESPOSTA + " — por que a resposta 3 acontece")
    porque_5: str = Field(description=_RESPOSTA + " — por que a resposta 4 acontece")
    causa_raiz: str

    def porques(self) -> list[str]:
        return [self.porque_1, self.porque_2, self.porque_3, self.porque_4, self.porque_5]


class Acao(BaseModel):
    acao: str
    causa_atacada: str = Field(description="Um dos motivos registrados para a máquina")
    tipo: TipoAcao
    responsavel: Responsavel
    prazo_dias: int = Field(description="Entre 7 e 30")


class Acompanhamento(BaseModel):
    indicador: str
    frequencia: str
    registro: str
    criterio_sucesso: str = Field(description="Meta numérica + período de sustentação, ex.: abaixo de 4,0% por 4 semanas seguidas")


class A3(BaseModel):
    maquina: str
    contexto: str = Field(description="Duas frases: o que a máquina faz e por que foi escolhida")
    situacao_atual: SituacaoAtual
    meta: Meta
    ishikawa_motivos: list[MotivoIshikawa] = Field(description="Cada motivo registrado, uma vez, na sua categoria 6M")
    ishikawa_hipoteses: list[Hipotese]
    cinco_porques: CincoPorques
    plano_acao: list[Acao]
    acompanhamento: Acompanhamento


INSTRUCOES = """Você é um especialista em Lean Manufacturing e melhoria contínua (Kaizen)
em indústrias de embalagens. Escreva em português do Brasil, com linguagem objetiva
de chão de fábrica, sem jargão desnecessário.

Com base APENAS nos dados fornecidos, preencha o relatório A3 no formato pedido.

Contexto: duas frases sobre o que a máquina faz e por que ela foi escolhida (posição no ranking).

Situação atual: perda em kg, R$ e % do material utilizado, e a meta. Liste TODOS os motivos
com kg e %. Se a diferença entre turnos for maior que 20%, descreva em destaque_turnos.

Meta: perda abaixo da meta, com o ganho em kg e R$ no período se a meta for atingida.
Use o valor de ganho já calculado nos dados e mostre a conta.

Ishikawa (6M): em ishikawa_motivos, coloque cada motivo registrado (com o nome exato
dos dados, sem reescrever) na categoria certa. Em ishikawa_hipoteses, acrescente causas
prováveis de chão de fábrica (ex.: falta de padrão de regulagem, desgaste de ferramenta,
temperatura de aquecimento, variação da chapa). Não repita um motivo como hipótese.

5 Porquês: o problema é o motivo com maior kg. Preencha exatamente 5 respostas, cada uma
explicando a anterior, sem escrever as perguntas. Os porquês ficam no nível da máquina,
do processo e da operação (como um supervisor experiente perguntaria no chão de fábrica),
terminando numa causa raiz corrigível na própria máquina ou no padrão de trabalho
(ex.: não existe folha de parâmetros, a ferramenta não tem troca preventiva).
Não termine em causas de gestão ou de pessoas (supervisão não priorizou, falta de
planejamento, equipe sobrecarregada, falta de comprometimento).

Plano de ação:
- Pelo menos uma ação para cada motivo que represente 10% ou mais da perda.
- Operacional: padrão de regulagem, folha de parâmetros, treinamento no posto.
- Mecânica: manutenção, ajuste do ponto da máquina, checklist preventivo.
- Treinamento é do Supervisor de produção ou do Líder de turno.
- Prazos entre 7 e 30 dias.
- A causa atacada é sempre um dos motivos registrados, escrito exatamente como nos dados
  (falta de treinamento ou de padrão é a hipótese por trás do motivo, não a causa atacada).
- Treinamento sozinho não resolve: para cada motivo com 10% ou mais da perda, inclua também
  uma ação Mecânica ou de Material (ex.: verificar temperatura e resistência da selagem,
  trocar borracha ou ferramenta desgastada, inspecionar a chapa no recebimento).

Acompanhamento: indicador, frequência, como registrar (o próprio app de perdas) e critério de sucesso
com meta numérica E período de sustentação (ex.: "perda abaixo de 4,0% por 4 semanas seguidas").

Regras:
- Escreva sempre "perda", nunca "prejuízo", para quantidades em kg.
- Nos textos, use números no padrão brasileiro: vírgula decimal e ponto de milhar,
  com "R$" antes do valor (ex.: 174,0 kg; R$ 2.772,06; 8,76%).
- Não invente números que não estejam nos dados ou não venham de uma conta mostrada.
- Seja específico para a máquina e para os motivos dela.
"""


def obter_chave() -> str | None:
    try:
        import streamlit as st
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass  # sem secrets.toml: segue para o .env
    return os.getenv("OPENAI_API_KEY")


def obter_modelo() -> str:
    return os.getenv("OPENAI_MODEL", MODELO_PADRAO)


def schema_da_maquina(motivos: list[str]) -> type[A3]:
    """A3 com o campo causa_atacada limitado aos motivos registrados desta máquina.
    O schema é montado na hora, então o modelo não consegue inventar outra causa."""
    if not motivos:
        return A3
    opcoes = Literal[tuple(motivos)]  # type: ignore[valid-type]
    AcaoMaquina = create_model("Acao", __base__=Acao, causa_atacada=(opcoes, ...))
    MotivoMaquina = create_model("MotivoPerda", __base__=MotivoPerda, motivo=(opcoes, ...))
    IshikawaMaquina = create_model("MotivoIshikawa", __base__=MotivoIshikawa, motivo=(opcoes, ...))
    SituacaoMaquina = create_model("SituacaoAtual", __base__=SituacaoAtual,
                                   motivos=(list[MotivoMaquina], ...))
    return create_model("A3", __base__=A3,
                        situacao_atual=(SituacaoMaquina, ...),
                        ishikawa_motivos=(list[IshikawaMaquina], ...),
                        plano_acao=(list[AcaoMaquina], ...))


def gerar_a3(resumo: str, motivos: list[str] | None = None) -> A3:
    """Envia o resumo da máquina para a OpenAI e devolve o A3 já validado."""
    from openai import OpenAI

    chave = obter_chave()
    if not chave:
        raise RuntimeError(
            "Chave da OpenAI não encontrada. Crie o arquivo .env com OPENAI_API_KEY=..."
        )

    cliente = OpenAI(api_key=chave)
    resposta = cliente.chat.completions.parse(
        model=obter_modelo(),
        temperature=0.2,
        messages=[
            {"role": "system", "content": INSTRUCOES},
            {"role": "user", "content": resumo},
        ],
        response_format=schema_da_maquina(list(motivos or [])),  # vira JSON Schema strict
    )
    mensagem = resposta.choices[0].message
    if mensagem.refusal:
        raise RuntimeError(f"O modelo recusou gerar o A3: {mensagem.refusal}")
    return mensagem.parsed


# ---------------------------------------------------------------------------
# Saídas montadas a partir dos campos
# ---------------------------------------------------------------------------
def _n(valor: float, casas: int = 1) -> str:
    """Número no padrão brasileiro: 1.234,5"""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def para_markdown(a3: A3) -> str:
    s, m = a3.situacao_atual, a3.meta
    linhas = [
        f"# A3 - Redução de perdas - {a3.maquina}",
        "", "## 1. Contexto", a3.contexto,
        "", "## 2. Situação atual",
        f"Perda de **{_n(s.perda_kg)} kg** (R$ {_n(s.perda_rs, 2)}), "
        f"**{_n(s.perda_pct, 2)}%** do material utilizado, contra meta de {_n(s.meta_pct)}%.",
        "", "| Motivo | kg | % |", "|---|---:|---:|",
    ]
    linhas += [f"| {x.motivo} | {_n(x.kg)} | {_n(x.pct, 0)}% |" for x in s.motivos]
    if s.destaque_turnos:
        linhas += ["", f"> **Turnos:** {s.destaque_turnos}"]

    linhas += ["", "## 3. Meta", m.descricao,
               "", f"Ganho estimado no período: **{_n(m.ganho_kg)} kg** e **R$ {_n(m.ganho_rs, 2)}**.",
               "", f"Conta: {m.conta}",
               "", "## 4. Análise de causas (Ishikawa)"]
    numeros = {x.motivo: x for x in s.motivos}  # kg e % vêm da situação atual
    for cat in ["Método", "Máquina", "Material", "Mão de obra", "Medição", "Meio ambiente"]:
        registrados = [c for c in a3.ishikawa_motivos if c.categoria == cat]
        hipoteses = [h for h in a3.ishikawa_hipoteses if h.categoria == cat]
        if not registrados and not hipoteses:
            continue
        linhas += ["", f"**{cat}**", ""]
        for c in registrados:
            x = numeros.get(c.motivo)
            linhas.append(f"- {c.motivo}" + (f" — {_n(x.kg)} kg ({_n(x.pct, 0)}%)" if x else ""))
        linhas += [f"- {h.causa} *(hipótese a validar)*" for h in hipoteses]

    p = a3.cinco_porques
    linhas += ["", "## 5. 5 Porquês da causa principal", f"**Problema:** {p.problema}", ""]
    linhas += [f"{i}. Por quê? {q}" for i, q in enumerate(p.porques(), 1)]
    linhas += ["", f"**Causa raiz:** {p.causa_raiz} *(hipótese a validar com o operador)*",
               "", "## 6. Plano de ação",
               "| Ação | Causa atacada | Tipo | Responsável | Prazo |", "|---|---|---|---|---|"]
    linhas += [f"| {x.acao} | {x.causa_atacada} | {x.tipo} | {x.responsavel} | {x.prazo_dias} dias |"
               for x in a3.plano_acao]

    ac = a3.acompanhamento
    linhas += ["", "## 7. Acompanhamento",
               f"- **Indicador:** {ac.indicador}", f"- **Frequência:** {ac.frequencia}",
               f"- **Registro:** {ac.registro}", f"- **Critério de sucesso:** {ac.criterio_sucesso}"]
    return "\n".join(linhas)


def plano_para_csv(a3: A3) -> str:
    """Plano de ação em CSV (separador ;) para abrir direto no Excel."""
    import pandas as pd
    df = pd.DataFrame([x.model_dump() for x in a3.plano_acao]).rename(columns={
        "acao": "Ação", "causa_atacada": "Causa atacada", "tipo": "Tipo",
        "responsavel": "Responsável", "prazo_dias": "Prazo (dias)"})
    return df.to_csv(index=False, sep=";")
