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

// USO Timeline
function showTimeline(selector, data) {
    const $element = $(selector);
    const chart = d3.timeline()
        .margin({left: 0, right: 0, top: 15, bottom: 15})
        .width($element.width())
        .height(70)
        .itemHeight(24)
        .tickFormat({
            format: d3.time.format("%d %b %Y"),
            tickTime: d3.time.months,
            tickInterval: 2,
            tickSize: 5
        })
        .showToday()
        .showTodayFormat({width: 2, marginTop: 2, marginBottom: 0, color: "rgba(254,128,40,0.5)"})
        .hover(function (d, i, datum) {
            $element.attr("title", datum.hover);
        });
    const width = $element.width();
    const svg = d3.select("#timeline")
        .append("svg")
        .attr("viewBox", `0 0 ${width}  70`)
        .attr("width", "100%")
        .datum(data).call(chart);
}

/**
 * jQuery Form Progress Plugin
 *
 * This plugin monitors an HTML form and calculates its completion percentage
 * based on the number of filled or selected input fields.
 *
 * Usage:
 * $(document).ready(function() {
 * $('#myForm').formProgress({
 * update: function(percentage) {
 * // 'this' inside this function refers to the form element.
 * // You can update a progress bar or text here.
 * $('#progressBar').css('width', percentage + '%').text(Math.round(percentage) + '% Complete');
 * console.log('Form completion: ' + percentage.toFixed(2) + '%');
 * }
 * });
 * });
 *
 * @param {object} options - Configuration options for the plugin.
 * @param {function} [options.update] - A callback function that is executed
 * whenever the form's completion percentage changes.
 * It receives the calculated percentage as its
 * first argument. 'this' inside the callback
 * will refer to the form DOM element.
 */
(function($) {
    $.fn.formProgress = function(options) {

        // Default options
        let settings = $.extend({
            update: null // Default update function is null
        }, options);

        // Iterate over each form selected by the jQuery object
        return this.each(function() {
            const $form = $(this); // Current form element

            /**
             * Calculates the completion percentage of the form.
             * @returns {number} The completion percentage (0-100).
             */
            function calculateProgress() {
                let totalFields = 0;
                let completedFields = 0;

                // Select all relevant input fields within the form
                // Exclude buttons, resets, submits, and hidden fields
                $form.find('input:not([type="button"], [type="submit"], [type="reset"], [type="hidden"]), select, textarea')
                     .each(function() {
                         const $field = $(this);
                         totalFields++; // Increment total fields for each relevant element

                    // Check if the field is completed
                    if ($field.is('input[type="text"], input[type="password"], input[type="email"], input[type="tel"], input[type="url"], input[type="number"], textarea')) {
                        // For text-based inputs and textareas, check if they have a value
                        if ($field.val() && $field.val().trim() !== '') {
                            completedFields++;
                        }
                    } else if ($field.is('input[type="checkbox"], input[type="radio"]')) {
                        // For checkboxes and radio buttons, check if they are checked
                        if ($field.is(':checked')) {
                            completedFields++;
                        }
                    } else if ($field.is('select')) {
                        // For select elements, check if an option other than the default (index 0) is selected
                        // or if the value is not empty (handles cases where option 0 might have a real value)
                        if ($field.val() && $field.val().trim() !== '' && $field.prop('selectedIndex') !== 0) {
                             completedFields++;
                        }
                    }
                    // Add more field types here if necessary
                });

                // Calculate the percentage
                const percentage = (totalFields > 0) ? (completedFields / totalFields) * 100 : 0;

                // If an update callback is provided in options, call it
                if (typeof settings.update === 'function') {
                    // Call the update function with 'this' pointing to the form element
                    // and passing the calculated percentage
                    settings.update.call($form[0], percentage);
                }

                return percentage;
            }

            // Bind events to trigger progress calculation
            // 'input' event for text fields; 'change' for selects/checkboxes/radios
            // 'keyup' is added for broader compatibility, though 'input' is generally preferred.
            $form.on('input change keyup', 'input, select, textarea', function() {
                calculateProgress();
            });

            // Perform an initial calculation when the plugin is first applied
            calculateProgress();
        });
    };
})(jQuery);
