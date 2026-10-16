# Propuesta de producto: coordinación geoespacial para emergencias

> Documento de trabajo. La necesidad local todavía no se ha validado con residentes, brigadistas o autoridades. Las funciones que no aparecen en la sección «Ya existe en el repositorio» son propuestas, no capacidades implementadas.

## 1. Punto de partida

El reto describe una respuesta a desastres con comunicaciones interrumpidas, rutas bloqueadas, demanda elevada y reportes incompletos. El equipo quiere plantear un prototipo para un escenario combinado de sismo y lluvias que provocan inundaciones en Sonsonate. La zona concreta aún está por definir.

La oportunidad a explorar no es simplemente «usar teléfonos viejos». Es ayudar a que residentes, brigadistas y coordinadores compartan una imagen operativa comprensible: qué incidentes se reportan, qué información ya fue confirmada, por dónde se puede pasar y qué lugares podrían requerir atención primero.

## 2. Problema de trabajo (hipótesis, versión 0.2)

Durante un sismo con lluvias e inundaciones en una zona de Sonsonate, residentes, brigadistas y coordinadores podrían no contar con una vista compartida y actualizada de los incidentes, los daños, las necesidades y el estado de las rutas por tipo de desplazamiento. La información dispersa o sin confirmar podría dificultar la priorización de zonas y la planificación de cómo llegar.

Esta formulación es una hipótesis derivada del reto académico, no un hallazgo confirmado para Sonsonate. Antes de presentar la carencia como un hecho local, se debe preguntar a personas que hayan vivido o atendido emergencias cómo reúnen reportes, verifican caminos y deciden a dónde enviar ayuda.

### Pregunta de investigación

¿Cómo podría una herramienta geoespacial ayudar a residentes, brigadistas y coordinadores a compartir y verificar información sobre incidentes y accesibilidad, para apoyar la priorización durante un evento de sismo e inundación?

## 3. Qué hace hoy el repositorio

El repositorio `geo-prioridad-vulnerable` ya contiene una base técnica útil:

- Backend en FastAPI, con contrato OpenAPI.
- Ingesta de lugares de OpenStreetMap mediante Overpass y almacenamiento espacial en PostgreSQL/PostGIS.
- Clasificación de hospitales, clínicas, escuelas, centros comunitarios, instalaciones sociales y otros lugares.
- Una puntuación para ordenar lugares según categoría, urgencia institucional, población vulnerable estimada y proximidad a otros lugares.
- Endpoints para listar zonas y lugares, sincronizar datos, actualizar el estado de atención y consultar datos para un mapa de calor.

La base actual prioriza **lugares vulnerables o sensibles** y ya incluye un tablero Vue con mapa de calor y cola de atención. No modela todavía reportes de incidentes, daños del evento, rutas cerradas, transitabilidad por modo, brigadas, asignaciones ni avisos.

Una distinción importante para el diseño: la vulnerabilidad de un hospital o albergue antes del evento no es lo mismo que la urgencia de un incidente ocurrido hoy. Deben ser capas relacionadas, pero separadas, para que una fórmula no confunda un sitio importante con un daño confirmado.

## 4. Usuarios y flujo de trabajo propuesto

1. **Residente:** envía un reporte sencillo con ubicación, categoría, hora aproximada y descripción breve. Puede reportar inundación, daño, personas que requieren ayuda o una ruta posiblemente bloqueada.
2. **Brigadista:** revisa los reportes cercanos, comprueba la situación cuando sea seguro hacerlo y cambia el estado a «confirmado», «no confirmado», «resuelto» o «requiere actualización».
3. **Coordinador:** ve una cola priorizada y un mapa con incidentes, lugares sensibles y accesos. Decide qué equipo enviar y comparte avisos relevantes.

El sistema muestra el estado de cada reporte y su antigüedad. Un reporte no confirmado no se presenta como hecho. El sistema apoya la coordinación; no sustituye a Protección Civil, no declara una ruta segura y no ordena a personas entrar en zonas peligrosas.

## 5. Cómo representar la accesibilidad

La palabra «accesible» debe estar vinculada a un modo de desplazamiento y al momento de la observación. Como mínimo, la interfaz debería diferenciar:

- a pie;
- motocicleta o vehículo liviano;
- vehículo de emergencia.

