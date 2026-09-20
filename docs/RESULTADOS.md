# Resultados medidos

Casi todas las decisiones de este proyecto salieron de una medición que **contradijo una intuición**.
Este documento recoge los experimentos y sus números.

Reproducibles con los scripts de `tests/`, sobre el corpus del proyecto piloto (no incluido en el
repositorio: contiene historial de un proyecto privado).

---

## 1. Qué modelo local puede llevar la memoria

**Banco:** 4 modelos × 16 registros = 64 extracciones. Sin decodificación restringida, a propósito: la
primera métrica pregunta si el modelo produce JSON válido **por sí solo**.

| Modelo | JSON válido | Tipo correcto | Cobertura módulos | Precisión relaciones | Mediana |
|---|---|---|---|---|---|
| **`llama3.2:3b`** | **100 %** | 81 % | **55 %** | 13 % | 2,7 s |
| `qwen2.5:3b-q4` | **100 %** | 81 % | 42 % | 11 % | 2,6 s |
| `phi3:mini` | 88 % | 79 % | 48 % | 7 % | 4,3 s |
| `qwen3.5:0.8b` | **0 %** | — | — | — | 16,2 s |

### Hallazgo 1 — por debajo de cierto tamaño no hay precio que valga

`qwen3.5:0.8b` falló **16 de 16 veces** y además tardó 16,2 s de mediana, seis veces más que modelos
que sí funcionan. No hay compensación posible: un modelo que nunca produce JSON válido no sirve aunque
fuera instantáneo.

El 7B ni siquiera arrancó: `llama runner process has terminated`. Con 15,9 GB totales, WSL2 reteniendo
4 GB y 4,4 GB libres, un modelo de 4,7 GB no tiene sitio. No es un fallo del modelo: es el presupuesto
de memoria funcionando.

### Hallazgo 2 — las relaciones son casi todas inventadas

Entre los 16 registros hay **9 relaciones verdaderas**. Esto propuso cada modelo:

| Modelo | Correctas | Inventadas |
|---|---|---|
| `llama3.2:3b` | 2 | 14 |
| `qwen2.5:3b` | 2 | 16 |
| `phi3:mini` | 1 | 14 |

Dos causas distintas. **Deriva de esquema**: se pide `{rel, target}` y devuelve
`{relation_type, dependent_module}`. Y **fabricación pura**: relaciones plausibles que no existen. La
primera se arregla con decodificación restringida; la segunda no — un JSON válido con contenido falso
sigue siendo falso.

**Consecuencia:** el modelo local no propone aristas. Ver `DEC-013`.

### Hallazgo 3 — cuando los cuatro fallan igual, el problema es nuestro

Los cuatro modelos erraron en **exactamente los mismos tres registros**, clasificando decisiones como
restricciones. Un fallo idéntico en familias distintas no es un fallo de los modelos: era una
ambigüedad en nuestra ontología. Ver `DEC-014`.

---

## 2. Léxico contra semántico contra híbrido

**Banco:** 40 consultas anotadas a mano y clasificadas por dificultad, sobre 111 registros, K = 8.

| Métrica | Léxico | Semántico | **Híbrido** |
|---|---|---|---|
| Precision@3 | 39,7 % | 38,2 % | **40,2 %** |
| Precision@5 | 31,4 % | **33,0 %** | 31,3 % |
| Precision@8 | 26,4 % | **31,6 %** | 27,9 % |
| Recall@5 | 57,1 % | 44,1 % | **59,3 %** |
| Recall@8 | 60,8 % | 46,6 % | **65,9 %** |
| MRR | 0,585 | 0,577 | **0,669** |
| nDCG@8 | 0,565 | 0,462 | **0,616** |
| Falsos precedentes | 1/6 | **0/6** | 1/6 |

### La media global esconde lo importante

