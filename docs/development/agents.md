# Convención de agentes de ADA

Esta carpeta usa una estructura simple para separar el rol del agente principal y la especialización de tareas.

## 1) Agente principal
El agente principal es el Tech Lead del proyecto.

Su función es:
- entender el problema global
- decidir qué tipo de revisión necesita el proyecto
- derivar la tarea al agente correcto
- integrar recomendaciones y entregar una decisión final

El archivo principal es:
- `.agents/orchestrator.md`

## 2) Agentes especializados
Los agentes especializados viven en `.agents/specialists/` y se usan solo cuando el problema está centrado en una dimensión concreta.

Por ahora, la idea es mantener esta estructura conceptual:
- UX/UI Streamlit
- Calidad y refactor
- Rendimiento y estabilidad
- Producto y flujo
- Validación y QA

No se crean todos de golpe; primero se define la convención y se usan solo cuando el problema lo requiere.

## 3) Regla general
El flujo recomendado es:

1. El problema llega al agente principal.
2. El agente principal identifica el dominio principal.
3. Se deriva la tarea al agente especializado más apropiado.
4. El agente principal integra la respuesta y decide la mejor solución.

## 4) Plantillas de uso

### Plantilla A: revisión general
Actúa como Tech Lead de ADA. Revisa el proyecto completo, identifica los puntos críticos y deriva la evaluación a los agentes especializados adecuados. Entrega un informe final con prioridad, riesgos y plan de acción.

### Plantilla B: mejora visual
Actúa como Tech Lead de ADA. Este problema afecta principalmente a UX/UI. Analiza el caso, identifica si requiere cambios de diseño, lógica o estructura, y propone la solución más equilibrada.

### Plantilla C: revisión de calidad
Actúa como Tech Lead de ADA. Revisa la calidad del código, prioriza los hallazgos más importantes y delega en el especialista correcto si hace falta refactor o limpieza.

### Plantilla D: revisión de rendimiento
Actúa como Tech Lead de ADA. Evalúa la app desde el punto de vista de rendimiento, estabilidad y tiempo de respuesta. Revisa si hay cuellos de botella y propone una solución con coste y riesgo razonables.

## 5) Cuándo usar `.agents/specialists/`
Usa la carpeta cuando:
- hay especialización clara del problema
- deseas separar dominios de trabajo
- quieres mantener un equipo de “minions” con propósito específico
- la tarea requiere más de una visión técnica

## 6) Cuando no hace falta
No hace falta crear un agente nuevo si:
- el problema es puntual y simple
- no requiere dominio específico
- la tarea puede resolverse directamente con el Tech Lead principal

## 7) Filosofía del proyecto
ADA se comporta como un agente central que coordina una familia de especialistas. Eso permite:
- mantener visión global
- evitar soluciones aisladas
- mejorar prioridad y claridad del trabajo
- escalar la arquitectura del proyecto sin complicar la ejecución diaria
