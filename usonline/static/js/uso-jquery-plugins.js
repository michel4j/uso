/*
 * USO jQuery plugins
 */

jQuery.fn.serializeObject = function () {
    const obj = {};
    this.serializeArray().forEach(({name, value}) => {
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
        return elements.map(function () {
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

    jQuery.fn.deserialize = function (data, options = {}) {
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
                    push.apply(normalized, jQuery.map(data[key], (v) => ({name: key, value: v})));
                } else {
                    push.call(normalized, {name: key, value: data[key]});
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

// Visibility
function renderWhenVisible(selector, callback) {
    const element = typeof selector === 'string' ? document.querySelector(selector) : selector;
    const options = {
        root: document.documentElement,
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            callback(entry.intersectionRatio > 0);
        });
    }, options);

    observer.observe(element);
}


// Ajax Progress
function setupAjaxProgress() {
    const $body = $("body");

    // Handle Spinner for all ajax calls
    $(document).ajaxStart(function (xhr) {
        $(document).data('xhrProgress', 0);
        $(document).data('xhrCount', 0);
        $(document).data('xhrPercent', 0);
        $body.css({
            '--uso-progress-percent': 0,
            '--uso-progress-opacity': 1,
        });
    }).ajaxStop(function () {
        setTimeout(function () {
            $("body").css({
                '--uso-progress-opacity': 0
            });
        }, 500);
    });

    // Handle XHR Progress
    let origOpen = XMLHttpRequest.prototype.open;
    $(document).data('xhrCount', $(document).data('xhrCount') || 0);
    $(document).data('xhrProgress', $(document).data('xhrProgress') || 0);
    $(document).data('xhrPercent', $(document).data('xhrPercent') || 0);

    XMLHttpRequest.prototype.open = function () {
        $(document).data('xhrCount', $(document).data('xhrCount') + 1);
        this.addEventListener('load', function () {
            $(document).data('xhrProgress', $(document).data('xhrProgress') + 1);
            $(document).data('xhrCount', $(document).data('xhrCount') - 1);
            if ($(document).data('xhrCount') === 0) {
                $(document).data('xhrPercent', 100)
                $("body").css({
                    '--uso-progress-percent': $(document).data('xhrPercent'),
                });
            } else {
                let percentComplete = 100 * $(document).data('xhrProgress') / $(document).data('xhrCount');
                $(document).data('xhrPercent', Math.max($(document).data('xhrPercent'), percentComplete));
                $("body").css({
                    '--uso-progress-percent': $(document).data('xhrPercent'),
                });
            }
        });
        origOpen.apply(this, arguments);
    };
}


// USO Timeline
function showTimeline(selector, data) {
    renderWhenVisible(selector, function(visible) {
        if (!visible) {
            return; // Do not render if the element is not visible
        }
        const $element = $(selector);
        const width = Math.min(1200, Math.max($element.width(), 576));
        const height = Math.max(60, width * 90 / 1000);
        const fontSize = Math.min(1, Math.max(0.8, width / 576)); // Scale font size based on width

        $element.empty(); // Clear any existing content
        const chart = d3.timeline()
            .margin({left: 0, right: 0, top: height / 5, bottom: height / 5})
            .width(width) // Default width if not set
            .height(height)
            .itemHeight(height / 3)
            .tickFormat({
                format: d3.time.format("%d %b %Y"),
                tickTime: d3.time.months,
                tickInterval: 2,
                tickSize: height / 14
            })
            .showToday()
            .showTodayFormat({width: 2, marginTop: 2, marginBottom: 0, color: "rgba(254,128,40,0.5)"})
            .hover(function (d, i, datum) {
                $element.attr("title", datum.hover);
            });
        const svg = d3.select(selector)
            .append("svg")
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("width", "100%")
            .attr('font-size', `${fontSize.toFixed(2)}em`)
            .datum(data).call(chart);
    });
}


