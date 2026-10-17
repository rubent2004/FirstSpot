# Guion del video de 2 minutos — FirstSpot

Rally Latinoamericano de Innovación 2026. Reto: priorización de recursos después
de una emergencia — a quién atender primero, dónde concentrar el esfuerzo y qué
recursos asignar, con viabilidad técnica y utilidad justificadas.

El guion está alineado 1:1 con el recorrido guiado (`?tour=1`), 14 pasos de unos
8-9 segundos. El presentador avanza con **Siguiente**, flecha derecha o
AvPág (control remoto); retrocede con flecha izquierda o RePág; **Esc** termina
y deja la aplicación como estaba. El recorrido no guarda, no publica ni inicia
sesión: solo muestra.

## Antes de grabar

- [ ] `just up2` y luego `just status`: backend, frontend y PostGIS arriba.
- [ ] Abrir `http://localhost:5173/?tour=1` (o pulsar Shift+Alt+T ya dentro).
- [ ] Ventana a 1920×1080; zoom del navegador al 100 %.
- [ ] Elegir tema claro u oscuro antes de empezar (botón de tema en la cabecera).
- [ ] Idioma de la interfaz en español (botón ES/EN).
- [ ] F11 para pantalla completa.
- [ ] Ensayo completo una vez: confirmar que el paso 5 muestra el sismo de 2001
      (puede tardar unos 5 segundos en cargar la primera vez) y que ningún paso
      dice "Paso no disponible".
- [ ] En el paso 8, anotar el nombre del lugar marcado en la cola: el recorrido
      lo elige en vivo (el primero con nombre real y población estimada).
- [ ] En el paso 10, revisar si la bitácora de ese lugar tiene acciones; si no,
      el recorrido lo dice ("aún no tiene acciones registradas") y el narrador
      no debe describir entradas.

## Pasos

| # | Seg. | En pantalla | Narración (≈ 20-25 palabras) |
|---|---|---|---|
| 1 / 14 (`opening`) | 0-9 | Tarjeta centrada "FirstSpot". | Después de un desastre hay que decidir rápido a quién atender primero. FirstSpot ordena territorios y lugares con datos públicos y un método citado: INFORM. |
| 2 / 14 (`zone`) | 9-17 | Selector "Zona de trabajo" en la cinta; queda Sonsonate. | Todo empieza eligiendo el área de operación. Trabajamos en Sonsonate, una zona con lugares reales cargados desde OpenStreetMap. |
| 3 / 14 (`baseline`) | 17-26 | Lista de distritos del departamento, con el aviso de límites abierto. | Sin evento, la línea base ordena distritos por vulnerabilidad y falta de capacidad de respuesta, con el Censo 2024. Es un orden relativo, nunca víctimas. |
| 4 / 14 (`mode`) | 26-35 | Control de modo pasa a "Evento"; aparecen fecha y hora del ShakeMap. | Ahora un sismo histórico real: el 13 de febrero de 2001, magnitud 6,6. El orden se recalcula con el ShakeMap de USGS, a escala nacional. |
| 5 / 14 (`eventTop`) | 35-43 | Primer grupo del ranking, en rojo. | Suben los distritos cercanos al epicentro. Los colores de alerta de Protección Civil aparecen solo ahora, cuando hay una amenaza que los justifica. |
| 6 / 14 (`detail`) | 43-51 | Panel de detalle del primer distrito: tres dimensiones. | ¿Por qué este distrito va primero? El detalle separa amenaza y exposición, vulnerabilidad y falta de capacidad de respuesta. Nada queda sin justificar. |
| 7 / 14 (`sphere`) | 51-59 | Bloque "Requerimiento mínimo Esfera". | Y qué enviar: el mínimo Esfera de agua, alimento y refugio para la población expuesta estimada. Es una referencia mínima, no una promesa de entrega. |
| 8 / 14 (`places`) | 59-67 | Cola de lugares de Sonsonate; el primero queda marcado y el mapa va hacia él. | Dentro de la zona, la cola dice qué lugares concretos atender, empezando por el primer lugar de la cola. Lo desconocido nunca se muestra como cero. |
| 9 / 14 (`placeSummary`) | 67-75 | Ficha del lugar: población estimada, grupos vulnerables, estado de atención. | La ficha muestra la población estimada alrededor, con adultos mayores, niñez y discapacidad, y su estado: pendiente, en atención o atendido. |
| 10 / 14 (`placeLog`) | 75-84 | Bitácora de coordinación del lugar. | Cada acción queda con autor y organización: unidad en camino, en el lugar, apoyo solicitado. Todas las organizaciones ven la misma bitácora. |
| 11 / 14 (`placeAccess`) | 84-91 | Pie de la ficha con "Acceso institucional". | Para registrar hay que iniciar sesión con una organización verificada. La verificación identifica a la organización; no certifica el reporte. |
| 12 / 14 (`exportFormat`) | 91-100 | Diálogo "Exportar": formatos, alcance con filas, nombre del archivo. | Para llevarlo al terreno: Excel, CSV, ranking en PDF o mapa. El nombre del archivo lleva modo, fecha y evento; se ve cuántas filas salen. |
| 13 / 14 (`exportMap`) | 100-110 | Opciones del "Mapa de la vista actual": plantillas y vista previa. | El mapa de la vista actual se arma con plantillas, como Despacho de un lugar. Límites y atribución siempre van. Se genera en el navegador. |
| 14 / 14 (`closing`) | 110-120 | Tarjeta centrada "Listo para operar". | Funciona en el teléfono, con contraste y teclado probados. Datos abiertos de BCR/ONEC, USGS y OpenStreetMap. FirstSpot: decidir rápido, con justificación. |

## Lo que el recorrido no afirma

- No cuenta víctimas: muestra población expuesta estimada.
- El requerimiento Esfera es un mínimo de referencia, no recursos a entregar.
- La verificación de una organización no confirma la exactitud de sus reportes.
- La exportación se genera en el navegador; el mapa base sigue necesitando
  conexión para sus teselas, por eso no se dice "sin conexión".
- No nombra organizaciones concretas (Cruz Roja u otras): la aplicación ofrece
  tipos de organización (Protección civil, Bomberos, Salud, ONG), no un padrón.
