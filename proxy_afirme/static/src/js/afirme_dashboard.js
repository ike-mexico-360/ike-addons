/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/*
 * GUÍA RÁPIDA PARA LEER ESTE ARCHIVO
 * ==================================
 *
 * 1. Odoo encuentra el elemento HTML con la clase `.o_afirme_dashboard`.
 * 2. `start()` guarda referencias a los controles de pantalla y consulta AFIRME.
 * 3. `_loadExpedientes()` llama al endpoint local `/api/proxy/expedientes`.
 * 4. La respuesta se guarda en `this.state.records`.
 * 5. `_render()` aplica búsqueda, orden y paginación.
 * 6. `_renderRows()` y `_createRecordRow()` construyen la tabla visible.
 *
 * Ejemplo simplificado de un expediente recibido del proxy:
 * {
 *   clExpediente: "22025332",
 *   nombre_completo: "J. ANGEL LARA",
 *   subservicio: "Arrastre de Grúa",
 *   eta_formateado: "00:25",
 *   idSeguimiento: 1
 * }
 *
 * Convención de nombres:
 * - `this.state`: datos que cambian mientras el usuario navega el tablero.
 * - `this.elements`: elementos HTML que ya existen en el template XML.
 * - Métodos que empiezan con `_`: funciones internas de este componente.
 */

// Número máximo de expedientes que se muestran por página.
const PAGE_SIZE = 50;

/**
 * Convierte el semáforo recibido del proxy a la clase visual correspondiente.
 * El valor 0 significa que el proveedor ya concluyó; valores desconocidos
 * representan que el proveedor hizo contacto.
 */
function getEtaClass(semaphoreId) {
    const classes = [
        "o_afirme_eta--white",
        "o_afirme_eta--green",
        "o_afirme_eta--yellow",
        "o_afirme_eta--orange",
        "o_afirme_eta--red",
    ];

    if (semaphoreId === null || semaphoreId === undefined) {
        return "o_afirme_eta--gray";
    }
    return classes[semaphoreId] || "o_afirme_eta--blue";
}

/** Devuelve la explicación que se muestra al pasar sobre el indicador ETA. */
function getEtaMessage(semaphoreId, translate) {
    const messages = [
        translate("provider_completed"),
        translate("within_first_third"),
        translate("within_second_third"),
        translate("within_third_third"),
        translate("estimated_time_overdue"),
    ];

    if (semaphoreId === null || semaphoreId === undefined) {
        return translate("calculation_unavailable");
    }
    return messages[semaphoreId] || translate("provider_made_contact");
}

/**
 * Esta es una pieza de Odoo llamada `publicWidget`.
 *
 * Odoo crea este componente automáticamente en cada página que contenga
 * `.o_afirme_dashboard`. Todo lo que está dentro de las llaves pertenece al
 * comportamiento particular del tablero AFIRME; no son métodos globales.
 */
