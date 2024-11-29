function init_fc_extras(sel, view) {
    var toolbar = $(".fc-toolbar");
    toolbar.find('.date-input').remove();
    var datepicker = '<button class="fc-button fc-state-default date-input"><input type="hidden"><i class="bi-calendar icon-fw"></i></button>';
    $('.fc-toolbar .fc-prev-button').after(datepicker);
    var date_tool = $('.date-input');
    var min_view = {
        'monthshift': 'months',
        'yearshift': 'years',
        'cycleshift': 'months',
        'weekshift': 'days'
    };
    var calendar = $(sel);
    date_tool.datepicker({
        format: "yyyy-mm-dd",
        autoclose: true,
        container: "#calendar-container",
        orientation: "auto",
        minViewMode: min_view[view.name]
    });
    date_tool.on('changeDate', function (event) {
        calendar.fullCalendar('gotoDate', moment(event.date));
    });
    if (view.name == 'yearshift') {
        //calendar.find(".fc-prev-button, .fc-next-button").addClass('hidden');
        calendar.find(".fc-nextYear-button, .fc-prevYear-button").removeClass('hidden');
    } else {
        calendar.find(".fc-prev-button, .fc-next-button").removeClass('hidden');
        calendar.find(".fc-nextYear-button, .fc-prevYear-button").addClass('hidden');
    }
    //toolbar.addClass('row');
    $(".fc-clear").remove();
    $(".fc-toolbar .fc-center, .fc-toolbar .fc-left, .fc-toolbar .fc-right");
}

var FC = $.fullCalendar; // a reference to FullCalendar's root namespace
var View = FC.BasicView;      // the class that all views must inherit from
var yearShiftView, monthShiftView, cycleShiftView;

yearShiftView = View.extend({
    duration: {months: 12},
    templateUrl: "",
    render: function () {
        var date = this.calendar.getDate();
        var params = '?date=' + date.format('YYYY-MM-DD');
        this.url = this.opt('templateUrl') + params;
        this.updateTitle(date.year());
    },
    renderSkeletonHtml: function() {
        return ""
    }
});


monthShiftView = View.extend({
    templateUrl: "",
    sectionHeaders: "",
    duration: {months: 1},
    renderSkeletonHtml: function() {
        return ""
    },
    render: function () {
        var date = this.calendar.getDate();
        var params = '?date=' + date.format('YYYY-MM-DD');
        if (this.opt('sectionHeaders')) {
            params += '&sections=' + this.opt('sectionHeaders');
        }
        if (this.opt('rangeStart')) {
            params += '&start=' + this.opt('rangeStart');
        }
        if (this.opt('rangeEnd')) {
            params += '&end=' + this.opt('rangeEnd');
        }
        this.url = this.opt('templateUrl') + params;
        this.updateTitle(date.format('MMMM, YYYY'));

    }
});


cycleShiftView = View.extend({
    templateUrl: "",
    sectionHeaders: "",
    duration: {months: 6},
    titleFormat: 'YYYY',
    render: function () {
        var date = this.calendar.getDate();
        var params = '?date=' + date.format('YYYY-MM-DD');
        if (this.opt('rangeStart')) {
            params += '&start=' + this.opt('rangeStart');
        }
        if (this.opt('rangeEnd')) {
            params += '&end=' + this.opt('rangeEnd');
        }
        this.url = this.opt('templateUrl') + params;
        this.intervalDuration = moment.duration({months: 6});
    },

    renderSkeletonHtml: function() {
        return ""
    },
    computeRange: function (date) {
        var cur_date = moment({
            year: date.year(),
            month: date.month() < 6 ? 0 : 6,
            date: 1
        });
        return View.prototype.computeRange.call(this, cur_date);
    },

	computeTitle: function() {
        return this.intervalStart.format('YYYY')
	}
});

FC.views.yearshift = yearShiftView;
FC.views.monthshift = monthShiftView;
FC.views.cycleshift = cycleShiftView;


function updateStats(url) {
    if (url) {
        $.ajax({
            type: 'GET',
            url: url,
            success: function (data) {
                $(".stats").html("");
                $.each(data, function (i, item) {
                    $('#stats-' + item.id).html(item.count);
                });
            }
        });
    }
}

