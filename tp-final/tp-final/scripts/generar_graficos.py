import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

C1, C2, GR = "#1f5fa8", "#d9822b", "#888888"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
import os; os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "graficos"))
NOTE = "ESTIMACIÓN con supuestos del caso (no son datos observados)"

# 1) Problema: cobertura de stock por SKU-local, hoy vs objetivo
fig, ax = plt.subplots(figsize=(8, 4.5))
cats = ["Quiebre\n(< 1 sem.)", "Saludable\n(1-8 sem.)", "Exceso\n(8-16 sem.)", "Sobrestock\n(> 16 sem.)"]
hoy = [12, 48, 22, 18]
obj = [6, 66, 20, 8]
x = range(len(cats)); w = 0.38
b1 = ax.bar([i - w/2 for i in x], hoy, w, label="Situación actual (supuesta)", color=GR)
b2 = ax.bar([i + w/2 for i in x], obj, w, label="Objetivo a 12 meses", color=C1)
for b in list(b1) + list(b2):
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 1, f"{b.get_height():.0f}%", ha="center", fontsize=10)
ax.set_xticks(list(x)); ax.set_xticklabels(cats)
ax.set_ylabel("% de combinaciones SKU-local"); ax.set_ylim(0, 80)
ax.set_title("Cobertura de stock: dónde se pierde plata hoy")
ax.legend(frameon=False)
fig.text(0.01, 0.01, NOTE, fontsize=8, color="#a00")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig("01_cobertura_stock.png", dpi=160)

# 2) Volumen estimado de datos
fig, ax = plt.subplots(figsize=(8, 4.5))
tablas = ["fact_stock_diario", "fact_ventas\n(locales + web)", "dim_producto", "dim_local"]
filas_anio = [70_000_000, 4_200_000, 12_000, 40]
bars = ax.barh(tablas[::-1], filas_anio[::-1], color=[GR, GR, C2, C1])
ax.set_xscale("log"); ax.set_xlabel("Filas por año (escala logarítmica)")
for b, v in zip(bars, filas_anio[::-1]):
    ax.text(v * 1.15, b.get_y() + b.get_height()/2, f"{v:,.0f}".replace(",", "."), va="center", fontsize=10)
ax.set_xlim(10, 6e8)
ax.set_title("Volumen estimado de las tablas Gold (~5 GB/año en total)")
fig.text(0.01, 0.01, NOTE, fontsize=8, color="#a00")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig("02_volumen_estimado.png", dpi=160)

# 3) Resultado esperado: KPIs
fig, axes = plt.subplots(1, 3, figsize=(10, 4))
kpis = [("Quiebres de stock\n(% SKU-local)", 12, 6, "%"),
        ("Sell-through a 12 sem.\n(% unidades vendidas)", 55, 62, "%"),
        ("Tiempo de armado de\nreporte semanal (horas)", 16, 1, " h")]
for ax, (t, a, b, u) in zip(axes, kpis):
    bs = ax.bar(["Hoy", "Meta"], [a, b], color=[GR, C1], width=0.55)
    for r in bs:
        ax.text(r.get_x() + r.get_width()/2, r.get_height() * 1.02, f"{r.get_height():.0f}{u}", ha="center")
    ax.set_title(t, fontsize=10); ax.set_ylim(0, max(a, b) * 1.25)
fig.suptitle("Resultado esperado de la plataforma (metas a validar en un piloto)")
fig.text(0.01, 0.01, NOTE, fontsize=8, color="#a00")
fig.tight_layout(rect=(0, 0.04, 1, 0.94)); fig.savefig("03_resultado_esperado.png", dpi=160)
