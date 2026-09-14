import {
    CustomFieldCard,
} from "@sale_pdf_quote_builder/js/custom_content_kanban_like_widget/custom_field_card/custom_field_card";

// The card already renders a <textarea>, but useAutoresize shrinks it to the height
// of its content, so an empty multiline field looks like a single line input. The
// template extension of this module adds a class that gives it a real minimum
// height; declare the prop that carries the flag so OWL validation accepts it.
CustomFieldCard.props = {
    ...CustomFieldCard.props,
    multiline: { type: Boolean, optional: true },
};
