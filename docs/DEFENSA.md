# Defensa técnica · 5–7 minutos

1. **Avilix, 0:00–0:45.** Presentar el problema, fuentes y diagrama. Aclarar que el XLSX es el archivo ATM recibido y también se soporta CSV. Mostrar los tres roles y sus commits.
2. **Maki, 0:45–2:15.** Abrir perfil inicial en resultados.json. Explicar nulos y duplicados, mediana frente a media, hipótesis MCAR/MAR y grupos mínimos de cinco observaciones. Mostrar un outlier y los dos montos, original y analítico.
3. **Avilix, 2:15–3:30.** Mostrar una transferencia USD, tasa 19.50, fecha ISO, catálogo y terciles. Explicar MinMax y el caso constante. Abrir un registro huérfano en cuarentena.
4. **Leo, 3:30–5:00.** Mostrar validadores, una CLABE inválida y los motivos. Ejecutar pytest. Explicar la prueba de rollback y la unicidad por fuente/ID. Enseñar ambas tablas SQLite.
5. **Avilix, 5:00–6:00.** Mostrar dashboard, registrar una consulta ATM y explicar el comprobante. Si hay tiempo, mostrar transferencia digital inválida. Son extras y simulaciones.
6. **Equipo, 6:00–7:00.** Conciliar 1,220 = 1,072 limpias + 128 cuarentena + 20 omitidas. Explicar limitaciones y responder preguntas.

## Preguntas que cada integrante debe poder contestar

- Maki: ¿por qué mediana?, ¿qué evidencia distingue MCAR/MAR y qué no puede probarse?, ¿cómo se calcula IQR y por qué no eliminar un outlier válido?
- Avilix: ¿por qué se conserva moneda e importe original?, ¿cómo evita una referencia recalcularse con una sola fila?, ¿qué pasa con una cuenta ausente?, ¿cómo se tratan fechas ambiguas?
- Leo: ¿qué hace ValidationError?, ¿cuándo se confirma o revierte?, ¿cómo se evita duplicación?, ¿cómo se preserva el motivo y el registro original?

Antes de entregar: abrir el PDF y la base, ejecutar la batería, confirmar acceso al repositorio y firmar realmente las reglas los tres integrantes. No usar datos manuales de demostración para explicar los conteos de la base entregable.
