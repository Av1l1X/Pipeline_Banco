# Flujo del pipeline

```mermaid
flowchart TD
    A[ATM XLSX/CSV + DIGITAL JSON] --> B[Lectura y perfil inicial]
    B --> C[Normalizar y validar tipos / fechas / divisas]
    C --> D[Identidad y duplicados]
    D --> O[Bitácora de omitidos]
    D --> E[Cruce con catálogo versionado]
    V[Catálogo CSV validado] --> E
    E --> F[Mediana por grupo / etiquetas controladas]
    F --> G[IQR 1.5 / capping analítico]
    G --> H[MinMax / terciles / validación final]
    C -->|inválido| Q[Cuarentena con original y motivos]
    D -->|ID conflictivo| Q
    E -->|huérfano| Q
    F -->|sin base suficiente| Q
    H -->|resultado analítico inválido| Q
    H --> T[Transacción SQLite]
    Q --> T
    O --> T
    T -->|commit| L[Limpias + cuarentena + evidencia]
    T -->|rollback| X[Ejecución FALLIDA sin filas parciales]
    L --> U[Dashboard / filtros / trazabilidad]
    U -->|corrección auditable| C
```

La validación temprana evita usar montos corruptos para ajustar estadísticas. La cuarentena conserva las filas rechazadas; el capping conserva el importe de origen y solo cambia el importe analítico. Los reprocesamientos generan nueva ejecución, sin borrar el rechazo original.