/** @odoo-module **/

import { registry } from "@web/core/registry";

const suplementoRedirectService = {
    dependencies: ["bus_service", "action"],
    start(env, { bus_service, action }) {
        bus_service.subscribe(
            "contrato_especifico_suplemento_creado",
            ({ suplemento_id, suplemento_name }) => {
                action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "contrato.especifico.suplemento",
                    views: [[false, "form"]],
                    res_id: suplemento_id,
                    target: "current",
                });
            }
        );
    },
};

registry
    .category("services")
    .add("suplementoRedirectService", suplementoRedirectService);