Cada observación de una vía incluiría tramo o punto, estado, modo observado, hora, fuente, evidencia opcional y una vigencia. Estados iniciales: **abierta**, **con precaución**, **bloqueada** y **desconocida**. «Desconocida» es distinta de «abierta».

Para el prototipo, es más seguro mostrar estos estados reportados y verificados que prometer navegación automática. Calcular una ruta alternativa requiere una red vial suficientemente completa, datos de cierres recientes y reglas de acceso por vehículo; se propone como una etapa posterior.

## 6. Prioridad: mostrar razones, no una caja negra

El equipo ha elegido combinar urgencia, población afectada y acceso. Para un demo, conviene usar reglas visibles y que una persona pueda corregir:

- **Urgencia:** peligro inmediato, necesidad médica, personas atrapadas o riesgo de aumento.
- **Personas afectadas:** estimación declarada, indicando si es aproximada o confirmada.
- **Acceso:** si puede llegar una brigada y con qué modo; una zona aislada puede necesitar una acción distinta, no necesariamente perder prioridad.
- **Contexto de vulnerabilidad:** presencia cercana de hospital, escuela, albergue u otro lugar sensible, como contexto adicional y no como sustituto de un reporte del evento.
- **Confianza y antigüedad:** quién reportó, quién verificó y cuándo se observó por última vez.

La prioridad se explicaría con sus factores («alta urgencia», «muchas personas afectadas», «acceso de ambulancia sin confirmar») y quedaría sujeta a revisión humana. Para la demo se recomienda ordenar por reglas simples, no entrenar un modelo de IA ni presentar una puntuación como verdad objetiva.

## 7. Qué ya existe y qué podría diferenciarnos

Hay soluciones relacionadas, así que no conviene afirmar que el proyecto es el primero o único:

