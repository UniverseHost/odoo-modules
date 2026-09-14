import {
    CustomContentKanbanLikeWidget,
} from "@sale_pdf_quote_builder/js/custom_content_kanban_like_widget/custom_content_kanban_like_widget";
import {
    CustomFieldCard,
} from "@sale_pdf_quote_builder/js/custom_content_kanban_like_widget/custom_field_card/custom_field_card";
import { patch } from "@web/core/utils/patch";

// The card already renders a <textarea>, but useAutoresize shrinks it to the height of
// its content, so an empty field looks like a single line input. The template extension
// of this module adds a class that gives it a real minimum height; declare the prop that
// carries the flag so OWL prop validation accepts it.
CustomFieldCard.props = {
    ...CustomFieldCard.props,
    multiline: { type: Boolean, optional: true },
};

const DOCUMENT_TYPES = ["quotation_document", "product_document"];

patch(CustomContentKanbanLikeWidget.prototype, {
    async updateState() {
        await super.updateState(...arguments);
        await this.markMultilineFormFields();
    },

    /**
     * Flag the form fields that are configured as multiline, so the template can give
     * them a taller box. Reading sale.pdf.form.field is allowed for every internal user.
     */
    async markMultilineFormFields() {
        if (!this.state.headers?.files && !this.state.footers?.files && !this.state.lines?.length) {
            return;
        }

        const namesByType = Object.fromEntries(DOCUMENT_TYPES.map((type) => [type, new Set()]));
        let records = [];
        try {
            records = await this.orm.searchRead(
                "sale.pdf.form.field",
                [["x_is_multiline", "=", true]],
                ["name", "document_type"],
            );
        } catch {
            return; // the flag is cosmetic, never break the tab over it
        }
        for (const record of records) {
            namesByType[record.document_type]?.add(record.name);
        }

        this.applyMultilineFlag(this.state.headers, namesByType.quotation_document);
        this.applyMultilineFlag(this.state.footers, namesByType.quotation_document);
        for (const line of this.state.lines || []) {
            this.applyMultilineFlag(line, namesByType.product_document);
        }
    },

    applyMultilineFlag(section, multilineNames) {
        for (const document of section?.files || []) {
            for (const formField of document.custom_form_fields || []) {
                formField.multiline = multilineNames.has(formField.name);
            }
        }
    },
});
