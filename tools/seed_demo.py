"""Siembra un proyecto de ejemplo para probar el sistema sin datos reales.

    python tools/seed_demo.py

Crea `memory/demo-tienda/` con la memoria de un proyecto ficticio. Sirve para
ver el comportamiento del Context Manager —incluido lo que hace cuando NO sabe
algo— sin necesidad de conectar ningun repositorio propio.

Los registros estan construidos para ejercitar los casos que importan:

- un bug que **reaparece** porque la primera correccion fue un parche;
- una `decision` y la `constraint` que **deriva** de ella (DEC-014);
- restricciones que actuan como guardarrail de un modulo (DEC-015);
- vocabulario que permite consultas por sinonimo y por termino ambiguo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acm.models import Link, MemoryRecord, Provenance, Source, SourceKind  # noqa: E402
from acm.store import MemoryStore  # noqa: E402

PID = "demo-tienda"
NOMBRE = "DemoTienda"


def commit(ref: str, detalle: str) -> Source:
    return Source(kind=SourceKind.GIT_COMMIT, ref=ref, detail=detalle)


def doc(ruta: str, detalle: str) -> Source:
    return Source(kind=SourceKind.FILE, ref=ruta, detail=detalle)


def R(**kw) -> MemoryRecord:
    return MemoryRecord(project_id=PID, project=NOMBRE, **kw)


RECORDS = [
    R(
        id="PROJECT-001", type="project",
        title="DemoTienda - comercio electronico de ejemplo",
        provenance=Provenance.FACT,
        source=doc("docs/ARQUITECTURA.md", "documento de arquitectura"),
        created_at="2026-01-10",
        summary=(
            "Tienda con catalogo, carrito y pedidos. Frontend en Next.js, API en "
            "FastAPI y PostgreSQL gestionado. El frontend nunca habla con la base de "
            "datos: todo pasa por la API."
        ),
        modules=["web", "api", "db"],
        tags=["arquitectura", "stack"],
    ),

    # --- Un bug que reaparece porque el primer arreglo fue un parche ---------
    R(
        id="BUG-001", type="bug",
        title="El catalogo se cortaba a 50 productos y los nuevos no aparecian",
        provenance=Provenance.RESOLVED,
        source=commit("a1b2c3d", "fix: subir el tope de /api/products a 200"),
        created_at="2026-02-03",
        summary=(
            "GET /api/products limitaba a 50 resultados. Un vendedor con mas de 50 "
            "productos los creaba, se guardaban en la base, pero la lista se cortaba "
            "alfabeticamente y no los mostraba. El fallo era silencioso: nada avisaba "
            "de que faltaban."
        ),
        modules=["api/products"],
        files=["api/routers/products.py"],
        links=[Link(rel="solucionado_con", target="SOL-001")],
        tags=["paginacion", "catalogo", "productos", "silencioso"],
    ),
    R(
        id="BUG-002", type="bug",
        title="Reaparicion: el front pedia limit=200 de una vez e ignoraba total",
        provenance=Provenance.RESOLVED,
        source=commit("d4e5f6a", "fix: paginar el catalogo de verdad en web y movil"),
        created_at="2026-02-19",
        summary=(
            "El mismo sintoma volvio dos semanas despues. Subir el tope habia sido un "
            "parche: la API devolvia un objeto paginado con el campo total, pero el "
            "cliente pedia limit=200 en una sola llamada y lo ignoraba, de modo que el "
            "truncado reaparecia en cuanto alguien superaba el nuevo tope."
        ),
        modules=["web/catalogo", "api/products"],
        files=["web/lib/apiClient.ts", "web/app/catalogo/page.tsx"],
        links=[
            Link(rel="reaparicion_de", target="BUG-001"),
            Link(rel="solucionado_con", target="SOL-002"),
        ],
        tags=["paginacion", "catalogo", "parche-insuficiente"],
        body={"leccion": "subir un tope no resuelve la paginacion, solo la aplaza"},
    ),
    R(
        id="SOL-001", type="solution",
        title="Subir el tope de /api/products de 50 a 200",
        provenance=Provenance.RESOLVED,
        source=commit("a1b2c3d", "cambio en el router de productos"),
        created_at="2026-02-03",
        summary=(
            "Parche retrocompatible y sin migracion, elegido para desbloquear a los "
            "vendedores el mismo dia. Resolvio el sintoma, no la causa: ver BUG-002."
        ),
        modules=["api/products"],
        links=[Link(rel="parche_de", target="BUG-001")],
        tags=["parche", "retrocompatible"],
    ),
    R(
        id="SOL-002", type="solution",
        title="Helper fetchAllPages que recorre hasta agotar total",
        provenance=Provenance.RESOLVED,
        source=commit("d4e5f6a", "web/lib/apiClient.ts"),
        created_at="2026-02-19",
        summary=(
            "Solucion real: un helper en el cliente HTTP que sigue pidiendo paginas "
            "hasta que la suma de resultados alcanza total. Aplicado en el catalogo y "
            "en el buscador."
        ),
        modules=["web/catalogo"],
        files=["web/lib/apiClient.ts"],
        tags=["paginacion", "solucion-real"],
    ),

    # --- Sinonimo: el registro dice 'sin conexion', la consulta dira 'offline'
    R(
        id="BUG-003", type="bug",
        title="El carrito se vaciaba al perder la conexion a mitad de compra",
        provenance=Provenance.RESOLVED,
        source=commit("b7c8d9e", "fix: persistir el carrito en almacenamiento local"),
        created_at="2026-03-11",
        summary=(
            "El carrito vivia solo en memoria. Si el navegador se quedaba sin conexion "
            "o el usuario recargaba, se perdia entero y habia que empezar de cero. "
            "Ahora se guarda en almacenamiento local y se reconcilia con el servidor "
            "al recuperar la conexion."
        ),
        modules=["web/carrito"],
        files=["web/store/cart.ts"],
        tags=["carrito", "persistencia", "sin-conexion"],
    ),
    R(
        id="BUG-004", type="bug",
        title="Se podian comprar productos sin stock si dos personas pagaban a la vez",
        provenance=Provenance.RESOLVED,
        source=commit("c9d0e1f", "fix: bloquear la fila del producto al confirmar"),
        created_at="2026-04-02",
        summary=(
            "Dos pedidos simultaneos leian el mismo stock antes de que ninguno lo "
            "descontara, asi que ambos pasaban la validacion. Se resolvio bloqueando "
            "la fila del producto dentro de la transaccion que confirma el pedido."
        ),
        modules=["api/orders", "db"],
        files=["api/services/orders.py"],
        links=[Link(rel="solucionado_con", target="SOL-003")],
        tags=["concurrencia", "stock", "pedidos", "transacciones"],
    ),
    R(
        id="SOL-003", type="solution",
        title="SELECT FOR UPDATE sobre la fila del producto al confirmar el pedido",
        provenance=Provenance.RESOLVED,
        source=commit("c9d0e1f", "api/services/orders.py"),
        created_at="2026-04-02",
        summary=(
            "Bloqueo pesimista dentro de la transaccion. Se descarto el optimista con "
            "reintentos porque en rebajas el numero de colisiones haria que el reintento "
            "fuera lo normal y no la excepcion."
        ),
        modules=["api/orders"],
        tags=["concurrencia", "patron-reutilizable"],
    ),

    # --- Decision que deriva en restriccion (DEC-014) ------------------------
    R(
        id="ADR-001", type="decision",
        title="Toda operacion con la base de datos pasa por la API, nunca desde el navegador",
        provenance=Provenance.DECISION,
        source=doc("docs/ARQUITECTURA.md", "seccion de acceso a datos"),
        created_at="2026-01-15",
        summary=(
            "El frontend no tiene credenciales de base de datos. Centralizar el acceso "
            "en la API permite validar permisos en un solo sitio y evita exponer "
            "credenciales en codigo que se descarga al navegador."
        ),
        modules=["web", "api", "db"],
        links=[Link(rel="deriva_en", target="CONSTRAINT-001")],
        tags=["seguridad", "arquitectura"],
        body={"estado": "ACTIVA"},
    ),
    R(
        id="CONSTRAINT-001", type="constraint",
        title="NUNCA poner credenciales de base de datos en el codigo del frontend",
        provenance=Provenance.DECISION,
        source=doc("CONTRIBUTING.md", "reglas del proyecto"),
        created_at="2026-01-15",
        summary="El navegador solo habla con la API. Ninguna clave de base de datos sale del servidor.",
        modules=["web"],
        links=[Link(rel="deriva_de", target="ADR-001")],
        tags=["seguridad", "critica"],
    ),
    R(
        id="ADR-002", type="decision",
        title="Los precios se guardan en centimos como entero, nunca en coma flotante",
        provenance=Provenance.DECISION,
        source=doc("docs/ARQUITECTURA.md", "modelo de datos"),
        created_at="2026-01-20",
        summary=(
            "Un float no puede representar 0,10 de forma exacta y los redondeos se "
            "acumulan al sumar lineas de pedido. Se guarda un entero de centimos y se "
            "formatea solo al mostrar."
        ),
        modules=["api", "db"],
        links=[Link(rel="deriva_en", target="CONSTRAINT-002")],
        tags=["dinero", "modelo-datos"],
        body={"estado": "ACTIVA"},
    ),
    R(
        id="CONSTRAINT-002", type="constraint",
        title="Prohibido usar float para importes: enteros de centimos",
        provenance=Provenance.DECISION,
        source=doc("CONTRIBUTING.md", "reglas del proyecto"),
        created_at="2026-01-20",
        summary="Cualquier importe nuevo se modela como entero. El formateo es cosa de la vista.",
        modules=["api", "db"],
        links=[Link(rel="deriva_de", target="ADR-002")],
        tags=["dinero", "critica"],
    ),
    R(
        id="CONSTRAINT-003", type="constraint",
        title="Toda migracion de base de datos debe ser reversible",
        provenance=Provenance.DECISION,
        source=doc("CONTRIBUTING.md", "reglas del proyecto"),
        created_at="2026-02-01",
        summary="Sin un downgrade probado, la migracion no se fusiona. Se comprueba en CI.",
        modules=["db"],
        tags=["migraciones", "critica"],
    ),
    R(
        id="CHG-001", type="change",
        title="Buscador de productos con indice de texto completo en PostgreSQL",
        provenance=Provenance.FACT,
        source=commit("e1f2a3b", "feat: buscador con tsvector"),
        created_at="2026-05-14",
        summary=(
            "Se anadio una columna tsvector generada y un indice GIN. Se descarto "
            "montar un motor de busqueda aparte porque el catalogo cabe de sobra en "
            "PostgreSQL y evitaba un servicio mas que mantener."
        ),
        modules=["api/search", "db"],
        files=["api/routers/search.py"],
        tags=["busqueda", "postgres", "rendimiento"],
    ),
]


def main() -> int:
    store = MemoryStore(ROOT / "memory", PID)
    nuevos = 0
    for record in RECORDS:
        try:
            store.append(record)
            nuevos += 1
        except ValueError:
            pass

    problemas = store.check()
    print(f"proyecto de ejemplo '{PID}': {nuevos} registros nuevos")
    print(f"  memoria: {store.stats()}")
    print(f"  integridad: {'OK' if not problemas else problemas[:3]}")
    if nuevos == 0:
        print("  (ya estaba sembrado)")

    print()
    print("Pruebalo:")
    print(f'  python ask.py "el catalogo sale cortado, faltan productos" '
          f'--project {PID} --lexico')
    print(f'  python ask.py "como integro los pagos con stripe" '
          f'--project {PID} --lexico')
    print()
    print("La segunda consulta deberia responder SIN PRECEDENTES REGISTRADOS:")
    print("este proyecto de ejemplo no tiene nada sobre pagos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
