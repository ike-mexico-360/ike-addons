# Proxy AFIRME

## Tablero de portal

La pantalla se abre en `/portal/afirme`. El archivo que contiene la lógica de
la página es `static/src/js/afirme_dashboard.js`.

El flujo es:

1. Odoo detecta `.o_afirme_dashboard` y crea `AfirmeDashboard`.
2. `start()` prepara filtros y ejecuta `_loadExpedientes()`.
3. El navegador pide datos al proxy local `/api/proxy/expedientes`.
4. El proxy consulta AFIRME y devuelve una lista de expedientes.
5. El componente filtra, ordena, pagina y dibuja esa lista en la tabla.

Ejemplo de respuesta que consume el JavaScript:

```json
{
  "data": {
    "expedientesPorCuentaFiltrado": {
      "content": [{
        "clExpediente": "22025332",
        "nombre_completo": "J. ANGEL LARA",
        "subservicio": "Arrastre de Grúa",
        "eta_formateado": "00:25",
        "idSeguimiento": 1
      }]
    }
  }
}
```

## Métodos que no son nativos de Odoo

- `_createRecordRow(record)`: función propia que recibe un expediente y crea
  la fila HTML de la tabla.
- `_createElement(tag, text, className)`: función propia para crear etiquetas
  HTML repetidas de manera segura. Internamente usa `document.createElement`,
  API nativa del navegador.

`publicWidget` sí es una utilidad de Odoo para ejecutar JavaScript en páginas
del portal.
