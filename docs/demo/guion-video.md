# Guion del video de 2 minutos — FirstSpot

Rally Latinoamericano de Innovación 2026. Reto: priorización de recursos después
de una emergencia — a quién atender primero, dónde concentrar el esfuerzo y qué
recursos asignar, con viabilidad técnica y utilidad justificadas.

El guion está alineado 1:1 con el recorrido guiado (`?tour=1`), 15 pasos de
6 a 9 segundos, 113 segundos en total. El presentador avanza con **Siguiente**, flecha derecha o
AvPág (control remoto); retrocede con flecha izquierda o RePág; **Esc** termina
y deja la aplicación como estaba. El recorrido no guarda, no publica ni inicia
sesión: solo muestra.

## Antes de grabar

- [ ] `just up2` y luego `just status`: backend, frontend y PostGIS arriba.
- [ ] `just demo-seed`: crea las dos organizaciones ficticias verificadas y el
      simulacro de coordinación (entradas "Simulacro:") en el lugar que el
      recorrido marca en el paso 8. Imprime qué lugar sembró; si ya estaba
      sembrado, no cambia nada.
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
- [ ] En el paso 10, confirmar que la bitácora muestra las cinco entradas del
      simulacro, de "Brigada Demo FirstSpot (ficticia)" y "Cuerpo de Socorro
      Demo (ficticio)". Si está vacía, el recorrido lo dice ("aún no tiene
      acciones registradas"), el paso 11 dice "Paso no disponible" y el
      narrador no debe describir entradas: correr `just demo-seed`.
- [ ] Comprobación sin grabar: `REHEARSE_ONLY=1 pnpm --dir frontend record:tour`
      recorre los 15 pasos, falla si alguno dice "Paso no disponible", si el
      recorrido escribe en el backend o si falta el simulacro en la bitácora.

## Pasos

| # | Seg. | En pantalla | Narración |
|---|---|---|---|
| 1 / 15 (`opening`) | 0-8 | Tarjeta centrada "FirstSpot". | Después de un desastre hay que decidir rápido a quién atender primero. FirstSpot ordena territorios y lugares con datos públicos y un método citado: INFORM. |
| 2 / 15 (`zone`) | 8-14 | Selector "Zona de trabajo" en la cinta; queda Sonsonate. | Todo empieza eligiendo el área de operación: Sonsonate, con lugares reales de OpenStreetMap. |
| 3 / 15 (`baseline`) | 14-22 | Lista de distritos del departamento, con el aviso de límites abierto. | Sin evento, la línea base ordena distritos por vulnerabilidad y falta de capacidad de respuesta, con el Censo 2024. Es un orden relativo, nunca víctimas. |
| 4 / 15 (`mode`) | 22-30 | Control de modo en "Evento"; el selector dice "Sismo M6.6 · 5 km S de Cojutepeque · 13 feb 2001". | Ahora un sismo histórico real: 13 de febrero de 2001, magnitud 6,6. El orden se recalcula con el ShakeMap de USGS, a escala nacional. |
| 5 / 15 (`eventTop`) | 30-37 | Primer grupo del ranking, en rojo. | Suben los distritos cercanos al epicentro. Los colores de alerta de Protección Civil aparecen solo ahora. |
| 6 / 15 (`detail`) | 37-44 | Panel de detalle del primer distrito: tres dimensiones. | ¿Por qué va primero? El detalle separa amenaza y exposición, vulnerabilidad y falta de capacidad de respuesta. |
| 7 / 15 (`sphere`) | 44-51 | Bloque "Requerimiento mínimo Esfera". | Qué enviar: el mínimo Esfera de agua, alimento y refugio para la población expuesta estimada. Es una referencia, no una entrega. |
| 8 / 15 (`places`) | 51-58 | Cola de lugares de Sonsonate; el primero queda marcado y el mapa va hacia él. | Dentro de la zona, la cola dice qué lugares concretos atender primero. Lo desconocido nunca se muestra como cero. |
| 9 / 15 (`placeSummary`) | 58-65 | Ficha del lugar: población estimada, grupos vulnerables, estado de atención. | La ficha muestra la población estimada alrededor, con adultos mayores, niñez y discapacidad, y su estado de atención. |
| 10 / 15 (`placeLog`) | 65-74 | Bitácora de coordinación con las cinco entradas del simulacro, de dos organizaciones. | Cada organización verificada registra lo que hace: reporte, unidad en camino, solicitud de apoyo, recurso disponible, en el lugar. Todas ven la misma bitácora: nadie duplica viajes ni llama a todos. |
| 11 / 15 (`placeExchange`) | 74-82 | Resaltadas: "Solicitar apoyo" de la Brigada y "Recurso disponible" del Cuerpo de Socorro. | En este simulacro, una organización pide lonas y agua, y otra responde con lo que puede enviar. Pedido y respuesta, en el mismo registro. |
| 12 / 15 (`placeAccess`) | 82-89 | Pie de la ficha con "Acceso institucional". | Para registrar hay que iniciar sesión con una organización verificada, y cada entrada lleva su nombre. La verificación no certifica el reporte. |
| 13 / 15 (`exportFormat`) | 89-97 | Diálogo "Exportar": formatos, alcance con filas, nombre del archivo. | Para llevarlo al terreno: Excel, CSV, ranking en PDF o mapa. Se ve cuántas filas salen, y el archivo lleva modo, fecha y evento. |
| 14 / 15 (`exportMap`) | 97-105 | Opciones del "Mapa de la vista actual": plantillas, contenido y la composición de la hoja (el recuadro del mapa aparece en gris en la vista previa). | El mapa de la vista actual se arma con plantillas, como Despacho de un lugar. Límites y atribución siempre van. Se genera en el navegador. |
| 15 / 15 (`closing`) | 105-113 | Tarjeta centrada "Listo para operar". | Funciona en el teléfono, con contraste y teclado probados. FirstSpot: decidir rápido, con justificación. |

## Lo que el recorrido no afirma

- No cuenta víctimas: muestra población expuesta estimada.
- El requerimiento Esfera es un mínimo de referencia, no recursos a entregar.
- La verificación de una organización no confirma la exactitud de sus reportes.
- La exportación se genera en el navegador; el mapa base sigue necesitando
  conexión para sus teselas, por eso no se dice "sin conexión".
- No nombra organizaciones concretas (Cruz Roja u otras): la aplicación ofrece
  tipos de organización (Protección civil, Bomberos, Salud, ONG), no un padrón.
- La bitácora de los pasos 10 y 11 es un simulacro sembrado con `just demo-seed`:
  las dos organizaciones son ficticias y cada nota empieza con "Simulacro:".
  No se presenta como un evento real.
- La vista previa del mapa muestra la composición de la hoja; el recuadro del
  mapa aparece en gris ahí. No se describe como una vista previa del mapa.
