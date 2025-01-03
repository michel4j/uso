/*
 * USO jQuery plugins
 */

jQuery.fn.serializeObject = function () {
    const obj = {};
    this.serializeArray().forEach(({ name, value }) => {
        if (obj[name] === undefined) {
            obj[name] = value;
        } else if (Array.isArray(obj[name])) {
            obj[name].push(value);
        } else {
            obj[name] = [obj[name], value];
        }
    });
    return obj;
};

/**
 * Based on jquery-deserialize, Copyright (C) 2017 Kyle Florence
 * Dual licensed under the MIT and GPLv2 licenses.
 */
((factory) => {
    if (typeof module === 'object' && module.exports) {
        // Node/CommonJS
        module.exports = factory(require('jquery'));
    } else {
        // Browser globals
        factory(window.jQuery);
    }
})((jQuery) => {

    const push = Array.prototype.push;
    const rcheck = /^(?:radio|checkbox)$/i;
    const rplus = /\+/g;
    const rselect = /^(?:option|select-one|select-multiple)$/i;
    const rvalue = /^(?:button|color|date|datetime|datetime-local|email|hidden|month|number|password|range|reset|search|submit|tel|text|textarea|time|url|week)$/i;

    const getElements = (elements, filter) => {
        return elements.map(function() {
            return this.elements ? jQuery.makeArray(this.elements) : this;
        }).filter(filter || ":input:not(:disabled)").get();
    };

    const getElementsByName = (elements) => {
        const elementsByName = {};

        jQuery.each(elements, (i, element) => {
            if (!elementsByName[element.name]) {
                elementsByName[element.name] = [];
            }
            elementsByName[element.name].push(element);
        });

        return elementsByName;
    };

    jQuery.fn.deserialize = function(data, options = {}) {
        let current, element, elements, elementsForName, i, j, k, key, len, length, name, nameIndex, optionsAndInputs,
            property, type, value,
            change = jQuery.noop,
            complete = jQuery.noop,
            names = {},
            normalized = [];

        if (jQuery.isFunction(options)) {
            complete = options;
        } else {
            change = jQuery.isFunction(options.change) ? options.change : change;
            complete = jQuery.isFunction(options.complete) ? options.complete : complete;
        }

        elements = getElements(this, options.filter);

        if (!data || !elements.length) {
            return this;
        }

        if (jQuery.isArray(data)) {
            normalized = data;
        } else if (jQuery.isPlainObject(data)) {
            for (key in data) {
                if (jQuery.isArray(data[key])) {
                    push.apply(normalized, jQuery.map(data[key], (v) => ({ name: key, value: v })));
                } else {
                    push.call(normalized, { name: key, value: data[key] });
                }
            }
        } else if (typeof data === "string") {
            data.split("&").forEach((part) => {
                const [name, value] = part.split("=");
                push.call(normalized, {
                    name: decodeURIComponent(name.replace(rplus, "%20")),
                    value: decodeURIComponent(value.replace(rplus, "%20"))
                });
            });
        }

        if (!(length = normalized.length)) {
            return this;
        }

        elements = getElementsByName(elements);

        for (i = 0; i < length; i++) {
            current = normalized[i];
            name = current.name;
            value = current.value;
            elementsForName = elements[name];

            if (!elementsForName || elementsForName.length === 0) {
                continue;
            }

            if (names[name] === undefined) {
                names[name] = 0;
            }
            nameIndex = names[name]++;

            if (elementsForName[nameIndex]) {
                element = elementsForName[nameIndex];
                type = (element.type || element.nodeName).toLowerCase();
                if (rvalue.test(type)) {
                    change.call(element, (element.value = value));
                    continue;
                }
            }

            for (j = 0, len = elementsForName.length; j < len; j++) {
                element = elementsForName[j];
                type = (element.type || element.nodeName).toLowerCase();
                property = null;

                if (rcheck.test(type)) {
                    property = "checked";
                } else if (rselect.test(type)) {
                    property = "selected";
                }

                if (property) {
                    optionsAndInputs = element.options ? Array.from(element.options) : [element];
                    optionsAndInputs.forEach((current) => {
                        if (current.value === value) {
                            change.call(current, (current[property] = true) && value);
                        }
                    });
                }
            }
        }

        complete.call(this);

        return this;
    };

});
