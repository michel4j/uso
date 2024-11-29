/* ===========================================================
 * trumbowyg.mathjax.js v1.0
 * MathJax plugin for Trumbowyg
 * ===========================================================
 * Author : Michel Fodje
 */


(function ($) {
    'use strict';

    $.extend(true, $.trumbowyg, {
        langs: {
            // jshint camelcase:false
            en: {
                mathjax: 'Insert Math'
            },
            fr: {
                mathjax: 'Équation'
            },
            it: {
                mathjax: 'Equazione'
            },
            zh_cn: {
                mathjax: '方程'
            }
        },
        // jshint camelcase:true

        plugins: {
            mathjax: {
                shouldInit: function() {return true},
                init: function (trumbowyg) {
                    var btnDef = {
                        isSupported: false,
                        class: "btn-icon bi-braces-asterisk",
                        fn: function () {
                            trumbowyg.saveRange();
                            trumbowyg.openModalInsert(
                                // Title
                                trumbowyg.lang.mathjax,

                                // Fields
                                {
                                    latex: {
                                        required: true,
                                        label: 'Tex Code',
                                        value: trumbowyg.getRangeText()
                                    }
                                },

                                // Callback
                                function (values) {
                                    if (values.latex.includes("\\\\")) {
                                        trumbowyg.execCmd('insertText', '$$\\begin{align}' + values.latex + '\\end{align}$$');
                                    } else {
                                        trumbowyg.execCmd('insertText', '$$' + values.latex + '$$');
                                    }
                                    trumbowyg.closeModal();
                                }
                            );
                        }
                    };

                    trumbowyg.addBtnDef('mathjax', btnDef);
                }
            }
        }
    });
})(jQuery);