- **OpenStreetMap y HOT Tasking Manager** apoyan la creación y validación colaborativa de mapas de edificios, caminos e infraestructura para labores humanitarias. [HOT Tasking Manager](https://tasks.hotosm.org/)
- **Ushahidi** permite recoger reportes geolocalizados, revisarlos, gestionarlos mediante flujos de trabajo y visualizarlos en mapa. [Manual de encuestas de Ushahidi](https://docs.ushahidi.com/platform-user-manual/3.-configuring-your-deployment/3.3-surveys) · [Descripción de sus flujos de trabajo](https://www.ushahidi.com/support/overview/)
- **Este repositorio** ya parte de lugares sensibles geolocalizados y su priorización por vulnerabilidad.

La diferenciación que vale la pena probar es integrar en una misma vista operativa: **la base de lugares sensibles + reportes del evento + verificación comunitaria + transitabilidad por modo + una cola explicable para coordinación**. Es una hipótesis de valor, no una prueba de originalidad; hay que comparar productos usados por la comunidad o las instituciones de la zona.

## 8. Alcance sugerido del prototipo

### Incluido en una demostración inicial

- Un área pequeña o un mapa de escenario en Sonsonate, todavía pendiente de escoger.
- Capas simuladas o de referencia para lugares sensibles, incidentes y rutas.
- Formulario de reporte de incidente.
- Vista de brigadista para confirmar o rechazar reportes y actualizar el estado de una ruta por modo.
- Vista de coordinación con mapa, filtros, estado de verificación y lista priorizada.
- Avisos demostrativos dentro de la aplicación o la pantalla; no mensajes reales a servicios de emergencia.
- Datos de prueba claramente marcados como simulados.

### Fuera del primer prototipo

- Detectar un sismo o una inundación con fiabilidad operativa.
- Decidir por sí solo el orden real de los rescates.
- Detectar personas atrapadas mediante micrófonos de teléfonos.
- Garantizar conectividad sin red móvil o internet, ni una malla de largo alcance entre celulares.
- Enviar alertas oficiales o integrar despachos reales sin autorización institucional.
- Calcular rutas de emergencia certificadas.

## 9. Tecnología candidata

La tecnología puede elegirse según lo que el equipo domine y el tiempo disponible. Para conservar la base del repositorio, una opción razonable para investigar es:

- **Backend actual:** FastAPI + PostgreSQL/PostGIS.
- **Interfaz existente:** tablero web Vue con mapa y cola para lugares sensibles. La ampliación podría añadir formularios de reporte y vistas por rol en ese mismo frontend.
- **Mapa:** Leaflet con una fuente de mapas cuyo uso y disponibilidad sean adecuados para la demo. Los mosaicos públicos de OpenStreetMap tienen política de uso y no ofrecen una garantía de disponibilidad; no deben tratarse como infraestructura de emergencia. [Política de mosaicos de OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/)
- **Datos iniciales:** lugares de OSM como referencia, más reportes y estados simulados para el demo.
- **Conectividad degradada:** guardar borradores localmente puede explorarse luego; la sincronización offline confiable no se debe dar por resuelta con solo una PWA.
- **Teléfonos en desuso:** opción futura para nodo fijo, registro de movimiento o pantalla local; requiere evaluar batería, alimentación, ubicación, permisos y mantenimiento. No es requisito del MVP.

## 10. Demo de 20 horas: qué se puede afirmar

Con backend y frontend ya existentes, 20 horas de equipo pueden alcanzar para una demostración web acotada si se reutiliza el mapa y la cola actuales, y se simulan las nuevas piezas. No alcanza para tener un sistema probado en campo, operación offline robusta, alertas oficiales y navegación validada.

Escenario de demo: un sismo y lluvias producen daños en varios puntos; un reporte indica un puente inundado; un residente envía otro incidente; una brigada confirma el cierre; el tablero cambia la transitabilidad por modo y muestra qué zonas requieren atención, por qué y qué información falta.

Una división orientativa de las 20 horas del equipo:

1. 2 h: fijar escenario, roles y datos ficticios.
2. 4 h: construir mapa y listado de incidentes.
3. 4 h: formulario de reportes.
4. 4 h: verificación y actualización de rutas por modo.
5. 3 h: reglas visibles de priorización y filtros.
6. 3 h: integrar el recorrido, pulir la presentación y preparar el guion de demo.

Si las 20 horas son de una sola persona, conviene reducirlo a prototipo navegable con datos simulados y centrarse en el flujo central. La cifra debe confirmarse con el tamaño del equipo y su experiencia técnica.

## 11. Validación pendiente

Antes de afirmar que la brecha existe en una comunidad específica, entrevistar a residentes, brigadistas y, si es posible, personal municipal o de Protección Civil. Preguntas iniciales:

1. En la emergencia más reciente que recuerde, ¿cómo supieron qué zonas estaban afectadas?
2. ¿Cómo se confirmó si una calle o puente estaba cerrado y para qué vehículos?
3. ¿Qué canales usaron y qué información se perdió, duplicó o llegó tarde?
4. ¿Quién decide a qué zona atender primero y qué factores usa?
5. ¿Qué información compartirían y cuál no debería publicarse?
6. ¿Qué tendría que mostrar un mapa para que realmente les ayude, y quién debe poder actualizarlo?

No pedir nombres, teléfonos ni datos sensibles de víctimas para una investigación académica inicial. Registrar opiniones sin atribuirlas públicamente a una persona y pedir permiso antes de guardar audio o fotografías.

## 12. Decisiones que faltan para cerrar el problema

- Zona exacta de Sonsonate para el escenario.
- Si «sismo + lluvias/inundación» representa un solo escenario hipotético o dos escenarios de prueba separados.
- Tipos concretos de vehículo a mostrar en el primer demo.
- Quién revisa los reportes y quién puede marcar una ruta como confirmada.
- Tamaño del equipo, tecnologías que conoce y si las 20 horas son por equipo o por integrante.
- Qué datos locales y qué mapas se pueden usar con atribución y vigencia adecuadas.

## Fuentes iniciales

- OCHA, [guía de conjuntos de datos operativos comunes para preparación y respuesta](https://knowledge.base.unocha.org/wiki/spaces/imtoolbox/pages/2235170878/Information%2BManagement%2BWorking%2BGroup%2BIMWG%2BGuidance%2Bon%2BCommon%2BOperational%2BDatasets%2BCODs%2Bin%2BEmergency%2BPreparedness%2Band%2BResponse).
- HOT, [Tasking Manager y flujo de mapeo y validación humanitaria](https://tasks.hotosm.org/).
- Ushahidi, [encuestas geolocalizadas](https://docs.ushahidi.com/platform-user-manual/3.-configuring-your-deployment/3.3-surveys) y [roles, revisión y flujos de trabajo](https://www.ushahidi.com/support/overview/).
- OpenStreetMap Foundation, [política de uso de mosaicos](https://operations.osmfoundation.org/policies/tiles/).