| Recall@8 | Léxico | Híbrido | |
|---|---|---|---|
| EXACT_MATCH | **0,917** | 0,881 | pierde algo |
| **SYNONYM** | 0,150 | **0,300** | el doble |
| **POLYSEMY** | 0,400 | **0,600** | |
| CROSS_MODULE | **0,867** | 0,817 | pierde algo |

En nDCG@8, que además mide el orden, los sinónimos pasan de **0,078 a 0,281** — ×3,6. El léxico no es
que los ordenara mal: es que casi no los encontraba.

**Criterio de aceptación cumplido:** los sinónimos mejoran y los falsos precedentes no aumentan. El
único que queda viene de la vía léxica, no de la semántica.

### Los embeddings no saben decir «aquí no hay nada»

Una consulta sobre un dominio que el proyecto no tiene alcanza similitud 0,653 — más que varias
consultas legítimas.

| Categoría | Similitud máxima | z-score |
|---|---|---|
| Consultas legítimas | 0,581 – 0,742 | 1,57 – 3,61 |
| Dominios inexistentes | 0,588 – 0,667 | 1,45 – 2,21 |

Las distribuciones **se solapan**. La solución fue exigir que el candidato destaque del fondo del
corpus, no que supere una cifra.

---

## 3. Qué corrige una persona al modelo

Al verificar una propuesta se registra qué campos se tocaron. Primera medición, **3 propuestas —
indicativa, no concluyente**:

```
Proposal Correction Rate   67 %  (2 de 3)

Field Correction Rate
  type       33 %        modules    0 %
  title      33 %        related    0 %
  summary    33 %
  tags       33 %
```

**Señal temprana:** `modules` y `related` en 0 %. Son los campos que produce la capa determinista y no
necesitaron corrección ni una vez. Todo lo corregido lo genera el modelo.

Si tras 30–50 tareas verificadas se sostiene el patrón, sería validación empírica de que **las
relaciones estructurales deben computarse, no generarse**. Hasta entonces es hipótesis. Ver `DEC-028`.

---

## 4. El caso que justificó la verificación editable

Con la justificación correcta delante, el modelo resumió:

> «…para mostrar el **número exacto** de clientes asignados a cada coleccion»

cuando el cambio real devolvía **la lista** de clientes, no arreglaba el conteo.

La evidencia era correcta. **La compresión la estropeó.** De ahí que la última milla antes de
canonicalizar sea editable, y que se conserven las dos versiones. Ver `DEC-026`.

---

## 5. Cuando un corpus crece, lo que funcionaba se rompe

Con 16 registros, la consulta insignia devolvía los 4 precedentes exactos. Al pasar a 111 cayó a cero.

Causa: un archivo de documentación que casi cada commit toca conectaba medio proyecto por
`comparte_archivo`, y una sola semilla arrastraba siete registros ajenos.

La corrección que más rindió fue otra: **cada término de la consulta puntúa una vez**, al peso del
campo más fuerte donde aparezca. Contar un mismo término tres veces por estar en etiquetas, título y
resumen premiaba la redundancia y producía empates masivos. Ese cambio subió el MRR de **0,53 a 0,74**.

> Las métricas de un banco solo valen dentro de ese banco. Cuando el banco pasó de 12 a 40 consultas,
> el `Recall@8` bajó de 94,4 % a 60,8 %. No fue una regresión: la prueba se hizo más honesta.

---

## Reproducir

```bash
python tests/benchmark_models.py      # comparación de modelos locales
python tests/compare_retrieval.py     # léxico vs semántico vs híbrido
python tests/eval_retrieval.py        # métricas de recuperación
python tests/smoke_stack.py           # el stack de extremo a extremo
```

Requieren un corpus sembrado. Con `tools/seed_demo.py` se obtiene uno pequeño de ejemplo.

Los números de arriba se midieron sobre **111 registros de un proyecto privado**, que no viajan en este
repositorio. `tests/evalset.py` conserva las 40 consultas anotadas y sus identificadores esperados:
documenta la metodología —las cinco categorías de dificultad y las métricas— aunque no pueda ejecutarse
sin ese corpus.
