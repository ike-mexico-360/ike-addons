import { onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { PhoneField, phoneField } from "@web/views/fields/phone/phone_field";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/* --------------------------------------------------------------------------
 * Bright Pattern singleton helpers
 * -------------------------------------------------------------------------- */

let bpConfigPromise = null;
const bpSdkLoadingPromises = new Map();
const bpSdkReadyPromises = new Map();

function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function getBpApi() {
    return window.bpspat?.api || null;
}

function normalizeTenant(tenant) {
    return String(tenant || "").trim().replace(/^https?:\/\//i, "").replace(/\/+$/, "");
}

function buildBpTenantUrl(tenant) {
    const normalizedTenant = normalizeTenant(tenant);
    return normalizedTenant ? `https://${normalizedTenant}.brightpattern.com` : "";
}

function buildBpSdkUrl(tenant) {
    const tenantUrl = buildBpTenantUrl(tenant);
    return tenantUrl ? `${tenantUrl}/agentdesktop/libs/servicepattern-sdk-v1.js` : "";
}

async function getBpConfig(orm) {
    if (!bpConfigPromise) {
        bpConfigPromise = (async () => {
            const [tenant, defaultService] = await Promise.all([
                orm.call("res.company", "x_get_bp_tenant", []),
                orm.call("res.company", "x_get_bp_default_service", []),
            ]);

            const normalizedTenant = normalizeTenant(tenant);
            const normalizedService = String(defaultService || "").trim();

            return {
                tenant: normalizedTenant,
                tenantUrl: buildBpTenantUrl(normalizedTenant),
                sdkUrl: buildBpSdkUrl(normalizedTenant),
                defaultService: normalizedService,
            };
        })();
    }
    return bpConfigPromise;
}

function getStateAsync(api, timeout = 1500) {
    return new Promise((resolve, reject) => {
        let finished = false;

        const timer = setTimeout(() => {
            if (!finished) {
                finished = true;
                reject(new Error("Timeout consultando Bright Pattern getState()."));
            }
        }, timeout);

        try {
            api.getState((state) => {
                if (!finished) {
                    finished = true;
                    clearTimeout(timer);
                    resolve(state);
                }
            });
        } catch (error) {
            clearTimeout(timer);
            reject(error);
        }
    });
}

async function waitForBpReady(api, options = {}) {
    const attempts = options.attempts || 12;
    const delay = options.delay || 400;
    let lastError = null;

    for (let i = 0; i < attempts; i++) {
        try {
            const state = await getStateAsync(api, 1500);
            if (state) {
                return state;
            }
        } catch (error) {
            lastError = error;
        }
        await wait(delay);
    }

    throw lastError || new Error("Bright Pattern no quedó listo a tiempo.");
}

function loadBPSdk(sdkUrl) {
    const existingApi = getBpApi();
    if (existingApi) {
        return Promise.resolve(existingApi);
    }

    if (bpSdkLoadingPromises.has(sdkUrl)) {
        return bpSdkLoadingPromises.get(sdkUrl);
    }

    const promise = new Promise((resolve, reject) => {
        const existingScript = document.querySelector(`script[src="${sdkUrl}"]`);

        if (existingScript) {
            const api = getBpApi();
            if (api) {
                resolve(api);
                return;
            }

            existingScript.addEventListener(
                "load",
                () => {
                    const loadedApi = getBpApi();
                    if (loadedApi) {
                        resolve(loadedApi);
                    } else {
                        reject(new Error("Bright Pattern SDK cargó, pero window.bpspat.api no está disponible."));
                    }
                },
                { once: true }
            );

            existingScript.addEventListener(
                "error",
                () => reject(new Error("No se pudo cargar Bright Pattern SDK.")),
                { once: true }
            );
            return;
        }

        const script = document.createElement("script");
        script.src = sdkUrl;
        script.type = "text/javascript";
        script.async = true;

        script.onload = () => {
            const loadedApi = getBpApi();
            if (loadedApi) {
                resolve(loadedApi);
            } else {
                reject(new Error("Bright Pattern SDK cargó, pero window.bpspat.api no está disponible."));
            }
        };

        script.onerror = () => reject(new Error("No se pudo cargar Bright Pattern SDK."));
        document.head.appendChild(script);
    });

    bpSdkLoadingPromises.set(sdkUrl, promise);
    return promise;
}

function initBPSdk(sdkUrl, tenantUrl) {
    const key = `${tenantUrl}|${sdkUrl}`;

    if (bpSdkReadyPromises.has(key)) {
        return bpSdkReadyPromises.get(key);
    }

    const promise = (async () => {
        const api = await loadBPSdk(sdkUrl);
        api.init(tenantUrl);
        await waitForBpReady(api);
        return api;
    })();

    bpSdkReadyPromises.set(key, promise);
    return promise;
}

async function selectServiceIfNeeded(api, serviceName) {
    if (!serviceName) {
        return;
    }
    await api.selectService(serviceName);
}

/* --------------------------------------------------------------------------
 * Field widget
 * -------------------------------------------------------------------------- */

export class BPPhoneDialField extends PhoneField {
    static template = "ike_event_api.BPPhoneDialField";

    static props = {
        ...PhoneField.props,
        groups: { type: String, optional: true },
    };

    static defaultProps = {
        ...PhoneField.defaultProps,
        groups: "base.group_user",
    };

    setup() {
        super.setup?.();
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.user = user;

        this.state = useState({
            showDialIcon: false,
            bpTenant: "",
            bpTenantUrl: "",
            bpSdkUrl: "",
            bpDefaultService: "",
            bpConfigured: false,
        });

        onWillStart(async () => {
            await this.loadBPConfig();
            this.state.showDialIcon = await this.computeShowDialIcon();

            if (this.state.bpConfigured) {
                initBPSdk(this.state.bpSdkUrl, this.state.bpTenantUrl).catch((error) => {
                    console.warn("Bright Pattern aún no quedó listo durante setup():", error);
                });
            }
        });

        onWillUpdateProps(async (nextProps) => {
            if (this.props.record.resId !== nextProps.record.resId || this.props.groups !== nextProps.groups) {
                this.state.showDialIcon = await this.computeShowDialIcon(nextProps);
            }
        });
    }

    async loadBPConfig() {
        const config = await getBpConfig(this.orm);

        this.state.bpTenant = config.tenant;
        this.state.bpTenantUrl = config.tenantUrl;
        this.state.bpSdkUrl = config.sdkUrl;
        this.state.bpDefaultService = config.defaultService;
        this.state.bpConfigured = Boolean(config.tenant && config.sdkUrl && config.defaultService);
    }

    groups(props = null) {
        const propsToUse = props || this.props;
        if (!propsToUse.groups) {
            return [];
        }
        return propsToUse.groups
            .split(",")
            .map((group) => group.trim())
            .filter(Boolean);
    }

    async computeShowDialIcon(props = null) {
        const propsToUse = props || this.props;

        if (!this.state.bpConfigured) {
            return false;
        }

        if (!this.phoneNumber(propsToUse)) {
            return false;
        }

        const groups = this.groups(propsToUse);

        if (!groups.length) {
            return true;
        }

        for (const groupXmlId of groups) {
            const hasGroup = await this.user.hasGroup(groupXmlId);
            if (hasGroup) {
                return true;
            }
        }

        return false;
    }

    get bpTenantUrl() {
        return this.state.bpTenantUrl;
    }

    get bpSdkUrl() {
        return this.state.bpSdkUrl;
    }

    get bpServiceName() {
        return this.state.bpDefaultService;
    }

    phoneNumber(props = null) {
        const propsToUse = props || this.props;
        return propsToUse.record?.data?.[propsToUse.name];
    }

    async dialNumber() {
        if (!this.state.bpConfigured) {
            this.notification.add(_t("Bright Pattern no está configurado correctamente."), {
                type: "danger",
                sticky: true,
            });
            return;
        }

        if (!this.state.showDialIcon) {
            this.notification.add(_t("No tienes permisos para marcar."), {
                type: "warning",
            });
            return;
        }

        const number = this.phoneNumber();

        if (!number) {
            this.notification.add(_t("No hay un número telefónico para marcar."), {
                type: "warning",
            });
            return;
        }

        const cleanNumber = String(number).replace(/\D/g, "");

        if (cleanNumber.length < 10) {
            this.notification.add(_t("El número telefónico debe tener al menos 10 dígitos."), {
                type: "danger",
                sticky: true,
            });
            return;
        }

        try {
            const api = await initBPSdk(this.bpSdkUrl, this.bpTenantUrl);

            const stateBefore = await getStateAsync(api).catch(() => null);
            console.log("Bright Pattern state before selectService/dial:", stateBefore);

            await selectServiceIfNeeded(api, this.bpServiceName);

            await wait(250);

            const response = await api.dialNumber(cleanNumber);
            console.log("Bright Pattern dialNumber response:", response);

            this.notification.add(_t("Llamada enviada a Bright Pattern."), {
                type: "success",
            });
        } catch (error) {
            console.error("Error al marcar con Bright Pattern:", error);
            this.notification.add(
                _t("No fue posible iniciar la llamada en Bright Pattern."),
                { type: "danger" }
            );
        }
    }
}

export const bpPhoneDialField = {
    ...phoneField,
    component: BPPhoneDialField,
    extractProps: ({ attrs }) => ({
        groups: attrs.show_groups,
    }),
};

registry.category("fields").add("bp_phone_dial", bpPhoneDialField);
