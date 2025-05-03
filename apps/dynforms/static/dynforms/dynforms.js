// Handle Repeats
(function($) {
    $.fn.extend({
        repeatable: function(options) {
            options = $.extend( {}, $.repeatable.defaults, options );
            this.each(function() {
                new $.repeatable(this,options);
            });
            return this;
        }
    });

    // ctl is the element, options is the set of defaults + user options
    $.repeatable = function( ctl, options ) {

    	var rp_sel = $(ctl).attr("data-repeat-add");
    	var all_rp = $(ctl).siblings(rp_sel);
    	var all_rp_rm = all_rp.find(options.remove);
    	
    	function updateRepeat(section){

    		section.find('.repeat-html-index').each(function() {
    			$(this).html(section.index());
    		});
    		section.find('.repeat-value-index').each(function() {
    			$(this).attr('value', section.index());
    		});
    		section.find('[data-repeat-index]').each(function() {
    			$(this).attr('data-repeat-index', section.index());
    		});
    		section.find(':input').each(function() {
    			$(this).attr('id', $(this).attr('id') + "_" + section.index());
    		});
    		section.attr('id', section.attr('id') + "_" + section.index())
    		
    		all_rp = $(ctl).siblings(rp_sel);

    		all_rp_rm = all_rp.find(options.remove);

			if (all_rp.length > 1 ) {
				all_rp_rm.removeAttr("disabled");
			} else {
				all_rp_rm.attr("disabled", "disabled");
			}

        	// rename multi-valued field names so values are kept separate
    		all_rp.each(function(idx, obj){
    			$(this).find("[data-repeat-name]").each(function(){
        			$(this).attr("name", $(this).attr("data-repeat-name") + "." + idx);
        		});
    		});
    	};
    	
    	$(ctl).click(function(e){
        	var rp_el = all_rp.last();
         	var field_cnt = $(ctl).closest(".df-field-runtime");

            var cloned = rp_el.clone(true);
            cloned.insertAfter(rp_el);
            if (options.clearNew) {
            	cloned.find(":input:not(.chosen)").each(function(){
            		$(this).val('').removeAttr('checked').removeAttr('selected');
            	});
            }
        	updateRepeat(cloned);
        	// rebuild chosen fields
        	cloned.find("select.select option").removeAttr('selected');
        	cloned.find("select.select").each(function(){
        		$(this).val('');
        		$(this).trigger('change')
        	});
    	});
    	
    	all_rp_rm.each(function() {
        	$(this).click(function(e){
	    		var del_el = $(this).closest(rp_sel);
	            var others = del_el.siblings(rp_sel);
	            if (others.length > 0){
	            	del_el.slideUp('fast', function(){
	            		del_el.remove();
	            		others.each(function(){
	                		updateRepeat($(this));
	                	});
	            	});
	            } else if (options.clearIfLast) {
	            	del_el.find(":input").each(function(){
	            		$(this).val('').removeAttr('checked').removeAttr('selected');
	            	})
	            };		    					           		
        	});
        });
    	
		if (all_rp.length > 1 ) {
			all_rp_rm.removeAttr("disabled");
		} else {
			all_rp_rm.attr("disabled", "disabled");
		}

		// Keep multi valued fields separate, by renaming them, __# can be stripped when cleaning
		// the data
		all_rp.each(function(idx, obj){
			$(obj).find("select[multiple]:not([data-repeat-name])").each(function(){
				$(this).attr("data-repeat-name", $(this).attr("name"));
    			$(this).attr("name", $(this).attr("data-repeat-name") + "." + idx);
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
function setupField(){
	if ($(this).is(".selected")) {
		return;
	}
	$('div.df-field.selected').toggleClass("selected", false);
	$(this).toggleClass("selected", true);
	$('#df-sidebar a[href="#field-settings"]').tab('show');
	
	// Ajax Update form
	var loadUrl = `${document.URL +	$('.df-container.active').index()}/put/${$(this).attr('data-fieldpos')}/`;
	$("#field-settings").load(loadUrl, function(){
		// $('#field-settings .chosen').chosen({disable_search_threshold: 5, display_disabled_options: false, search_contains: true});
		setupMenuForm("#field-settings .df-menu-form");
	});
};

// Form customization for each form
function setupMenuForm(form_id) {
	
	// Setup Repeatable Fields
	$(form_id + ' button[data-repeat-add]').repeatable({clearIfLast: false});
	
	// handle deleting fields
	$(form_id + ' button[name="delete-field"]').click(function(e){
		var cur_fld = $('div.df-field.selected');
		var loadUrl = `${document.URL + $('.df-container.active').index()}/del/${cur_fld.index()}/`;
		cur_fld.remove()
		$("#field-settings").load(loadUrl);
		// renumber all fields on active page
		$('.df-container.active .df-field').each(function(){
			$(this).attr('data-fieldpos', $(this).index());
		});
	});

	// handle applying field settings
	function submitHandler(event) {
		$(form_id).ajaxSubmit({
			type: 'post',
			url: `${document.URL + $('.df-container.active').index()}/put/${$('div.df-field.selected').index()}/`,
			success: function(result) {
				$("#field-settings").html(result);
				setupMenuForm("#field-settings .df-menu-form");
				var cur_fld = $('div.df-field.selected');
				var loadUrl = `${document.URL +	$('.df-container.active').index()}/get/${cur_fld.index()}/`;
				cur_fld.load(loadUrl);				
			}
		});		
	}
	$(form_id + ' button[name="apply-field"]').click(submitHandler);
	$(form_id + ' :input').each(function(){
		$(this).change(submitHandler);
	});
	
	// handle launching rule editor
	$(form_id + ' button[name="edit-rules"]').click(function(e){
		var cur_fld = $('div.df-field.selected');
		var loadUrl = `${document.URL + $('.df-container.active').index()}/rules/${cur_fld.index()}/`;
		$("#modal-holder").load(loadUrl);
	});

	// $(form_id +' select.chosen').chosen({disable_search_threshold: 5, display_disabled_options: false, search_contains: true});
    $(form_id +" button[name='move-next']").click(function(e){
		var cur_fld = $('div.df-field.selected');
		var page_no = $('.df-container.active').index();
		var loadUrl = `${document.URL + page_no}/mov/${cur_fld.index()}/${Math.min(page_no + 1, $('.df-container').last().index())}/`;
    	$('<div class="ajax"></div>').load(loadUrl, function(){
    		window.location.reload();
    	});
    });
    $(form_id +" button[name='move-prev']").click(function(e){
		var cur_fld = $('div.df-field.selected');
		var page_no = $('.df-container.active').index();
		var loadUrl = `${document.URL + page_no}/mov/${cur_fld.index()}/${Math.max(page_no - 1, 0)}/`;
    	$('<div class="ajax"></div>').load(loadUrl,function(){
    		window.location.reload();
    	});
    });

};

function doBuilderLoad(){
    if (!$('#df-form-preview').is('.loaded')) {
	    $('div.field-btn').draggable({
		    connectToSortable: '#df-main .df-container.active',
		    revert: "invalid",
		    appendTo: '.df-container.active',
		    cursorAt: {left: 5, top: 5},
		    scroll: true,
		    helper: "clone",
	        start: function(event, ui) {
	        	var exp = $('.df-container.active');
	        	ui.helper.addClass("ui-draggable-helper");
		        ui.helper.width(exp.width()/4);
	        },
	        drag: function(event,ui){
	            ui.position.top = NaN;
	         }
	    }).click(function(){
		    if ( $(this).is('.ui-draggable-dragging') ) {
			    return;
		    }
		    var new_el = $('<div class="df-field container no-space"></div>');
		    var cur_pg = $('.df-container.active');
		    cur_pg.append(new_el);
		    new_el.attr('data-fieldtype', $(this).attr('data-fieldtype'));
		    new_el.attr('data-fieldpos', new_el.index());
		    new_el.click(setupField);
		    // Ajax Add Field
		    var loadUrl = `${document.URL + cur_pg.index()}/add/${new_el.attr('data-fieldtype')}/${new_el.index()}/`;
		    new_el.load(loadUrl, function(){
			    $(this).click();
		    });
	    }).disableSelection();

	    $('#df-main .df-container').sortable({
		    items: '.df-field',
		    revert: false,
		    forcePlaceholderSize: true,
		    stop: function(event, ui){
			    if (ui.item.hasClass("field-btn")){
				    ui.item.removeClass();
				    ui.item.addClass("df-field container no-space").attr("style", "");
				    ui.item.html("");
				    ui.item.click(setupField);
				    // Ajax Add Field
				    var loadUrl = `${document.URL + $('.df-container.active').index()}/add/${ui.item.attr('data-fieldtype')}/${ui.item.index()}/`;
				    ui.item.load(loadUrl, function(){
					    $(this).click();
					    // renumber all fields on active page
					    $('.df-container.active .df-field').each(function(){
						    $(this).attr('data-fieldpos', $(this).index());
					    });					
				    });
			    } else {
				    // move dropped field to new position on server
				    var loadUrl = `${document.URL + $('.df-container.active').index()}/mov/${ui.item.attr('data-fieldpos')}-${ui.item.index()}/`;
				    $('<div class="ajax"></div>').load(loadUrl);
				    // renumber all fields on active page
				    $('.df-container.active .df-field').each(function(){
					    $(this).attr('data-fieldpos', $(this).index());
				    });
			    }
		    }
	    }).droppable({});
		
	    $('div.df-field').click(setupField);
	    setupMenuForm("#form-settings .df-menu-form");
	    setupMenuForm("#field-settings .df-menu-form");
	    $("button[data-page-number]").click(function(e){
	    	$('<div class="ajax"></div>').load(`${document.URL + $(this).attr('data-page-number')}/del/`);
	    	window.location.reload();
	    });
	    $("#df-form-preview").addClass("loaded");
	}

};


function testRule(first, operator, second) {
	switch(operator) {
	case "lt": return (first < second);
	case "lte": return (first <= second);
	case "exact": return (first == second);
	case "iexact": return(typeof first == 'string'? first.toLowerCase() === second.toLowerCase() : false);
	case "neq": return (first != second);
	case "gte": return (first >= second);
	case "eq" : return (first === second);
	case "gt" : return (first > second);
	case "in" : return (second.indexOf(first) >= 0);
	case "contains" : {
	    return (first != null ? (typeof first == 'array'? $.inArray(second, first): first.indexOf(second) >= 0) : false);
	}
	case "startswith": return (first.indexOf(second) == 0);
	case "istartswith": return (typeof first == 'string' ? first.toLowerCase().indexOf(second.toLowerCase()) == 0: false);
	case "endswith": return (first.slice(-second.length) == second);
	case "iendswith": return (typeof first == 'string' ? first.toLowerCase().slice(-second.length) == second.toLowerCase(): false);
	case "nin": return !(second.indexOf(first) >= 0);
	case "isnull": return !(first);
	case "notnull": return !(!(first));
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
	$(va).each(function(){value.push(this.value)});
	return value;
}

$(document).on("keypress", ":input:not(textarea):not([type=submit])", function(event) {
	return event.keyCode != 13;
});