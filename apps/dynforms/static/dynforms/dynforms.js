// Handle Repeats
(function ($) {
    $.fn.extend({
        repeatable: function (options) {
            options = $.extend({}, $.repeatable.defaults, options);
            this.each(function () {
                new $.repeatable(this, options);
            });
            return this;
        }
    });

    // ctl is the element, options is the set of defaults + user options
    $.repeatable = function (ctl, options) {

        let rp_sel = $(ctl).data("repeat-add");
        let all_rp = $(ctl).siblings(rp_sel);
        let all_rp_rm = all_rp.find(options.remove);

        function updateRepeat(section) {

            section.find('.repeat-html-index').each(function () {
                $(this).html(section.index());
            });
            section.find('.repeat-value-index').each(function () {
                $(this).attr('value', section.index());
            });
            section.find('[data-repeat-index]').each(function () {
                $(this).attr('data-repeat-index', section.index());
            });
            section.find(':input').each(function () {
                $(this).attr('id', $(this).attr('id') + "_" + section.index());
            });
            section.find('label').each(function () {
                let lbl = $(this);
                if (lbl.attr('for')) {
                    lbl.attr('for', lbl.attr('for') + "_" + section.index());
                }
            });
            section.attr('id', section.attr('id') + "_" + section.index())

            all_rp = $(ctl).siblings(rp_sel);

            all_rp_rm = all_rp.find(options.remove);

            if (all_rp.length > 1) {
                all_rp_rm.removeAttr("disabled");
            } else {
                all_rp_rm.attr("disabled", "disabled");
            }

            // rename multivalued field names so values are kept separate
            all_rp.each(function (idx, obj) {
                $(this).find("[data-repeat-name]").each(function () {
                    $(this).attr("name", $(this).data("repeat-name") + "." + idx);
                });
            });
        }

        $(ctl).click(function (e) {
            var rp_el = all_rp.last();
            var field_cnt = $(ctl).closest(".df-field-runtime");

            var cloned = rp_el.clone(true);
            cloned.insertAfter(rp_el);
            if (options.clearNew) {

            }
            updateRepeat(cloned);
            // rebuild chosen fields
            cloned.find("select.select option").removeAttr('selected');
            cloned.find("select.select").each(function () {
                $(this).val('');
                $(this).trigger('change')
            });
        });

        all_rp_rm.each(function () {
            $(this).click(function (e) {
                var del_el = $(this).closest(rp_sel);
                var others = del_el.siblings(rp_sel);
                if (others.length > 0) {
                    del_el.slideUp('fast', function () {
                        del_el.remove();
                        others.each(function () {
                            updateRepeat($(this));
                        });
                    });
                } else if (options.clearIfLast) {
                    del_el.find(":input").each(function () {
                        $(this).val('').removeAttr('checked').removeAttr('selected');
                    })
                }
                ;
            });
        });

        if (all_rp.length > 1) {
            all_rp_rm.removeAttr("disabled");
        } else {
            all_rp_rm.attr("disabled", "disabled");
        }

        // Keep multi valued fields separate, by renaming them, __# can be stripped when cleaning
        // the data
        all_rp.each(function (idx, obj) {
            $(obj).find("select[multiple]:not([data-repeat-name])").each(function () {
                $(this).data("repeat-name", $(this).attr("name"));
                $(this).attr("name", $(this).data("repeat-name") + "." + idx);
            });
        });

    };

    // option defaults
    $.repeatable.defaults = {
        remove: ".remove-repeat",
        clearIfLast: true,
        clearNew: true
    };
})(jQuery);


// field preview customizer
function setupField() {
    if ($(this).is(".selected")) {
        return;
    }
    let prev_field = $('div.df-field.selected');
    let active_field = $(this);
    let active_page = $('.df-container.active');
    let rules_url = `${document.URL}${active_page.index()}/rules/${active_field.data('fieldpos')}/`;
    let put_url = `${document.URL}${active_page.index()}/put/${active_field.data('fieldpos')}/`;
    // remove selected class from all fields
    prev_field.toggleClass("selected", false);
    active_field.toggleClass("selected", true);

    $('#df-sidebar a[href="#field-settings"]').tab('show');

    // Ajax Update form
    $("#field-settings").load(put_url, function () {
        setupMenuForm("#field-settings .df-menu-form");
        $('#field-settings #edit-rules').attr('data-modal-url', rules_url);
    });
};

// Form customization for each form
function setupMenuForm(form_id) {

    // Setup Repeatable Fields
    $(form_id + ' button[data-repeat-add]').repeatable({clearIfLast: false});


    // handle applying field settings
    function submitHandler(event) {
        let active_page = $('.df-container.active');
        let active_field = $('div.df-field.selected');
        let put_url = `${document.URL}${active_page.index()}/put/${active_field.index()}/`;
        let get_url = `${document.URL}${active_page.index()}/get/${active_field.index()}/`;

        $(form_id).ajaxSubmit({
            type: 'post',
            url: put_url,
            success: function (result) {
                $("#field-settings").html(result);
                setupMenuForm("#field-settings .df-menu-form");
                active_field.load(get_url);
            }
        });
    }

    $(form_id + ' button[name="apply-field"]').click(submitHandler);
    $(form_id + ' :input').each(function () {
        $(this).change(submitHandler);
    });
}

