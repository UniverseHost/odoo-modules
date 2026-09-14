import { user } from "@web/core/user";

export const SIGN_MODES = ["draw", "auto", "load"];

export const ALL_SIGN_MODES = { draw: true, auto: true, load: true };

let currentScope = "backend";

export function setSignatureScope(scope) {
    currentScope = scope;
}

export function getSignatureScope() {
    return currentScope;
}

function pickCompanyConfig() {
    const companies = odoo.__signature_widget_options__;
    if (!Array.isArray(companies) || !companies.length) {
        return null;
    }
    const activeId = user.context.allowed_company_ids?.[0];
    return companies.find((company) => company.id === activeId) || companies[0];
}

let allowedModes;

export function getAllowedSignatureModes() {
    if (!allowedModes) {
        const config = pickCompanyConfig();
        allowedModes = config
            ? Object.fromEntries(
                  SIGN_MODES.map((mode) => [
                      mode,
                      Boolean(config[`x_signature_${currentScope}_mode_${mode}`]),
                  ])
              )
            : ALL_SIGN_MODES;
    }
    return allowedModes;
}