function setupAjax(spinner_sel, csrf_token) {
    // Handle Spinner for all ajax calls
	$(document).ajaxStart(function () {
    	$(spinner_sel).addClass('spinner');
  	}).ajaxStop(function () {
    	$(spinner_sel).removeClass('spinner');
  	});
    $.ajaxSetup({
		beforeSend: function(xhr, settings) {
			if (!(/^(GET|HEAD|OPTIONS|TRACE)$/.test(settings.type)) && !this.crossDomain) {
				xhr.setRequestHeader("X-CSRFToken", csrf_token);
			}
		},
        error : function(jqXHR, textStatus, errorThrown) {
            //alert("Error: " + textStatus + ": " + errorThrown);
            var msg = "Operation Failed: " + errorThrown
            toastr.options = {
                "closeButton": true,
                "debug": true,
                "progressBar": true,
                "preventDuplicates": false,
                "positionClass": "toast-top-right",
                "onclick": null,
                "showDuration": "1200",
                "hideDuration": "800",
                "timeOut": "3000",
                "extendedTimeOut": "3000",
                "showEasing": "swing",
                "hideEasing": "linear",
                "showMethod": "fadeIn",
                "hideMethod": "fadeOut"
            };
            toastr["error"](msg);
        },
		async: true,
		dataType: "json",
		contentType: "application/json; charset=utf-8"
	});
}
function setupCalendar(sel, options) {
    var defaults = {
        editorType: 'event',
        editor: false,
        showLinks: true,
        rangeStart : '',
        rangeEnd: '',
        viewChoices: ''
    };
    options = $.extend({}, defaults, options || {});
    $(sel).fullCalendar({
		header: {
			left: 'title',
			center: options.viewChoices, //options.multiView ? 'cycleshift,monthshift,weekshift' : options.ViewChoices,
			right: 'prevYear,prev,next,nextYear,today'
		},
	    buttonText: {
			today: 'Today',
			monthshift: 'Month',
			yearshift: 'Year',
            weekshift: 'Week',
            cycleshift: 'Cycle'
		},
		allDaySlot: false,
		contentHeight: "auto",
		defaultDate: options.defaultDate,
		timezone: options.timezone,
		defaultView: options.defaultView,
		slotEventOverlap: false,
		allDay: false,
		eventSources: options.eventSources,
        views: {
            monthshift: {
                duration: {months: 1},
                templateUrl: options.monthTemplateUrl,
                rangeStart: options.rangeStart,
                rangeEnd: options.rangeEnd
            },
            cycleshift: {
                titleFormat: 'YYYY',
                duration: {months: 6},
                templateUrl: options.cycleTemplateUrl
            },
            yearshift: {
                duration: {months: 12},
                templateUrl: options.yearTemplateUrl
            },
            weekshift: {
                type: 'monthshift',
                unit: 'week',
                duration: {days: 7},
                templateUrl: options.weekTemplateUrl,
                sectionHeaders: options.weekSectionHeaders
            }
        },

		viewRender: function(view, element) {
			init_fc_extras(sel, view);
			$('.date-input').datepicker('update', view.start.toDate());
            view.el.load(view.url, function(){
               $(sel).fullCalendar( 'refetchEvents' );
            });
		},
		eventRender: function(event, element, view) {
			var duration = moment.duration({hours: options.shiftDuration});
            var cur_shift = event.start.clone();
            var section_prefix = "";
            var shift, shift_sel;
            if ((view.name == 'weekshift') && (event.section)) {
               section_prefix = ".cal-section-" + event.section + " > ";
            }

            var first_shift = $('.shift-' + cur_shift.tz(options.timezone).format('YYYY-MM-DD[T]HH'));
            while (cur_shift < event.end) {
                shift_sel = '.shift-' + cur_shift.tz(options.timezone).format('YYYY-MM-DD[T]HH');
                cur_shift.add(duration);
                shift = $(section_prefix + shift_sel);
                if (event.rendering == 'mode') {
                    shift.attr('class', shift.attr('data-default-class') + " " + event.name);
                    shift.attr('title', event.description);
                    if (event.tentative) shift.addClass("tentative");
                    if (event.cancelled) {
                        shift.addClass("Can");
                        shift.attr('title', event.description + " [cancelled]");
                    }
                    if ((view.name == 'monthshift') && (options.editorType == 'mode')) {
                        shift.html("<div class='event-tools'></div><div class='text-condensed mode-label'>" + event.display + "</div>");
                        first_shift.find('.event-tools').addClass('active').data('event', event);
                    }
                } else if (event.rendering == 'preferences') {
                    $('#' + event.start.format('YYYY-MM-DD')).addClass('prefs-' + event.type);
                } else if ((event.rendering == 'beamtime') || ((event.rendering == 'staff') && ((view.name == 'weekshift') || options.editor)) ){
                    var tag_html = "";
                    var tag_titles = [];
                    shift.attr('title', event.description);
                    $.each(event.tags, function (i, tag) {
                        tag_titles.push($('#tag-' + tag).data('tag'));
                        tag_html += "<i class='bi-tag cat-fg-" + $('#tag-' + tag).data('cat') + "'></i>";
                    });
                    tag_html = "<span title='"+ tag_titles.join('; ') +"'>" + tag_html + "</span>";
                    if ((view.name == 'monthshift') || (view.name == 'weekshift')) {
                        shift.addClass("fg-" + event.project_type);
                        shift.html("<div class='event-tools'></div><div class='text-condensed overflow ellipsis event-label'>" +
                            "<span class='hidden-sm'>" + event.display + "</span>" +
                            "<span class='visible-sm' title='"+ event.display +"'>" + event.name + "</span>" +
                            tag_html + "</div>"
                        );
                        if (options.editor) {
                            first_shift.find('.event-tools').addClass('active').data('event', event);
                        }
                        if (options.showLinks && event.url) {
                            shift.find('.event-label').attr('data-href', event.url);
                        }
                    }
                    if (event.cancelled) {
                        shift.find('.event-label').addClass('cancelled');
                    }
                }
            }
			return false;
		}
	});

    // Handle data-url and data-href
    $(sel+':not(.starting, .ending)').on('click', '[data-event-href]', function(){
        window.document.location = $(this).attr("data-event-href");
    });
}

