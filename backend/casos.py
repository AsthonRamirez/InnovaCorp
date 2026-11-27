# (área, consulta, tipo, esperado) -> esperado: nombre de manual | lista de manuales | "SIN" (sin evidencia) | None (ambigua)
SIN = "SIN"
CASOS = [
 ("soporte_interno", "¿Cuál es el procedimiento para solicitar un equipo de cómputo nuevo?", "Válida", "SOP_Equipamiento"),
 ("soporte_interno", "¿Cómo le hago para pedir una laptop nueva?", "Similar", "SOP_Equipamiento"),
 ("recursos_humanos", "¿Cuántos días de vacaciones me tocan y con cuánta anticipación las pido?", "Válida", "Manual_Vacaciones"),
 ("ti", "¿Cómo solicito acceso a la VPN para trabajar desde casa?", "Válida", "Manual_TI"),
 ("finanzas", "¿Qué días se paga la nómina?", "Válida", "Procedimiento_Pago_Nomina"),
 ("ventas", "¿Quién autoriza un descuento mayor al 10 por ciento?", "Válida", "Politica_Descuentos"),
 ("atencion_cliente", "¿En cuánto tiempo debo resolver un caso crítico?", "Válida", "Manual_SLA_Tiempos"),
 ("produccion", "¿Qué hago si ocurre un accidente en la planta?", "Compleja", ["Procedimiento_Reporte_Incidentes_Planta", "Procedimiento_Paro_Emergencia"]),
 ("soporte_interno", "¿Y cuánto tarda?", "Ambigua", None),
 ("finanzas", "¿Cuál es el procedimiento para solicitar un equipo de cómputo nuevo?", "Otra área (acceso)", SIN),
 ("logistica", "¿Cuál es la capital de Francia?", "Inexistente", SIN),
 ("administracion", "¿Cuál es la política de mascotas en la oficina?", "Inexistente", SIN),
 ("todas", "¿Cuántos días de vacaciones me tocan y con cuánta anticipación las pido?", "Admin (todas las áreas)", "Manual_Vacaciones"),
 ("todas", "¿Cómo solicito acceso a la VPN para trabajar desde casa?", "Admin (todas las áreas)", "Manual_TI")]