publicWidget.registry.AfirmeDashboard = publicWidget.Widget.extend({
    selector: ".o_afirme_dashboard",

    events: {
        "click .js-afirme-refresh": "_loadExpedientes",
        "change .js-afirme-account": "_loadExpedientes",
        "input .js-afirme-search": "_filterExpedientes",
        "click .js-afirme-prev": "_goToPreviousPage",
        "click .js-afirme-next": "_goToNextPage",
        "click .js-afirme-sort": "_toggleSortOrder",
    },

    /**
     * Punto de entrada del componente. Odoo ejecuta este método una sola vez
     * cuando termina de cargar la página.
     *
     * Aquí no se crean datos de negocio: solo se prepara la pantalla y se hace
     * la primera consulta para que el usuario vea los expedientes del mes actual.
     */
    async start() {
        await this._super(...arguments);

        this.state = {
            records: [],
            page: 1,
            query: "",
            ascending: true,
        };

        this.elements = {
            account: this.el.querySelector(".js-afirme-account"),
            month: this.el.querySelector(".js-afirme-month"),
            year: this.el.querySelector(".js-afirme-year"),
            search: this.el.querySelector(".js-afirme-search"),
            body: this.el.querySelector(".js-afirme-body"),
            results: this.el.querySelector(".js-afirme-results"),
            page: this.el.querySelector(".js-afirme-page"),
            previous: this.el.querySelector(".js-afirme-prev"),
            next: this.el.querySelector(".js-afirme-next"),
            sortIcon: this.el.querySelector(".js-afirme-sort-icon"),
        };
        this.translations = Object.fromEntries(
            [...this.el.querySelectorAll(".js-afirme-translations [data-key]")].map((element) => [
                element.dataset.key,
                element.textContent.trim(),
            ])
        );

        this._setCurrentPeriod();
        return this._loadExpedientes();
    },

    /**
     * Llena el selector de años y selecciona el mes/año actuales.
     * Ejemplo: si hoy es octubre de 2026, crea opciones 2024 a 2029 y elige 2026.
     */
    _setCurrentPeriod() {
        const now = new Date();
        const currentYear = now.getFullYear();

        for (let year = currentYear - 2; year <= currentYear + 3; year++) {
            const option = new Option(year, year, year === currentYear, year === currentYear);
            this.elements.year.add(option);
        }

        this.elements.month.value = String(now.getMonth() + 1).padStart(2, "0");
    },

    /**
     * Construye las fechas que entiende el proxy a partir de los selectores.
     * Ejemplo: mes "02" y año "2026" devuelve:
     * { fechaDesde: "2026-02-01", fechaHasta: "2026-02-28" }
     */
    _getSelectedPeriod() {
        const year = Number(this.elements.year.value);
        const month = Number(this.elements.month.value);
        const paddedMonth = String(month).padStart(2, "0");
        const lastDay = new Date(year, month, 0).getDate();

        return {
            fechaDesde: `${year}-${paddedMonth}-01`,
            fechaHasta: `${year}-${paddedMonth}-${lastDay}`,
        };
    },

    /**
     * Consulta el proxy local. Este proxy es quien habla con GraphQL de AFIRME;
     * el navegador nunca llama directamente al servicio externo.
     *
     * Al cambiar cuenta, mes o año se vuelve a ejecutar. Si responde bien, se
     * borra la búsqueda anterior, se vuelve a la página 1 y se dibuja la tabla.
     */
    async _loadExpedientes() {
        this._renderMessage(this._translate("loading_open_cases"), "loading");

        try {
            const response = await fetch(this.el.dataset.apiUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    variables: {
                        clcuenta: Number(this.elements.account.value),
                        ...this._getSelectedPeriod(),
                    },
                }),
            });
            const data = await response.json();

            if (!response.ok || data.error || data.errors) {
                throw new Error(
                    data.error || data.errors?.[0]?.message || this._translate("unable_retrieve_cases")
                );
            }

            this.state.records = data.data?.expedientesPorCuentaFiltrado?.content || [];
            this.state.query = "";
            this.state.page = 1;
            this.elements.search.value = "";
            this._render();
        } catch (error) {
            this.state.records = [];
            this._renderMessage(this._translate("unable_load_cases", error.message), "error");
            this._updatePager(0);
        }
    },

    /**
     * Filtra por clave de expediente sin volver a consultar AFIRME.
     * Esto hace que buscar sea inmediato porque opera sobre los datos ya cargados.
     */
    _filterExpedientes() {
        this.state.query = this.elements.search.value.trim();
        this.state.page = 1;
        this._render();
    },

    /** Alterna solo el orden visual de los resultados; no cambia datos del servidor. */
    _toggleSortOrder() {
        this.state.ascending = !this.state.ascending;
        this.state.page = 1;
        this.elements.sortIcon.textContent = this.state.ascending ? "▲ Asc" : "▼ Desc";
        this._render();
    },

    _goToPreviousPage() {
        if (this.state.page > 1) {
            this.state.page--;
            this._render();
        }
    },

    _goToNextPage() {
        const totalPages = Math.ceil(this._getFilteredRecords().length / PAGE_SIZE) || 1;
        if (this.state.page < totalPages) {
            this.state.page++;
            this._render();
        }
    },

    /**
     * Devuelve registros filtrados y ordenados, sin modificar `state.records`.
     * Mantener el arreglo original intacto permite alternar búsqueda/orden sin
     * pedir nuevamente información al proxy.
     */
    _getFilteredRecords() {
        const records = this.state.query
            ? this.state.records.filter((record) =>
                String(record.clExpediente || "").includes(this.state.query)
            )
            : [...this.state.records];

        return this.state.ascending ? records : records.reverse();
    },

    /**
     * Decide qué 50 registros pertenecen a la página actual y actualiza:
     * tabla, contador de resultados y botones Anterior/Siguiente.
     */
    _render() {
        const records = this._getFilteredRecords();
        const totalPages = Math.ceil(records.length / PAGE_SIZE) || 1;
        this.state.page = Math.min(this.state.page, totalPages);

        const firstRecord = (this.state.page - 1) * PAGE_SIZE;
        const pageRecords = records.slice(firstRecord, firstRecord + PAGE_SIZE);

        this._renderRows(pageRecords);
        this.elements.results.textContent = this.state.query
            ? this._translate("showing_results", pageRecords.length, records.length)
            : this._translate("showing_open_cases", pageRecords.length, this.state.records.length);
        this._updatePager(totalPages);
    },

    /** Actualiza texto y estado habilitado/deshabilitado de la paginación. */
    _updatePager(totalPages) {
        const pages = totalPages || 1;
        this.elements.page.textContent = this._translate("page", this.state.page, pages);
        this.elements.previous.disabled = this.state.page === 1;
        this.elements.next.disabled = this.state.page === pages;
    },

    /**
     * Limpia la tabla y agrega una fila por cada expediente mostrado.
     * La fila se crea mediante `_createRecordRow()` para concentrar la lógica
     * de columnas en un solo lugar.
     */
    _renderRows(records) {
        this.elements.body.replaceChildren();

        if (!records.length) {
            this._renderMessage(this._translate("no_open_cases"));
            return;
        }

        records.forEach((record) => this.elements.body.append(this._createRecordRow(record)));
    },

    /**
     * Muestra carga, error o lista vacía sin usar `innerHTML`.
     * El texto puede provenir de un servicio externo, por eso se inserta como
     * texto plano y nunca como HTML ejecutable.
     */
    _renderMessage(text, type = "") {
        const row = document.createElement("tr");
        const cell = this._createElement(
            "td",
            text,
            `o_afirme_dashboard__message${type === "error" ? " o_afirme_dashboard__message--error" : ""}`
        );
        cell.colSpan = 10;

        if (type === "loading") {
            const spinner = document.createElement("span");
            spinner.className = "o_afirme_dashboard__loader";
            spinner.setAttribute("aria-label", this._translate("loading"));
            cell.prepend(spinner, document.createElement("br"));
        }

        row.append(cell);
        this.elements.body.replaceChildren(row);
    },

    /**
     * MÉTODO PROPIO DEL TABLERO; no es nativo de Odoo.
     *
     * Recibe un objeto `record` del proxy y devuelve un elemento HTML `<tr>`.
     * Ejemplo: para `{ clExpediente: "22025332" }` crea la primera celda con
     * ese valor. No guarda nada en base de datos: solamente prepara la vista.
     */
    _createRecordRow(record) {
        const row = document.createElement("tr");
        const standardCells = [
            [record.clExpediente, "o_afirme_dashboard__expediente"],
            [record.vin_limpio],
            [record.fechaAsignacion_formateada, "text-center"],
            [record.fechaContacto_formateada, "text-center"],
            [record.nombre_completo],
        ];

        standardCells.forEach(([value, className]) => {
            row.append(this._createElement("td", value || "—", className));
        });

        const serviceCell = this._createElement("td", "");
        serviceCell.append(
            this._createElement("div", record.subservicio || "—", "o_afirme_dashboard__service-name"),
            this._createElement("div", record.servicio || "", "o_afirme_dashboard__service-type")
        );
        row.append(serviceCell);

        [record.vehiculo_formateado, record.origen_formateado, record.destino_formateado].forEach(
            (value) => row.append(this._createElement("td", value || "—"))
        );

        const etaCell = this._createElement("td", "", "text-center");
        const eta = this._createElement(
            "span",
            record.eta_formateado || "—",
            `o_afirme_eta ${getEtaClass(record.idSeguimiento)}`
        );
        eta.title = getEtaMessage(record.idSeguimiento, this._translate.bind(this));
        etaCell.append(eta);
        row.append(etaCell);

        return row;
    },

    /**
     * MÉTODO PROPIO DEL TABLERO; no es nativo de Odoo.
     *
     * Es un atajo para crear etiquetas HTML repetidas. Por dentro utiliza
     * `document.createElement()`, que sí es una función nativa del navegador.
     *
     * Ejemplo:
     *   this._createElement("td", "22025332", "o_afirme_dashboard__expediente")
     * crea: <td class="o_afirme_dashboard__expediente">22025332</td>
     *
     * Se usa `textContent` en lugar de `innerHTML` para que un valor recibido
     * desde AFIRME se muestre como texto, no como código HTML.
     */
    _createElement(tag, text, className = "") {
        const element = document.createElement(tag);
        element.textContent = text;
        element.className = className;
        return element;
    },

    /**
     * Returns the server-translated text stored in the QWeb template.
     * `%s` placeholders are replaced in their order of appearance.
     */
    _translate(key, ...values) {
        let text = this.translations[key] || key;
        values.forEach((value) => {
            text = text.replace("%s", value);
        });
        return text;
    },
});
