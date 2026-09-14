import { NameAndSignature } from "@web/core/signature/name_and_signature";
import { patch } from "@web/core/utils/patch";
import { getAllowedSignatureModes, SIGN_MODES } from "./signature_modes";

patch(NameAndSignature.prototype, {
    setup() {
        super.setup(...arguments);

        if (!this.isCoreSignatureWidget) {
            return;
        }

        this.state.signMode = this.getAllowedSignMode(this.state.signMode);

        if (!this.hasAnySignMode) {
            this.props.signature.isSignatureEmpty = true;
        }
    },

    get isCoreSignatureWidget() {
        return this.constructor === NameAndSignature;
    },

    get isAutoSignModeRelevant() {
        return !this.props.noInputName || Boolean(this.defaultName);
    },

    get allowedSignModes() {
        if (!this.isCoreSignatureWidget) {
            return { draw: true, auto: this.isAutoSignModeRelevant, load: true };
        }
        const modes = getAllowedSignatureModes();
        return {
            draw: modes.draw,
            auto: modes.auto && this.isAutoSignModeRelevant,
            load: modes.load,
        };
    },

    get hasAnySignMode() {
        return SIGN_MODES.some((mode) => this.allowedSignModes[mode]);
    },

    getAllowedSignMode(preferredMode) {
        const allowed = this.allowedSignModes;
        return (
            [preferredMode, ...SIGN_MODES].find((mode) => allowed[mode]) || preferredMode
        );
    },
});