function doBuilderLoad() {
    if (!$('#df-form-preview').is('.loaded')) {
        $('div.field-btn').draggable({
            connectToSortable: '#df-main .df-container.active',
            revert: "invalid",
            appendTo: '.df-container.active',
            cursorAt: {left: 5, top: 5},
            scroll: true,
            helper: "clone",
            start: function (event, ui) {
                let exp = $('.df-container.active');
                ui.helper.addClass("ui-draggable-helper");
                ui.helper.width(exp.width() / 4);
            },
            drag: function (event, ui) {
                ui.position.top = NaN;
            }
        }).click(function () {
            if ($(this).is('.ui-draggable-dragging')) {
                return;
            }
            var new_el = $('<div class="df-field container no-space"></div>');
            var cur_pg = $('.df-container.active');
            cur_pg.append(new_el);
            new_el.data('fieldtype', $(this).data('fieldtype'));
            new_el.data('fieldpos', new_el.index());
            new_el.click(setupField);
            // Ajax Add Field
            var loadUrl = `${document.URL + cur_pg.index()}/add/${new_el.data('fieldtype')}/${new_el.index()}/`;
            new_el.load(loadUrl, function () {
                $(this).click();
            });
        }).disableSelection();

        $('#df-main .df-container').sortable({
            items: '.df-field',
            revert: false,
            forcePlaceholderSize: true,
            stop: function (event, ui) {
                if (ui.item.hasClass("field-btn")) {
                    ui.item.removeClass();
                    ui.item.addClass("df-field container no-space").attr("style", "");
                    ui.item.html("");
                    ui.item.click(setupField);
                    // Ajax Add Field
                    var loadUrl = `${document.URL + $('.df-container.active').index()}/add/${ui.item.data('fieldtype')}/${ui.item.index()}/`;
                    ui.item.load(loadUrl, function () {
                        $(this).click();
                        // renumber all fields on active page
                        $('.df-container.active .df-field').each(function () {
                            $(this).data('fieldpos', $(this).index());
                        });
                    });
                } else {
                    // move dropped field to new position on server
                    var loadUrl = `${document.URL + $('.df-container.active').index()}/mov/${ui.item.data('fieldpos')}-${ui.item.index()}/`;
                    $('<div class="ajax"></div>').load(loadUrl);
                    // renumber all fields on active page
                    $('.df-container.active .df-field').each(function () {
                        $(this).data('fieldpos', $(this).index());
                    });
                }
            }
        }).droppable({});

        $('div.df-field').click(setupField);
        setupMenuForm("#form-settings .df-menu-form");
        setupMenuForm("#field-settings .df-menu-form");

        $(document).on('click', "button[data-page-number]", function (e) {
            e.preventDefault();
            $('<div class="ajax"></div>').load(`${document.URL + $(this).data('page-number')}/del/`);
            window.location.reload();
        });

        $("#df-form-preview").addClass("loaded");

        // handle deleting fields
        $(document).on('click', '#field-settings #delete-field', function (e) {
            e.preventDefault();
            // handle deleting fields
            let active_field = $('div.df-field.selected');
            let active_page = $('.df-container.active');
            let del_url = `${document.URL}${active_page.index()}/del/${active_field.index()}/`;
            active_field.remove()
            $("#field-settings").load(del_url);

            // renumber all fields on active page
            $('.df-container.active .df-field').each(function () {
                $(this).data('fieldpos', $(this).index());
            });
        });

        // Move field to next page
        $(document).on('click', "#field-settings #move-next", function (e) {
            e.preventDefault();
            let active_field = $('div.df-field.selected');
            let active_page = $('.df-container.active');
            let next_page = Math.min(active_page.index() + 1, $('.df-container').last().index());
            let move_url = `${document.URL}${active_page.index()}/mov/${active_field.index()}/${next_page}/`;
            $('<div class="ajax"></div>').load(move_url, function () {
                window.location.reload();
            });
        });

        //
        $(document).on('click', "#field-settings #move-prev", function (e) {
            e.preventDefault();
            let cur_fld = $('div.df-field.selected');
            let page_no = $('.df-container.active').index();
            let loadUrl = `${document.URL + page_no}/mov/${cur_fld.index()}/${Math.max(page_no - 1, 0)}/`;
            $('<div class="ajax"></div>').load(loadUrl, function () {
                window.location.reload();
            });
        });

    }

};


function testRule(first, operator, second) {
    switch (operator) {
        case "lt":
            return (first < second);
        case "lte":
            return (first <= second);
        case "exact":
            return (first == second);
        case "iexact":
            return (typeof first == 'string' ? first.toLowerCase() === second.toLowerCase() : false);
        case "neq":
            return (first != second);
        case "gte":
            return (first >= second);
        case "eq" :
            return (first === second);
        case "gt" :
            return (first > second);
        case "in" :
            return (second.indexOf(first) >= 0);
        case "contains" : {
            return (first != null ? (typeof first == 'array' ? $.inArray(second, first) : first.indexOf(second) >= 0) : false);
        }
        case "startswith":
            return (first.indexOf(second) == 0);
        case "istartswith":
            return (typeof first == 'string' ? first.toLowerCase().indexOf(second.toLowerCase()) == 0 : false);
        case "endswith":
            return (first.slice(-second.length) == second);
        case "iendswith":
            return (typeof first == 'string' ? first.toLowerCase().slice(-second.length) == second.toLowerCase() : false);
        case "nin":
            return !(second.indexOf(first) >= 0);
        case "isnull":
            return !(first);
        case "notnull":
            return !(!(first));
    }
}

function valuesOnly(va) {
    var value = [];
    if (va.length == 1) {
        return va[0].value;
    }
    if (va.length == 0) {
        return null;
    }
    $(va).each(function () {
        value.push(this.value)
    });
    return value;
}

$(document).on("keypress", ":input:not(textarea):not([type=submit])", function (event) {
    return event.keyCode != 13;
});
