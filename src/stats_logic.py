"""
Presentacion y logica estadistica compartida por las paginas.

PALETA. Un color por regimen, y los mismos tres en todo el aplicativo. No es
decoracion: el regimen es la variable que organiza la investigacion, y que
"Demora prolongada" sea siempre el mismo tono permite leer cualquier grafico
sin volver a la leyenda.

FORMATO. Se escribe en convencion castellana -punto para los miles, coma para
los decimales-, que no es lo que hace Python por defecto.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# --- paleta ------------------------------------------------------------------
ACENTO = "#2BD4E8"
FONDO = "#080E14"
PANEL = "#101E28"
TEXTO = "#E8F2F5"
TENUE = "#6E8894"
REJILLA = "#1C2E3A"

REGIMEN = {
    "Puntual":            "#3DDC97",   # verde: sale al minuto
    "Demora breve":       "#2BD4E8",   # cian: el modo bajo, la inmensa mayoria
    "Demora prolongada":  "#F2545B",   # rojo: el modo alto, separado del resto
}
BANDA = {
    "Principal":   "#2BD4E8",
    "Intermedio":  "#7FA8BC",
    "Secundario":  "#44606E",
}
BLOQUE = {
    "Madrugada": "#2F4858", "Manana": "#2BD4E8",
    "Tarde": "#7FD8E8", "Noche": "#4A7A8C",
}


# --- formato -----------------------------------------------------------------

def miles(valor) -> str:
    """33121 -> '33.121'"""
    return f"{int(valor):,}".replace(",", ".")


def decimal(valor, cifras: int = 2) -> str:
    """12.2065 -> '12,21'"""
    return f"{float(valor):,.{cifras}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def porcentaje(valor, cifras: int = 2) -> str:
    return decimal(valor, cifras) + " %"


# --- graficos ----------------------------------------------------------------

def _base(fig: go.Figure, alto: int = 380, titulo_y: str = "", titulo_x: str = "") -> go.Figure:
    """Aplica el tema oscuro del aplicativo a cualquier figura."""
    fig.update_layout(
        height=alto,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXTO, size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h",
                    yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(title=titulo_x, gridcolor=REJILLA, zerolinecolor=REJILLA),
        yaxis=dict(title=titulo_y, gridcolor=REJILLA, zerolinecolor=REJILLA),
    )
    return fig


def barras(datos: pd.DataFrame, x: str, y: str, color_por: str | None = None,
           mapa: dict | None = None, color: str = ACENTO, alto: int = 380,
           titulo_y: str = "", titulo_x: str = "", horizontal: bool = False,
           texto: str | None = None) -> go.Figure:
    fig = go.Figure()
    if color_por and mapa:
        for clave in datos[color_por].unique():
            sub = datos[datos[color_por] == clave]
            fig.add_bar(
                x=sub[y] if horizontal else sub[x],
                y=sub[x] if horizontal else sub[y],
                name=str(clave), marker_color=mapa.get(str(clave), ACENTO),
                orientation="h" if horizontal else "v",
                text=sub[texto] if texto else None, textposition="outside",
            )
    else:
        fig.add_bar(
            x=datos[y] if horizontal else datos[x],
            y=datos[x] if horizontal else datos[y],
            marker_color=color, orientation="h" if horizontal else "v",
            text=datos[texto] if texto else None, textposition="outside",
            showlegend=False,
        )
    return _base(fig, alto, titulo_y, titulo_x)


def lineas(datos: pd.DataFrame, x: str, y: str, color: str = ACENTO,
           alto: int = 380, titulo_y: str = "", titulo_x: str = "",
           relleno: bool = False) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=datos[x], y=datos[y], mode="lines+markers",
                    line=dict(color=color, width=2),
                    marker=dict(size=5, color=color),
                    fill="tozeroy" if relleno else None,
                    fillcolor="rgba(43,212,232,0.12)", showlegend=False)
    return _base(fig, alto, titulo_y, titulo_x)


def linea_de_referencia(fig: go.Figure, x: float, etiqueta: str,
                        color: str = "#F2C14E") -> go.Figure:
    """Marca vertical, para senalar la media sobre una distribucion."""
    fig.add_vline(x=x, line_width=2, line_dash="dash", line_color=color,
                  annotation_text=etiqueta, annotation_position="top",
                  annotation_font_color=color)
    return fig


def franja_vacia(fig: go.Figure, desde: float, hasta: float,
                 etiqueta: str = "") -> go.Figure:
    """Sombrea el tramo en el que no cae ningun vuelo."""
    fig.add_vrect(x0=desde, x1=hasta, fillcolor="#F2545B", opacity=0.10,
                  line_width=0, annotation_text=etiqueta,
                  annotation_position="top left",
                  annotation_font_color="#F2545B")
    return fig


def tabla_frecuencias(datos: pd.DataFrame, columna: str) -> pd.DataFrame:
    """
    Tabla de frecuencias completa: absoluta, relativa y ambas acumuladas.

    Es la forma en que la estadistica descriptiva presenta una distribucion, y
    la que permite ver de un vistazo que el acumulado salta del 95 % al 100 %
    sin pasar por nada intermedio.
    """
    conteo = datos[columna].value_counts().sort_index()
    total = int(conteo.sum())
    return pd.DataFrame({
        "valor": conteo.index,
        "fi": conteo.to_numpy(),
        "hi": (conteo.to_numpy() / total * 100),
        "Fi": conteo.cumsum().to_numpy(),
        "Hi": (conteo.cumsum().to_numpy() / total * 100),
    })