function setupEditor(sel, options) {
    var defaults = {
        editorType: 'event'
    };
    options = $.extend({}, defaults, options || {});
    var rangeStart = moment(options.rangeStart, "YYYY-MM-DD");
    var rangeEnd = moment(options.rangeStart, "YYYY-MM-DD");

    // prepare click events for event source
    var calendar = $(sel);
    calendar.addClass('idle');
    function clearEvents() {
        $('.cal-day .cal-shift').each(function(){
            var shift = $(this);
            shift.attr('class', shift.attr('data-default-class'));
            shift.html("");
        });
    }

    $(document).on('click', '.event-src', function (event) {
        calendar.fullCalendar('removeEventSource', $('.active-src').attr('data-extra-events-url'));
        $('.fc-day-number.prefs-available, .fc-day-number.prefs-unavailable').removeClass('prefs-available prefs-unavailable');
        if (!($(this).is('.active-src'))) {
            $('.event-src').removeClass('active-src');
            calendar.removeClass('idle ending').addClass('starting');
            $(this).addClass('active-src');
            calendar.fullCalendar('addEventSource', $(this).attr('data-extra-events-url'));
            $.each($(this).data('event').tags, function (i, id) {
                $('#tag-' + id).addClass('active');
            });
        } else {
            var class_name = "selected-" + $('.event-src.active-src').attr('data-key');
            $('.event-src').removeClass('active-src');
            calendar.removeClass('ending starting').addClass('idle');
            $(".cal-shift." + class_name).removeClass(class_name);
            $('.tag').removeClass('active');
        }
    });

    // starting shift selected
    $(document).on('click', '.starting .fc-view .cal-day .cal-shift', function (event) {
        $(sel + '.starting').removeClass('idle starting').addClass('ending').attr('data-range-start', $(this).attr('data-shift-id'));
    });
    // ending shift selected
    $(document).on('click', '.ending .fc-view .cal-day .cal-shift', function (event) {
        var t1 = moment(calendar.attr('data-range-start'), 'YYYY-MM-DDTHH');
        var t2 = moment($(this).attr('data-shift-id'), 'YYYY-MM-DDTHH');
        var start_time = moment(moment.min(t1, t2));
        var end_time = moment(moment.max(t1, t2));
        end_time.add(moment.duration({hours: options.shiftDuration}));
        var post_data = $.extend(true, {}, $('.event-src.active-src').data('event'));
        post_data['start'] = start_time.toISOString();
        post_data['end'] = end_time.toISOString();
        post_data['tags'] = $('.tag.active').map(function () {
            return $(this).data('tag');
        }).get();
        $.ajax({
            url: options.eventsAPI,
            type: "POST",
            data: JSON.stringify(post_data),
            success: function (data) {
                clearEvents();
                calendar.fullCalendar('refetchEvents');
                calendar.removeClass('starting ending').addClass('idle');
                $('.event-src').removeClass('active-src');
                updateStats(options.statsAPI);
            }
        });
    });

    //highlihght range while editing
    $(document).on('mouseenter', '.ending .fc-view .cal-shift', function (event) {
        var selected = [];
        var t1 = moment(calendar.attr('data-range-start'), 'YYYY-MM-DDTHH');
        var t2 = moment($(this).attr('data-shift-id'), 'YYYY-MM-DDTHH');
        var class_name = "selected-" + $('.event-src.active-src').attr('data-key');
        var start_time = moment(moment.min(t1, t2));
        var end_time = moment(moment.max(t1, t2));
        end_time = end_time.add(moment.duration({hours: options.shiftDuration}));
        var cur_shift = moment(start_time);
        while (cur_shift < end_time) {
            selected.push('.shift-' + cur_shift.tz(options.timezone).format('YYYY-MM-DD[T]HH'));
            cur_shift = cur_shift.add(moment.duration({hours: options.shiftDuration}));
        }
        $(".cal-shift." + class_name).removeClass(class_name);
        $(selected.join()).addClass(class_name);
    });

    // Escape pressed while editing
    $(document).keyup(function(e) {
        if (e.keyCode == 27) {
            calendar.fullCalendar('removeEventSource', $('.active-src').attr('data-extra-events-url'));
            var class_name = "selected-" + $('.event-src.active-src').attr('data-key');
            $('.event-src').removeClass('active-src');
            calendar.removeClass('ending starting').addClass('idle');
            $(".cal-shift." + class_name).removeClass(class_name);
            $('.tag').removeClass('active');
        }
    });

    // Shift on weekday clicked
    $(document).on('click', '.starting .cal-day-header .cal-shift', function () {
        var shifts = $(this).closest('.cal-row').find('.shift-' + $(this).attr('data-shift-time'));
        var post_data = [];
        shifts.each(function () {
            var t1 = moment($(this).attr('data-shift-id'), 'YYYY-MM-DDTHH');
            var t2 = moment(t1);
            t2.add(moment.duration({hours: options.shiftDuration}));
            var entry = $.extend(true, {}, $('.event-src.active-src').data('event'));
            entry['start'] = t1.toISOString();
            entry['end'] = t2.toISOString();
            entry['tags'] = $('.tag.active').map(function () {
                return $(this).data('tag');
            }).get();
            post_data.push(entry)
        });
        $.ajax({
            url: options.eventsAPI,
            type: "POST",
            data: JSON.stringify(post_data),
            success: function (data) {
                clearEvents();
                calendar.fullCalendar('refetchEvents');
                updateStats(options.statsAPI);
            }
        });
    });

    // Handle display of event tools
    $(document).on('mouseenter', '.idle .cal-shift .event-tools.active', function() {
        var control = $(this);
        var event = control.data("event");
        var comments = event.comments ? event.comments : ""
        control.popover({
            html: true,
            trigger: 'hover',
            placement: 'bottom',
            container: control,
            content: function() {
                return (
                    "<div class='row no-space'>"+
                    "   <div class='col-xs-12'>" +
                    "      <textarea class='formcontrol' name='comments' rows='4' cols='40' placeholder='Enter comments and save ...'>"+ comments +"</textarea>" +
                    "   </div>" +
                    "</div>" +
                    "<div class='tools'>" +
                    "   <a href='#0' data-action='comments'><i class='bi-floppy icon-1x'></i><br/>Save</a>" +
                    "   <a href='#0' data-action='cancel'><i class='bi-ban icon-1x'></i><br/>Cancel</a>" +
                    "   <a href='#0' data-action='reset'><i class='bi-arrow-clockwise icon-1x'></i><br/>Reset</a>" +
                    "   <a href='#0' data-action='delete'><i class='bi-trash icon-1x'></i><br/>Delete</a>" +
                    "</div>");
            }
        });
        control.popover("show");
    });

    // Handle editing actions from event tools
    $(document).on('click', '.cal-shift .event-tools.active .popover a[data-action]', function() {
        var tools = $(this).closest('.event-tools');
        var event = tools.data('event');
        var action = $(this).attr('data-action');
        if (action == 'comments') {
            event['comments'] = tools.find('textarea').val()
        } else {
            event[action] = true;
        }
        $.ajax({
            url: options.eventsAPI,
            type: "POST",
            data: JSON.stringify(event),
            success: function (data) {
                clearEvents();
                calendar.fullCalendar('refetchEvents');
                updateStats(options.statsAPI);
            }
        });
    });

    $(document).on('mouseenter', '.starting .cal-day-header .cal-shift', function (event) {
        var class_name = "selected-" + $('.event-src.active-src').attr('data-key');
        $(".cal-shift." + class_name).removeClass(class_name);
        $(".cal-shift.shift-day-" + $(this).attr('data-shift-day') + ".shift-time-" + $(this).attr('data-shift-time')).addClass(class_name);
    });

    $(document).on('mouseleave', '.fc-view', function (event) {
        var class_name = "selected-" + $('.event-src.active-src').attr('data-key');
        $(".cal-day .cal-shift." + class_name).removeClass(class_name);
    });

    $(document).on('click', '.tag', function () {
        $(this).toggleClass('active');
    });
    updateStats(options.statsAPI);

}
