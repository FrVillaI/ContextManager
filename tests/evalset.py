"""Banco de consultas anotadas sobre el proyecto de ejemplo (DEC-016, DEC-020).

Siembra el corpus antes de usarlo:

    python tools/seed_demo.py

Las consultas estan clasificadas por el tipo de dificultad que plantean. La
clasificacion no es decorativa: sirve para ver **donde** mejora o empeora cada
estrategia de recuperacion, en vez de mirar una media global que lo esconde todo.

    EXACT_MATCH    la consulta usa el vocabulario del registro
    SYNONYM        dice lo mismo con otras palabras
    POLYSEMY       contiene terminos ambiguos que invitan a falsos positivos
    CROSS_MODULE   el problema cruza varios modulos
    UNKNOWN_DOMAIN el proyecto no tiene experiencia sobre esto

Aviso sobre el tamaño
---------------------
El corpus de ejemplo tiene 14 registros. Los umbrales de especificidad estan
calibrados para corpus de ~100, asi que **los numeros que salen aqui son bajos a
proposito** y no son comparables con los publicados en `docs/RESULTADOS.md`, que
se midieron sobre 111 registros. Sirve para ver la mecanica y para comparar
estrategias entre si, no para juzgar la calidad del sistema.

Aviso sobre la verdad de referencia
-----------------------------------
La anotacion es un juicio humano, no una verdad absoluta. Se anotan solo los
registros de cuya pertinencia hay confianza razonable; ante la duda se deja
fuera, lo que tiende a **infraestimar** el recall en vez de inflarlo.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Caso:
    query: str
    categoria: str
    esperados: frozenset[str] = field(default_factory=frozenset)
    nota: str = ""

    @property
    def sin_precedente(self) -> bool:
        return self.categoria == "UNKNOWN_DOMAIN"


def _c(query: str, categoria: str, *ids: str, nota: str = "") -> Caso:
    return Caso(query, categoria, frozenset(ids), nota)


CASOS: list[Caso] = [
    # ---------- EXACT_MATCH -------------------------------------------------
    _c("el catalogo se corta y faltan productos que si cree",
       "EXACT_MATCH", "BUG-001", "BUG-002", "SOL-001", "SOL-002"),
    _c("la paginacion del catalogo esta mal en el cliente web",
       "EXACT_MATCH", "BUG-002", "SOL-002"),
    _c("hay concurrencia al descontar stock en pedidos simultaneos",
       "EXACT_MATCH", "BUG-004", "SOL-003"),
    _c("el carrito se vacia al perder la conexion",
       "EXACT_MATCH", "BUG-003"),
    _c("voy a tocar web/lib/apiClient.ts",
       "EXACT_MATCH", "SOL-002", nota="coincidencia literal de ruta, DEC-017"),
    _c("buscador de productos con indice de texto completo",
       "EXACT_MATCH", "CHG-001"),

    # ---------- SYNONYM -----------------------------------------------------
    _c("el listado se queda corto y no salen todos los articulos",
       "SYNONYM", "BUG-001", "BUG-002", nota="listado corto = truncado por paginacion"),
    _c("dos personas compran la ultima unidad a la vez",
       "SYNONYM", "BUG-004", "SOL-003", nota="sin decir concurrencia ni stock"),
    _c("quiero guardar los importes como numero decimal",
       "SYNONYM", "ADR-002", "CONSTRAINT-002", nota="lo prohibido, dicho al reves"),
    _c("el navegador deberia consultar la base de datos directamente",
       "SYNONYM", "ADR-001", "CONSTRAINT-001", nota="lo prohibido, dicho al reves"),

    # ---------- POLYSEMY ----------------------------------------------------
    _c("necesito una solucion real, no otro parche",
       "POLYSEMY", "SOL-001", "SOL-002", "BUG-002",
       nota="'real' y 'parche' son literales en la memoria"),
    _c("hay que revisar el orden de los productos en la pagina",
       "POLYSEMY", "BUG-001", "BUG-002", nota="'orden' tambien es pedido"),

    # ---------- CROSS_MODULE ------------------------------------------------
    _c("cambiar como se guardan los pedidos entre la api y la base de datos",
       "CROSS_MODULE", "BUG-004", "SOL-003"),
    _c("una migracion que toca el modelo de precios",
       "CROSS_MODULE", "ADR-002", "CONSTRAINT-002", "CONSTRAINT-003"),

    # ---------- UNKNOWN_DOMAIN ----------------------------------------------
    _c("como integro los pagos con stripe", "UNKNOWN_DOMAIN"),
    _c("configurar el envio de correos transaccionales con sendgrid", "UNKNOWN_DOMAIN"),
    _c("anadir un chat en tiempo real con websockets", "UNKNOWN_DOMAIN"),
    _c("como configuro kubernetes para el despliegue", "UNKNOWN_DOMAIN"),
    _c("un motor de recomendaciones con machine learning", "UNKNOWN_DOMAIN"),
]

CATEGORIAS = ["EXACT_MATCH", "SYNONYM", "POLYSEMY", "CROSS_MODULE", "UNKNOWN_DOMAIN"]
