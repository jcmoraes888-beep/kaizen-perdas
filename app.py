"""
App Kaizen de Perdas - Fase 2 (MVP)

Telas:
  1. Registro de perda (operador)
  2. Painel geral (gestor) com farol por máquina
  3. Pareto por máquina ou por motivo

Uso:  streamlit run app.py
(rode antes:  python gerar_dados.py)
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "kaizen.db"

VERDE, AMARELO, VERMELHO = "#22c55e", "#eab308", "#ef4444"
AZUL = "#1e3a8a"

st.set_page_config(page_title="Kaizen de Perdas", page_icon="📉", layout="wide")

# Streamlit marca a página como inglês; isso faz o Chrome "traduzir" o português e estragar o texto.
import streamlit.components.v1 as components  # noqa: E402

components.html(
    """<script>
    const d = window.parent.document;
    d.documentElement.lang = "pt-BR";
    d.documentElement.setAttribute("translate", "no");
    if (!d.querySelector('meta[name="google"]')) {
      const m = d.createElement("meta"); m.name = "google"; m.content = "notranslate";
      d.head.appendChild(m);
    }
    </script>""",
    height=0,
)


# ---------------------------------------------------------------------------
# Acesso aos dados
# ---------------------------------------------------------------------------
def conectar() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def ler(sql: str, params: tuple = ()) -> pd.DataFrame:
    with conectar() as con:
        return pd.read_sql_query(sql, con, params=params)


def carregar_perdas(inicio: date, fim: date) -> pd.DataFrame:
    """Perdas do período já com nome da máquina, motivo, material e valor em R$."""
    df = ler(
        """
        SELECT p.id, p.data, p.turno, p.operador, p.kg, p.observacao,
               m.nome  AS maquina, m.meta_perda_pct,
               mo.descricao AS motivo, mo.tipo_acao,
               ma.nome AS material, ma.custo_kg_rs
        FROM perdas p
        JOIN maquinas  m  ON m.maquina_id   = p.maquina_id
        JOIN motivos   mo ON mo.motivo_id   = p.motivo_id
        JOIN materiais ma ON ma.material_id = p.material_id
        WHERE p.data BETWEEN ? AND ?
        """,
        (inicio.isoformat(), fim.isoformat()),
    )
    df["valor_rs"] = df["kg"] * df["custo_kg_rs"]
    return df


def carregar_producao(inicio: date, fim: date) -> pd.DataFrame:
    return ler(
        """
        SELECT pr.data, m.nome AS maquina, pr.kg_utilizado
        FROM producao pr JOIN maquinas m ON m.maquina_id = pr.maquina_id
        WHERE pr.data BETWEEN ? AND ?
        """,
        (inicio.isoformat(), fim.isoformat()),
    )


def ordem_maquinas(nomes) -> list:
    """Ordena 'AUTO 1', 'AUTO 2', ..., 'AUTO 10' pelo número."""
    return sorted(nomes, key=lambda n: int(n.split()[-1]) if n.split()[-1].isdigit() else 0)


def farol(perda_pct: float, meta: float) -> str:
    if perda_pct <= meta:
        return VERDE
    if perda_pct <= meta * 1.5:
        return AMARELO
    return VERMELHO


def fmt_rs(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_num(v: float, casas: int = 1) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Tela 1 - Registro de perda
# ---------------------------------------------------------------------------
def tela_registro() -> None:
    st.header("Registro de perda")
    st.caption("Tela do operador: registre cada perda com o motivo. Leva menos de 30 segundos.")

    maquinas = ler("SELECT maquina_id, nome FROM maquinas WHERE ativa = 1")
    maquinas = maquinas.set_index("nome").loc[ordem_maquinas(maquinas["nome"])].reset_index()
    motivos = ler("SELECT motivo_id, descricao FROM motivos ORDER BY motivo_id")
    materiais = ler("SELECT material_id, nome FROM materiais ORDER BY material_id")

    with st.form("registro", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        dia = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        turno = c2.selectbox("Turno", ["1º turno", "2º turno"])
        operador = c3.text_input("Operador")

        c4, c5, c6 = st.columns(3)
        maquina = c4.selectbox("Máquina", maquinas["nome"])
        material = c5.selectbox("Material", materiais["nome"])
        kg = c6.number_input("Quantidade perdida (kg)", min_value=0.0, step=0.1, format="%.2f")

        motivo = st.radio("Motivo da perda", motivos["descricao"], horizontal=True)
        obs = st.text_input("Observação (opcional)")

        enviado = st.form_submit_button("Registrar perda", type="primary")

    if enviado:
        if kg <= 0 or not operador.strip():
            st.error("Preencha o operador e uma quantidade maior que zero.")
        else:
            with conectar() as con:
                con.execute(
                    """INSERT INTO perdas (data, turno, maquina_id, operador, material_id,
                                           kg, motivo_id, observacao)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        dia.isoformat(), turno,
                        int(maquinas.loc[maquinas["nome"] == maquina, "maquina_id"].iloc[0]),
                        operador.strip(),
                        int(materiais.loc[materiais["nome"] == material, "material_id"].iloc[0]),
                        float(kg),
                        int(motivos.loc[motivos["descricao"] == motivo, "motivo_id"].iloc[0]),
                        obs.strip() or None,
                    ),
                )
            st.success(f"Perda registrada: {fmt_num(kg, 2)} kg na {maquina} ({motivo}).")

    st.subheader("Últimos registros")
    ultimos = ler(
        """
        SELECT strftime('%d/%m/%Y', p.data) AS Data, p.turno AS Turno, m.nome AS Máquina, p.operador AS Operador,
               ma.nome AS Material, p.kg AS "Perda (kg)", mo.descricao AS Motivo
        FROM perdas p
        JOIN maquinas m ON m.maquina_id = p.maquina_id
        JOIN motivos mo ON mo.motivo_id = p.motivo_id
        JOIN materiais ma ON ma.material_id = p.material_id
        ORDER BY p.id DESC LIMIT 10
        """
    )
    st.dataframe(ultimos, hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Tela 2 - Painel geral
# ---------------------------------------------------------------------------
def tela_painel(inicio: date, fim: date) -> None:
    st.header("Painel de perdas")
    st.caption(f"Período: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} · farol: verde ≤ meta · amarelo até 1,5× a meta · vermelho acima")

    perdas = carregar_perdas(inicio, fim)
    prod = carregar_producao(inicio, fim)
    if perdas.empty or prod.empty:
        st.info("Sem dados no período escolhido.")
        return

    meta = float(perdas["meta_perda_pct"].iloc[0])
    total_kg = perdas["kg"].sum()
    total_rs = perdas["valor_rs"].sum()
    perda_pct = total_kg / prod["kg_utilizado"].sum() * 100

    por_maq = (
        perdas.groupby("maquina").agg(kg=("kg", "sum"), valor_rs=("valor_rs", "sum"))
        .join(prod.groupby("maquina")["kg_utilizado"].sum())
    )
    por_maq["perda_pct"] = por_maq["kg"] / por_maq["kg_utilizado"] * 100
    por_maq = por_maq.loc[ordem_maquinas(por_maq.index)]
    fora_meta = int((por_maq["perda_pct"] > meta).sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Perda total", f"{fmt_num(total_kg)} kg")
    k2.metric("Custo da perda", fmt_rs(total_rs))
    k3.metric("Perda geral", f"{fmt_num(perda_pct, 2)}%", f"{fmt_num(perda_pct - meta, 2)} p.p. vs meta {fmt_num(meta, 0)}%", delta_color="inverse")
    k4.metric("Máquinas fora da meta", f"{fora_meta} de {len(por_maq)}")

    # Farol por máquina
    cores = [farol(v, meta) for v in por_maq["perda_pct"]]
    fig = go.Figure(go.Bar(
        x=por_maq.index, y=por_maq["perda_pct"], marker_color=cores,
        text=[f"{fmt_num(v, 1)}%" for v in por_maq["perda_pct"]], textposition="outside",
        customdata=list(zip(por_maq["kg"], por_maq["valor_rs"])),
        hovertemplate="%{x}<br>Perda: %{y:.2f}%<br>%{customdata[0]:.1f} kg · R$ %{customdata[1]:.2f}<extra></extra>",
    ))
    fig.add_hline(y=meta, line_dash="dash", line_color="#64748b",
                  annotation_text=f"Meta {fmt_num(meta, 0)}%", annotation_position="top left")
    fig.update_layout(title="Perda % por máquina", yaxis_title="Perda (%)", height=420,
                      margin=dict(t=60, b=40), showlegend=False)
    st.plotly_chart(fig, width="stretch")

    # Evolução diária
    diario = perdas.groupby("data")["kg"].sum().reset_index()
    fig2 = go.Figure(go.Scatter(x=pd.to_datetime(diario["data"]), y=diario["kg"],
                                mode="lines", line=dict(color=AZUL, width=2)))
    fig2.update_layout(title="Perda diária (kg)", yaxis_title="kg", height=320, margin=dict(t=60, b=40))
    st.plotly_chart(fig2, width="stretch")

    with st.expander("Tabela por máquina"):
        tabela = por_maq.reset_index().rename(columns={
            "maquina": "Máquina", "kg": "Perda (kg)", "valor_rs": "Custo (R$)",
            "kg_utilizado": "Utilizado (kg)", "perda_pct": "Perda (%)"})
        st.dataframe(tabela.round(2), hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Tela 3 - Pareto
# ---------------------------------------------------------------------------
def tela_pareto(inicio: date, fim: date) -> None:
    st.header("Pareto de perdas")
    perdas = carregar_perdas(inicio, fim)
    if perdas.empty:
        st.info("Sem dados no período escolhido.")
        return

    c1, c2, c3 = st.columns(3)
    agrupar = c1.radio("Agrupar por", ["Motivo", "Máquina"], horizontal=True)
    medida = c2.radio("Medida", ["kg", "R$"], horizontal=True)
    maquinas = ["Todas"] + ordem_maquinas(perdas["maquina"].unique())
    filtro = c3.selectbox("Máquina", maquinas, disabled=(agrupar == "Máquina"))

    if agrupar == "Motivo" and filtro != "Todas":
        perdas = perdas[perdas["maquina"] == filtro]

    coluna = "motivo" if agrupar == "Motivo" else "maquina"
    valor = "kg" if medida == "kg" else "valor_rs"
    p = perdas.groupby(coluna)[valor].sum().sort_values(ascending=False).reset_index()
    p["acum_pct"] = p[valor].cumsum() / p[valor].sum() * 100

    fig = go.Figure()
    fig.add_bar(x=p[coluna], y=p[valor], name=medida, marker_color=AZUL,
                text=[fmt_num(v) for v in p[valor]], textposition="outside")
    fig.add_scatter(x=p[coluna], y=p["acum_pct"], name="% acumulado", yaxis="y2",
                    mode="lines+markers", line=dict(color=VERMELHO, width=2))
    fig.add_hline(y=80, yref="y2", line_dash="dot", line_color="#64748b")
    titulo = f"Pareto por {agrupar.lower()}" + (f" · {filtro}" if agrupar == "Motivo" and filtro != "Todas" else "")
    fig.update_layout(
        title=titulo, height=480, margin=dict(t=60, b=40),
        yaxis=dict(title=medida),
        yaxis2=dict(title="% acumulado", overlaying="y", side="right", range=[0, 105],
                    tickvals=[0, 20, 40, 60, 80, 100], ticksuffix="%", showgrid=False),
        legend=dict(orientation="h", y=-0.15),
    )
    st.plotly_chart(fig, width="stretch")

    # Leitura automática do Pareto
    n80 = int((p["acum_pct"] < 80).sum()) + 1
    principais = ", ".join(p[coluna].head(n80))
    st.markdown(
        f"**Leitura:** {n80} de {len(p)} itens ({principais}) concentram cerca de "
        f"**{fmt_num(p['acum_pct'].iloc[n80 - 1], 0)}%** da perda. Comece por eles."
    )

    if agrupar == "Motivo":
        tipos = perdas.groupby("tipo_acao")[valor].sum().sort_values(ascending=False)
        st.caption("Tipo de ação sugerida: " + " · ".join(
            f"{t}: {fmt_num(v / tipos.sum() * 100, 0)}%" for t, v in tipos.items()))


# ---------------------------------------------------------------------------
# Tela 4 - Diagnóstico por máquina + A3 com IA
# ---------------------------------------------------------------------------
ACAO_SUGERIDA = {
    "Operacional": "treinamento do operador, padronização da regulagem e do setup",
    "Mecânica": "manutenção corretiva/preventiva e ajuste do ponto da máquina",
    "Material": "inspeção de recebimento e conversa com o fornecedor",
}


def montar_resumo(maquina: str, inicio: date, fim: date, kg: float, rs: float,
                  pct: float, meta: float, posicao: int, total_maq: int,
                  motivos: pd.DataFrame, tipos: pd.Series, turnos: pd.Series,
                  utilizado: float, dias: int) -> str:
    """Texto com os números da máquina, enviado para a IA montar o A3."""
    linhas = [
        f"Máquina: {maquina} (termoformagem de embalagens a partir de lâmina PET extrudada, dados fictícios)",
        f"Período: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}",
        f"Perda: {kg:.1f} kg, R$ {rs:.2f}, {pct:.2f}% do material utilizado",
        f"Material utilizado no período: {utilizado:.1f} kg em {dias} dias com produção",
        f"Custo médio da perda: R$ {rs / kg:.2f} por kg",
        f"Meta de perda: {meta:.1f}%",
        f"Perda máxima na meta: {utilizado * meta / 100:.1f} kg no período",
        f"Ganho se atingir a meta: {max(kg - utilizado * meta / 100, 0):.1f} kg e "
        f"R$ {max(kg - utilizado * meta / 100, 0) * rs / kg:.2f} no período (cálculo já feito, use este valor)",
        f"Ranking: {posicao}ª maior perda % entre {total_maq} máquinas",
        "Perda por motivo (kg e % do total da máquina):",
    ]
    total = motivos["kg"].sum()
    for _, r in motivos.iterrows():
        linhas.append(f"- {r['motivo']} ({r['tipo_acao']}): {r['kg']:.1f} kg ({r['kg'] / total * 100:.0f}%)")
    linhas.append("Perda por tipo de ação: " + ", ".join(
        f"{t} {v / tipos.sum() * 100:.0f}%" for t, v in tipos.items()))
    linhas.append("Perda por turno: " + ", ".join(
        f"{t} {v:.1f} kg" for t, v in turnos.items()))
    return "\n".join(linhas)


LIMITE_A3_POR_SESSAO = 5  # protege os créditos da API quando o app estiver público


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def a3_em_cache(resumo: str, versao: str) -> str:
    """Mesmos dados = mesmo A3, sem gastar crédito de novo (vale por 24 h)."""
    import ia_a3
    return ia_a3.gerar_a3(resumo)


def tela_diagnostico(inicio: date, fim: date) -> None:
    st.header("Diagnóstico por máquina")
    perdas = carregar_perdas(inicio, fim)
    prod = carregar_producao(inicio, fim)
    if perdas.empty or prod.empty:
        st.info("Sem dados no período escolhido.")
        return

    # ranking de perda % para sugerir a pior máquina primeiro
    ranking = (perdas.groupby("maquina")["kg"].sum()
               / prod.groupby("maquina")["kg_utilizado"].sum() * 100).sort_values(ascending=False)
    maquina = st.selectbox("Máquina", list(ranking.index),
                           help="Ordenadas da maior para a menor perda %")

    dm = perdas[perdas["maquina"] == maquina]
    pm = prod[prod["maquina"] == maquina]
    meta = float(dm["meta_perda_pct"].iloc[0]) if not dm.empty else 4.0
    kg, rs = dm["kg"].sum(), dm["valor_rs"].sum()
    pct = kg / pm["kg_utilizado"].sum() * 100
    posicao = list(ranking.index).index(maquina) + 1
    dias = pm["data"].nunique()

    st.caption(f"{posicao}ª maior perda % entre {len(ranking)} máquinas no período")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Perda", f"{fmt_num(kg)} kg")
    k2.metric("Custo", fmt_rs(rs))
    k3.metric("Perda %", f"{fmt_num(pct, 2)}%", f"{fmt_num(pct - meta, 2)} p.p. vs meta", delta_color="inverse")
    k4.metric("Média por dia", f"{fmt_num(kg / dias, 2)} kg")

    motivos = (dm.groupby(["motivo", "tipo_acao"])["kg"].sum()
               .reset_index().sort_values("kg", ascending=False))
    tipos = dm.groupby("tipo_acao")["kg"].sum().sort_values(ascending=False)
    turnos = dm.groupby("turno")["kg"].sum()

    c1, c2 = st.columns([3, 2])
    with c1:
        m = motivos.sort_values("kg")
        fig = go.Figure(go.Bar(
            x=m["kg"], y=m["motivo"], orientation="h", marker_color=AZUL,
            text=[f"{fmt_num(v)} kg" for v in m["kg"]], textposition="outside"))
        fig.update_layout(title="Perda por motivo", height=360, margin=dict(t=60, l=10, r=40),
                          xaxis=dict(title="kg", range=[0, m["kg"].max() * 1.25]))
        st.plotly_chart(fig, width="stretch")
    with c2:
        semanal = dm.assign(semana=pd.to_datetime(dm["data"]).dt.to_period("W").dt.start_time)
        ps = pm.assign(semana=pd.to_datetime(pm["data"]).dt.to_period("W").dt.start_time)
        s = (semanal.groupby("semana")["kg"].sum() / ps.groupby("semana")["kg_utilizado"].sum() * 100).dropna()
        fig2 = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines+markers",
                                    line=dict(color=VERMELHO if pct > meta else VERDE, width=2)))
        fig2.add_hline(y=meta, line_dash="dash", line_color="#64748b")
        fig2.update_layout(title="Perda % por semana", height=360, margin=dict(t=60, r=10),
                           yaxis_title="%", yaxis=dict(rangemode="tozero"))
        st.plotly_chart(fig2, width="stretch")

    principal = tipos.index[0]
    st.markdown(
        f"**Leitura:** {fmt_num(tipos.iloc[0] / tipos.sum() * 100, 0)}% da perda é de causa "
        f"**{principal.lower()}**. Motivo principal: **{motivos.iloc[0]['motivo']}** "
        f"({fmt_num(motivos.iloc[0]['kg'] / motivos['kg'].sum() * 100, 0)}%). "
        f"Ação sugerida: {ACAO_SUGERIDA.get(principal, 'investigar no chão de fábrica')}."
    )
    st.caption("Por turno: " + " · ".join(f"{t}: {fmt_num(v)} kg" for t, v in turnos.items()))

    # ---------------- A3 com IA ----------------
    st.divider()
    st.subheader("Relatório A3 com IA")
    st.caption("A IA monta um rascunho a partir dos números acima. Revise e valide as causas no chão de fábrica.")
    import importlib
    import ia_a3
    importlib.reload(ia_a3)  # garante que mudanças no ia_a3.py valham sem reiniciar
    st.caption(f"Instruções do A3: versão {getattr(ia_a3, 'VERSAO_INSTRUCOES', '1')} · modelo: {ia_a3.obter_modelo()}")

    resumo = montar_resumo(maquina, inicio, fim, kg, rs, pct, meta, posicao,
                           len(ranking), motivos, tipos, turnos,
                           pm["kg_utilizado"].sum(), dias)
    with st.expander("Dados que serão enviados para a IA"):
        st.code(resumo, language=None)

    chave_ok = ia_a3.obter_chave() is not None
    if not chave_ok:
        st.warning("Chave da OpenAI não configurada. Crie o arquivo .env com OPENAI_API_KEY=... e reinicie o app.")

    chave_estado = f"a3_{maquina}_{inicio}_{fim}"
    usados = st.session_state.get("a3_gerados", 0)
    restantes = LIMITE_A3_POR_SESSAO - usados
    st.caption(f"Limite de demonstração: {restantes} de {LIMITE_A3_POR_SESSAO} A3 nesta sessão.")
    if st.button("Gerar A3 com IA", type="primary", disabled=not chave_ok or restantes <= 0):
        with st.spinner(f"Gerando o A3 da {maquina} com {ia_a3.obter_modelo()}..."):
            try:
                st.session_state[chave_estado] = a3_em_cache(resumo, ia_a3.VERSAO_INSTRUCOES)
                st.session_state["a3_gerados"] = usados + 1
            except Exception as erro:  # mostra o erro sem derrubar o app
                st.error(f"Não foi possível gerar o A3: {erro}")

    if chave_estado in st.session_state:
        a3 = st.session_state[chave_estado]
        st.markdown(a3.replace("$", "\\$"))  # evita que "R$" vire fórmula LaTeX
        st.download_button("Baixar A3 (.md)", a3, file_name=f"A3_{maquina.replace(' ', '_')}.md",
                           mime="text/markdown")


# ---------------------------------------------------------------------------
# Navegação
# ---------------------------------------------------------------------------
def main() -> None:
    if not DB_PATH.exists():
        import gerar_dados  # na nuvem o kaizen.db não vai para o GitHub: cria a base fictícia
        with st.spinner("Criando a base de dados fictícia..."):
            gerar_dados.main()

    st.sidebar.title("📉 Kaizen de Perdas")
    tela = st.sidebar.radio("Tela", ["Registro de perda", "Painel", "Pareto", "Diagnóstico + A3"])

    st.sidebar.divider()
    hoje = date.today()
    periodo = st.sidebar.date_input(
        "Período de análise", value=(hoje - timedelta(days=30), hoje), format="DD/MM/YYYY")
    inicio, fim = periodo if isinstance(periodo, tuple) and len(periodo) == 2 else (periodo, periodo)
    st.sidebar.caption("Dados fictícios para demonstração.")

    if tela == "Registro de perda":
        tela_registro()
    elif tela == "Painel":
        tela_painel(inicio, fim)
    elif tela == "Pareto":
        tela_pareto(inicio, fim)
    else:
        tela_diagnostico(inicio, fim)


main()